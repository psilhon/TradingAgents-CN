<template>
  <div class="mkt-ticker" :title="tickerTitle">
    <div v-if="tickers.length === 0" class="mkt-loading">
      <span class="muted-small">指数加载中…</span>
    </div>
    <div v-else class="mkt-track">
      <!-- 主轨 -->
      <div
        v-for="(item, idx) in tickers"
        :key="'a' + item.code"
        class="ticker-row"
        :class="{ 'is-stale': item.stale }"
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
        :class="{ 'is-stale': item.stale }"
      >
        <span class="ticker-label">{{ item.label }}</span>
        <span class="ticker-val num">{{ item.value }}</span>
        <span class="ticker-chg num" :class="item.dir">
          {{ item.dir === 'up' ? '+' : '' }}{{ item.chg }}%
        </span>
        <span v-if="idx < tickers.length - 1" class="ticker-sep" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// MarketTicker — 顶部指数滚动条，从 GET /api/market/indices/snapshot 拉取。
// 后端 scheduler 每 5s 刷新 mongo market_indices，前端 polling 同步频率（5s）。
// 数据时间戳非今日（CN tz 日历日比较）时，对应 ticker 灰化 + tooltip 注明「昨日收盘」。
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { marketApi, type IndexSnapshot } from '@/api/market'

interface TickerItem {
  code: string
  label: string
  value: string         // 已格式化（含千分位）
  chg: string           // 已格式化（2 位小数，含正负号在 template 里另加）
  dir: 'up' | 'down' | 'flat'
  stale: boolean        // as_of 非今日时为 true，UI 灰化
}

const tickers = ref<TickerItem[]>([])
const lastUpdated = ref<string>('')

const tickerTitle = computed(() => {
  if (tickers.value.length === 0) return '指数加载中'
  return `指数行情（A股+港股，5s 刷新） · 最近一次：${lastUpdated.value || '—'}`
})

// 数字千分位格式（仅整数部分加逗号，保留 2 位小数）
const formatValue = (v: number | null): string => {
  if (v == null || !isFinite(v)) return '—'
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// CN tz 日历日比较：mongo updated_at 是 UTC，加 8 小时取 YYYY-MM-DD
const isStaleAsOf = (asOf: string | null): boolean => {
  if (!asOf) return true
  const dt = new Date(asOf)
  if (isNaN(dt.getTime())) return true
  const cnDate = new Date(dt.getTime() + 8 * 3600 * 1000).toISOString().slice(0, 10)
  const todayCn = new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10)
  return cnDate !== todayCn
}

const mapSnapshot = (raw: IndexSnapshot[]): TickerItem[] => {
  return raw
    .filter((s) => s.value != null)
    .map((s) => {
      const pct = s.pct_chg
      const dir: TickerItem['dir'] =
        pct == null ? 'flat' : pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat'
      return {
        code: s.code,
        label: s.label,
        value: formatValue(s.value),
        chg: pct == null ? '—' : pct.toFixed(2),
        dir,
        stale: isStaleAsOf(s.as_of),
      }
    })
}

const loadIndices = async () => {
  try {
    const resp = await marketApi.getIndicesSnapshot()
    if (resp.success && Array.isArray(resp.data)) {
      tickers.value = mapSnapshot(resp.data)
      lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    }
  } catch (e) {
    // 静默失败 — 保留上次成功值；首次失败则 ticker 显示「指数加载中…」
    console.warn('[MarketTicker] load failed', e)
  }
}

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadIndices()
  // 后端 5s 写一次 mongo，前端 5s polling，节奏匹配 — 不必比后端更频繁
  timer = setInterval(loadIndices, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style lang="scss" scoped>
.mkt-ticker {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px;
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
    black calc(100% - 30px),
    transparent 100%
  );
  -webkit-mask-image: linear-gradient(
    90deg,
    transparent 0,
    black 30px,
    black calc(100% - 30px),
    transparent 100%
  );
}

.mkt-loading {
  padding: 0 8px;
  opacity: 0.6;
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
  transition: opacity 0.15s;

  // 数据时间戳非今日 → 灰化（如港股 16:00 后到次日开盘前）
  &.is-stale {
    opacity: 0.55;
  }
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
.ticker-chg.flat { color: var(--fg-muted); }

@media (max-width: 1200px) {
  .mkt-ticker { display: none; }
}
</style>
