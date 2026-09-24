export interface SourceMeta {
  source: string
  updated_at?: string
  cached?: boolean
  stale?: boolean
  fallback_reason?: string | null
}

export interface ApiResult<T> {
  data: T
  meta: SourceMeta
}

export interface Quote {
  code: string
  name: string
  price?: number
  change?: number
  change_amount?: number
  open?: number
  high?: number
  low?: number
  previous_close?: number
  volume?: number
  amount?: number
  turnover_rate?: number
  amplitude?: number
  volume_ratio?: number
  pe?: number
  pb?: number
  market_cap?: number
  float_market_cap?: number
  main_net_inflow?: number
  [key: string]: unknown
}

export interface LimitStock extends Quote {
  board_height: number
  reason: string
  first_time: string
  last_time: string
  order_amount?: number
  status: string
  plates: string[]
}

export interface Overview {
  indices: Quote[]
  sentiment: {
    score: number
    label: string
    rises: number
    falls: number
    flats: number
    limit_up: number
    broken: number
    high_boards: number
  }
  market_amount: number
  top_gainers: Quote[]
  limit_preview: LimitStock[]
}

export interface StockDetail {
  quote: Quote
  kline: Array<Record<string, number | string | null>>
  minute: Array<Record<string, number | string | null>>
}
