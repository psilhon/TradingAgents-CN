<template>
  <div class="dashboard">
    <!-- Hero 区 -->
    <section class="hero" ref="heroEl">
      <!-- 装饰 K 线 SVG（极淡，仅深色可见）-->
      <svg
        class="hero-decoration"
        viewBox="0 0 800 200"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polyline
          points="0,150 50,140 80,160 120,120 150,135 200,90 240,110 280,70 320,95 380,55 420,80 470,40 520,65 580,30 640,55 700,25 760,45 800,20"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
      </svg>
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
          <Sparkline class="hero-stat-spark" :data="heroTrend.total" color="accent" :width="60" :height="10" :fill="true" />
          <div class="hero-stat-sub">今日 +{{ todayAnalyses }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">成功率</div>
          <div class="hero-stat-val num down">{{ successRate }}%</div>
          <Sparkline class="hero-stat-spark" :data="heroTrend.success" color="down" :width="60" :height="10" :fill="true" />
          <div class="hero-stat-sub">
            {{ userStats.successfulAnalyses }} / {{ userStats.totalAnalyses }}
          </div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">模拟总资产</div>
          <div class="hero-stat-val num accent">¥{{ formatMoney(totalEquity) }}</div>
          <Sparkline class="hero-stat-spark" :data="heroTrend.equity" color="accent" :width="60" :height="10" :fill="true" />
          <div class="hero-stat-sub">A股账户</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">自选股数量</div>
          <div class="hero-stat-val num">{{ favoriteStocks.length }}</div>
          <Sparkline class="hero-stat-spark" :data="heroTrend.fav" color="flat" :width="60" :height="10" :fill="true" />
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
          <div v-if="analysisLoading" class="skeleton-wrap">
            <div class="skeleton-line" v-for="n in 3" :key="n" style="height: 32px"></div>
          </div>
          <div v-else-if="recentAnalyses.length === 0" class="empty-block">
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
          <div v-if="newsLoading" class="skeleton-wrap">
            <div v-for="n in 4" :key="n" style="margin-bottom: 12px;">
              <div class="skeleton-line" style="width: 30%; height: 10px;"></div>
              <div class="skeleton-line" style="width: 90%; height: 12px;"></div>
            </div>
          </div>
          <div v-else-if="marketNews.length > 0" class="news-list scroll-body">
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
          <div v-if="watchlistLoading" class="skeleton-wrap">
            <div v-for="n in 4" :key="n" class="skeleton-row">
              <div class="skeleton-line" style="width: 40%; height: 12px;"></div>
              <div class="skeleton-line" style="width: 25%; height: 12px;"></div>
            </div>
          </div>
          <div v-else-if="favoriteStocks.length === 0" class="empty-block">
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
              <Sparkline
                class="watchlist-spark"
                :data="mockTrend(strSeed(stock.stock_code), 14, stock.change_percent > 0 ? 'up' : stock.change_percent < 0 ? 'down' : 'flat')"
                :color="stock.change_percent > 0 ? 'up' : stock.change_percent < 0 ? 'down' : 'flat'"
                :width="50"
                :height="18"
                :fill="true"
              />
              <div class="watchlist-right">
                <div
                  class="watchlist-price num"
                  :class="getPriceChangeClass(stock.change_percent)"
                >¥<NumberFlip :value="Number(stock.current_price).toFixed(2)" /></div>
                <div
                  class="watchlist-chg num"
                  :class="getPriceChangeClass(stock.change_percent)"
                >
                  {{ stock.change_percent > 0 ? '▲' : stock.change_percent < 0 ? '▼' : '—' }}
                  <NumberFlip :value="Math.abs(Number(stock.change_percent)).toFixed(2)" />%
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3 左：模拟交易账户（方案 A + Tier 3） -->
        <div class="panel account-panel ga-account">
          <div class="panel-hdr">
            <div class="sec-title">
              <span>🇨🇳 A 股模拟账户</span>
              <span v-if="paperAccount" class="position-chip num">{{ positionCount }} 持仓</span>
            </div>
            <span class="sec-link" @click="goToPaperTrading">详情 →</span>
          </div>
          <div class="account-body">
            <template v-if="paperAccount">
              <!-- Hero 全宽：总资产 + 累计盈亏 + 资产曲线 sparkline -->
              <div class="account-hero hero-full">
                <div class="hero-info">
                  <div class="hero-label">账户总资产 (¥)</div>
                  <div class="hero-val num accent">
                    {{ formatMoney(getCurrencyAmount(paperAccount.equity, 'CNY')) }}
                  </div>
                  <div class="hero-pnl num" :class="totalPnl >= 0 ? 'up' : 'down'">
                    <span class="pnl-amount">
                      {{ totalPnl >= 0 ? '+' : '−' }}¥{{ formatMoney(Math.abs(totalPnl)) }}
                    </span>
                    <span class="pnl-rate">
                      ({{ totalPnl >= 0 ? '+' : '' }}{{ pnlRate }}%)
                    </span>
                  </div>
                </div>
                <div v-if="paperPerformance && paperPerformance.sparkline_points.length >= 2" class="hero-spark">
                  <svg viewBox="0 0 130 50" class="spark-svg">
                    <polyline
                      :points="sparklineLinePoints"
                      fill="none"
                      :stroke="(paperPerformance.twrr ?? 0) >= 0 ? 'var(--up)' : 'var(--down)'"
                      stroke-width="1.6"
                    />
                    <polyline
                      :points="sparklineFillPoints"
                      :fill="(paperPerformance.twrr ?? 0) >= 0 ? 'var(--up)' : 'var(--down)'"
                      fill-opacity="0.12"
                      stroke="none"
                    />
                  </svg>
                  <div class="spark-meta">
                    <span class="dim">90 天</span>
                    <span class="num" :class="(paperPerformance.twrr ?? 0) >= 0 ? 'up' : 'down'">
                      {{ formatPctSigned(paperPerformance.twrr) }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- KPI 6 列横铺全宽 -->
              <div class="account-kpis kpis-6col">
                <div class="kpi-cell">
                  <div class="kpi-label">可用现金</div>
                  <div class="kpi-val num">
                    ¥{{ formatMoney(getCurrencyAmount(paperAccount.cash, 'CNY')) }}
                  </div>
                </div>
                <div class="kpi-cell">
                  <div class="kpi-label">持仓市值</div>
                  <div class="kpi-val num">
                    ¥{{ formatMoney(getCurrencyAmount(paperAccount.positions_value, 'CNY')) }}
                  </div>
                </div>
                <div class="kpi-cell">
                  <div class="kpi-label">已实现盈亏</div>
                  <div class="kpi-val num" :class="realizedPnl >= 0 ? 'up' : 'down'">
                    {{ realizedPnl >= 0 ? '+' : '−' }}¥{{ formatMoney(Math.abs(realizedPnl)) }}
                  </div>
                </div>
                <div class="kpi-cell">
                  <div class="kpi-label">浮动盈亏</div>
                  <div class="kpi-val num" :class="unrealizedPnl >= 0 ? 'up' : 'down'">
                    {{ unrealizedPnl >= 0 ? '+' : '−' }}¥{{ formatMoney(Math.abs(unrealizedPnl)) }}
                  </div>
                </div>
                <div class="kpi-cell">
                  <div class="kpi-label">TWRR</div>
                  <div class="kpi-val num" :class="paperPerformance?.twrr != null ? ((paperPerformance.twrr >= 0) ? 'up' : 'down') : ''">
                    {{ paperPerformance?.twrr != null ? formatPctSigned(paperPerformance.twrr) : '—' }}
                  </div>
                </div>
                <div class="kpi-cell">
                  <div class="kpi-label">Sharpe</div>
                  <div class="kpi-val num strong">
                    {{ paperPerformance?.sharpe != null ? paperPerformance.sharpe.toFixed(2) : '—' }}
                  </div>
                </div>
              </div>

              <!-- 月度收益柱图 全宽 -->
              <div v-if="paperPerformance && paperPerformance.monthly_returns.length > 0" class="month-bars">
                <div class="month-bars-label">月度收益</div>
                <div class="month-bars-row">
                  <div v-for="m in paperPerformance.monthly_returns.slice(-7)" :key="m.month" class="month-bar-cell">
                    <div class="month-bar-track">
                      <div
                        class="month-bar-fill"
                        :class="m.return_pct >= 0 ? 'up' : 'down'"
                        :style="{
                          height: Math.min(Math.abs(m.return_pct) * 1.6, 12) + 'px',
                          bottom: m.return_pct >= 0 ? '50%' : 'auto',
                          top: m.return_pct < 0 ? '50%' : 'auto',
                        }"
                      ></div>
                      <div class="month-bar-axis"></div>
                    </div>
                    <div class="month-bar-label">{{ m.month.slice(5) }}月</div>
                  </div>
                </div>
              </div>

              <!-- 底部两列：左 [progress + 风险 + button] / 右 [持仓 list] -->
              <div class="account-footer">
                <div class="footer-left">
                  <div class="risk-stats">
                    <div class="risk-stat">
                      <span class="risk-label">当前回撤</span>
                      <span class="risk-val num down">
                        {{ paperPerformance?.current_drawdown != null ? formatPctSigned(paperPerformance.current_drawdown) : '—' }}
                      </span>
                    </div>
                    <div class="risk-stat">
                      <span class="risk-label">最大回撤</span>
                      <span class="risk-val num down">
                        {{ paperPerformance?.max_drawdown != null ? formatPctSigned(paperPerformance.max_drawdown) : '—' }}
                      </span>
                    </div>
                  </div>
                  <div class="tier4-kpis">
                    <div class="kpi-cell">
                      <div class="kpi-label">Beta</div>
                      <div class="kpi-val num">
                        <template v-if="portfolioMetrics?.beta">
                          {{ portfolioMetrics.beta.value.toFixed(2) }}
                          <span class="kpi-tag" :class="betaTagClass(portfolioMetrics.beta.tag)">
                            {{ portfolioMetrics.beta.tag }}
                          </span>
                        </template>
                        <template v-else>—</template>
                      </div>
                    </div>
                    <div class="kpi-cell">
                      <div class="kpi-label">VaR (1D, 95%)</div>
                      <div class="kpi-val num down">
                        <template v-if="portfolioMetrics?.var">
                          −¥{{ formatMoney(Math.abs(portfolioMetrics.var.amount)) }}
                        </template>
                        <template v-else>—</template>
                      </div>
                    </div>
                    <div class="kpi-cell">
                      <div class="kpi-label">加权 PE</div>
                      <div class="kpi-val num">
                        {{ portfolioMetrics?.weighted_pe != null ? portfolioMetrics.weighted_pe.toFixed(1) + '×' : '—' }}
                      </div>
                    </div>
                    <div class="kpi-cell">
                      <div class="kpi-label">加权 PB</div>
                      <div class="kpi-val num">
                        {{ portfolioMetrics?.weighted_pb != null ? portfolioMetrics.weighted_pb.toFixed(1) + '×' : '—' }}
                      </div>
                    </div>
                  </div>
                  <div class="account-progress account-progress-bottom">
                    <div class="progress-label">
                      <span>持仓比例</span>
                      <span class="num">{{ positionRatio }}%</span>
                    </div>
                    <div class="progress-bar">
                      <div class="progress-fill" :style="{ width: positionRatio + '%' }"></div>
                    </div>
                  </div>
                </div>
                <div v-if="paperPositions.length > 0" class="footer-right">
                  <div class="positions-header">
                    <span>持仓明细</span>
                    <span class="muted-small">{{ positionCount }} 只</span>
                  </div>
                  <div class="positions-list">
                    <div
                      v-for="p in paperPositions"
                      :key="p.code"
                      class="position-item"
                    >
                      <div class="pos-row pos-row-main">
                        <span class="pos-code">
                          <span class="num">{{ p.code }}</span>
                          <span v-if="p.name" class="pos-name">{{ p.name }}</span>
                        </span>
                        <span
                          v-if="positionTodayPnl(p) !== null"
                          class="pos-today-pnl num"
                          :class="(positionTodayPnl(p) ?? 0) >= 0 ? 'up' : 'down'"
                          :title="`今日浮动盈亏（基于 ws 实时推送 pct_chg 反推昨收价）`"
                        >
                          今日 {{ (positionTodayPnl(p) ?? 0) >= 0 ? '+' : '−' }}¥{{ formatMoney(Math.abs(positionTodayPnl(p) ?? 0)) }}
                        </span>
                        <span v-else class="pos-today-pnl muted-small">今日 —</span>
                        <span
                          class="pos-pnl num"
                          :class="(p.unrealized_pnl ?? 0) >= 0 ? 'up' : 'down'"
                        >
                          {{ (p.unrealized_pnl ?? 0) >= 0 ? '+' : '−' }}¥{{ formatMoney(Math.abs(p.unrealized_pnl ?? 0)) }}
                        </span>
                      </div>
                      <div class="pos-row pos-row-meta">
                        <span class="pos-meta">
                          {{ p.quantity }} 股 @ ¥{{ formatMoney(p.avg_cost) }}
                          <template v-if="p.last_price != null">
                            <span class="pos-arrow">→</span>
                            ¥{{ formatMoney(p.last_price) }}
                          </template>
                        </span>
                        <span
                          class="pos-pnl-rate"
                          :class="positionPnlRate(p) >= 0 ? 'up' : 'down'"
                        >
                          {{ positionPnlRate(p) >= 0 ? '+' : '' }}{{ positionPnlRate(p).toFixed(2) }}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="empty-block">
              <p class="muted-small">暂无账户信息</p>
              <el-button type="primary" size="small" @click="goToPaperTrading">
                查看模拟交易
              </el-button>
            </div>
          </div>
        </div>

        <!-- Row 4 右：今日市场概况（实时数据，盘中每 5 min 刷新） -->
        <div class="panel market-overview-panel ga-market">
          <div class="panel-hdr">
            <div class="sec-title">今日市场概况</div>
            <div class="panel-hdr-actions">
              <span v-if="marketOverviewLoading" class="market-loading-chip">加载中…</span>
              <span v-else-if="marketOverview && marketOverview.total > 0" class="market-fresh-chip">
                {{ marketOverview.total }} 只 · 5 min 刷新
              </span>
              <el-tooltip content="刷新全部行情（市场概况 + 自选股 + 模拟账户）" placement="top">
                <el-button
                  :icon="Refresh"
                  size="small"
                  circle
                  :loading="quotesRefreshing"
                  @click="handleRefreshQuotes"
                  class="refresh-quotes-btn"
                />
              </el-tooltip>
            </div>
          </div>
          <div class="market-grid">
            <div class="market-cell">
              <div class="market-cell-label">涨停家数</div>
              <div class="market-cell-val num up">
                {{ marketOverview?.limit_up ?? '—' }}
              </div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">跌停家数</div>
              <div class="market-cell-val num down">
                {{ marketOverview?.limit_down ?? '—' }}
              </div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">成交额</div>
              <div class="market-cell-val num">
                <template v-if="marketOverview?.amount_total != null">
                  {{ formatMoney(marketOverview.amount_total) }}<span class="market-cell-unit">亿</span>
                </template>
                <template v-else>—</template>
              </div>
            </div>
            <div class="market-cell">
              <div class="market-cell-label">上涨家数</div>
              <div class="market-cell-val num up">
                {{ marketOverview?.advance != null ? marketOverview.advance.toLocaleString() : '—' }}
              </div>
            </div>
          </div>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Search,
  Document,
  Files,
  List,
  ArrowRight,
  ArrowDown,
  Download,
  Refresh,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { AnalysisTask, AnalysisStatus } from '@/types/analysis'
import MultiSourceSyncCard from '@/components/Dashboard/MultiSourceSyncCard.vue'
import Sparkline from '@/components/Common/Sparkline.vue'
import NumberFlip from '@/components/Common/NumberFlip.vue'
import { favoritesApi } from '@/api/favorites'
import { analysisApi } from '@/api/analysis'
import { newsApi } from '@/api/news'
import { paperApi, type PaperAccountSummary, type PaperPositionItem } from '@/api/paper'
import { marketApi, type MarketOverview } from '@/api/market'
import { paperPerformanceApi, type PaperPerformance } from '@/api/paperPerformance'
import { portfolioMetricsApi, type PortfolioMetrics } from '@/api/portfolioMetrics'
import { useQuotesStore } from '@/stores/quotes'

const router = useRouter()
const authStore = useAuthStore()
const quotesStore = useQuotesStore()

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
const paperPositions = ref<PaperPositionItem[]>([])
const marketOverview = ref<MarketOverview | null>(null)
const marketOverviewLoading = ref(false)
const paperPerformance = ref<PaperPerformance | null>(null)
const portfolioMetrics = ref<PortfolioMetrics | null>(null)

// Beta tag chip 配色（按弹性等级）
const betaTagClass = (tag: string): string => {
  switch (tag) {
    case '高弹性':
      return 'tag-high'
    case '中高弹性':
      return 'tag-mid-high'
    case '中性':
      return 'tag-neutral'
    case '防御':
      return 'tag-defensive'
    default:
      return ''
  }
}

// Loading 状态（首次加载时显示 skeleton shimmer）
const watchlistLoading = ref(true)
const analysisLoading = ref(true)
const newsLoading = ref(true)

// 汇总状态指示灯（暂用静态 ok；真实状态通过展开后的 MultiSourceSyncCard 查看）
const syncOverall = ref<'ok' | 'warn' | 'err'>('ok')

// 基于 seed 的确定性 mock 趋势数组（sparkline 演示用，没有真实历史 API 时填充）
const mockTrend = (seed: number, length = 14, direction: 'up' | 'down' | 'flat' = 'flat') => {
  const arr: number[] = []
  let value = 50
  for (let i = 0; i < length; i++) {
    const noise = Math.sin(seed * 9301 + i * 49297) * 4
    const trend = direction === 'up' ? i * 1.4 : direction === 'down' ? -i * 1.2 : 0
    value += noise * 0.3 + trend * 0.4
    arr.push(value)
  }
  return arr
}

// 字符串 → 简单 hash 数字（用作 mockTrend seed）
const strSeed = (s: string) => {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h) % 1000
}

