import { describe, expect, it } from 'vitest'
import { ApiError } from './api'

describe('ApiError', () => {
  it('保留 HTTP 状态码与错误信息', () => {
    const error = new ApiError('数据源不可用', 503)
    expect(error.message).toBe('数据源不可用')
    expect(error.status).toBe(503)
  })
})
