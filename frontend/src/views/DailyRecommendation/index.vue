<template>
  <div class="daily-recommendation">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Sunrise /></el-icon>
        每日推荐
      </h1>
      <p class="page-description">
        每个交易日收盘后自动筛选并分析的推荐股票，每日 16:30 生成
      </p>
    </div>

    <!-- 操作栏 -->
    <el-card class="action-card" shadow="never">
      <div class="action-bar">
        <span class="action-hint">手动触发当日推荐（后台运行，约 30-50 分钟）</span>
        <div class="action-buttons">
          <el-button :loading="running" @click="triggerRun">
            <el-icon><VideoPlay /></el-icon>
            立即生成
          </el-button>
          <el-button @click="loadList">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="24">
      <!-- 左侧：日期列表 -->
      <el-col :span="6">
        <el-card class="date-list-card" shadow="never" v-loading="listLoading">
          <template #header>
            <span>推荐日期</span>
          </template>
          <el-empty v-if="!listLoading && dateList.length === 0" description="暂无推荐记录" :image-size="80" />
          <ul v-else class="date-list">
            <li
              v-for="item in dateList"
              :key="item.date"
              class="date-item"
              :class="{ active: item.date === selectedDate }"
              @click="selectDate(item.date)"
            >
              <span class="date-text">{{ item.date }}</span>
              <span class="date-meta">
                <el-tag :type="statusTagType(item.status)" size="small" effect="plain">
                  {{ statusText(item.status) }}
                </el-tag>
                <span class="stock-count">{{ item.stock_count }} 只</span>
              </span>
            </li>
          </ul>
        </el-card>
      </el-col>

      <!-- 右侧：当日推荐股票卡片 -->
      <el-col :span="18">
        <el-card class="detail-card" shadow="never" v-loading="detailLoading">
          <template #header>
            <div class="detail-header">
              <span>{{ selectedDate ? `${selectedDate} 推荐股票` : '股票详情' }}</span>
              <el-tag
                v-if="detail"
                :type="statusTagType(detail.status)"
                size="small"
              >
                {{ statusText(detail.status) }}
              </el-tag>
            </div>
          </template>

          <el-empty
            v-if="!detailLoading && !detail"
            description="请从左侧选择一个日期查看推荐股票"
          />
          <el-empty
            v-else-if="!detailLoading && detail && detail.stocks.length === 0"
            description="该日期暂无推荐股票"
          />
          <el-row v-else-if="detail" :gutter="16">
            <el-col
              v-for="stock in detail.stocks"
              :key="stock.symbol"
              :xs="24"
              :sm="12"
              :lg="8"
            >
              <el-card class="stock-card" shadow="hover">
                <div class="stock-card-header">
                  <div class="stock-name">
                    <span class="symbol">{{ stock.symbol }}</span>
                    <span class="name">{{ stock.name }}</span>
                  </div>
                  <el-tag :type="statusTagType(stock.status)" size="small" effect="plain">
                    {{ statusText(stock.status) }}
                  </el-tag>
                </div>

                <div class="stock-card-body">
                  <div class="field">
                    <span class="label">分析结论</span>
                    <span class="value">{{ stock.recommendation || '—' }}</span>
                  </div>
                  <div class="field">
                    <span class="label">风险等级</span>
                    <el-tag
                      v-if="stock.risk_level"
                      :type="riskTagType(stock.risk_level)"
                      size="small"
                    >
                      {{ stock.risk_level }}
                    </el-tag>
                    <span v-else class="value">—</span>
                  </div>
                  <div v-if="stock.summary" class="field summary">
                    <span class="label">摘要</span>
                    <span class="value summary-text">{{ stock.summary }}</span>
                  </div>
                </div>

                <div class="stock-card-footer">
                  <el-link type="primary" @click="goToStock(stock.symbol)">
                    查看股票详情
                  </el-link>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Sunrise, VideoPlay, Refresh } from '@element-plus/icons-vue'
import {
  dailyRecommendationApi,
  type DailyRecommendationSummary,
  type DailyRecommendationDetail,
} from '@/api/dailyRecommendation'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const router = useRouter()

