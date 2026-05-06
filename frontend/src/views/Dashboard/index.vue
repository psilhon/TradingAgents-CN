<template>
  <div class="dashboard">
    <!-- Hero 区 -->
    <section class="hero">
      <div class="hero-top">
        <div class="hero-left">
          <h1 class="hero-title">
            欢迎使用 <span class="accent">TradingAgents-CN</span>
          </h1>
          <p class="hero-sub">
            现代化多智能体股票分析学习平台，辅助你掌握更全面的市场视角，实现精准量化分析与投资决策
          </p>
        </div>
      </div>

      <div class="hero-stats">
        <div class="hero-stat">
          <div class="hero-stat-label">分析任务总数</div>
          <div class="hero-stat-val num">{{ userStats.totalAnalyses }}</div>
          <div class="hero-stat-sub">今日 +{{ todayAnalyses }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">成功率</div>
          <div class="hero-stat-val num down">{{ successRate }}%</div>
          <div class="hero-stat-sub">
            {{ userStats.successfulAnalyses }} / {{ userStats.totalAnalyses }}
          </div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">模拟总资产</div>
          <div class="hero-stat-val num accent">¥{{ formatMoney(totalEquity) }}</div>
          <div class="hero-stat-sub">A股账户</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">自选股数量</div>
          <div class="hero-stat-val num">{{ favoriteStocks.length }}</div>
          <div class="hero-stat-sub">{{ favUpCount }}涨 {{ favDownCount }}跌</div>
        </div>
      </div>
    </section>

    <!-- 主网格 4 行 2 列：左右每行 panel 强制等高 -->
    <div class="content-grid">
        <!-- Row 1 左：快速操作 sec-hdr -->
        <div class="sec-hdr ga-quick-hdr">
          <div class="sec-title">快速操作</div>
        </div>
        <!-- Row 2 左：快速操作 4 卡 -->
        <div class="quick-actions ga-quick">
          <div class="action-card" @click="goToSingleAnalysis">
            <div class="action-icon gold"><el-icon><Document /></el-icon></div>
            <div class="action-body">
              <div class="action-name">单股分析</div>
              <div class="action-desc">深度分析单只股票的投资价值</div>
            </div>
            <el-icon class="action-arrow"><ArrowRight /></el-icon>
          </div>
          <div class="action-card" @click="goToBatchAnalysis">
            <div class="action-icon blue"><el-icon><Files /></el-icon></div>
            <div class="action-body">
              <div class="action-name">批量分析</div>
              <div class="action-desc">同时分析多只股票，提高效率</div>
            </div>
            <el-icon class="action-arrow"><ArrowRight /></el-icon>
          </div>
          <div class="action-card" @click="goToScreening">
            <div class="action-icon green"><el-icon><Search /></el-icon></div>
            <div class="action-body">
              <div class="action-name">股票筛选</div>
              <div class="action-desc">通过多维度条件筛选优质股票</div>
            </div>
            <el-icon class="action-arrow"><ArrowRight /></el-icon>
          </div>
          <div class="action-card" @click="goToQueue">
            <div class="action-icon red"><el-icon><List /></el-icon></div>
            <div class="action-body">
              <div class="action-name">任务中心</div>
              <div class="action-desc">查看和管理分析任务列表</div>
            </div>
            <el-icon class="action-arrow"><ArrowRight /></el-icon>
          </div>
        </div>

        <!-- Row 3 左：最近分析 -->
        <div class="panel analysis-panel ga-analysis">
          <div class="panel-hdr">
            <div class="sec-title">最近分析</div>
            <span class="sec-link" @click="goToHistory">查看全部历史 →</span>
          </div>
          <div v-if="recentAnalyses.length === 0" class="empty-block">
            <el-empty description="暂无分析任务" :image-size="60" />
          </div>
          <div v-else class="analysis-list">
            <div
              v-for="row in recentAnalyses.slice(0, 3)"
              :key="(row as any).task_id"
              class="analysis-item"
              @click="viewAnalysis(row)"
            >
              <div class="analysis-left">
                <div class="analysis-code">
                  <span class="code-badge">{{ (row as any).stock_code || '—' }}</span>
                  <span class="analysis-name">{{ (row as any).stock_name || '—' }}</span>
                </div>
                <div class="analysis-time num">{{ formatTime((row as any).start_time) }}</div>
              </div>
              <div class="analysis-right">
                <span class="status-badge" :class="statusBadgeClass(row.status)">
                  <span class="status-dot"></span>
                  {{ getStatusText(row.status) }}
                </span>
                <el-icon
                  v-if="row.status === 'completed'"
                  class="analysis-download"
                  title="下载报告"
                  @click.stop="downloadReport(row)"
                ><Download /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 4 左：市场快讯 -->
        <div class="panel news-panel ga-news">
          <div class="panel-hdr">
            <div class="sec-title">市场快讯</div>
          </div>
          <div v-if="marketNews.length > 0" class="news-list scroll-body">
            <div
              v-for="news in marketNews"
              :key="news.id"
              class="news-item"
              @click="openNewsUrl(news.url)"
            >
              <div class="news-tag">
                {{ news.source || '快讯' }} · {{ formatTime(news.time) }}
              </div>
              <div class="news-headline">{{ news.title }}</div>
            </div>
          </div>
          <div v-else class="empty-block">
            <el-empty description="暂无市场快讯" :image-size="50" />
          </div>
        </div>

        <!-- Row 1 右：数据源同步条 -->
        <el-popover
          placement="bottom-end"
          :width="380"
          trigger="click"
          popper-class="hero-sync-popover"
        >
          <template #reference>
            <div class="sync-bar clickable ga-sync">
              <div class="sec-title">
                <span class="sync-status-dot" :class="syncOverall"></span>
                <span>数据源同步</span>
              </div>
              <span class="sec-link">
                详情
                <el-icon><ArrowDown /></el-icon>
              </span>
            </div>
          </template>
          <div class="hero-sync-popover-body">
            <MultiSourceSyncCard />
          </div>
        </el-popover>

        <!-- Row 2 右：自选股 Watchlist -->
        <div class="panel watchlist-panel ga-watchlist">
          <div class="panel-hdr">
            <div class="sec-title">我的自选股</div>
            <span class="sec-link" @click="goToFavorites">管理 →</span>
          </div>
          <div v-if="favoriteStocks.length === 0" class="empty-block">
            <el-empty description="暂无自选股" :image-size="50">
              <el-button type="primary" size="small" @click="goToFavorites">
                添加自选股
              </el-button>
            </el-empty>
          </div>
          <div v-else class="watchlist-list scroll-body">
            <div
              v-for="stock in favoriteStocks"
              :key="stock.stock_code"
              class="watchlist-item"
              @click="viewStockDetail(stock)"
            >
              <div class="watchlist-left">
                <div class="watchlist-code">{{ stock.stock_code }}</div>
                <div class="watchlist-name">{{ stock.stock_name }}</div>
              </div>
              <div class="watchlist-right">
                <div
                  class="watchlist-price num"
                  :class="getPriceChangeClass(stock.change_percent)"
                >¥{{ Number(stock.current_price).toFixed(2) }}</div>
                <div
                  class="watchlist-chg num"
                  :class="getPriceChangeClass(stock.change_percent)"
                >
                  {{ stock.change_percent > 0 ? '▲' : stock.change_percent < 0 ? '▼' : '—' }}
                  {{ Math.abs(Number(stock.change_percent)).toFixed(2) }}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3 右：模拟交易账户 -->
        <div class="panel account-panel ga-account">
          <div class="panel-hdr">
            <div class="sec-title">模拟交易账户</div>
            <span class="sec-link" @click="goToPaperTrading">详情 →</span>
          </div>
          <div class="account-tabs">
            <div
              v-for="tab in accountTabs"
              :key="tab.key"
              class="account-tab"
              :class="{ active: activeAccountTab === tab.key }"
              @click="activeAccountTab = tab.key"
            >
              {{ tab.flag }} {{ tab.label }}
            </div>
          </div>
          <div class="account-body">
            <template v-if="paperAccount">
              <div class="account-row">
                <span class="account-label">可用现金</span>
                <span class="account-val num">
                  {{ currentCurrency.symbol }}{{ formatMoney(getCurrencyAmount(paperAccount.cash, currentCurrency.key)) }}
                </span>
              </div>
              <div class="account-row">
                <span class="account-label">持仓市值</span>
                <span class="account-val num">
                  {{ currentCurrency.symbol }}{{ formatMoney(getCurrencyAmount(paperAccount.positions_value, currentCurrency.key)) }}
                </span>
              </div>
              <div class="account-divider"></div>
              <div class="account-row">
                <span class="account-label">账户总资产</span>
                <span class="account-val num accent strong">
                  {{ currentCurrency.symbol }}{{ formatMoney(getCurrencyAmount(paperAccount.equity, currentCurrency.key)) }}
                </span>
              </div>
              <div class="account-progress">
                <div class="progress-label">
                  <span>持仓比例</span>
                  <span class="num">{{ positionRatio }}%</span>
                </div>
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: positionRatio + '%' }"></div>
                </div>
              </div>
              <el-button
                type="primary"
                style="width: 100%; margin-top: 14px;"
                @click="goToPaperTrading"
              >开始模拟交易</el-button>
            </template>
            <div v-else class="empty-block">
              <p class="muted-small">暂无账户信息</p>
              <el-button type="primary" size="small" @click="goToPaperTrading">
                查看模拟交易
              </el-button>
            </div>
          </div>
        </div>

        <!-- Row 4 右：今日市场概况 (mock 占位) -->
        <div class="panel market-overview-panel ga-market">
          <div class="panel-hdr">
            <div class="sec-title">今日市场概况</div>
            <span class="demo-chip">演示</span>
          </div>
          <div class="market-grid">
            <div class="market-cell">
              <div class="market-cell-label">涨停家数</div>
              <div class="market-cell-val num up">87</div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">跌停家数</div>
              <div class="market-cell-val num down">12</div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">成交额</div>
              <div class="market-cell-val num">
                8,423<span class="market-cell-unit">亿</span>
              </div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">上涨家数</div>
              <div class="market-cell-val num up">2,841</div>
            </div>
          </div>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  TrendCharts,
  Search,
  Document,
  Files,
  List,
  ArrowRight,
  ArrowDown,
  Download,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { AnalysisTask, AnalysisStatus } from '@/types/analysis'