// Hero 4 个 stat 的 mock 趋势（固定，不随数据变）
const heroTrend = {
  total: mockTrend(11, 14, 'up'),
  success: mockTrend(22, 14, 'flat'),
  equity: mockTrend(33, 14, 'up'),
  fav: mockTrend(44, 14, 'flat'),
}

// Hero 区鼠标跟随光斑：用 rAF throttle 更新 CSS var（GPU 友好）
const heroEl = ref<HTMLElement | null>(null)
let heroRafId: number | null = null
let heroPendingX = 50
let heroPendingY = 50
const onHeroMouseMove = (e: MouseEvent) => {
  if (!heroEl.value) return
  const rect = heroEl.value.getBoundingClientRect()
  heroPendingX = ((e.clientX - rect.left) / rect.width) * 100
  heroPendingY = ((e.clientY - rect.top) / rect.height) * 100
  if (heroRafId !== null) return
  heroRafId = requestAnimationFrame(() => {
    if (heroEl.value) {
      heroEl.value.style.setProperty('--mx', heroPendingX + '%')
      heroEl.value.style.setProperty('--my', heroPendingY + '%')
    }
    heroRafId = null
  })
}

// 模拟账户固定走 A 股 / CNY；港股美股暂时不展示在 Dashboard 卡片
type AccountKey = 'CNY' | 'HKD' | 'USD'

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
  const equity = getCurrencyAmount(paperAccount.value.equity, 'CNY')
  const positions = getCurrencyAmount(paperAccount.value.positions_value, 'CNY')
  if (!equity) return 0
  return ((positions / equity) * 100).toFixed(1)
})