const dateList = ref<DailyRecommendationSummary[]>([])
const selectedDate = ref<string>('')
const detail = ref<DailyRecommendationDetail | null>(null)
const listLoading = ref(false)
const detailLoading = ref(false)
const running = ref(false)

// 状态 -> 标签颜色
const statusTagType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    completed: 'success',
    running: 'warning',
    pending: 'info',
    partial: 'warning',
    failed: 'danger',
  }
  return map[status] || 'info'
}

// 状态 -> 中文文案
const statusText = (status: string): string => {
  const map: Record<string, string> = {
    completed: '已完成',
    running: '生成中',
    pending: '待分析',
    partial: '部分完成',
    failed: '失败',
  }
  return map[status] || status
}

// 风险等级 -> 标签颜色
const riskTagType = (risk: string): TagType => {
  if (/高/.test(risk)) return 'danger'
  if (/中/.test(risk)) return 'warning'
  if (/低/.test(risk)) return 'success'
  return 'info'
}

// 加载推荐日期列表
const loadList = async () => {
  listLoading.value = true
  try {
    const res = await dailyRecommendationApi.list(100, 0)
    dateList.value = res.data || []
    // 默认选中最近一个日期
    if (dateList.value.length > 0) {
      const exists = dateList.value.some((d) => d.date === selectedDate.value)
      if (!exists) {
        selectDate(dateList.value[0].date)
      }
    } else {
      selectedDate.value = ''
      detail.value = null
    }
  } catch (error) {
    console.error('获取每日推荐列表失败:', error)
  } finally {
    listLoading.value = false
  }
}

// 选择日期并加载详情
const selectDate = async (date: string) => {
  selectedDate.value = date
  detailLoading.value = true
  detail.value = null
  try {
    const res = await dailyRecommendationApi.detail(date)
    detail.value = res.data || null
  } catch (error) {
    // 404 等错误已由响应拦截器统一提示
    console.error('获取每日推荐详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

// 跳转到股票详情页
const goToStock = (symbol: string) => {
  router.push(`/stocks/${symbol}`)
}

// 手动触发当日推荐
const triggerRun = async () => {
  running.value = true
  try {
    const res = await dailyRecommendationApi.run()
    if (res.success) {
      ElMessage.info('已在后台生成，约 30-50 分钟')
    } else {
      ElMessage.warning(res.message || '今日推荐已生成，请勿重复触发')
    }
  } catch (error) {
    console.error('触发每日推荐失败:', error)
    ElMessage.error('触发每日推荐失败，请稍后重试')
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadList()
})
</script>

<style lang="scss" scoped>
.daily-recommendation {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .action-card {
    margin-bottom: 24px;

    .action-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .action-hint {
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }

    .action-buttons {
      display: flex;
      gap: 8px;
    }
  }

  .date-list-card {
    .date-list {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .date-item {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: background-color 0.2s;

      &:hover {
        background-color: var(--el-fill-color-light);
      }

      &.active {
        background-color: var(--el-color-primary-light-9);

        .date-text {
          color: var(--el-color-primary);
          font-weight: 600;
        }
      }

      .date-text {
        font-size: 14px;
        color: var(--el-text-color-primary);
      }

      .date-meta {
        display: flex;
        align-items: center;
        gap: 8px;

        .stock-count {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
        }
      }
    }
  }

  .detail-card {
    min-height: 320px;

    .detail-header {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .stock-card {
    margin-bottom: 16px;

    .stock-card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 12px;

      .stock-name {
        display: flex;
        flex-direction: column;
        gap: 2px;

        .symbol {
          font-size: 15px;
          font-weight: 600;
          color: var(--el-text-color-primary);
        }

        .name {
          font-size: 13px;
          color: var(--el-text-color-regular);
        }
      }
    }

    .stock-card-body {
      .field {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin-bottom: 8px;

        .label {
          flex-shrink: 0;
          width: 56px;
          font-size: 12px;
          color: var(--el-text-color-placeholder);
        }

        .value {
          font-size: 13px;
          color: var(--el-text-color-primary);
        }

        &.summary {
          align-items: flex-start;
        }

        .summary-text {
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
          color: var(--el-text-color-regular);
        }
      }
    }

    .stock-card-footer {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--el-border-color-lighter);
    }
  }
}
</style>
