// Data-correctness audit — 直连 MongoDB 检查关键集合的字段完整率与数值合理性。
//
// 用途：迁移后验证 + 定期复核数据健康（重复 code / 字段名分裂 / neg·zero·null·NaN 异常值）。
// 缘起：2026-05-17 数据正确性审计（docs/data-audit-2026-05-17.md），由 data-audit-phase3 固化入库。
//
// 运行：
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --file scripts/data_audit.js
//
// 连接串里的 admin/tradingagents123 是本项目公开的本地 dev 默认凭据（见 CLAUDE.md / docs/USAGE.md），非密钥。

function pct(n, total) { return total ? (100 * n / total).toFixed(1) + "%" : "n/a"; }

function fieldCoverage(coll, fields) {
  const total = coll.estimatedDocumentCount();
  print("  total docs: " + total);
  fields.forEach(f => {
    const present = coll.countDocuments({ [f]: { $exists: true, $ne: null } });
    const empty = coll.countDocuments({ [f]: "" });
    const flag = (present / total < 0.95) ? "  <-- LOW" : "";
    print("    " + f.padEnd(20) + " present=" + String(present).padStart(6) +
          " (" + pct(present, total).padStart(7) + ")  empty-str=" + empty + flag);
  });
}

function numericSanity(coll, field) {
  const total = coll.estimatedDocumentCount();
  const neg = coll.countDocuments({ [field]: { $lt: 0 } });
  const zero = coll.countDocuments({ [field]: 0 });
  const nullish = coll.countDocuments({ $or: [{ [field]: null }, { [field]: { $exists: false } }] });
  const nan = coll.countDocuments({ [field]: { $type: "double" }, $expr: { $ne: [{ $cmp: ["$" + field, "$" + field] }, 0] } });
  print("    " + field.padEnd(18) + " neg=" + String(neg).padStart(6) +
        " zero=" + String(zero).padStart(6) + " null/missing=" + String(nullish).padStart(6) +
        " NaN=" + nan);
}

print("########## DATA-CORRECTNESS AUDIT ##########");
print("time: " + new Date().toISOString());

// ---- stock_basic_info ----
print("\n===== stock_basic_info =====");
const sbi = db.stock_basic_info;
print("-- field-name consistency (data-audit-phase3 后应只剩 data_source) --");
print("  has 'source':       " + sbi.countDocuments({ source: { $exists: true } }));
print("  has 'data_source':  " + sbi.countDocuments({ data_source: { $exists: true } }));
print("  source distinct:    " + JSON.stringify(sbi.distinct("source")));
print("  data_source distinct: " + JSON.stringify(sbi.distinct("data_source")));
print("-- duplicate code check (data-audit-phase3 后应为 0) --");
const dupCodes = sbi.aggregate([
  { $group: { _id: "$code", n: { $sum: 1 } } },
  { $match: { n: { $gt: 1 } } },
  { $count: "duplicated" }
]).toArray();
print("  codes with >1 doc:  " + (dupCodes.length ? dupCodes[0].duplicated : 0));
print("  total docs:         " + sbi.estimatedDocumentCount());
print("  distinct codes:     " + sbi.distinct("code").length);
print("-- identity / descriptive field coverage --");
fieldCoverage(sbi, ["code", "symbol", "full_symbol", "ts_code", "name", "industry", "area", "market", "list_date", "category"]);
print("-- financial field coverage --");
fieldCoverage(sbi, ["total_mv", "circ_mv", "pe", "pe_ttm", "pb", "pb_mrq", "ps", "ps_ttm", "turnover_rate", "volume_ratio", "total_share", "float_share"]);
print("-- numeric sanity (neg/zero/null/NaN) --");
print("   注: 负 pe / 负 pb 合法（亏损 / 负净资产）；负 ps / total_mv / circ_mv 数学上不可能。");
["total_mv", "circ_mv", "pe", "pb", "ps", "turnover_rate"].forEach(f => numericSanity(sbi, f));
print("-- top 5 / bottom 5 total_mv --");
sbi.find({ total_mv: { $ne: null } }).sort({ total_mv: -1 }).limit(5).forEach(d => print("    HIGH " + d.code + " " + d.name + " total_mv=" + d.total_mv + " pe=" + d.pe));
sbi.find({ total_mv: { $ne: null } }).sort({ total_mv: 1 }).limit(5).forEach(d => print("    LOW  " + d.code + " " + d.name + " total_mv=" + d.total_mv + " pe=" + d.pe));

// ---- stock_daily_quotes ----
print("\n===== stock_daily_quotes =====");
const sdq = db.stock_daily_quotes;
printjson(sdq.findOne());
print("-- distinct stock count / date range --");
print("  distinct codes: " + sdq.distinct("code").length + " / " + sdq.distinct("symbol").length + " (symbol)");

// ---- market_quotes ----
print("\n===== market_quotes =====");
const mq = db.market_quotes;
printjson(mq.findOne());

// ---- stock_financial_data ----
print("\n===== stock_financial_data =====");
printjson(db.stock_financial_data.findOne());

// ---- stock_indicators ----
print("\n===== stock_indicators =====");
printjson(db.stock_indicators.findOne());

print("\n########## END AUDIT ##########");