import MultiSourceSyncCard from '@/components/Dashboard/MultiSourceSyncCard.vue'
import { favoritesApi } from '@/api/favorites'
import { analysisApi } from '@/api/analysis'
import { newsApi } from '@/api/news'
import { paperApi, type PaperAccountSummary } from '@/api/paper'

const router = useRouter()
const authStore = useAuthStore()

// 响应式数据
const userStats = ref({
  totalAnalyses: 0,
  successfulAnalyses: 0,
  dailyQuota: 1000,
  dailyUsed: 0,
  concurrentLimit: 3,
})

const recentAnalyses = ref<AnalysisTask[]>([])
const favoriteStocks = ref<any[]>([])
const marketNews = ref<any[]>([])
const paperAccount = ref<PaperAccountSummary | null>(null)

// 汇总状态指示灯（暂用静态 ok；真实状态通过展开后的 MultiSourceSyncCard 查看）
const syncOverall = ref<'ok' | 'warn' | 'err'>('ok')

// 账户 tab 切换
type AccountKey = 'CNY' | 'HKD' | 'USD'
const accountTabs: { key: AccountKey; label: string; flag: string; symbol: string }[] = [
  { key: 'CNY', label: 'A股', flag: '🇨🇳', symbol: '¥' },
  { key: 'HKD', label: '港股', flag: '🇭🇰', symbol: 'HK$' },
  { key: 'USD', label: '美股', flag: '🇺🇸', symbol: '$' },
]
const activeAccountTab = ref<AccountKey>('CNY')
const currentCurrency = computed(() => {
  return accountTabs.find((t) => t.key === activeAccountTab.value) || accountTabs[0]
})

