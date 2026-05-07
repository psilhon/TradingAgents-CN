<template>
  <span class="num-flip" :class="flashClass">
    <span class="num-flip-inner" :class="{ flipping }">
      <span class="num-flip-prev">{{ prevValue }}</span>
      <span class="num-flip-next">{{ value }}</span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  value: string | number
  // flash 持续时间 (ms)
  flashDuration?: number
  // 翻牌动画时间 (ms)
  flipDuration?: number
}

const props = withDefaults(defineProps<Props>(), {
  flashDuration: 400,
  flipDuration: 300,
})

const prevValue = ref<string | number>(props.value)
const flipping = ref(false)
const flashClass = ref<'' | 'flash-up' | 'flash-down'>('')

watch(
  () => props.value,
  (newVal, oldVal) => {
    if (newVal === oldVal) return

    // 比较数值方向（去除千位分隔符 / 货币符号）
    const oldNum = parseFloat(String(oldVal).replace(/[^\d.-]/g, ''))
    const newNum = parseFloat(String(newVal).replace(/[^\d.-]/g, ''))
    if (!isNaN(oldNum) && !isNaN(newNum)) {
      flashClass.value = newNum > oldNum ? 'flash-up' : newNum < oldNum ? 'flash-down' : ''
    }

    // 触发翻牌动画
    flipping.value = false
    requestAnimationFrame(() => {
      flipping.value = true
    })

    // 翻牌结束后更新 prev
    setTimeout(() => {
      prevValue.value = newVal
      flipping.value = false
    }, props.flipDuration)

    // flash 结束清除
    setTimeout(() => {
      flashClass.value = ''
    }, props.flashDuration)
  },
)
</script>

<style lang="scss" scoped>
.num-flip {
  display: inline-block;
  position: relative;
  transition: color 0.2s, text-shadow 0.2s;

  &.flash-up {
    color: var(--up) !important;
    text-shadow: 0 0 8px rgba(var(--up-rgb), 0.50);
  }
  &.flash-down {
    color: var(--down) !important;
    text-shadow: 0 0 8px rgba(var(--down-rgb), 0.50);
  }
}

.num-flip-inner {
  display: inline-block;
  position: relative;
  height: 1em;
  line-height: 1em;
  overflow: hidden;
  vertical-align: baseline;
}

.num-flip-prev,
.num-flip-next {
  display: inline-block;
  white-space: nowrap;
}

// prev 留在布局流里撑开父级宽度（修复数字消失 bug）
.num-flip-prev {
  position: relative;
  transform: translateY(0);
}

// next 绝对定位浮在 prev 上方（初始藏在下方 100%）
.num-flip-next {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  transform: translateY(100%);
}

// 翻牌中：prev 上滑出，next 上滑入
.num-flip-inner.flipping {
  .num-flip-prev {
    animation: flip-out 0.3s ease-in-out forwards;
  }
  .num-flip-next {
    animation: flip-in 0.3s ease-in-out forwards;
  }
}

@keyframes flip-out {
  0%   { transform: translateY(0);     opacity: 1; }
  100% { transform: translateY(-100%); opacity: 0; }
}
@keyframes flip-in {
  0%   { transform: translateY(100%);  opacity: 0; }
  100% { transform: translateY(0);     opacity: 1; }
}
</style>
