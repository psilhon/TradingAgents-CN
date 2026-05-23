// dataflows-schema-consistency-hardening stage 2.3 — stock_basic_info full_symbol audit
//
// Audit-only script — never writes to mongo. Reports docs missing `full_symbol`
// or with non-canonical form (not matching `^\d{6}\.(SH|SZ|BJ)$`).
//
// Exit code: 0 if 0 anomalies, non-zero if any (useful as CI gate).
//
// Usage:
//   mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" \
//     --quiet --file scripts/migrations/2.3_audit_full_symbol.js

print("===== 2.3 Audit: stock_basic_info full_symbol invariant =====");
print("Started:", new Date().toISOString());
print("");

const TOTAL = db.stock_basic_info.countDocuments({});
const WITH_FIELD = db.stock_basic_info.countDocuments({full_symbol: {$exists: true}});
const CANONICAL = db.stock_basic_info.countDocuments({
  full_symbol: /^\d{6}\.(SH|SZ|BJ)$/
});

const MISSING_FIELD = TOTAL - WITH_FIELD;
const NON_CANONICAL = WITH_FIELD - CANONICAL;

print(`  Total docs:            ${TOTAL}`);
print(`  With full_symbol:      ${WITH_FIELD}`);
print(`  Canonical .SH/.SZ/.BJ: ${CANONICAL}`);
print(`  Missing full_symbol:   ${MISSING_FIELD}`);
print(`  Non-canonical form:    ${NON_CANONICAL}`);
print("");

if (MISSING_FIELD > 0) {
  print(`  WARNING: ${MISSING_FIELD} docs missing full_symbol field`);
  print(`  Sample missing docs:`);
  db.stock_basic_info.find({full_symbol: {$exists: false}}, {code: 1, symbol: 1}).limit(3).toArray().forEach(d => print(`    ${JSON.stringify(d)}`));
}

if (NON_CANONICAL > 0) {
  print(`  WARNING: ${NON_CANONICAL} docs have non-canonical full_symbol`);
  print(`  Sample non-canonical:`);
  db.stock_basic_info.find(
    {full_symbol: {$exists: true, $not: /^\d{6}\.(SH|SZ|BJ)$/}},
    {code: 1, full_symbol: 1}
  ).limit(5).toArray().forEach(d => print(`    ${JSON.stringify(d)}`));
}

print("");
print("===== Summary =====");
const ANOMALIES = MISSING_FIELD + NON_CANONICAL;
if (ANOMALIES === 0) {
  print(`  OK: 0 anomalies (all ${TOTAL} docs have canonical full_symbol)`);
} else {
  print(`  FAIL: ${ANOMALIES} anomalies (${MISSING_FIELD} missing + ${NON_CANONICAL} non-canonical)`);
}
print(`  Finished: ${new Date().toISOString()}`);

// Exit code for CI gate use
if (ANOMALIES > 0) {
  quit(1);
}
