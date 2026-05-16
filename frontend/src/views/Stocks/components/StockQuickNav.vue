<template>
  <div class="stock-quick-nav">
    <!-- 自选股快速切换 -->
    <el-select
      v-model="favVal"
      class="qn-select"
      size="small"
      placeholder="自选股"
      filterable
      clearable
      :no-data-text="favLoaded ? '暂无自选股' : '加载中…'"
      @change="onPickFav"
    >
      <template #prefix>
        <el-icon><Star /></el-icon>
      </template>
      <el-option
        v-for="f in favorites"
        :key="favCode(f)"
        :label="`${favCode(f)} ${f.stock_name}`"
        :value="favCode(f)"
      >
        <span>{{ favCode(f) }} {{ f.stock_name }}</span>
        <el-tag
          v-if="favCode(f) === props.currentCode"
          size="small"
          type="primary"
          class="qn-cur"
        >当前</el-tag>
      </el-option>
    </el-select>

    <!-- 代码 / 名称搜索跳转 -->
    <el-select
      v-model="searchVal"
      class="qn-select qn-search"
      size="small"
      placeholder="搜代码 / 名称"
      filterable
      remote
      :remote-method="onSearch"
      :loading="searching"
      :reserve-keyword="false"
      @change="onPickSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
      <el-option
        v-for="s in searchResults"
        :key="s.symbol"
        :label="`${s.symbol} ${s.name}`"
        :value="s.symbol"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Star } from '@element-plus/icons-vue'
import { favoritesApi, type FavoriteItem } from '@/api/favorites'
import { analysisApi } from '@/api/analysis'

const props = defineProps<{ currentCode: string }>()

const router = useRouter()

const favorites = ref<FavoriteItem[]>([])
const favLoaded = ref(false)
const favVal = ref('')

const searchVal = ref('')
const searchResults = ref<Array<{ symbol: string; name: string; market: string; type: string }>>([])
const searching = ref(false)

const favCode = (f: FavoriteItem): string => String(f.symbol || f.stock_code || '')

onMounted(async () => {
  try {
    const res = await favoritesApi.list()
    favorites.value = res.data ?? []
  } catch {
    favorites.value = []
  } finally {
    favLoaded.value = true
  }
})

// 跳转到目标股票详情；目标为空或就是当前股票则不跳
const go = (target: string): void => {
  const c = target.trim()
  if (!c || c.toUpperCase() === props.currentCode.toUpperCase()) return
  router.push({ name: 'StockDetail', params: { code: c } })
}

const onPickFav = (val: string): void => {
  go(val)
  favVal.value = ''
}

const onSearch = async (query: string): Promise<void> => {
  const q = query.trim()
  if (!q) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    searchResults.value = await analysisApi.searchStocks(q)
  } catch {
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

const onPickSearch = (val: string): void => {
  go(val)
  searchVal.value = ''
  searchResults.value = []
}
</script>

<style scoped>
.stock-quick-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qn-select {
  width: 168px;
}
.qn-search {
  width: 188px;
}
.qn-cur {
  margin-left: 6px;
}
</style>