const getCurrencyAmount = (
  amount: number | { CNY: number; HKD: number; USD: number } | undefined,
  currency: AccountKey,
  fallback = 0,
): number => {
  if (typeof amount === 'number') return amount
  return amount?.[currency] ?? fallback
}

// computed
const successRate = computed(() => {
  const t = userStats.value.totalAnalyses
  if (!t) return 0
  return ((userStats.value.successfulAnalyses / t) * 100).toFixed(1)
})

const todayAnalyses = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return recentAnalyses.value.filter((r) => {
    const t = (r as any).start_time || ''
    return String(t).startsWith(today)
  }).length
})

const totalEquity = computed(() => {
  if (!paperAccount.value) return 0
  return getCurrencyAmount(paperAccount.value.equity, 'CNY')
})

const favUpCount = computed(() =>
  favoriteStocks.value.filter((s) => Number(s.change_percent) > 0).length,
)
const favDownCount = computed(() =>
  favoriteStocks.value.filter((s) => Number(s.change_percent) < 0).length,
)

const positionRatio = computed(() => {
  if (!paperAccount.value) return 0
  const equity = getCurrencyAmount(paperAccount.value.equity, activeAccountTab.value)
  const positions = getCurrencyAmount(paperAccount.value.positions_value, activeAccountTab.value)
  if (!equity) return 0
  return ((positions / equity) * 100).toFixed(1)
})

