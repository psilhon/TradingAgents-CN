import { ApiClient } from './request'

export interface MonthlyReturn {
  month: string  // "2026-04"
  return_pct: number  // 4.8
}

export interface PaperPerformance {
  twrr: number | null  // 小数 (0.186 = 18.6%)
  sharpe: number | null
  current_drawdown: number | null  // 负数小数
  max_drawdown: number | null
  monthly_returns: MonthlyReturn[]
  sparkline_points: number[]  // 90 天 equity 等距 11 点
}

export const paperPerformanceApi = {
  async getPerformance() {
    return ApiClient.get<PaperPerformance>('/api/paper/performance')
  },
}
