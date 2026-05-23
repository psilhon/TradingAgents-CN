// dataflows-schema-consistency-hardening stage 2.2 — trade_date ISO 8601 统一
//
// 把 mongo collections 内 trade_date 字段从 yyyymmdd ("20260521") 形式统一为
// ISO 8601 yyyy-mm-dd ("2026-05-21") canonical 格式。
//
// Idempotent: 重跑无副作用（updateMany 在已 yyyy-mm-dd 形式的 docs 上 matchCount = 0）。
//
// Usage:
//   # Dry-run (默认):
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --file scripts/migrations/2.2_trade_date_iso.js
//
//   # Commit:
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --eval "DRY_RUN = false; load('scripts/migrations/2.2_trade_date_iso.js')"

const DRY_RUN = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;

print("===== 2.2 Migration: trade_date yyyymmdd → yyyy-mm-dd =====");
print("DRY_RUN:", DRY_RUN);
print("Started:", new Date().toISOString());
print("");

// Collections + field name. Only `market_quotes.trade_date` is known to use
// yyyymmdd (verified 2026-05-23); include other collections defensively in
// case future writers slip in non-canonical format.
const TARGETS = [
  ["market_quotes",      "trade_date"],
  ["stock_basic_info",   "trade_date"],
  ["stock_basic_info",   "last_trade_date"],
  ["market_indices",     "trade_date"],
];

let totalScanned = 0;
let totalRewritten = 0;

for (const [collName, fieldName] of TARGETS) {
  const coll = db.getCollection(collName);
  const filter = {[fieldName]: /^\d{8}$/};  // yyyymmdd 8-digit literal
  const matchCount = coll.countDocuments(filter);
  totalScanned += matchCount;

  if (matchCount === 0) {
    print(`  ${collName}.${fieldName}: 0 docs in yyyymmdd format (skip)`);
    continue;
  }

  print(`  ${collName}.${fieldName}: ${matchCount} docs in yyyymmdd format`);
  if (!DRY_RUN) {
    // Aggregation pipeline: insert dashes at positions 4 and 7 via substr
    const result = coll.updateMany(
      filter,
      [{
        "$set": {
          [fieldName]: {
            "$concat": [
              {"$substr": ["$" + fieldName, 0, 4]},
              "-",
              {"$substr": ["$" + fieldName, 4, 2]},
              "-",
              {"$substr": ["$" + fieldName, 6, 2]}
            ]
          }
        }
      }]
    );
    print(`    updated: ${result.modifiedCount}`);
    totalRewritten += result.modifiedCount;
  } else {
    print(`    [dry-run] would update ${matchCount} docs`);
  }
}

print("");
print("===== Summary =====");
print(`  Scanned:    ${totalScanned}`);
print(`  Rewritten:  ${totalRewritten} ${DRY_RUN ? "(dry-run, no writes performed)" : ""}`);
print(`  Finished:   ${new Date().toISOString()}`);

if (!DRY_RUN) {
  print("");
  print("===== Post-migration sanity =====");
  for (const [collName, fieldName] of TARGETS) {
    const remaining = db.getCollection(collName).countDocuments({[fieldName]: /^\d{8}$/});
    if (remaining > 0) {
      print(`  WARNING: ${collName}.${fieldName} still has ${remaining} docs in yyyymmdd format`);
    } else {
      print(`  OK:      ${collName}.${fieldName}: 0 yyyymmdd remaining`);
    }
  }
}
