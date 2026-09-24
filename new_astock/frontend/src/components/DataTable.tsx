import { useMemo } from 'react'
import { Button, Checkbox, Dropdown, Space, Table, Tooltip } from 'antd'
import { DownloadOutlined, SettingOutlined } from '@ant-design/icons'
import type { ColumnsType, ColumnType } from 'antd/es/table'

import { exportRows } from '../api'
import { useAppStore } from '../store'

type Row = Record<string, unknown>

interface DataTableProps<T extends Row> {
  id: string
  title: string
  rows: T[]
  columns: ColumnsType<T>
  loading?: boolean
  rowKey?: string | ((row: T) => string)
  onRowClick?: (row: T) => void
  maxHeight?: number
}

function columnKey<T extends Row>(column: ColumnType<T>): string {
  if (column.key != null) return String(column.key)
  if (typeof column.dataIndex === 'string') return column.dataIndex
  return String(column.title || '')
}

export function DataTable<T extends Row>({
  id,
  title,
  rows,
  columns,
  loading,
  rowKey = 'code',
  onRowClick,
  maxHeight = 540,
}: DataTableProps<T>) {
  const hidden = useAppStore((state) => state.hiddenColumns[id] || [])
  const setHidden = useAppStore((state) => state.setHiddenColumns)
  const size = useAppStore((state) => state.tableSize)
  const visible = useMemo(
    () => columns.filter((column) => !hidden.includes(columnKey(column as ColumnType<T>))),
    [columns, hidden],
  )
  const exportColumns = visible.map((column) => {
    const typedColumn = column as ColumnType<T>
    return {
      key: typeof typedColumn.dataIndex === 'string' ? typedColumn.dataIndex : columnKey(typedColumn),
      title: String(typedColumn.title || columnKey(typedColumn)),
    }
  })
  const columnMenu = (
    <div className="column-menu">
      {columns.map((column) => {
        const key = columnKey(column as ColumnType<T>)
        return (
          <Checkbox
            key={key}
            checked={!hidden.includes(key)}
            onChange={(event) => setHidden(id, event.target.checked ? hidden.filter((item) => item !== key) : [...hidden, key])}
          >
            {String(column.title || key)}
          </Checkbox>
        )
      })}
    </div>
  )
  return (
    <section className="data-table" aria-label={title}>
      <div className="table-toolbar">
        <strong>{title}</strong>
        <Space>
          <Dropdown
            menu={{
              items: [
                { key: 'xlsx', label: '导出 Excel', onClick: () => exportRows(title, 'xlsx', exportColumns, rows) },
                { key: 'csv', label: '导出 CSV', onClick: () => exportRows(title, 'csv', exportColumns, rows) },
              ],
            }}
          >
            <Tooltip title="导出当前结果"><Button size="small" icon={<DownloadOutlined />}>导出</Button></Tooltip>
          </Dropdown>
          <Dropdown dropdownRender={() => columnMenu} trigger={['click']}>
            <Tooltip title="配置显示列"><Button size="small" icon={<SettingOutlined />} aria-label="配置显示列" /></Tooltip>
          </Dropdown>
        </Space>
      </div>
      <Table<T>
        size={size}
        loading={loading}
        columns={visible}
        dataSource={rows}
        rowKey={rowKey}
        sticky
        virtual
        scroll={{ x: 'max-content', y: maxHeight }}
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: [20, 50, 100, 200], showTotal: (total) => `共 ${total} 条` }}
        onRow={(row) => ({ onClick: () => onRowClick?.(row), className: onRowClick ? 'clickable-row' : '' })}
      />
    </section>
  )
}
