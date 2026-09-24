import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ThemeMode = 'dark' | 'light'

interface AppState {
  theme: ThemeMode
  collapsed: boolean
  tradeDate: string
  tableSize: 'small' | 'middle'
  hiddenColumns: Record<string, string[]>
  toggleTheme: () => void
  setCollapsed: (collapsed: boolean) => void
  setTradeDate: (date: string) => void
  setTableSize: (size: 'small' | 'middle') => void
  setHiddenColumns: (table: string, keys: string[]) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: 'dark',
      collapsed: false,
      tradeDate: '',
      tableSize: 'small',
      hiddenColumns: {},
      toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
      setCollapsed: (collapsed) => set({ collapsed }),
      setTradeDate: (tradeDate) => set({ tradeDate }),
      setTableSize: (tableSize) => set({ tableSize }),
      setHiddenColumns: (table, keys) => set((state) => ({ hiddenColumns: { ...state.hiddenColumns, [table]: keys } })),
    }),
    { name: 'new-astock-ui' },
  ),
)
