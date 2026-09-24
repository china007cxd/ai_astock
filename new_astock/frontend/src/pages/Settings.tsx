import { Button, Card, Col, Form, InputNumber, message, Radio, Row, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import { ClearOutlined, CloudSyncOutlined, SaveOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '../api'
import { PageTitle, QueryState } from '../components/common'
import { useAppStore } from '../store'

interface SourceHealth { source: string; ok: boolean | null; checked_at: string | null; error: string }

export default function Settings() {
  const theme = useAppStore((state) => state.theme)
  const toggleTheme = useAppStore((state) => state.toggleTheme)
  const tableSize = useAppStore((state) => state.tableSize)
  const setTableSize = useAppStore((state) => state.setTableSize)
  const settings = useQuery({ queryKey: ['settings'], queryFn: () => api.raw<{ data: Record<string, unknown> }>('/api/v1/settings') })
  const sources = useQuery({ queryKey: ['sources'], queryFn: () => api.raw<{ data: SourceHealth[] }>('/api/v1/sources'), refetchInterval: 30_000 })
  const save = useMutation({ mutationFn: (values: Record<string, unknown>) => api.patch('/api/v1/settings', { values }), onSuccess: () => message.success('设置已保存') })
  const clear = useMutation({ mutationFn: () => api.post<{ removed: number }>('/api/v1/cache/clear'), onSuccess: (data) => message.success(`已清理 ${data.removed} 个缓存文件`) })
  return (
    <div className="page-stack">
      <PageTitle title="系统设置" description="主题、刷新频率、表格密度、数据源与本地缓存" />
      <Row gutter={[12, 12]}>
        <Col xs={24} xl={10}>
          <Card title="界面与刷新">
            <Form layout="vertical" initialValues={{ market: Number(settings.data?.data['refresh.market'] || 10), list: Number(settings.data?.data['refresh.list'] || 30) }} onFinish={(values) => save.mutate({ 'refresh.market': values.market, 'refresh.list': values.list })}>
              <Form.Item label="主题"><Radio.Group value={theme} onChange={() => toggleTheme()} options={[{ label: '深色', value: 'dark' }, { label: '浅色', value: 'light' }]} /></Form.Item>
              <Form.Item label="表格密度"><Select value={tableSize} onChange={setTableSize} options={[{ value: 'small', label: '紧凑' }, { value: 'middle', label: '舒适' }]} /></Form.Item>
              <Row gutter={12}><Col span={12}><Form.Item name="market" label="行情刷新（秒）"><InputNumber min={3} max={60} style={{ width: '100%' }} /></Form.Item></Col><Col span={12}><Form.Item name="list" label="榜单刷新（秒）"><InputNumber min={10} max={300} style={{ width: '100%' }} /></Form.Item></Col></Row>
              <Space><Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={save.isPending}>保存</Button><Button danger icon={<ClearOutlined />} loading={clear.isPending} onClick={() => clear.mutate()}>清理缓存</Button></Space>
            </Form>
          </Card>
          <Card title="可选付费数据源" style={{ marginTop: 12 }}>
            <Typography.Paragraph type="secondary">龙虎VIP 默认关闭。若合法拥有 Token/UserID，请写入项目根目录 `.env` 后重启；凭证不会通过网页读取或回显。</Typography.Paragraph>
            <Space><Switch checked={Boolean(settings.data?.data['source.longhuvip.enabled'])} disabled /><span>龙虎VIP</span><Tag>环境变量配置</Tag></Space>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="数据源健康状态" extra={<Button icon={<CloudSyncOutlined />} onClick={() => sources.refetch()}>刷新状态</Button>}>
            <QueryState loading={sources.isLoading} error={sources.error} onRetry={() => sources.refetch()} />
            <Table size="small" pagination={false} rowKey="source" dataSource={sources.data?.data || []} columns={[
              { title: '数据源', dataIndex: 'source' },
              { title: '状态', dataIndex: 'ok', render: (value) => value == null ? <Tag>尚未请求</Tag> : value ? <Tag color="success">正常</Tag> : <Tag color="error">异常</Tag> },
              { title: '检查时间', dataIndex: 'checked_at', width: 170 },
              { title: '说明', dataIndex: 'error', ellipsis: true },
            ]} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