// 路由跳转
const quickAnalysis = () => router.push('/analysis/single')
const goToSingleAnalysis = () => router.push('/analysis/single')
const goToBatchAnalysis = () => router.push('/analysis/batch')
const goToScreening = () => router.push('/screening')
const goToQueue = () => router.push('/queue')
const goToHistory = () => router.push('/tasks?tab=completed')
const goToFavorites = () => router.push('/favorites')
const goToPaperTrading = () => router.push('/paper')

const viewAnalysis = (analysis: AnalysisTask) => {
  const status = (analysis as any)?.status
  if (status === 'completed') {
    router.push({ name: 'ReportDetail', params: { id: analysis.task_id } })
  } else {
    router.push('/tasks?tab=running')
  }
}

const downloadReport = async (analysis: AnalysisTask) => {
  try {
    const reportId = analysis.task_id
    const res = await fetch(`/api/reports/${reportId}/download?format=markdown`, {
      headers: { Authorization: `Bearer ${authStore.token}` },
    })
    if (!res.ok) {
      ElMessage.error('下载失败，报告可能尚未生成')
      return
    }
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const code = (analysis as any).stock_code || (analysis as any).stock_symbol || 'stock'
    const dateStr = (analysis as any).analysis_date || (analysis as any).start_time || ''
    a.download = `${code}_分析报告_${String(dateStr).slice(0, 10)}.md`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    ElMessage.success('报告已开始下载')
  } catch (err) {
    console.error('下载报告出错:', err)
    ElMessage.error('下载失败，请稍后重试')
  }
}

const openNewsUrl = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  } else {
    ElMessage.info('该新闻暂无详情链接')
  }
}

const viewStockDetail = (stock: any) => {
  router.push(`/analysis/single?stock_code=${stock.stock_code}`)
}

const getStatusText = (status: string | AnalysisStatus) => {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    running: '分析中',
    completed: '完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || String(status)
}

const statusBadgeClass = (status: string | AnalysisStatus) => {
  const map: Record<string, string> = {
    pending: 'running',
    processing: 'running',
    running: 'running',
    completed: 'success',
    failed: 'fail',
    cancelled: 'fail',
  }
  return map[status] || 'running'
}

