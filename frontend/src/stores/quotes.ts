/**
 * Quotes WebSocket store — 订阅 /ws/quotes 实时行情 + PnL 推送.
 *
 * OpenSpec capability `realtime-trading-data-flow` Requirement
 * "WebSocket /ws/quotes MUST 提供按 code 订阅的实时推送" 前端落地.
 *
 * 协议（server: app/routers/websocket_quotes.py）：
 *   client → server:
 *     {"type": "subscribe", "codes": ["000001", ...]}
 *     {"type": "subscribe_pnl"}                        // user_id 强制取自 token
 *     {"type": "unsubscribe", "codes": [...]}
 *     {"type": "ping"}
 *   server → client:
 *     {"type": "connected"|"subscribed"|"subscribed_pnl"|"unsubscribed"}
 *     {"type": "quote", "data": {code, close, pct_chg, amount, as_of_ts}}
 *     {"type": "pnl",   "data": {user_id, positions, total_unrealized, total_equity, as_of_ts, ...}}
 *     {"type": "heartbeat"|"pong"|"error"}
 *
 * 复用 notifications.ts 的 reconnect / heartbeat 模式（auth token 取自 authStore + localStorage fallback）.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

export interface QuoteData {
  code: string
  close: number | null
  pct_chg: number | null
  amount: number | null
  as_of_ts: string | null
}

export interface PnLPositionData {
  code: string
  quantity: number
  avg_cost: number
  last_price: number | null
  last_price_as_of: string | null
  market_value: number
  unrealized_pnl: number
}

export interface PnLData {
  user_id: string
  positions: PnLPositionData[]
  total_unrealized: number
  total_realized: number
  total_equity: number
  as_of_ts: string | null
}

export const useQuotesStore = defineStore('quotes', () => {
  // 行情 reactive map：code → 最近一次推送的 quote
  const quoteByCode = ref<Record<string, QuoteData>>({})
  // 实时 PnL（subscribe_pnl 后由后端 push）
  const latestPnl = ref<PnLData | null>(null)

  // WebSocket 连接状态
  const ws = ref<WebSocket | null>(null)
  const wsConnected = ref(false)
  let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
  let wsReconnectAttempts = 0
  const maxReconnectAttempts = 10

  // 已订阅 codes（重连后自动重新 subscribe）
  const subscribedCodes = ref<Set<string>>(new Set())
  const pnlSubscribed = ref(false)

  const connected = computed(() => wsConnected.value)

  function connect(): void {
    try {
      if (ws.value) {
        try {
          ws.value.close()
        } catch {
          // noop
        }
        ws.value = null
      }
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer)
        wsReconnectTimer = null
      }

      const authStore = useAuthStore()
      const token = authStore.token || localStorage.getItem('auth-token') || ''
      if (!token) {
        console.warn('[WS-Quotes] 未找到 token，无法连接')
        return
      }

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${wsProtocol}//${host}/api/ws/quotes?token=${encodeURIComponent(token)}`

      console.log('[WS-Quotes] 连接到:', wsUrl)
      const socket = new WebSocket(wsUrl)
      ws.value = socket

      socket.onopen = () => {
        console.log('[WS-Quotes] 连接成功')
        wsConnected.value = true
        wsReconnectAttempts = 0

        // 重连后自动恢复订阅
        if (subscribedCodes.value.size > 0) {
          sendMessage({ type: 'subscribe', codes: Array.from(subscribedCodes.value) })
        }
        if (pnlSubscribed.value) {
          sendMessage({ type: 'subscribe_pnl' })
        }
      }

      socket.onclose = (event) => {
        console.log('[WS-Quotes] 关闭:', event.code, event.reason)
        wsConnected.value = false
        ws.value = null

        if (wsReconnectAttempts < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000)
          wsReconnectTimer = setTimeout(() => {
            wsReconnectAttempts += 1
            connect()
          }, delay)
        } else {
          console.error('[WS-Quotes] 达到最大重连次数')
        }
      }

      socket.onerror = (err) => {
        console.error('[WS-Quotes] 连接错误:', err)
        wsConnected.value = false
      }

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          handleMessage(msg)
        } catch (err) {
          console.error('[WS-Quotes] 解析消息失败:', err)
        }
      }
    } catch (err) {
      console.error('[WS-Quotes] 连接异常:', err)
      wsConnected.value = false
    }
  }

  function handleMessage(msg: { type: string; data?: any }): void {
    switch (msg.type) {
      case 'connected':
      case 'subscribed':
      case 'subscribed_pnl':
      case 'unsubscribed':
      case 'pong':
      case 'heartbeat':
        // 控制类消息，无需更新 state（仅 debug log）
        break

      case 'quote': {
        const data = msg.data as QuoteData | undefined
        if (data && data.code) {
          // reactive merge：直接 set key 让 Vue 监听到
          quoteByCode.value = { ...quoteByCode.value, [data.code]: data }
        }
        break
      }

      case 'pnl': {
        const data = msg.data as PnLData | undefined
        if (data) {
          latestPnl.value = data
        }
        break
      }

      case 'error':
        console.warn('[WS-Quotes] server error:', msg.data)
        break

      default:
        console.warn('[WS-Quotes] 未知消息类型:', msg.type)
    }
  }

  function sendMessage(payload: Record<string, unknown>): boolean {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return false
    }
    try {
      ws.value.send(JSON.stringify(payload))
      return true
    } catch (err) {
      console.error('[WS-Quotes] 发送消息失败:', err)
      return false
    }
  }

  function subscribe(codes: string[]): void {
    const cleaned = codes
      .map((c) => (typeof c === 'string' ? c.trim() : ''))
      .filter((c) => c.length > 0 && !subscribedCodes.value.has(c))
    if (cleaned.length === 0) return
    cleaned.forEach((c) => subscribedCodes.value.add(c))
    sendMessage({ type: 'subscribe', codes: cleaned })
  }

  function unsubscribe(codes: string[]): void {
    const cleaned = codes
      .map((c) => (typeof c === 'string' ? c.trim() : ''))
      .filter((c) => c.length > 0 && subscribedCodes.value.has(c))
    if (cleaned.length === 0) return
    cleaned.forEach((c) => subscribedCodes.value.delete(c))
    sendMessage({ type: 'unsubscribe', codes: cleaned })
  }

  function subscribePnl(): void {
    if (pnlSubscribed.value) return
    pnlSubscribed.value = true
    sendMessage({ type: 'subscribe_pnl' })
  }

  function disconnect(): void {
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer)
      wsReconnectTimer = null
    }
    wsReconnectAttempts = maxReconnectAttempts // 阻止 onclose 触发重连
    if (ws.value) {
      try {
        ws.value.close()
      } catch {
        // noop
      }
      ws.value = null
    }
    wsConnected.value = false
    subscribedCodes.value = new Set()
    pnlSubscribed.value = false
  }

  return {
    quoteByCode,
    latestPnl,
    connected,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    subscribePnl,
  }
})
