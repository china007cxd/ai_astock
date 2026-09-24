import { useState } from 'react'
import { Button, Card, Col, Form, Input, InputNumber, message, Row, Select, Space } from 'antd'
import { SaveOutlined, SearchOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, quoteColumns } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import type { ApiResult, Quote } from '../types'

interface FormValues { query?: string; field?: string; operator?: string; value?: number; name?: string }

export default function Screener() {
  const [result, setResult] = useState<ApiResult<Quote[] | { total: number; rows: Quote[] }> | null>(null)
  const [values, setValues] = useState<FormValues>({ field: 'change', operator: 'gte', value: 5 })
  const navigate = useNavigate()
  const run = useMutation({
    mutationFn: (form: FormValues) => api.post<ApiResult<Quote[] | { total: number; rows: Quote[] }>>('/api/v1/screeners/run', { query: form.query || '', filters: form.query ? [] : [{ field: form.field, operator: form.operator, value: form.value }], page: 1, page_size: 200 }),
    onSuccess: setResult,
    onError: (error) => message.error(error.message),
  })
  const save = () => api.post(`/api/v1/screeners/${encodeURIComponent(values.name || '未命名条件')}`, { query: values.query || '', filters: values.query ? [] : [{ field: values.field, operator: values.operator, value: values.value }], page: 1, page_size: 200 }).then(() => message.success('条件已保存'))
  const rows = Array.isArray(result?.data) ? result.data : result?.data.rows || []
  return (
    <div className="page-stack">
      <PageTitle title="智能选股" description="自然语言问财式查询与本地量化条件筛选" extra={<SourceStatus meta={result?.meta} />} />
      <Card>
        <Form layout="vertical" initialValues={values} onValuesChange={(_, all) => setValues(all)} onFinish={(form) => run.mutate(form)}>
          <Row gutter={12}>
            <Col xs={24} xl={9}><Form.Item name="query" label="自然语言条件"><Input allowClear placeholder="例如：今日涨停且换手率小于15%的非ST股票" /></Form.Item></Col>
            <Col xs={8} xl={4}><Form.Item name="field" label="本地指标"><Select options={[{ value: 'change', label: '涨跌幅' }, { value: 'turnover_rate', label: '换手率' }, { value: 'volume_ratio', label: '量比' }, { value: 'market_cap', label: '总市值' }, { value: 'main_net_inflow', label: '主力净流入' }]} /></Form.Item></Col>
            <Col xs={8} xl={3}><Form.Item name="operator" label="关系"><Select options={[{ value: 'gte', label: '大于等于' }, { value: 'lte', label: '小于等于' }, { value: 'gt', label: '大于' }, { value: 'lt', label: '小于' }, { value: 'eq', label: '等于' }]} /></Form.Item></Col>
            <Col xs={8} xl={3}><Form.Item name="value" label="数值"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
            <Col xs={12} xl={3}><Form.Item name="name" label="保存名称"><Input placeholder="可选" /></Form.Item></Col>
            <Col xs={12} xl={2}><Form.Item label="执行"><Space><Button type="primary" htmlType="submit" loading={run.isPending} icon={<SearchOutlined />} /><Button icon={<SaveOutlined />} onClick={save} /></Space></Form.Item></Col>
          </Row>
        </Form>
      </Card>
      <DataTable id="screener-result" title={`筛选结果（${rows.length}）`} rows={rows} columns={quoteColumns} loading={run.isPending} onRowClick={(row) => navigate(`/stock/${row.code}`)} />
    </div>
  )
}