const getPriceChangeClass = (changePercent: number) => {
  const v = Number(changePercent)
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

import { formatDateTime } from '@/utils/datetime'
const formatTime = (time: string) => formatDateTime(time)

const formatMoney = (value: number) => {
  if (!value) return '0.00'
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

// data loaders
const loadFavoriteStocks = async () => {
  try {
    const response = await favoritesApi.list()
    if (response.success && response.data) {
      favoriteStocks.value = response.data.map((item: any) => ({
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        current_price: item.current_price || 0,
        change_percent: item.change_percent || 0,
      }))
    }
  } catch (error) {
    console.error('加载自选股失败:', error)
  }
}

const loadRecentAnalyses = async () => {
  try {
    const res = await analysisApi.getTaskList({
      limit: 10,
      offset: 0,
      status: undefined,
    })
    const body: any = (res as any)?.data?.data || (res as any)?.data || res || {}
    const tasks = body.tasks || []
    recentAnalyses.value = tasks
    userStats.value.totalAnalyses = body.total ?? tasks.length
    userStats.value.successfulAnalyses = tasks.filter(
      (item: any) => item.status === 'completed',
    ).length
  } catch (error) {
    console.error('加载最近分析失败:', error)
    recentAnalyses.value = []
  }
}

const loadMarketNews = async () => {
  try {
    let response = await newsApi.getLatestNews(undefined, 10, 24)
    if (response.success && response.data && response.data.news.length === 0) {
      response = await newsApi.getLatestNews(undefined, 10, 24 * 365)
    }
    if (response.success && response.data) {
      marketNews.value = response.data.news.map((item: any) => ({
        id: item.id || item.title,
        title: item.title,
        time: item.publish_time,
        url: item.url,
        source: item.source,
      }))
    }
  } catch (error) {
    console.error('加载市场快讯失败:', error)
    marketNews.value = []
  }
}

const loadPaperAccount = async () => {
  try {
    const response = await paperApi.getAccount()
    if (response.success && response.data) {
      paperAccount.value = response.data.account
    }
  } catch (error) {
    console.error('加载模拟交易账户失败:', error)
    paperAccount.value = null
  }
}

onMounted(async () => {
  await loadFavoriteStocks()
  await loadRecentAnalyses()
  await loadMarketNews()
  await loadPaperAccount()
})
</script>

<style lang="scss" scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--fg-primary);
}

// =================================================================
// Hero
// =================================================================
.hero {
  position: relative;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 10px 20px;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: -60px;
    right: -40px;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
    pointer-events: none;
  }
  &::after {
    content: '';
    position: absolute;
    bottom: -80px;
    left: 30%;
    width: 400px;
    height: 200px;
    background: radial-gradient(circle, var(--blue-soft) 0%, transparent 70%);
    pointer-events: none;
  }
}

.hero-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.hero-left {
  flex: 1;
  min-width: 0;
}


.hero-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: hero-pulse 2s infinite;
}
@keyframes hero-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.hero-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 2px 0;
  color: var(--fg-primary);

  // accent 词用渐变填充（金属字效，深浅两套渐变在 token）
  .accent {
    background: var(--gradient-title);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }
}

.hero-sub {
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.4;
  max-width: 560px;
  margin: 0;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-default);
  position: relative;
  z-index: 1;
}

// 4 个 stat 全部居中
.hero-stat {
  text-align: center;
}

.hero-stat-label {
  font-size: 10px;
  color: var(--fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 1px;
}

.hero-stat-val {
  font-size: 17px;
  font-weight: 600;
  color: var(--fg-primary);
  line-height: 1.15;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
  &.accent { color: var(--accent); }
}

.hero-stat-sub {
  font-size: 10px;
  color: var(--fg-muted);
  margin-top: 1px;
}

// =================================================================
// Content grid
// =================================================================
// =================================================================
// 主网格 4 行 2 列：每行内左右 panel 强制等高 (grid stretch 默认)
// 行高由各行较高 panel 决定
// =================================================================
.content-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  grid-template-rows: auto auto auto auto;
  gap: 10px 16px;          // row gap 10px, col gap 16px
  align-items: stretch;
  min-width: 0;
}

// 每个 panel 指定其 grid 位置
.ga-quick-hdr   { grid-column: 1; grid-row: 1; }
.ga-sync        { grid-column: 2; grid-row: 1; }
.ga-quick       { grid-column: 1; grid-row: 2; }
.ga-market      { grid-column: 2; grid-row: 2; }
.ga-analysis    { grid-column: 1; grid-row: 3; }
.ga-account     { grid-column: 2; grid-row: 3; }
.ga-news        { grid-column: 1; grid-row: 4; }
.ga-watchlist   { grid-column: 2; grid-row: 4; }

// 移动端：单列、按声明顺序流式排
@media (max-width: 1100px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .ga-quick-hdr,
  .ga-sync,
  .ga-quick,
  .ga-watchlist,
  .ga-analysis,
  .ga-account,
  .ga-news,
  .ga-market {
    grid-column: 1;
    grid-row: auto;
  }
}

