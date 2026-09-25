export const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(message: string, public code: string, public requestId = '') { super(message) }
}

export function request<T>(path: string, method: 'GET' | 'POST' = 'GET', data?: unknown, operationId?: string): Promise<T> {
  const token = uni.getStorageSync('fitmind.token')
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${baseUrl}${path}`, method, data: data as Record<string, unknown>, timeout: 60000,
      header: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(operationId ? { 'Idempotency-Key': operationId } : {}) },
      success(response) {
        const body = response.data as { data: T; error?: { code: string; message: string }; request_id: string }
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(body.data)
        else reject(new ApiError(body.error?.message || '请求未完成，请稍后重试。', body.error?.code || 'HTTP_ERROR', body.request_id))
      },
      fail() { reject(new ApiError('连接中断，结果尚未确认。请重试原提交，系统会避免重复保存。', 'NETWORK_ERROR')) },
    })
  })
}

// IDs identify retries, not credentials. Authentication tokens are issued by the server.
export function operationId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.floor(Math.random() * 16)
    return (c === 'x' ? r : (r & 3) | 8).toString(16)
  })
}

export interface FitnessObject {
  id: string; kind: string; payload: Record<string, unknown>; version: number; source: string
}
export interface Receipt { operation_id: string; objects: FitnessObject[]; undoable: boolean }
export interface Turn {
  operation_id: string; text: string; reply: string; status: string; receipts: Receipt[]; model: string
}
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : '请求未完成。' }
