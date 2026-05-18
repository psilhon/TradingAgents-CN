/**
 * 每日推荐 API
 *
 * 对应后端路由 /api/daily-recommendations：多个命名配置的 CRUD、手动按配置
 * 触发推荐，以及推荐结果列表 / 详情。结果按 (日期, 配置) 唯一。
 */

import { ApiClient } from './request'

// 每日推荐列表项（摘要字段）
export interface DailyRecommendationSummary {
  date: string
  status: string
  stock_count: number
  config_id: string | null
  config_name: string | null
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

// 指定日期 + 配置的每日推荐完整文档
export interface DailyRecommendationDetail {
  date: string
  status: string
  config_id?: string
  config_name?: string
  config_snapshot?: Record<string, unknown>
  stocks: DailyRecommendationStock[]
  created_at?: string
  completed_at?: string
}

// 单条筛选条件（对应后端 ScreeningCondition）
export interface ScreeningConditionItem {
  field: string
  operator: string
  value: number | string | Array<number | string>
}

// 每日推荐配置（对应 config/daily_recommendations/<id>.json）
export interface DailyRecommendationConfig {
  id?: string // 服务端管理；新建时不传
  name: string
  screening: {
    conditions: ScreeningConditionItem[]
    order_by: string
    order_direction: 'asc' | 'desc'
    limit: number
  }
  analysis: {
    research_depth: string
    market_type: string
  }
}

// 历史结果中出现过的配置（含已删除配置）
export interface ResultConfigItem {
  config_id: string
  config_name: string | null
}

export const dailyRecommendationApi = {
  /**
   * 获取推荐结果列表（按日期倒序）
   * @param configId 按配置过滤；缺省返回全部
   */
  list: (configId?: string, limit = 100, offset = 0) =>
    ApiClient.get<DailyRecommendationSummary[]>('/api/daily-recommendations', {
      config_id: configId,
      limit,
      offset,
    }),

  /**
   * 获取指定日期 + 配置的每日推荐完整文档
   * @param date 日期（YYYY-MM-DD）
   * @param configId 配置 id
   */
  detail: (date: string, configId: string) =>
    ApiClient.get<DailyRecommendationDetail>(`/api/daily-recommendations/${date}`, {
      config_id: configId,
    }),

  /**
   * 手动触发指定配置的当日推荐任务（后台异步执行）
   *
   * 注意：该配置当日推荐已存在时后端返回 success=false + 提示 message。
   * 传 skipErrorHandler 跳过响应拦截器的统一错误处理，让调用方
   * 自行处理 success / 非 success 两种分支。
   */
  run: (configId: string) =>
    ApiClient.post<{ date: string; config_id: string } | null>(
      '/api/daily-recommendations/run',
      { config_id: configId },
      { skipErrorHandler: true },
    ),

  /** 列出所有每日推荐配置 */
  listConfigs: () =>
    ApiClient.get<DailyRecommendationConfig[]>('/api/daily-recommendations/configs'),

  /** 读取单个配置 */
  getConfig: (id: string) =>
    ApiClient.get<DailyRecommendationConfig>(`/api/daily-recommendations/configs/${id}`),

  /** 新建配置（后端生成 id；校验失败返回 400 + 错误信息） */
  createConfig: (config: DailyRecommendationConfig) =>
    ApiClient.post<DailyRecommendationConfig>('/api/daily-recommendations/configs', config),

  /** 更新配置（校验失败 400，配置不存在 404） */
  updateConfig: (id: string, config: DailyRecommendationConfig) =>
    ApiClient.put<DailyRecommendationConfig>(
      `/api/daily-recommendations/configs/${id}`,
      config,
    ),

  /** 删除配置（历史推荐结果不受影响） */
  deleteConfig: (id: string) =>
    ApiClient.delete(`/api/daily-recommendations/configs/${id}`),

  /** 列出历史结果中出现过的配置（含已删除配置，用于补齐选择器） */
  resultConfigs: () =>
    ApiClient.get<ResultConfigItem[]>('/api/daily-recommendations/result-configs'),
}