// section header
.sec-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: -4px;
}

// 数据源同步条（右栏顶部，与左栏 .sec-hdr "快速操作" 标题高度对齐）
.sync-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0;
  height: 28px;       // 与 .sec-hdr 视觉高度一致
  cursor: pointer;
  user-select: none;
  margin-bottom: -4px;
  transition: opacity 0.15s;

  &:hover { opacity: 0.85; }

  .sec-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;

    .el-icon {
      font-size: 10px;
      transition: transform 0.2s;
    }
  }
}

// 通用 panel
.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border-default);
  flex-shrink: 0;
}

// list-type panel：内容区限高 + 内部滚动
// 用法：在 panel 内的 list 容器上加 .scroll-body class
.scroll-body {
  max-height: 320px;
  overflow-y: auto;
  overscroll-behavior: contain;

  // 滚动条更细更弱
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 2px;
    &:hover { background: var(--fg-muted); }
  }
}

// 各 list panel 单独可选高度（按业务密度调）
.watchlist-list.scroll-body { max-height: 320px; }  // ~5 只可见
.news-list.scroll-body { max-height: 360px; }       // ~5 条可见
// 最近分析固定 3 条不滚动（与自选股呼应的卡片列表风格）

// =================================================================
// Quick actions
// =================================================================
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: 1fr 1fr;
  gap: 8px;
  height: 100%;            // 让 quick-actions 在 grid stretch 时填满 row
}

.action-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;

  &:hover {
    border-color: var(--border-strong);
    background: var(--bg-hover);
    transform: translateY(-1px);

    .action-arrow {
      opacity: 1;
      transform: translate(2px, 0);
    }
  }
}

.action-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
  box-shadow: var(--icon-shadow);

  :deep(.el-icon) { font-size: 20px; }

  &.gold {
    background: var(--icon-bg-gold);
    color: var(--icon-fg-gold);
  }
  &.blue {
    background: var(--icon-bg-blue);
    color: var(--icon-fg-blue);
  }
  &.green {
    background: var(--icon-bg-green);
    color: var(--icon-fg-green);
  }
  &.red {
    background: var(--icon-bg-red);
    color: var(--icon-fg-red);
  }
}

.action-body {
  flex: 1;
  min-width: 0;
}

.action-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-primary);
  margin-bottom: 1px;
}

.action-desc {
  font-size: 11px;
  color: var(--fg-secondary);
  line-height: 1.4;
}

.action-arrow {
  opacity: 0;
  transition: all 0.2s;
  color: var(--fg-muted);
  font-size: 16px;
  flex-shrink: 0;
}

// =================================================================
// 最近分析 list（卡片风格，与自选股呼应）
// =================================================================
.analysis-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 14px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--bg-hover); }
}

.analysis-left {
  flex: 1;
  min-width: 0;
}

.analysis-code {
  display: flex;
  align-items: center;
  gap: 10px;

  .code-badge { flex-shrink: 0; }
}

.analysis-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.analysis-time {
  font-size: 11px;
  color: var(--fg-muted);
  margin-top: 2px;
}

.analysis-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.analysis-download {
  color: var(--fg-muted);
  cursor: pointer;
  font-size: 14px;
  transition: color 0.15s;

  &:hover { color: var(--accent); }
}

.empty-block {
  padding: 32px 16px;
  text-align: center;
}

.muted-small {
  font-size: 12px;
  color: var(--fg-muted);
  margin-bottom: 10px;
}

// =================================================================
// 市场快讯
// =================================================================
.news-item {
  padding: 6px 14px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--bg-hover); }
}

.news-tag {
  font-size: 10px;
  color: var(--accent);
  font-family: var(--font-mono);
  margin-bottom: 3px;
  letter-spacing: 0.04em;
}

.news-headline {
  font-size: 12px;
  color: var(--fg-primary);
  line-height: 1.5;
}

// =================================================================
// 自选股 watchlist
// =================================================================
.watchlist-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--bg-hover); }
}

.watchlist-code {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-primary);
}

.watchlist-name {
  font-size: 11px;
  color: var(--fg-secondary);
  margin-top: 1px;
}

