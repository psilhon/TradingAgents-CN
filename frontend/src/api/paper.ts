import { ApiClient } from './request'

export interface CurrencyAmount {
  CNY: number
  HKD: number
  USD: number
}

export interface PaperAccountSummary {
  cash: CurrencyAmount | number  // 支持新旧格式
  realized_pnl: CurrencyAmount | number  // 支持新旧格式
  positions_value: CurrencyAmount
  equity: CurrencyAmount | number  // 支持新旧格式
  updated_at?: string
}

export interface PaperPositionItem {
  code: string
  name?: string
  quantity: number
  avg_cost: number
  last_price?: number | null
  market_value?: number
  unrealized_pnl?: number | null
}

export interface PaperOrderItem {
  user_id?: string
  code: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  amount: number
  status: 'filled' | 'rejected' | string
  created_at: string
  filled_at?: string
}

export interface GetAccountResponse {
  account: PaperAccountSummary
  positions: PaperPositionItem[]
}

export interface PlaceOrderPayload {
  code: string
  side: 'buy' | 'sell'
  quantity: number
  analysis_id?: string
}

export interface ImportPositionPayload {
  code: string
  market?: 'CN' | 'HK' | 'US'
  name?: string
  quantity: number
  avg_cost: number
  available_qty?: number
}

export interface ImportAccountPayload {
  mode: 'merge' | 'replace'
  cash?: Partial<CurrencyAmount>
  positions: ImportPositionPayload[]
}

export const paperApi = {
  async getAccount() {
    return ApiClient.get<GetAccountResponse>('/api/paper/account')
  },
  async placeOrder(data: PlaceOrderPayload) {
    return ApiClient.post<{ order: PaperOrderItem }>('/api/paper/order', data, { showLoading: true })
  },
  async getPositions() {
    return ApiClient.get<{ items: PaperPositionItem[] }>('/api/paper/positions')
  },
  async getOrders(limit = 50) {
    return ApiClient.get<{ items: PaperOrderItem[] }>(`/api/paper/orders`, { limit })
  },
  async importAccount(data: ImportAccountPayload) {
    return ApiClient.post<{
      message: string
      mode: string
      imported_positions: number
      updated_cash: string[]
    }>('/api/paper/import', data, { showLoading: true })
  },
  async resetAccount() {
    // 后端要求 confirm=true
    return ApiClient.post<{ message: string; cash: number }>(`/api/paper/reset?confirm=true`)
  }
}
