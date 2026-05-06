<template>
  <div class="mkt-ticker" title="演示数据 — 未接行情 API">
    <div
      v-for="(item, idx) in tickers"
      :key="item.code"
      class="ticker-row"
    >
      <span class="ticker-label">{{ item.label }}</span>
      <span class="ticker-val num">{{ item.value }}</span>
      <span class="ticker-chg num" :class="item.dir">
        {{ item.dir === 'up' ? '+' : '' }}{{ item.chg }}%
      </span>
      <span v-if="idx < tickers.length - 1" class="ticker-sep" />
    </div>
    <span class="demo-chip">演示</span>
  </div>
</template>

<script setup lang="ts">
// 占位 mock —— 真实行情 API 接入后替换
const tickers = [
  { code: 'sh000001', label: '上证', value: '3,342.12', chg: '0.82', dir: 'up' },
  { code: 'sz399001', label: '深证', value: '10,621.35', chg: '-0.34', dir: 'down' },
  { code: 'hsi', label: '恒指', value: '19,847.50', chg: '1.23', dir: 'up' },
]
</script>

<style lang="scss" scoped>
.mkt-ticker {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  padding: 5px 12px 5px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
}

.ticker-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ticker-sep {
  display: inline-block;
  width: 1px;
  height: 12px;
  background: var(--border-default);
  margin-left: 8px;
}

.ticker-label {
  color: var(--fg-muted);
  font-family: var(--font-sans);
  font-size: 11px;
}

.ticker-val {
  color: var(--fg-primary);
  font-weight: 500;
}

.ticker-chg.up { color: var(--up); }
.ticker-chg.down { color: var(--down); }

@media (max-width: 1200px) {
  .mkt-ticker { display: none; }
}
</style>
