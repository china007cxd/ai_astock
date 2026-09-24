import { useState } from 'react'
import { Button, Card, Descriptions, Drawer, message, Space, Tag, Typography } from 'antd'
import { CameraOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import { useAppStore } from '../store'

type Snapshot = { date: string; category: string; data: unknown; source: string; created_at: string; [key: string]: unknown }

const columns: ColumnsType<Snapshot> = [
  { title: '交易日', dataIndex: 'date', key: 'date', width: 120, fixed: 'left' },
  { title: '分类', dataIndex: 'category', key: 'category', width: 130, render: (value) => <Tag color="blue">{value}</Tag> },
  { title: '数据源', dataIndex: 'source', key: 'source', width: 180 },
  { title: '生成时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (value: string) => value?.replace('T', ' ').slice(0, 19) },
  { title: '摘要', key: 'summary', width: 280, render: (_, row) => Array.isArray(row.data) ? `${row.data.length} 条记录` : `${Object.keys((row.data as object) || {}).length} 个数据块` },
]

export default function History() {
  const tradeDate = useAppStore((state) => state.tradeDate)
  const [selected, setSelected] = useState<Snapshot | null>(null)
  const query = useQuery({ queryKey: ['history', tradeDate], queryFn: () => api.get<Snapshot[]>(`/api/v1/history${tradeDate ? `?trade_date=${tradeDate}` : ''}`) })
  const snapshot = useMutation({ mutationFn: () => api.post('/api/v1/history/snapshot'), onSuccess: () => { message.success('复盘快照已生成'); query.refetch() } })
  return (
    <div className="page-stack">
      <PageTitle title="历史与导出" description="最近 30 个交易日复盘快照；各业务表格可直接导出 Excel/CSV" extra={<Space><SourceStatus meta={query.data?.meta} /><Button icon={<CameraOutlined />} loading={snapshot.isPending} onClick={() => snapshot.mutate()}>生成今日快照</Button><Button icon={<ReloadOutlined />} onClick={() => query.refetch()}>刷新</Button></Space>} />
      <Card size="small"><Typography.Text type="secondary">历史快照用于统一回看大盘、涨停和板块口径。导出请在任一业务表格右上角选择 Excel 或 CSV。</Typography.Text></Card>
      <QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} empty={!query.isLoading && query.data?.data.length === 0} />
      <DataTable id="history" title="复盘快照" rows={query.data?.data || []} columns={columns} rowKey={(row) => `${row.date}-${row.category}`} onRowClick={setSelected} />
      <Drawer title={`${selected?.date || ''} · ${selected?.category || ''}`} width="min(880px, 92vw)" open={Boolean(selected)} onClose={() => setSelected(null)}>
        {selected && <><Descriptions items={[{ key: 'source', label: '数据源', children: selected.source }, { key: 'time', label: '生成时间', children: selected.created_at }]} /><pre className="snapshot-json">{JSON.stringify(selected.data, null, 2)}</pre></>}
      </Drawer>
    </div>
  )
}
