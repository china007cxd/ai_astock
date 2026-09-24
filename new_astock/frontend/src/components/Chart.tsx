import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart, GaugeChart, LineChart, PieChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'

import { useAppStore } from '../store'

echarts.use([
  BarChart,
  CandlestickChart,
  GaugeChart,
  LineChart,
  PieChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

interface ChartProps {
  option: EChartsCoreOption
  height?: number
  ariaLabel: string
}

export function Chart({ option, height = 300, ariaLabel }: ChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const theme = useAppStore((state) => state.theme)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current, theme === 'dark' ? 'dark' : undefined, { renderer: 'canvas' })
    chart.setOption({ backgroundColor: 'transparent', animationDuration: 350, ...option })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => {
      observer.disconnect()
      chart.dispose()
    }
  }, [option, theme])

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ width: '100%', height }} />
}