.watchlist-right { text-align: right; }

.watchlist-price {
  font-size: 14px;
  font-weight: 600;
}

.watchlist-chg {
  font-size: 11px;
  margin-top: 1px;
}

// =================================================================
// 模拟账户
// =================================================================
.account-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-default);
}

.account-tab {
  flex: 1;
  padding: 4px;
  text-align: center;
  font-size: 12px;
  color: var(--fg-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;

  &:hover { color: var(--fg-secondary); }

  &.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
}

.account-body {
  padding: 8px 14px;
}

.account-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;

  &:last-child { margin-bottom: 0; }
}

.account-label {
  font-size: 12px;
  color: var(--fg-secondary);
}

.account-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg-primary);

  &.accent { color: var(--accent); }
  &.strong { font-weight: 600; }
}

.account-divider {
  height: 1px;
  background: var(--border-default);
  margin: 6px 0;
}

.account-progress {
  margin-top: 8px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 4px;
}

.progress-bar {
  height: 4px;
  background: var(--border-default);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 4px;
  transition: width 0.3s ease;
}

// =================================================================
// 今日市场概况
// =================================================================
.market-overview-panel .panel-hdr { padding: 8px 14px; }

.market-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px 14px;
}

.market-cell {
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
}

.market-cell-label {
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 2px;
}

.market-cell-val {
  font-size: 18px;
  font-weight: 600;
  color: var(--fg-primary);
  line-height: 1.2;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

.market-cell-unit {
  font-size: 11px;
  color: var(--fg-muted);
  margin-left: 2px;
  font-weight: 400;
}

// =================================================================
// 数据源同步折叠条
// =================================================================
.sync-collapse-panel {
  .panel-hdr.clickable {
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;

    &:hover { background: var(--bg-hover); }
  }

  // 收起时去掉 panel-hdr 底边线
  &:not(.expanded) .panel-hdr { border-bottom: none; }
}

.sync-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.ok {
    background: var(--down);
    box-shadow: 0 0 6px rgba(var(--down-rgb), 0.6);
  }
  &.warn {
    background: var(--warning);
    box-shadow: 0 0 6px rgba(var(--warning-rgb), 0.6);
  }
  &.err {
    background: var(--up);
    box-shadow: 0 0 6px rgba(var(--up-rgb), 0.6);
  }
}

.sync-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sync-toggle-icon {
  transition: transform 0.2s;
  transform: rotate(90deg);

  &.flipped { transform: rotate(-90deg); }
}

// MultiSourceSyncCard 嵌入折叠区时去除自己的 el-card 边框 / 阴影 / 背景
.sync-detail-wrap {
  :deep(.multi-source-sync-card) { padding: 0; }
  :deep(.el-card) {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
  }
  :deep(.el-card__header) {
    background: transparent !important;
    padding: 12px 18px 0 18px !important;
    border-bottom: none !important;
  }
  :deep(.el-card__body) {
    padding: 12px 18px 16px 18px !important;
  }
}

// =================================================================
// 响应式
// =================================================================
@media (max-width: 768px) {
  .hero { padding: 20px; }
  .hero-top { flex-direction: column; }
  .hero-stats { grid-template-columns: 1fr 1fr; gap: 16px; }
  .quick-actions { grid-template-columns: 1fr; }
}
</style>

<!-- popover 渲染在 body 下，scoped 不生效，用 unscoped 全局样式 -->
<style lang="scss">
.el-popper.hero-sync-popover {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  padding: 0 !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;

  .el-popper__arrow::before {
    background: var(--bg-surface) !important;
    border-color: var(--border-default) !important;
  }

  .hero-sync-popover-body {
    padding: 4px;

    // 折叠区里的 MultiSourceSyncCard：去掉自带 el-card 边框 / 阴影
    .el-card {
      border: none !important;
      background: transparent !important;
      box-shadow: none !important;
    }
    .el-card__header {
      background: transparent !important;
      padding: 8px 12px 4px 12px !important;
      border-bottom: 1px solid var(--border-subtle) !important;
    }
    .el-card__body {
      padding: 12px !important;
    }
  }
}
</style>