// 持仓数 + 累计盈亏 KPI
const positionCount = computed(() => paperPositions.value.length)

const positionPnlRate = (p: PaperPositionItem): number => {
  const pnl = p.unrealized_pnl ?? 0
  const cost = p.quantity * p.avg_cost
  if (!cost) return 0
  return (pnl / cost) * 100
}

// 今日浮动盈亏（区别于右侧 unrealized_pnl 累计盈亏）.
// 公式：从 ws 推送的 pct_chg(%) + last_price 反推今日相对昨收的金额变动.
//   prev_close = last_price / (1 + pct_chg/100)
//   today_pnl  = (last_price - prev_close) × qty
//             = market_value × pct_chg / (100 + pct_chg)
// 取自 ws push 的 pct_chg，盘外或缺数据时返回 null（UI 显示「—」）.
const positionTodayPnl = (p: PaperPositionItem): number | null => {
  const pctChg = (p as any)?.pct_chg
  const lastPrice = p.last_price
  const qty = Number(p.quantity ?? 0)
  if (pctChg == null || lastPrice == null || qty <= 0) return null
  const denominator = 100 + Number(pctChg)
  if (Math.abs(denominator) < 1e-9) return null
  return (Number(lastPrice) * qty * Number(pctChg)) / denominator
}

