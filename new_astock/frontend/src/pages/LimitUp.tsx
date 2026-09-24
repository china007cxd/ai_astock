import { useMemo, useState } from 'react'
import { Card, Segmented, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState, changeClass, money, percent } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import { useAppStore } from '../store'
import type { LimitStock } from '../types'

const columns: ColumnsType<LimitStock> = [
  { title: '代码', dataIndex: 'code', key: 'code', fixed: 'left', width: 86 },
  { title: '名称', dataIndex: 'name', key: 'name', fixed: 'left', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 78, render: (value) => <Tag color={value === '炸板' ? 'warning' : 'error'}>{value}</Tag> },
  { title: '连板', dataIndex: 'board_height', key: 'board_height', width: 76, align: 'center', render: (value) => <b>{value}板</b>, sorter: (a, b) => a.board_height - b.board_height },
  { title: '涨幅', dataIndex: 'change', key: 'change', width: 92, align: 'right', render: (value) => <span className={changeClass(value)}>{percent(value)}</span> },
  { title: '现价', dataIndex: 'price', key: 'price', width: 88, align: 'right' },
  { title: '首次封板', dataIndex: 'first_time', key: 'first_time', width: 100 },
  { title: '最后封板', dataIndex: 'last_time', key: 'last_time', width: 100 },
  { title: '封单额', dataIndex: 'order_amount', key: 'order_amount', width: 110, align: 'right', render: money },
  { title: '换手率', dataIndex: 'turnover_rate', key: 'turnover_rate', width: 96, align: 'right', render: percent },
  { title: '涨停原因', dataIndex: 'reason', key: 'reason', width: 240, ellipsis: true },
  { title: '相关题材', dataIndex: 'plates', key: 'plates', width: 240, render: (items: string[]) => items?.map((item) => <Tag key={item}>{item}</Tag>) },
]

export default function LimitUp() {
  const [mode, setMode] = useState<'limit_up' | 'broken'>('limit_up')
  const tradeDate = useAppStore((state) => state.tradeDate)
  const navigate = useNavigate()
  const suffix = tradeDate ? `&trade_date=${tradeDate}` : ''
  const query = useQuery({ queryKey: ['limit-up', mode, tradeDate], queryFn: () => api.get<LimitStock[]>(`/api/v1/limit-up?status=${mode}${suffix}`), refetchInterval: tradeDate ? false : 20_000 })
  const summary = useMemo(() => {
    const rows = query.data?.data || []
    return { total: rows.length, highest: Math.max(0, ...rows.map((row) => row.board_height)), amount: rows.reduce((sum, row) => sum + (row.order_amount || 0), 0) }
  }, [query.data])
  return (
    <div className="page-stack">
      <PageTitle title="涨停复盘" description="涨停池、炸板池、连板梯队与涨停原因" extra={<SourceStatus meta={query.data?.meta} />} />
      <Card size="small"><div className="summary-bar"><Segmented options={[{ label: '涨停池', value: 'limit_up' }, { label: '炸板池', value: 'broken' }]} value={mode} onChange={(value) => setMode(value as typeof mode)} /><span>数量 <b>{summary.total}</b></span><span>最高 <b>{summary.highest}板</b></span><span>封单合计 <b>{money(summary.amount)}</b></span></div></Card>
      <QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} />
      <DataTable id={`limit-${mode}`} title={mode === 'limit_up' ? '涨停股票' : '炸板股票'} rows={query.data?.data || []} columns={columns} loading={query.isFetching} onRowClick={(row) => navigate(`/stock/${row.code}`)} />
    </div>
  )
}
