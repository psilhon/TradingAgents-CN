import type { ImportPositionPayload } from '@/api/paper'

type MarketCode = 'CN' | 'HK' | 'US'

const MARKET_ALIASES: Record<string, MarketCode> = {
  CN: 'CN',
  CNY: 'CN',
  A: 'CN',
  A股: 'CN',
  沪深: 'CN',
  港股: 'HK',
  HK: 'HK',
  HKD: 'HK',
  美股: 'US',
  US: 'US',
  USD: 'US',
}

const HEADER_ALIASES: Record<string, keyof ImportPositionPayload> = {
  market: 'market',
  市场: 'market',
  code: 'code',
  symbol: 'code',
  股票代码: 'code',
  代码: 'code',
  name: 'name',
  股票名称: 'name',
  名称: 'name',
  quantity: 'quantity',
  qty: 'quantity',
  数量: 'quantity',
  持仓数量: 'quantity',
  avg_cost: 'avg_cost',
  cost: 'avg_cost',
  成本价: 'avg_cost',
  持仓成本: 'avg_cost',
  available_qty: 'available_qty',
  可用数量: 'available_qty',
  可卖数量: 'available_qty',
}

const DEFAULT_COLUMNS: (keyof ImportPositionPayload)[] = [
  'market',
  'code',
  'name',
  'quantity',
  'avg_cost',
  'available_qty',
]

function splitLine(line: string): string[] {
  if (line.includes('\t')) return line.split('\t')
  if (line.includes(',')) return line.split(',')
  return line.trim().split(/\s{2,}|\s+/)
}

function normalizeHeader(value: string): keyof ImportPositionPayload | null {
  return HEADER_ALIASES[value.trim()] || HEADER_ALIASES[value.trim().toLowerCase()] || null
}

function normalizeMarket(value: string): MarketCode {
  const key = value.trim().toUpperCase()
  return MARKET_ALIASES[value.trim()] || MARKET_ALIASES[key] || 'CN'
}

function toNumber(value: string): number {
  const normalized = value.replace(/,/g, '').trim()
  const n = Number(normalized)
  return Number.isFinite(n) ? n : 0
}

function looksLikeHeader(cells: string[]): boolean {
  return cells.some((cell) => normalizeHeader(cell) !== null)
}

export function parsePaperPositionsText(text: string): ImportPositionPayload[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length === 0) return []

  let columns = DEFAULT_COLUMNS
  let startIndex = 0
  const firstCells = splitLine(lines[0])

  if (looksLikeHeader(firstCells)) {
    const parsedColumns = firstCells
      .map(normalizeHeader)
      .filter((column): column is keyof ImportPositionPayload => column !== null)
    if (parsedColumns.length > 0) columns = parsedColumns
    startIndex = 1
  }

  return lines.slice(startIndex).flatMap((line) => {
    const cells = splitLine(line)
    const row: Partial<ImportPositionPayload> = {}

    columns.forEach((column, index) => {
      const value = cells[index]?.trim() || ''
      if (!value) return

      if (column === 'market') row.market = normalizeMarket(value)
      else if (column === 'quantity' || column === 'available_qty' || column === 'avg_cost') row[column] = toNumber(value)
      else row[column] = value
    })

    if (!row.code || !row.quantity || row.quantity <= 0) return []

    return [{
      market: row.market || 'CN',
      code: row.code,
      name: row.name || '',
      quantity: Math.round(row.quantity),
      avg_cost: Number(row.avg_cost || 0),
      available_qty: Math.min(
        Math.round(Number(row.available_qty ?? row.quantity)),
        Math.round(row.quantity),
      ),
    }]
  })
}