// =================================================================
// Tier 3 真实数据：从 GET /api/paper/performance 拉取（OpenSpec change
// `paper-account-snapshots` 已落地）。snapshot < 2 条时所有字段为 null，
// 前端显示「—」。
// =================================================================

// 把后端 sparkline_points (90 天 equity 等距 11 点) 转成 SVG polyline points
// 字符串。viewBox 130×50，留 4px 上下 padding 避免顶天/触底
const sparklineLinePoints = computed(() => {
  const pts = paperPerformance.value?.sparkline_points
  if (!pts || pts.length < 2) return ''
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  const w = 130
  const h = 50
  const padTop = 4
  const padBottom = 4
  const usableH = h - padTop - padBottom
  return pts
    .map((p, i) => {
      const x = (i / (pts.length - 1)) * w
      // 高 equity 在上 (y 小)，低在下 (y 大)
      const y = padTop + (1 - (p - min) / range) * usableH
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const sparklineFillPoints = computed(() => {
  const line = sparklineLinePoints.value
  if (!line) return ''
  // 闭合到底部形成填充区域
  return `${line} 130,50 0,50`
})

// 格式化 0.186 → "+18.60%" / -0.032 → "-3.20%"
const formatPctSigned = (v: number | null | undefined): string => {
  if (v == null) return '—'
  const pct = v * 100
  const sign = pct >= 0 ? '+' : '−'
  return `${sign}${Math.abs(pct).toFixed(2)}%`
}

const realizedPnl = computed(() => {
  if (!paperAccount.value) return 0
  return getCurrencyAmount(paperAccount.value.realized_pnl, 'CNY')
})

const unrealizedPnl = computed(() => {
  return paperPositions.value.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0)
})

const totalPnl = computed(() => realizedPnl.value + unrealizedPnl.value)

const pnlRate = computed(() => {
  if (!paperAccount.value) return '0.00'
  const equity = getCurrencyAmount(paperAccount.value.equity, 'CNY')
  const cost = equity - totalPnl.value
  if (!cost) return '0.00'
  return ((totalPnl.value / cost) * 100).toFixed(2)
})

// 路由跳转
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

// A 股代码 → 东方财富个股页 URL 映射
// - 6xx → 沪市 (sh)
// - 4/8/9xx → 北交所 (bj)
// - 其余 (0/1/2/3xx) → 深市 (sz)
const getEastMoneyStockUrl = (code: string): string => {
  const c = String(code).trim().padStart(6, '0')
  let prefix: string
  if (c.startsWith('6')) prefix = 'sh'
  else if (c.startsWith('4') || c.startsWith('8') || c.startsWith('9')) prefix = 'bj'
  else prefix = 'sz'
  return `https://quote.eastmoney.com/${prefix}${c}.html`
}

const viewStockDetail = (stock: any) => {
  const code = stock?.stock_code
  if (!code) return
  window.open(getEastMoneyStockUrl(code), '_blank', 'noopener,noreferrer')
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
  } finally {
    watchlistLoading.value = false
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
  } finally {
    analysisLoading.value = false
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
  } finally {
    newsLoading.value = false
  }
}

const loadPaperAccount = async () => {
  try {
    const response = await paperApi.getAccount()
    if (response.success && response.data) {
      paperAccount.value = response.data.account
      paperPositions.value = response.data.positions ?? []
    }
  } catch (error) {
    console.error('加载模拟交易账户失败:', error)
    paperAccount.value = null
    paperPositions.value = []
  }
}

const loadPaperPerformance = async () => {
  try {
    const response = await paperPerformanceApi.getPerformance()
    if (response.success && response.data) {
      paperPerformance.value = response.data
    }
  } catch (error) {
    console.error('加载 paper 性能指标失败:', error)
    // 失败时保留 null，前端各字段显示「—」
  }
}

const loadPortfolioMetrics = async () => {
  try {
    const response = await portfolioMetricsApi.get()
    if (response.success && response.data) {
      portfolioMetrics.value = response.data
    }
  } catch (error) {
    console.error('加载组合 Beta/VaR/估值指标失败:', error)
  }
}

const loadMarketOverview = async () => {
  marketOverviewLoading.value = true
  try {
    const response = await marketApi.getOverview()
    if (response.success && response.data) {
      marketOverview.value = response.data
    }
  } catch (error) {
    console.error('加载市场概况失败:', error)
  } finally {
    marketOverviewLoading.value = false
  }
}

// 每 5 分钟刷新市场概况 — 项目铁律（capability trading-calendar）：
// 自动刷新仅在 A 股交易日盘中执行。盘外（周末 / 节假日 / 工作日盘外时段）跳过。
// 数据保持上一次成功值，让用户看到最近一次盘中的快照。
let marketOverviewHandle: ReturnType<typeof setInterval> | null = null
const startMarketOverviewPolling = () => {
  marketOverviewHandle = setInterval(() => {
    if (document.hidden) return  // 视图隐藏时不刷新
    if (!marketOverview.value?.is_intraday) return  // 盘外不刷新
    loadMarketOverview()
  }, 5 * 60 * 1000)
}

// 手动刷新行情（清除后端缓存 → 重新拉取 → 刷新本地数据）
const quotesRefreshing = ref(false)
const handleRefreshQuotes = async () => {
  if (quotesRefreshing.value) return
  quotesRefreshing.value = true
  try {
    const response = await marketApi.refreshQuotes()
    if (response.success) {
      const stats = response.data
      ElMessage.success(`行情已刷新：共 ${stats?.updated ?? 0} 只股票更新`)
      // 刷新后重新加载所有行情相关区域
      await Promise.all([
        loadMarketOverview(),
        loadFavoriteStocks(),
        loadPaperAccount(),
        loadPaperPerformance(),
        loadPortfolioMetrics(),
      ])
      // 重新订阅 WebSocket 推送，让自选股/持仓实时价格立即更新
      refreshQuoteSubscriptions()
    }
  } catch (error) {
    ElMessage.error('行情刷新失败，请稍后重试')
    console.error('手动刷新行情失败:', error)
  } finally {
    quotesRefreshing.value = false
  }
}

// 删除原 mock priceTicker（每 4.5s 随机改一支股票 ±0.5%）：违反项目铁律
// 「自动刷新仅在 A 股交易日盘中」+ mock 数据让 UI 显示与真实 mongo 不一致，
// 用户在盘外仍看到数字跳动误以为后端在刷新。盘中真实数据走 5 min polling 即可。

// OpenSpec capability `realtime-trading-data-flow`：自选股 + paper 持仓的 last_price
// 通过 /ws/quotes 实时推送 (channel:quote:{code})；paper PnL 通过 channel:pnl:{user_id}
// 服务端聚合后推送（每 ≤ 3s diff > 0.01 才发，盘外不发）.
//
// quoteByCode reactive 由 quotesStore 维护；下面 watchEffect 把推送的 last_price
// merge 到既有 favoriteStocks / paperPositions 数组对应行，保持原渲染逻辑兼容.
const collectAllCodes = (): string[] => {
  const codes = new Set<string>()
  for (const s of favoriteStocks.value) {
    const c = String(s?.stock_code ?? s?.code ?? '').trim()
    if (c) codes.add(c)
  }
  for (const p of paperPositions.value) {
    const c = String(p?.code ?? '').trim()
    // PaperPositionItem 类型未声明 market 字段——如有则按 CN 过滤，否则一律订阅
    const market = (p as any)?.market
    if (c && (market === 'CN' || !market)) codes.add(c)
  }
  return Array.from(codes)
}

let lastSubscribedCodes: string[] = []
const refreshQuoteSubscriptions = () => {
  const next = collectAllCodes()
  const nextSet = new Set(next)
  const lastSet = new Set(lastSubscribedCodes)
  const toAdd = next.filter((c) => !lastSet.has(c))
  const toRemove = lastSubscribedCodes.filter((c) => !nextSet.has(c))
  if (toRemove.length > 0) quotesStore.unsubscribe(toRemove)
  if (toAdd.length > 0) quotesStore.subscribe(toAdd)
  lastSubscribedCodes = next
}

// quoteByCode push 到来时合并到 favoriteStocks / paperPositions 的 last_price 字段
watch(
  () => quotesStore.quoteByCode,
  (qmap) => {
    for (const fav of favoriteStocks.value) {
      const code = String(fav?.stock_code ?? fav?.code ?? '').trim()
      const q = qmap[code]
      if (q && q.close != null) {
        fav.current_price = q.close
        if (q.pct_chg != null) fav.pct_change = q.pct_chg
        fav.last_price_as_of = q.as_of_ts
      }
    }
    for (const pos of paperPositions.value) {
      const code = String(pos?.code ?? '').trim()
      const q = qmap[code]
      if (q && q.close != null) {
        pos.last_price = q.close
        // 重算 unrealized_pnl 让 UI 立即更新（avg_cost 是固定的，qty * (last - cost)）
        const qty = Number(pos.quantity ?? 0)
        const avg = Number(pos.avg_cost ?? 0)
        if (qty > 0) {
          pos.market_value = Number((q.close * qty).toFixed(2))
          pos.unrealized_pnl = Number(((q.close - avg) * qty).toFixed(2))
        }
        ;(pos as any).last_price_as_of = q.as_of_ts
        // 透传 pct_chg 让 UI 能算今日盈亏（market_value × pct_chg / (100 + pct_chg)）
        ;(pos as any).pct_chg = q.pct_chg
      }
    }
  },
  { deep: true }
)

// PnL 推送到来时覆盖 paper 总指标（避免前端用 stale price 算错）
watch(
  () => quotesStore.latestPnl,
  (pnl) => {
    if (!pnl || !paperAccount.value) return
    // 后端 PnL 已基于最新 last_price 聚合 — 把总指标覆盖到 paperAccount summary
    paperAccount.value.equity = paperAccount.value.equity || ({} as any)
    if (typeof paperAccount.value.equity === 'object') {
      ;(paperAccount.value.equity as any).CNY = pnl.total_equity
    }
    ;(paperAccount.value as any).realtime_unrealized_pnl = pnl.total_unrealized
    ;(paperAccount.value as any).realtime_as_of_ts = pnl.as_of_ts
  }
)

onMounted(async () => {
  // 鼠标跟随光斑监听
  heroEl.value?.addEventListener('mousemove', onHeroMouseMove)

  await loadFavoriteStocks()
  await loadRecentAnalyses()
  await loadMarketNews()
  await loadPaperAccount()
  await loadPaperPerformance()
  await loadPortfolioMetrics()
  await loadMarketOverview()

  // 启动市场概况 5 min polling（内部含 is_intraday guard，盘外跳过）
  startMarketOverviewPolling()

  // 启动 ws 实时行情订阅（自选股 + paper 持仓 codes）+ PnL 流
  quotesStore.connect()
  // 等 onopen 后 subscribe；这里直接发，store 在 connected 回调里也会 resub
  refreshQuoteSubscriptions()
  quotesStore.subscribePnl()
})

onUnmounted(() => {
  heroEl.value?.removeEventListener('mousemove', onHeroMouseMove)
  if (heroRafId !== null) cancelAnimationFrame(heroRafId)
  if (marketOverviewHandle !== null) clearInterval(marketOverviewHandle)
  // 断开 ws + 清空订阅
  quotesStore.disconnect()
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

  // 鼠标跟随光斑（::before），未触发时居中
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(
      circle 360px at var(--mx, 80%) var(--my, 30%),
      var(--hero-spotlight-color) 0%,
      transparent 60%
    );
    pointer-events: none;
    transition: background 0.2s ease-out;
    z-index: 0;
  }
  // 蓝色固定光晕（::after），下方装饰
  &::after {
    content: '';
    position: absolute;
    bottom: -80px;
    left: 30%;
    width: 400px;
    height: 200px;
    background: radial-gradient(circle, var(--blue-soft) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }
}

// K 线 SVG 装饰：极淡折线在 Hero 底层
.hero-decoration {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--accent);
  opacity: 0.06;
  pointer-events: none;
  z-index: 0;

  // 浅色下用蓝色装饰
  :where(html.light) & {
    color: var(--blue);
    opacity: 0.04;
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
  position: relative;
  display: inline-block;

  // accent 词用渐变填充（金属字效，深浅两套渐变在 token）
  .accent {
    background: var(--gradient-title);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    position: relative;
    display: inline-block;

    // 标题下渐变 underline + 慢速呼吸（仅深色）
    &::after {
      content: '';
      position: absolute;
      left: 0;
      right: 30%;
      bottom: -2px;
      height: 1px;
      background: linear-gradient(90deg, var(--accent) 0%, transparent 100%);
      opacity: 0.5;
      animation: hero-underline-pulse 3.5s ease-in-out infinite;
    }
  }
}

@keyframes hero-underline-pulse {
  0%, 100% { opacity: 0.35; transform: scaleX(0.8); transform-origin: left; }
  50%      { opacity: 0.8;  transform: scaleX(1);   transform-origin: left; }
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
  font-size: 22px;
  font-weight: 600;
  color: var(--fg-primary);
  line-height: 1.15;
  letter-spacing: -0.01em;
  position: relative;
  display: inline-block;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
  &.accent { color: var(--accent); }

  // 数字 shimmer：每 9s 一次高光从左扫到右（深浅双主题，高光色由 token 切换）
  background: linear-gradient(
    90deg,
    currentColor 0%,
    currentColor 40%,
    var(--shimmer-highlight) 50%,
    currentColor 60%,
    currentColor 100%
  );
  background-size: 250% 100%;
  background-position: 100% 0;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: stat-shimmer 9s ease-in-out infinite;
}

@keyframes stat-shimmer {
  0%, 70%, 100% { background-position: 100% 0; }
  85%           { background-position: 0% 0; }
}

// 4 个 stat 错开 shimmer 时间，避免同时闪
.hero-stat:nth-child(2) .hero-stat-val { animation-delay: 2s; }
.hero-stat:nth-child(3) .hero-stat-val { animation-delay: 4s; }
.hero-stat:nth-child(4) .hero-stat-val { animation-delay: 6s; }

.hero-stat-sub {
  font-size: 10px;
  color: var(--fg-muted);
  margin-top: 1px;
}

// Hero stat sparkline 居中放在 val 和 sub 之间
.hero-stat-spark {
  display: block;
  margin: 2px auto 1px;
  opacity: 0.85;
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
.ga-account     { grid-column: 1; grid-row: 3; }
.ga-watchlist   { grid-column: 2; grid-row: 3; }
.ga-news        { grid-column: 1; grid-row: 4; }
.ga-analysis    { grid-column: 2; grid-row: 4; }

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
  transition: border-color 0.25s, box-shadow 0.25s;
  position: relative;

  // border 垂直渐变（深浅双主题，色调由 token 切换）
  border-image: var(--panel-border-grad) 1;
  border-style: solid;
  border-width: 1px;

  // 顶部 1px 渐变高光（macOS 玻璃质感，深色更明显）
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 8%;
    right: 8%;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      var(--accent-border) 30%,
      var(--accent) 50%,
      var(--accent-border) 70%,
      transparent 100%
    );
    opacity: 0.5;
    pointer-events: none;
  }

  // hover：4 边 accent glow ring（深浅双主题）
  &:hover {
    border-color: var(--accent-border);
    box-shadow:
      0 0 0 1px var(--accent-border),
      0 0 20px -4px var(--accent-glow);

    &::before { opacity: 1; }
  }
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
// watchlist 在 grid row 3 跟 ga-account 同行，被 stretch 到 ga-account 高度
// 所以让 panel 用 flex column + list flex:1 撑满，避免底部空白 + 最后一行被截断
.watchlist-panel {
  display: flex;
  flex-direction: column;
}
.watchlist-list.scroll-body {
  flex: 1;
  min-height: 0;
  max-height: none;
}
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
  transition: all 0.25s;
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

    // icon 旋转 + scale（深浅双主题）
    .action-icon {
      transform: rotate(-6deg) scale(1.08);
    }
  }

  // hover 外发光环（深浅双主题）
  &:hover {
    border-color: var(--accent-border);
    box-shadow:
      0 0 0 1px var(--accent-border),
      0 0 24px -6px var(--accent-glow);
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
  transition: transform 0.25s ease-out;

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

// Skeleton 加载态外壳
.skeleton-wrap {
  padding: 12px 14px;

  .skeleton-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    &:last-child { margin-bottom: 0; }
  }
}

.empty-block {
  padding: 32px 16px;
  text-align: center;

  // 替代 el-empty 默认插画：用 dashboard 风格的迷你 K 线 SVG
  :deep(.el-empty__image) {
    width: 80px !important;
    height: 40px !important;
    background: none !important;

    img, svg { display: none; }

    // 替换为 ::before 伪元素绘制 K 线 SVG (data URI)
    position: relative;
    &::before {
      content: '';
      position: absolute;
      inset: 0;
      background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 40' fill='none' stroke='%23d4a843' stroke-width='1' stroke-linecap='round' stroke-linejoin='round' opacity='0.5'><polyline points='0,28 8,24 16,30 24,18 32,22 40,12 48,16 56,8 64,14 72,6 80,10'/><circle cx='80' cy='10' r='1.5' fill='%23d4a843'/></svg>") no-repeat center / contain;
    }
  }
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
  gap: 10px;
  padding: 6px 14px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--bg-hover); }
}

