<template>
  <svg
    class="sparkline"
    :viewBox="`0 0 ${width} ${height}`"
    :width="width"
    :height="height"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <!-- 区域填充（淡渐变）-->
    <path
      v-if="fill"
      :d="areaPath"
      :fill="`url(#sparkline-grad-${gradId})`"
    />
    <linearGradient :id="`sparkline-grad-${gradId}`" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" :stop-color="strokeColor" stop-opacity="0.30" />
      <stop offset="100%" :stop-color="strokeColor" stop-opacity="0" />
    </linearGradient>

    <!-- 折线 -->
    <polyline
      :points="polyPoints"
      fill="none"
      :stroke="strokeColor"
      stroke-width="1.4"
      stroke-linejoin="round"
      stroke-linecap="round"
    />

    <!-- 末端点 -->
    <circle
      v-if="dot"
      :cx="lastX"
      :cy="lastY"
      r="1.6"
      :fill="strokeColor"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  data: number[]
  width?: number
  height?: number
  color?: 'up' | 'down' | 'flat' | 'accent'
  fill?: boolean
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 60,
  height: 16,
  color: 'flat',
  fill: true,
  dot: false,
})

// 唯一 id 防止多 sparkline 渐变冲突
const gradId = Math.random().toString(36).slice(2, 8)

const strokeColor = computed(() => {
  const map = {
    up: 'var(--up)',
    down: 'var(--down)',
    flat: 'var(--fg-muted)',
    accent: 'var(--accent)',
  }
  return map[props.color]
})

// 把 data 映射到 [0, width] x [0, height] 坐标空间
const points = computed(() => {
  const data = props.data
  if (!data || data.length < 2) return []
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const stepX = props.width / (data.length - 1)
  const padY = 2  // 上下留 2px 防止贴边
  const usableH = props.height - padY * 2

  return data.map((v, i) => {
    const x = i * stepX
    const y = padY + (1 - (v - min) / range) * usableH
    return [x, y]
  })
})

const polyPoints = computed(() =>
  points.value.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' '),
)

const areaPath = computed(() => {
  if (points.value.length < 2) return ''
  const start = `M 0 ${props.height}`
  const lines = points.value.map(([x, y]) => `L ${x.toFixed(2)} ${y.toFixed(2)}`).join(' ')
  const end = `L ${props.width} ${props.height} Z`
  return `${start} ${lines} ${end}`
})

const lastX = computed(() => {
  const last = points.value[points.value.length - 1]
  return last ? last[0] : 0
})
const lastY = computed(() => {
  const last = points.value[points.value.length - 1]
  return last ? last[1] : 0
})
</script>

<style lang="scss" scoped>
.sparkline {
  display: inline-block;
  flex-shrink: 0;
  overflow: visible;
}
</style>
