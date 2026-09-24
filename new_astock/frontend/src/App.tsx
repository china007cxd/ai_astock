import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ErrorBoundary } from './components/ErrorBoundary'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const LimitUp = lazy(() => import('./pages/LimitUp'))
const Auction = lazy(() => import('./pages/Auction'))
const Sectors = lazy(() => import('./pages/Sectors'))
const Intelligence = lazy(() => import('./pages/Intelligence'))
const StockCenter = lazy(() => import('./pages/StockCenter'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Screener = lazy(() => import('./pages/Screener'))
const History = lazy(() => import('./pages/History'))
const Settings = lazy(() => import('./pages/Settings'))

const fallback = <div className="page-loading"><span className="pulse-dot" />正在加载模块...</div>

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={fallback}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="limit-up" element={<LimitUp />} />
            <Route path="auction" element={<Auction />} />
            <Route path="sectors" element={<Sectors />} />
            <Route path="intelligence" element={<Intelligence />} />
            <Route path="stock/:code" element={<StockCenter />} />
            <Route path="watchlist" element={<Watchlist />} />
            <Route path="screener" element={<Screener />} />
            <Route path="history" element={<History />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
