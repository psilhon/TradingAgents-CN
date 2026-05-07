import { ApiClient } from './request'

export interface BetaMetric {
  value: number
  tag: '高弹性' | '中高弹性' | '中性' | '防御'
}

export interface VarMetric {
  amount: number  // 元，负数
  pct: number  // 小数，负数
}

export interface PortfolioMetrics {
  beta: BetaMetric | null
  var: VarMetric | null
  weighted_pe: number | null
  weighted_pb: number | null
}

export const portfolioMetricsApi = {
  async get() {
    return ApiClient.get<PortfolioMetrics>('/api/paper/portfolio_metrics')
  },
}
