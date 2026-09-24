import { Button, message } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../api'
import { DataTable } from '../components/DataTable'
import { PageTitle, QueryState, quoteColumns } from '../components/common'
import { SourceStatus } from '../components/SourceStatus'
import type { Quote } from '../types'

export default function Watchlist() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['watchlist'], queryFn: () => api.get<Quote[]>('/api/v1/watchlist'), refetchInterval: 10_000 })
  const remove = useMutation({ mutationFn: (code: string) => api.delete(`/api/v1/watchlist/${code}`), onSuccess: () => { message.success('已移除'); client.invalidateQueries({ queryKey: ['watchlist'] }) } })
  const columns: ColumnsType<Quote> = [...quoteColumns, { title: '操作', key: 'action', fixed: 'right', width: 70, render: (_, row) => <Button danger type="text" icon={<DeleteOutlined />} aria-label={`移除${row.name}`} onClick={(event) => { event.stopPropagation(); remove.mutate(row.code) }} /> }]
  return <div className="page-stack"><PageTitle title="自选股" description="本地保存并实时刷新关注股票" extra={<SourceStatus meta={query.data?.meta} />} /><QueryState loading={query.isLoading} error={query.error} onRetry={() => query.refetch()} empty={!query.isLoading && query.data?.data.length === 0} /><DataTable id="watchlist" title="我的自选" rows={query.data?.data || []} columns={columns} onRowClick={(row) => navigate(`/stock/${row.code}`)} /></div>
}
