import type { ApiResult } from './types'

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      message = body.detail?.message || body.detail || message
    } catch {
      // 非 JSON 错误响应使用默认说明。
    }
    throw new ApiError(String(message), response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<ApiResult<T>>(path),
  raw: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export async function exportRows(
  title: string,
  format: 'csv' | 'xlsx',
  columns: Array<{ key: string; title: string }>,
  rows: Array<Record<string, unknown>>,
): Promise<void> {
  const response = await fetch('/api/v1/exports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, format, columns, rows }),
  })
  if (!response.ok) throw new ApiError('导出失败', response.status)
  const blob = await response.blob()
  const disposition = response.headers.get('content-disposition') || ''
  const matched = disposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
  const filename = matched ? decodeURIComponent(matched[1].replaceAll('"', '')) : `${title}.${format}`
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}
