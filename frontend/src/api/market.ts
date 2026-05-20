import { ApiClient } from './request'

export interface MarketOverview {
  limit_up: number | null
  limit_down: number | null
  advance: number | null
  decline: number | null
  amount_total: number | null  // 单位：亿元
  total: number  // 全市场样本数
  is_intraday: boolean  // 当前是否 A 股交易日盘中（前端 polling guard）
}

export interface RefreshQuotesResult {
  total: number
  fetched: number
  updated: number
  errors: number
}

/** 指数行情快照单条（capability market-indices-ticker）。 */
export interface IndexSnapshot {
  code: string                    // 内部稳定 key：sh000001 / sz399001 / sz399006 / HSI
  label: string                   // 中文短名：上证 / 深证 / 创业板 / 恒指
  kind: 'a_index' | 'hk_index'    // 解析格式标记 — 前端目前只用来灰化港股盘外
  value: number | null            // 当前点位
  change: number | null           // 涨跌点数（绝对值）
  pct_chg: number | null          // 涨跌幅 %
  as_of: string | null            // mongo updated_at ISO8601；非今日 → 灰化
}

export const marketApi = {
  async getOverview() {
    return ApiClient.get<MarketOverview>('/api/market/overview')
  },

  /** 4 个指数当前快照（A 股 3 + 港股 1）。后端 scheduler 每 5s 刷新 market_indices。 */
  async getIndicesSnapshot() {
    return ApiClient.get<IndexSnapshot[]>('/api/market/indices/snapshot')
  },

  /** 手动刷新行情：清除后端缓存 → 立即同步自选股+持仓行情 → 返回同步统计 */
  async refreshQuotes() {
    return ApiClient.post<RefreshQuotesResult>('/api/market/refresh-quotes')
  },
}