.watchlist-spark {
  flex-shrink: 0;
  opacity: 0.8;
  margin: 0 4px;
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
.account-panel {
  .sec-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
}

.position-chip {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--fg-secondary);
  background: var(--border-default);
  padding: 2px 6px;
  border-radius: 8px;
  line-height: 1;
}

.account-body {
  padding: 10px 14px 8px;
  display: flex;
  flex-direction: column;
}

// Hero 全宽：左侧大数字 + 右侧资产曲线 sparkline
.account-hero {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-default);

  &.hero-full {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 14px;
  }
}

.hero-info { flex: 1; min-width: 0; }

.hero-spark {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  flex-shrink: 0;
}

.spark-svg {
  width: 96px;
  height: 30px;
  display: block;
}

.spark-meta {
  font-size: 11px;
  display: flex;
  gap: 6px;
  align-items: baseline;

  .dim { color: var(--fg-muted); }
  .up { color: var(--up); font-weight: 600; }
}

// preview-chip：标识 mock 数据来源（待 paper-account-snapshots 接入）
.preview-chip {
  background: rgba(212, 168, 67, 0.18) !important;
  color: var(--accent) !important;
  font-weight: 600;
}

.hero-label {
  font-size: 10px;
  color: var(--fg-muted);
  margin-bottom: 1px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.hero-val {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.025em;
  display: block;
  // 强制金色（覆盖 .num 的 shimmer + background-clip:text 干扰）
  color: var(--accent) !important;
  background: none !important;
  -webkit-background-clip: unset !important;
  background-clip: unset !important;
  -webkit-text-fill-color: var(--accent) !important;
}

.hero-pnl {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: baseline;
  gap: 6px;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

.pnl-amount {
  font-weight: 700;
}

.pnl-rate {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.85;
}

// 资金 KPI 网格 — 默认 6 列横铺；中等宽度 3 列；移动端 2 列
.account-kpis {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 18px;
  margin-bottom: 8px;

  &.kpis-6col {
    grid-template-columns: repeat(6, 1fr);
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-default);

    @media (max-width: 1100px) {
      grid-template-columns: repeat(3, 1fr);
    }

    @media (max-width: 600px) {
      grid-template-columns: repeat(2, 1fr);
    }
  }
}

.kpi-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.kpi-label {
  font-size: 10px;
  color: var(--fg-muted);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.kpi-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-primary);
  letter-spacing: -0.01em;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
  &.strong { font-weight: 700; }
}

