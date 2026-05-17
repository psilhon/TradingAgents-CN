/**
 * 每日推荐API
 *
 * 对应后端路由 /api/daily-recommendations：收盘后定时任务生成的
 * 推荐结果列表 / 详情，以及手动触发当日推荐。
 */

import { ApiClient } from './request'

// 每日推荐列表项（摘要字段）
export interface DailyRecommendationSummary {
  date: string
  status: string
  stock_count: number
}

// 推荐文档里单只股票的结构（见 daily_recommendation_service._persist_final）
export interface DailyRecommendationStock {
  symbol: string
  name: string
  task_id: string | null
  recommendation: string | null
  summary: string | null
  risk_level: string | null
  status: string
}

// 指定日期的每日推荐完整文档
export interface DailyRecommendationDetail {
  date: string
  status: string
  config_snapshot?: Record<string, any>
  stocks: DailyRecommendationStock[]
  created_at?: string
  completed_at?: string
}

export const dailyRecommendationApi = {
  /**
   * 获取每日推荐列表（按日期倒序）
   * @param limit 返回数量限制（后端上限 100）
   * @param offset 偏移量
   */
  list: (limit = 100, offset = 0) =>
    ApiClient.get<DailyRecommendationSummary[]>('/api/daily-recommendations', { limit, offset }),

  /**
   * 获取指定日期的每日推荐完整文档
   * @param date 日期（YYYY-MM-DD）
   */
  detail: (date: string) =>
    ApiClient.get<DailyRecommendationDetail>(`/api/daily-recommendations/${date}`),

  /**
   * 手动触发当日每日推荐任务（后台异步执行）
   *
   * 注意：当日推荐已存在时后端返回 success=false + 提示 message。
   * 传 skipErrorHandler 跳过响应拦截器的统一错误处理，让调用方
   * 自行处理 success / 非 success 两种分支。
   */
  run: () =>
    ApiClient.post<{ date: string } | null>('/api/daily-recommendations/run', {}, {
      skipErrorHandler: true,
    }),
}
