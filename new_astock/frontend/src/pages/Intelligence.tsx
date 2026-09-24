import { Card, List, Tabs, Tag, Timeline, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState, changeClass, money, percent } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import { useAppStore } from '../store'

type Row = Record<string, unknown>
interface IntelligenceData { lhb: Row[]; news: Row[]; events: Row[] }

const lhbColumns: ColumnsType<Row> = [
  { title: '代码', dataIndex: 'SECURITY_CODE', key: 'SECURITY_CODE', width: 90, fixed: 'left' },
  { title: '名称', dataIndex: 'SECURITY_NAME_ABBR', key: 'SECURITY_NAME_ABBR', width: 110, fixed: 'left' },
  { title: '上榜原因', dataIndex: 'EXPLANATION', key: 'EXPLANATION', width: 280, ellipsis: true },
  { title: '涨跌幅', dataIndex: 'CHANGE_RATE', key: 'CHANGE_RATE', width: 100, align: 'right', render: (value) => <span className={changeClass(Number(value))}>{percent(Number(value))}</span> },
  { title: '龙虎榜净买额', dataIndex: 'BILLBOARD_NET_AMT', key: 'BILLBOARD_NET_AMT', width: 140, align: 'right', render: (value) => money(Number(value)) },
  { title: '成交额', dataIndex: 'BILLBOARD_DEAL_AMT', key: 'BILLBOARD_DEAL_AMT', width: 120, align: 'right', render: (value) => money(Number(value)) },
  { title: '换手率', dataIndex: 'TURNOVERRATE', key: 'TURNOVERRATE', width: 100, align: 'right', render: (value) => percent(Number(value)) },
]

function textOf(row: Row) {
  return String(row.title || row.summary || row.content || row.description || row.news_title || row.name || '资讯')
}

export default function Intelligence() {
  const tradeDate = useAppStore((state) => state.tradeDate)
  const query = useQuery({ queryKey: ['intelligence', tradeDate], queryFn: () => api.get<IntelligenceData>(`/api/v1/intelligence${tradeDate ? `?trade_date=${tradeDate}` : ''}`), refetchInterval: tradeDate ? false : 30_000 })
  return (
    <div className="page-stack">
      <PageTitle title="龙虎资讯" description="龙虎榜、机构动向、题材事件与 7×24 快讯" extra={<SourceStatus meta={query.data?.meta} />} />
      <QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} />
      <Tabs items={[
        { key: 'lhb', label: `龙虎榜 ${query.data?.data.lhb.length || 0}`, children: <DataTable id="lhb" title="龙虎榜明细" rows={query.data?.data.lhb || []} columns={lhbColumns} rowKey={(row) => String(row.SECURITY_CODE) + String(row.EXPLANATION)} /> },
        { key: 'news', label: '7×24 快讯', children: <Card><List dataSource={query.data?.data.news || []} renderItem={(item) => <List.Item><List.Item.Meta title={textOf(item)} description={String(item.showTime || item.time || item.date || '')} /></List.Item>} /></Card> },
        { key: 'events', label: '题材事件', children: <Card><Timeline items={(query.data?.data.events || []).slice(0, 100).map((item) => ({ color: 'blue', children: <><Typography.Text strong>{textOf(item)}</Typography.Text><br /><Typography.Text type="secondary">{String(item.created_at || item.time || '')}</Typography.Text>{item.tag ? <Tag>{String(item.tag)}</Tag> : null}</> }))} /></Card> },
      ]} />
    </div>
  )
}