// 月度收益柱图 全宽
.month-bars {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-default);
}

.month-bars-label {
  font-size: 10px;
  color: var(--fg-muted);
  margin-bottom: 2px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.month-bars-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 5px;
}

.month-bar-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.month-bar-track {
  position: relative;
  width: 100%;
  height: 24px;
}

.month-bar-axis {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: var(--border-default);
}

.month-bar-fill {
  position: absolute;
  left: 25%;
  width: 50%;
  border-radius: 2px;

  &.up { background: var(--up); }
  &.down { background: var(--down); }
}

.month-bar-label {
  font-size: 10px;
  color: var(--fg-muted);
}

// 底部两列：左 [progress + 风险 + Tier 4 KPI + button] / 右 [持仓 list]
// 用 stretch + flex 让两列等高（左列 button 推到底，持仓 list 撑满）
.account-footer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 18px;
  align-items: stretch;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.footer-left {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.footer-right {
  min-width: 0;
  border-left: 1px solid var(--border-default);
  padding-left: 18px;
  display: flex;
  flex-direction: column;

  @media (max-width: 900px) {
    border-left: none;
    padding-left: 0;
    padding-top: 14px;
    border-top: 1px solid var(--border-default);
  }
}

// Tier 4 — 风险/估值 KPI 2×2 网格
.tier4-kpis {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-default);
  flex: 1;  // 撑开剩余空间，把持仓比例 progress 推到底（与右列持仓 list 对齐）
}

