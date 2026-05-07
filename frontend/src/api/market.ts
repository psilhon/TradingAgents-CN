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

export const marketApi = {
  async getOverview() {
    return ApiClient.get<MarketOverview>('/api/market/overview')
  },
}
