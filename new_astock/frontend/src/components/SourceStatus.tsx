import { Alert, Space, Tag, Tooltip, Typography } from 'antd'
import { CloudSyncOutlined, DatabaseOutlined, WarningOutlined } from '@ant-design/icons'
import type { SourceMeta } from '../types'

export function SourceStatus({ meta }: { meta?: SourceMeta }) {
  if (!meta) return null
  return (
    <div className="source-status">
      <Space size={6} wrap>
        <Tag icon={<DatabaseOutlined />} color={meta.stale ? 'warning' : 'processing'}>{meta.source}</Tag>
        {meta.cached && <Tag icon={<CloudSyncOutlined />}>缓存</Tag>}
        <Tooltip title={meta.updated_at}><Typography.Text type="secondary">{meta.updated_at?.slice(11)}</Typography.Text></Tooltip>
      </Space>
      {meta.fallback_reason && (
        <Alert type="warning" showIcon icon={<WarningOutlined />} message="已启用降级数据" description={meta.fallback_reason} closable />
      )}
    </div>
  )
}
