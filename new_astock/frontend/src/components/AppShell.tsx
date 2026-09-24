import { useState } from 'react'
import { AutoComplete, Button, DatePicker, Layout, Menu, Space, Spin, Tooltip, Typography } from 'antd'
import {
  ApartmentOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  BulbOutlined,
  CalendarOutlined,
  FireOutlined,
  FundOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  SearchOutlined,
  SettingOutlined,
  StarOutlined,
  SunOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAppStore } from '../store'
import type { Quote } from '../types'

const { Header, Sider, Content } = Layout
const menuItems = [
  { key: '/dashboard', icon: <AreaChartOutlined />, label: '大盘复盘' },
  { key: '/limit-up', icon: <FireOutlined />, label: '涨停复盘' },
  { key: '/auction', icon: <ThunderboltOutlined />, label: '竞价异动' },
  { key: '/sectors', icon: <ApartmentOutlined />, label: '板块题材' },
  { key: '/intelligence', icon: <BulbOutlined />, label: '龙虎资讯' },
  { key: '/stock/000001', icon: <FundOutlined />, label: '个股中心' },
  { key: '/watchlist', icon: <StarOutlined />, label: '自选股' },
  { key: '/screener', icon: <BarChartOutlined />, label: '智能选股' },
  { key: '/history', icon: <CalendarOutlined />, label: '历史导出' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
]

export function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const [search, setSearch] = useState('')
  const collapsed = useAppStore((state) => state.collapsed)
  const setCollapsed = useAppStore((state) => state.setCollapsed)
  const theme = useAppStore((state) => state.theme)
  const toggleTheme = useAppStore((state) => state.toggleTheme)
  const tradeDate = useAppStore((state) => state.tradeDate)
  const setTradeDate = useAppStore((state) => state.setTradeDate)
  const { data, isFetching } = useQuery({
    queryKey: ['search', search],
    queryFn: () => api.get<Quote[]>(`/api/v1/stocks/search?q=${encodeURIComponent(search)}`),
    enabled: search.trim().length > 0,
    staleTime: 60_000,
  })
  const active = menuItems.find((item) => location.pathname.startsWith(item.key.split('/').slice(0, 2).join('/')))?.key
  return (
    <Layout className="app-layout">
      <Sider collapsible collapsed={collapsed} trigger={null} width={216} className="app-sider">
        <div className="brand" aria-label="new_astock">
          <span className="brand-mark">N</span>
          {!collapsed && <div><strong>new_astock</strong><small>复盘工作台</small></div>}
        </div>
        <Menu mode="inline" selectedKeys={[active || location.pathname]} items={menuItems} onClick={({ key }) => navigate(key)} />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size="middle">
            <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} aria-label="切换导航" />
            <AutoComplete
              value={search}
              onChange={setSearch}
              onSelect={(code) => { navigate(`/stock/${code}`); setSearch('') }}
              options={(data?.data || []).map((stock) => ({ value: stock.code, label: `${stock.code}  ${stock.name}` }))}
              style={{ width: 280 }}
              placeholder="搜索股票代码或名称"
              suffixIcon={isFetching ? <Spin size="small" /> : <SearchOutlined />}
            />
          </Space>
          <Space>
            <DatePicker value={tradeDate ? dayjs(tradeDate) : null} onChange={(value) => setTradeDate(value?.format('YYYY-MM-DD') || '')} allowClear placeholder="实时 / 选择交易日" />
            <Tooltip title={theme === 'dark' ? '切换浅色' : '切换深色'}>
              <Button type="text" icon={theme === 'dark' ? <SunOutlined /> : <MoonOutlined />} onClick={toggleTheme} aria-label="切换主题" />
            </Tooltip>
            <Typography.Text className="market-clock">A股市场</Typography.Text>
          </Space>
        </Header>
        <Content className="app-content"><Outlet /></Content>
      </Layout>
    </Layout>
  )
}