// 持仓比例 progress 移到 footer-left 底部
.account-progress-bottom {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-default);
}

.kpi-tag {
  font-size: 9.5px;
  font-weight: 500;
  color: var(--fg-muted);
  background: var(--border-default);
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 4px;
  vertical-align: middle;
  letter-spacing: 0;
  text-transform: none;

  // Beta 弹性 tag 配色
  &.tag-high {
    color: var(--down);  // 红 = 高风险
    background: rgba(244, 67, 54, 0.12);
  }
  &.tag-mid-high {
    color: var(--accent);  // 金 = 中高（项目主题色）
    background: rgba(212, 168, 67, 0.14);
  }
  &.tag-neutral {
    color: #2196f3;
    background: rgba(33, 150, 243, 0.14);
  }
  &.tag-defensive {
    color: var(--up);  // 绿 = 防御
    background: rgba(76, 175, 80, 0.12);
  }
}

.risk-stats {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  padding: 5px 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}

.risk-stat {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.risk-label {
  font-size: 10px;
  color: var(--fg-muted);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.risk-val {
  font-size: 12.5px;
  font-weight: 600;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

// 持仓明细 list — flex 撑满 footer-right 高度
.positions-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.positions-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;

  .muted-small {
    font-size: 11px;
    color: var(--fg-muted);
    text-transform: none;
    letter-spacing: 0;
  }
}

.positions-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 2px;
    &:hover { background: var(--fg-muted); }
  }
}

