import { useMemo } from 'react'
import { Button, Card, Col, Descriptions, message, Row, Space, Statistic, Tabs, Tag } from 'antd'
import { StarOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { api } from '../api'
import { Chart } from '../components/Chart'
import { PageTitle, QueryState, changeClass, money, percent } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import type { StockDetail } from '../types'

export default function StockCenter() {
  const code = useParams().code || '000001'
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['stock', code], queryFn: () => api.get<StockDetail>(`/api/v1/stocks/${code}`), refetchInterval: 10_000 })
  const add = useMutation({
    mutationFn: () => api.post(`/api/v1/watchlist/${code}`, { name: query.data?.data.quote.name || '' }),
    onSuccess: () => { message.success('已加入自选'); client.invalidateQueries({ queryKey: ['watchlist'] }) },
  })
  const data = query.data?.data
  const klineOption = useMemo(() => {
    const rows = data?.kline || []
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['K线', 'MA5', 'MA10', 'MA20'] },
      grid: { left: 48, right: 20, top: 38, bottom: 58 },
      xAxis: { type: 'category', data: rows.map((row) => row.date), boundaryGap: true },
      yAxis: { scale: true },
      dataZoom: [{ type: 'inside', start: 55 }, { type: 'slider', start: 55 }],
      series: [
        { name: 'K线', type: 'candlestick', data: rows.map((row) => [row.open, row.close, row.low, row.high]), itemStyle: { color: '#ef5350', color0: '#19a974', borderColor: '#ef5350', borderColor0: '#19a974' } },
        ...(['ma5', 'ma10', 'ma20'] as const).map((key) => ({ name: key.toUpperCase(), type: 'line', symbol: 'none', smooth: true, data: rows.map((row) => row[key]) })),
      ],
    }
  }, [data])
  const minuteOption = useMemo(() => ({
    tooltip: { trigger: 'axis' }, grid: { left: 48, right: 20, top: 20, bottom: 36 },
    xAxis: { type: 'category', data: (data?.minute || []).map((row) => row.time), axisLabel: { hideOverlap: true } },
    yAxis: { scale: true },
    series: [{ type: 'line', symbol: 'none', smooth: true, areaStyle: { opacity: 0.12 }, data: (data?.minute || []).map((row) => row.price) }],
  }), [data])
  if (!data) return <><PageTitle title="个股中心" description={`正在加载 ${code}`} /><QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} /></>
  const quote = data.quote
  return (
    <div className="page-stack">
      <PageTitle title={`${quote.name || code} · ${quote.code}`} description="实时行情、分时、K线与技术指标" extra={<Space><SourceStatus meta={query.data?.meta} /><Button icon={<StarOutlined />} loading={add.isPending} onClick={() => add.mutate()}>加入自选</Button></Space>} />
      <Row gutter={[12, 12]}>
        <Col xs={24} xl={7}>
          <Card className="quote-panel">
            <div className="quote-price"><strong className={changeClass(quote.change)}>{quote.price?.toFixed(2) || '--'}</strong><span className={changeClass(quote.change)}>{percent(quote.change)}</span></div>
            <Descriptions size="small" column={2} items={[
              { key: 'open', label: '今开', children: quote.open?.toFixed(2) || '--' }, { key: 'high', label: '最高', children: quote.high?.toFixed(2) || '--' },
              { key: 'low', label: '最低', children: quote.low?.toFixed(2) || '--' }, { key: 'prev', label: '昨收', children: quote.previous_close?.toFixed(2) || '--' },
              { key: 'amount', label: '成交额', children: money(quote.amount) }, { key: 'turn', label: '换手', children: percent(quote.turnover_rate) },
              { key: 'ratio', label: '量比', children: quote.volume_ratio || '--' }, { key: 'amp', label: '振幅', children: percent(quote.amplitude) },
              { key: 'cap', label: '流通市值', children: money(quote.float_market_cap) }, { key: 'flow', label: '主力净流', children: money(quote.main_net_inflow) },
            ]} />
          </Card>
        </Col>
        <Col xs={24} xl={17}>
          <Card><Tabs items={[{ key: 'minute', label: '分时', children: <Chart option={minuteOption} height={360} ariaLabel="股票分时走势图" /> }, { key: 'kline', label: '日K与均线', children: <Chart option={klineOption} height={420} ariaLabel="股票日K线与技术指标" /> }]} /></Card>
        </Col>
      </Row>
      <Row gutter={[12, 12]}>{data.kline.length > 0 && ['ma5', 'ma10', 'ma20', 'ma60', 'dif', 'dea', 'macd', 'k', 'd', 'j'].map((key) => <Col xs={8} md={4} xl={3} key={key}><Card size="small"><Statistic title={key.toUpperCase()} value={Number(data.kline.at(-1)?.[key] || 0)} precision={3} /></Card></Col>)}</Row>
      {query.data?.meta.fallback_reason && <Tag color="warning">{query.data.meta.fallback_reason}</Tag>}
    </div>
  )
}
