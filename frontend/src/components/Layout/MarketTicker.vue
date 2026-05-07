<template>
  <div class="mkt-ticker" title="演示数据 — 未接行情 API">
    <div class="mkt-track">
      <!-- 主轨 -->
      <div
        v-for="(item, idx) in tickers"
        :key="'a' + item.code"
        class="ticker-row"
      >
        <span class="ticker-label">{{ item.label }}</span>
        <span class="ticker-val num">{{ item.value }}</span>
        <span class="ticker-chg num" :class="item.dir">
          {{ item.dir === 'up' ? '+' : '' }}{{ item.chg }}%
        </span>
        <span v-if="idx < tickers.length - 1" class="ticker-sep" />
      </div>
      <!-- 复制一遍以实现无缝循环 -->
      <div
        v-for="(item, idx) in tickers"
        :key="'b' + item.code"
        class="ticker-row"
      >
        <span class="ticker-label">{{ item.label }}</span>
        <span class="ticker-val num">{{ item.value }}</span>
        <span class="ticker-chg num" :class="item.dir">
          {{ item.dir === 'up' ? '+' : '' }}{{ item.chg }}%
        </span>
        <span v-if="idx < tickers.length - 1" class="ticker-sep" />
      </div>
    </div>
    <span class="demo-chip">演示</span>
  </div>
</template>

<script setup lang="ts">
// 占位 mock —— 真实行情 API 接入后替换；多支以体现循环滚动效果
const tickers = [
  { code: 'sh000001', label: '上证', value: '3,342.12', chg: '0.82', dir: 'up' },
  { code: 'sz399001', label: '深证', value: '10,621.35', chg: '-0.34', dir: 'down' },
  { code: 'sz399006', label: '创业板', value: '2,156.78', chg: '1.45', dir: 'up' },
  { code: 'hsi', label: '恒指', value: '19,847.50', chg: '1.23', dir: 'up' },
  { code: 'spx', label: '标普', value: '5,302.18', chg: '-0.18', dir: 'down' },
  { code: 'ndx', label: '纳指', value: '18,720.45', chg: '0.62', dir: 'up' },
]
</script>

<style lang="scss" scoped>
.mkt-ticker {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px 5px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  width: 480px;
  max-width: 60vw;

  // 左右两端淡出 mask
  mask-image: linear-gradient(
    90deg,
    transparent 0,
    black 30px,
    black calc(100% - 50px),
    transparent 100%
  );
  -webkit-mask-image: linear-gradient(
    90deg,
    transparent 0,
    black 30px,
    black calc(100% - 50px),
    transparent 100%
  );
}

.mkt-track {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  animation: ticker-scroll 40s linear infinite;
  padding-right: 14px;
}

.mkt-ticker:hover .mkt-track {
  animation-play-state: paused;
}

@keyframes ticker-scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
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

.demo-chip {
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

@media (max-width: 1200px) {
  .mkt-ticker { display: none; }
}
</style>