.position-item {
  padding: 5px 0;
  border-bottom: 1px solid var(--border-default);

  &:first-child { padding-top: 0; }
  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
}

.pos-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.pos-row-main {
  margin-bottom: 1px;
}

.pos-code {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fg-primary);
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.pos-name {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--fg-secondary);
  letter-spacing: normal;
}

.pos-pnl {
  font-size: 12.5px;
  font-weight: 600;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

/* 今日浮动盈亏（main row 中间，区别于右侧累计盈亏） */
.pos-today-pnl {
  flex: 1;
  text-align: center;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.02em;

  &.up { color: var(--up); }
  &.down { color: var(--down); }

  &.muted-small {
    color: var(--fg-muted);
    font-size: 10.5px;
    font-weight: 400;
  }
}

.pos-row-meta {
  font-size: 10.5px;
  color: var(--fg-muted);
}

.pos-meta {
  font-variant-numeric: tabular-nums;
}

.pos-arrow {
  margin: 0 3px;
  opacity: 0.6;
}

.pos-pnl-rate {
  font-variant-numeric: tabular-nums;
  font-weight: 500;

  &.up { color: var(--up); opacity: 0.85; }
  &.down { color: var(--down); opacity: 0.85; }
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

.panel-hdr-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.refresh-quotes-btn {
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--border-subtle);
  --el-button-hover-bg-color: var(--bg-elevated);
  --el-button-hover-border-color: var(--accent);
  --el-button-hover-text-color: var(--accent);
  width: 24px;
  height: 24px;
  font-size: 12px;
}

.market-loading-chip,
.market-fresh-chip {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--fg-muted);
  letter-spacing: 0.02em;
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.market-fresh-chip {
  color: var(--accent);
  border-color: var(--accent-border);
}

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
