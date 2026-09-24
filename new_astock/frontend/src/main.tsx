import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider, theme as antTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import App from './App'
import { useAppStore } from './store'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 5_000, refetchOnWindowFocus: false },
  },
})

function Root() {
  const theme = useAppStore((state) => state.theme)
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme === 'dark' ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#3b82f6',
          colorError: '#ef5350',
          colorSuccess: '#19a974',
          borderRadius: 8,
          fontFamily: 'Inter, "Microsoft YaHei UI", "Microsoft YaHei", sans-serif',
        },
        components: { Table: { headerBg: theme === 'dark' ? '#111a2e' : '#f3f6fb' }, Layout: { bodyBg: theme === 'dark' ? '#080d19' : '#f1f4f9', siderBg: theme === 'dark' ? '#0d1527' : '#ffffff' } },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter><App /></BrowserRouter>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><Root /></StrictMode>)
