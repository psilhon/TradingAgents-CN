// dataflows-schema-consistency-hardening stage 2.1 — 交易所后缀统一
//
// 把 mongo collections (market_quotes / stock_basic_info / stock_daily_quotes)
// 内 `.SS` (Yahoo Finance 风格) 后缀统一为 `.SH` (tushare 国内主流) canonical。
//
// Idempotent: 重跑无副作用（updateMany 在已 `.SH` 的 docs 上 matchCount = 0）。
//
// Usage:
//   # Dry-run (默认，仅统计不写库):
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --file scripts/migrations/2.1_unify_exchange_suffix.js
//
//   # Commit (实际写库):
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --eval "DRY_RUN = false; load('scripts/migrations/2.1_unify_exchange_suffix.js')"

// Default safe to dry-run; caller flips via --eval "DRY_RUN = false;"
const DRY_RUN = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;

print("===== 2.1 Migration: .SS → .SH =====");
print("DRY_RUN:", DRY_RUN);
print("Started:", new Date().toISOString());
print("");

// (collection, field) pairs to scan + rewrite
const TARGETS = [
  ["market_quotes",       "full_symbol"],
  ["market_quotes",       "ts_code"],
  ["market_quotes",       "symbol"],
  ["stock_basic_info",    "full_symbol"],
  ["stock_basic_info",    "ts_code"],
  ["stock_basic_info",    "symbol"],
  ["stock_daily_quotes",  "full_symbol"],
  ["stock_daily_quotes",  "ts_code"],
  ["stock_daily_quotes",  "symbol"],
];

let totalScanned = 0;
let totalRewritten = 0;

for (const [collName, fieldName] of TARGETS) {
  const coll = db.getCollection(collName);
  const filter = {[fieldName]: /\.SS$/};
  const matchCount = coll.countDocuments(filter);
  totalScanned += matchCount;

  if (matchCount === 0) {
    print(`  ${collName}.${fieldName}: 0 docs with .SS suffix (skip)`);
    continue;
  }

  print(`  ${collName}.${fieldName}: ${matchCount} docs with .SS suffix`);
  if (!DRY_RUN) {
    // Aggregation pipeline update: strip ".SS" (3 chars) + append ".SH"
    const result = coll.updateMany(
      filter,
      [{
        "$set": {
          [fieldName]: {
            "$concat": [
              {"$substr": ["$" + fieldName, 0, {"$subtract": [{"$strLenCP": "$" + fieldName}, 3]}]},
              ".SH"
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

// Post-migration sanity check
if (!DRY_RUN) {
  print("");
  print("===== Post-migration sanity =====");
  for (const [collName, fieldName] of TARGETS) {
    const remaining = db.getCollection(collName).countDocuments({[fieldName]: /\.SS$/});
    if (remaining > 0) {
      print(`  WARNING: ${collName}.${fieldName} still has ${remaining} docs with .SS suffix`);
    } else {
      print(`  OK:      ${collName}.${fieldName}: 0 .SS remaining`);
    }
  }
}
