import { Alert, Button, Empty, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Quote } from '../types'

export const money = (value?: number) => {
  if (value == null) return '--'
  const absolute = Math.abs(value)
  if (absolute >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (absolute >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(2)
}

export const percent = (value?: number) => value == null ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`

export const changeClass = (value?: number) => value && value > 0 ? 'rise' : value && value < 0 ? 'fall' : ''

export const quoteColumns: ColumnsType<Quote> = [
  { title: '代码', dataIndex: 'code', key: 'code', fixed: 'left', width: 86 },
  { title: '名称', dataIndex: 'name', key: 'name', fixed: 'left', width: 100 },
  { title: '现价', dataIndex: 'price', key: 'price', align: 'right', width: 90, render: (value, row) => <span className={changeClass(row.change)}>{value?.toFixed?.(2) ?? '--'}</span>, sorter: (a, b) => (a.price || 0) - (b.price || 0) },
  { title: '涨跌幅', dataIndex: 'change', key: 'change', align: 'right', width: 96, render: (value) => <span className={changeClass(value)}>{percent(value)}</span>, sorter: (a, b) => (a.change || 0) - (b.change || 0) },
  { title: '成交额', dataIndex: 'amount', key: 'amount', align: 'right', width: 110, render: money, sorter: (a, b) => (a.amount || 0) - (b.amount || 0) },
  { title: '换手率', dataIndex: 'turnover_rate', key: 'turnover_rate', align: 'right', width: 96, render: percent },
  { title: '量比', dataIndex: 'volume_ratio', key: 'volume_ratio', align: 'right', width: 80 },
  { title: '振幅', dataIndex: 'amplitude', key: 'amplitude', align: 'right', width: 90, render: percent },
  { title: '流通市值', dataIndex: 'float_market_cap', key: 'float_market_cap', align: 'right', width: 110, render: money },
  { title: '主力净流入', dataIndex: 'main_net_inflow', key: 'main_net_inflow', align: 'right', width: 120, render: (value) => <span className={changeClass(value)}>{money(value)}</span> },
]

export function PageTitle({ title, description, extra }: { title: string; description: string; extra?: React.ReactNode }) {
  return <div className="page-title"><div><Typography.Title level={3}>{title}</Typography.Title><Typography.Text type="secondary">{description}</Typography.Text></div>{extra}</div>
}

export function QueryState({ loading, error, onRetry, empty }: { loading: boolean; error?: Error | null; onRetry: () => void; empty?: boolean }) {
  if (loading) return <div className="page-loading" aria-label="加载中"><span className="pulse-dot" />正在获取真实行情...</div>
  if (error) return <Alert type="error" showIcon message="数据加载失败" description={error.message} action={<Button icon={<ReloadOutlined />} onClick={onRetry}>重试</Button>} />
  if (empty) return <Empty description="当前没有可展示的数据" />
  return null
}
