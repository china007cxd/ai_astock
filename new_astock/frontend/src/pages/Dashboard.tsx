import { useMemo } from 'react'
import { Card, Col, Progress, Row, Statistic, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { Chart } from '../components/Chart'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState, changeClass, money, quoteColumns } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import type { Overview } from '../types'

export default function Dashboard() {
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['overview'], queryFn: () => api.get<Overview>('/api/v1/market/overview'), refetchInterval: 10_000 })
  const data = query.data?.data
  const distributionOption = useMemo(() => ({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['55%', '78%'], avoidLabelOverlap: false,
      label: { formatter: '{b}\n{c}' },
      data: data ? [
        { name: '上涨', value: data.sentiment.rises, itemStyle: { color: '#f05252' } },
        { name: '下跌', value: data.sentiment.falls, itemStyle: { color: '#19a974' } },
        { name: '平盘', value: data.sentiment.flats, itemStyle: { color: '#8290a7' } },
      ] : [],
    }],
  }), [data])
  if (!data) return <><PageTitle title="大盘复盘" description="市场全景、量能与情绪强弱" /><QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} /></>
  return (
    <div className="page-stack">
      <PageTitle title="大盘复盘" description="实时市场全景、量能与情绪强弱" extra={<SourceStatus meta={query.data?.meta} />} />
      <Row gutter={[12, 12]}>
        {data.indices.map((item) => (
          <Col xs={12} md={8} xl={4} key={item.code}>
            <Card className="index-card" onClick={() => navigate(`/stock/${item.code}`)} hoverable>
              <span>{item.name}</span><strong className={changeClass(item.change)}>{item.price?.toFixed(2) ?? '--'}</strong>
              <small className={changeClass(item.change)}>{item.change != null ? `${item.change > 0 ? '+' : ''}${item.change.toFixed(2)}%` : '--'}</small>
            </Card>
          </Col>
        ))}
      </Row>
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={8}>
          <Card title="市场情绪" className="full-card">
            <div className="sentiment"><Progress type="dashboard" percent={data.sentiment.score} strokeColor={data.sentiment.score >= 60 ? '#ef5350' : '#19a974'} /><Tag color="blue">{data.sentiment.label}</Tag></div>
            <div className="stat-grid"><Statistic title="涨停" value={data.sentiment.limit_up} /><Statistic title="炸板" value={data.sentiment.broken} /><Statistic title="三板以上" value={data.sentiment.high_boards} /><Statistic title="成交额" value={money(data.market_amount)} /></div>
          </Card>
        </Col>
        <Col xs={24} lg={8}><Card title="涨跌分布" className="full-card"><Chart option={distributionOption} height={260} ariaLabel="市场涨跌家数分布" /></Card></Col>
        <Col xs={24} lg={8}>
          <Card title="今日焦点" className="full-card">
            <div className="focus-list">{data.limit_preview.slice(0, 8).map((item, index) => <button key={item.code} onClick={() => navigate(`/stock/${item.code}`)}><em>{index + 1}</em><span>{item.name}</span><b>{item.board_height}板</b><small>{item.reason || '涨停'}</small></button>)}</div>
          </Card>
        </Col>
      </Row>
      <DataTable id="dashboard-gainers" title="市场强势股" rows={data.top_gainers} columns={quoteColumns} onRowClick={(row) => navigate(`/stock/${row.code}`)} />
    </div>
  )
}
