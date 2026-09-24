import { Card, Col, Collapse, Row, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api'
import { PageTitle, QueryState } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'

interface AuctionData { live: unknown; seal_orders: unknown; plate_analysis: Record<string, unknown> }

function JsonPanel({ value }: { value: unknown }) {
  const rows = Array.isArray(value) ? value : value && typeof value === 'object' ? Object.entries(value as Record<string, unknown>) : []
  if (!rows.length) return <Typography.Text type="secondary">当前数据源暂无记录</Typography.Text>
  return <div className="raw-grid">{rows.slice(0, 100).map((row, index) => <article key={index}><pre>{JSON.stringify(row, null, 2)}</pre></article>)}</div>
}

export default function Auction() {
  const query = useQuery({ queryKey: ['auction'], queryFn: () => api.get<AuctionData>('/api/v1/auction'), refetchInterval: 15_000 })
  return (
    <div className="page-stack">
      <PageTitle title="竞价异动" description="竞价直播、封单排行、板块异动与盘中雷达" extra={<SourceStatus meta={query.data?.meta} />} />
      <QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} />
      <Row gutter={[12, 12]}>
        <Col xs={24} xl={12}><Card title="竞价直播" className="full-card"><JsonPanel value={query.data?.data.live} /></Card></Col>
        <Col xs={24} xl={12}><Card title="封单排行" className="full-card"><JsonPanel value={query.data?.data.seal_orders} /></Card></Col>
      </Row>
      <Collapse items={[{ key: 'plate', label: '板块涨跌与连板分析', children: <JsonPanel value={query.data?.data.plate_analysis} /> }]} defaultActiveKey={['plate']} />
    </div>
  )
}
