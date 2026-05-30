// reports-idor-fix — backfill analysis_reports.user_id from linked analysis_tasks
//
// 报告资源此前无 owner 字段（reports IDOR：任一登录用户可凭 report_id 读/删他人
// 报告）。修复后 writer (simple_analysis_service._save_analysis_result_web_style)
// 会写 user_id，但存量 analysis_reports 缺 owner。本脚本按 task_id 从 analysis_tasks
// 回填 owner（owner 字段两种命名并存：user_id 主 / user 兼容）。
//
// 重要：reports.py 的 reader 修复后，非 admin 用户看不到缺 owner 的 legacy 报告
// （仅 admin 可见）——这是安全选择（绝不放行 owner-less 给所有人）。**跑完本回填后
// owner 恢复可见**。本 fork 主用户通常是 admin，回填前后均可见全部；多人场景须
// 部署后尽快跑本脚本。
//
// Idempotent: 只处理 user_id 缺失 / 为 null 的 docs，重跑无副作用。
//
// Usage:
//   # Dry-run (默认，只统计不写):
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --file scripts/migrations/2.4_backfill_report_owner.js
//
//   # Commit (实写):
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --eval "DRY_RUN = false; load('scripts/migrations/2.4_backfill_report_owner.js')"

const DRY_RUN = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;

print("===== 2.4 Migration: backfill analysis_reports.user_id (reports IDOR) =====");
print("DRY_RUN:", DRY_RUN);
print("Started:", new Date().toISOString());
print("");

const reports = db.getCollection("analysis_reports");
const tasks = db.getCollection("analysis_tasks");

// 缺 owner 的报告：user_id 不存在 或 为 null
const missingFilter = { "$or": [{ "user_id": { "$exists": false } }, { "user_id": null }] };
const totalMissing = reports.countDocuments(missingFilter);
print(`  analysis_reports 缺 owner: ${totalMissing} docs`);

let backfilled = 0;
let orphans = 0; // 无 task_id / task 不存在 / task 无 owner — 无法回填
let noTaskId = 0;

reports.find(missingFilter, { task_id: 1 }).forEach(function (rep) {
  const taskId = rep.task_id;
  if (!taskId) {
    noTaskId++;
    orphans++;
    return;
  }
  const task = tasks.findOne({ task_id: taskId }, { user_id: 1, user: 1 });
  const owner = task ? (task.user_id || task.user) : null;
  if (owner === null || owner === undefined) {
    orphans++;
    return;
  }
  const ownerStr = String(owner);
  if (!DRY_RUN) {
    reports.updateOne({ _id: rep._id }, { "$set": { user_id: ownerStr } });
  }
  backfilled++;
});

print("");
print("===== Summary =====");
print(`  缺 owner 总数:       ${totalMissing}`);
print(`  可回填:              ${backfilled} ${DRY_RUN ? "(dry-run, 未写入)" : "(已写入)"}`);
print(`  orphan (无法回填):   ${orphans}  (其中无 task_id: ${noTaskId})`);
print(`  Finished:            ${new Date().toISOString()}`);
print("");
print(`  注：orphan 报告 (${orphans}) 无法确定 owner，将保持仅 admin 可见（安全默认）。`);

if (!DRY_RUN) {
  const remaining = reports.countDocuments(missingFilter);
  print("");
  print("===== Post-migration sanity =====");
  print(`  仍缺 owner: ${remaining} (应 = orphan ${orphans})`);
}
