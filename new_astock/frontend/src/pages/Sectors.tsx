import { useState } from 'react'
import { Card, Col, List, Row, Tabs, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState, quoteColumns } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import type { Quote } from '../types'

interface SectorData { ranking: Quote[]; hot: Array<Record<string, unknown>>; limit_up: Array<Record<string, unknown>> }
interface ThemeData { industry: unknown[]; plates: Array<Record<string, unknown>>; timeline: Array<Record<string, unknown>> }

export default function Sectors() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState('')
  const query = useQuery({ queryKey: ['sectors'], queryFn: () => api.get<SectorData>('/api/v1/sectors'), refetchInterval: 30_000 })
  const themes = useQuery({ queryKey: ['themes'], queryFn: () => api.get<ThemeData>('/api/v1/themes'), staleTime: 60_000 })
  const stocks = useQuery({ queryKey: ['sector-stocks', selected], queryFn: () => api.get<Quote[]>(`/api/v1/sectors/${selected}/stocks`), enabled: Boolean(selected) })
  return (
    <div className="page-stack">
      <PageTitle title="板块题材" description="板块强弱、热门概念、涨停聚合与成分股" extra={<SourceStatus meta={query.data?.meta} />} />
      <QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} />
      <Row gutter={[12, 12]}>
        <Col xs={24} xl={16}><DataTable id="sector-ranking" title="板块涨幅排行（点击查看成分股）" rows={query.data?.data.ranking || []} columns={quoteColumns} onRowClick={(row) => setSelected(row.code)} maxHeight={420} /></Col>
        <Col xs={24} xl={8}><Card title="热门概念" className="full-card"><List dataSource={query.data?.data.hot || []} renderItem={(item, index) => <List.Item><Tag color={index < 3 ? 'red' : 'blue'}>{index + 1}</Tag><span>{String(item.name || item.plate_name || item.code || '--')}</span><small>{String(item.rate || item.tag || '')}</small></List.Item>} /></Card></Col>
      </Row>
      {selected && <DataTable id="sector-stocks" title={`板块 ${selected} 成分股`} rows={stocks.data?.data || []} columns={quoteColumns} loading={stocks.isLoading} onRowClick={(row) => navigate(`/stock/${row.code}`)} />}
      <Card title="题材与产业链">
        <Tabs items={[
          { key: 'plates', label: '涨停题材', children: <div className="tag-cloud">{[...(query.data?.data.limit_up || []), ...(themes.data?.data.plates || [])].slice(0, 100).map((item, index) => <Tag key={index}>{String(item.name || item.plate_name || item.id || `板块 ${index + 1}`)}</Tag>)}</div> },
          { key: 'industry', label: '产业链', children: <pre className="snapshot-json">{JSON.stringify(themes.data?.data.industry || [], null, 2)}</pre> },
          { key: 'timeline', label: '题材时间线', children: <List dataSource={themes.data?.data.timeline || []} renderItem={(item) => <List.Item><Typography.Text>{String(item.title || item.content || item.name || '题材事件')}</Typography.Text></List.Item>} /> },
        ]} />
      </Card>
    </div>
  )
}
