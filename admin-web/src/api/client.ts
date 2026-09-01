import type { ApiEnvelope, ApiErrorEnvelope } from '@/types'

const API_BASE = '/api/admin/v1'
let csrfToken = sessionStorage.getItem('yuepai_admin_csrf') || ''

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public requestId = '',
    public details: Record<string, unknown> = {},
  ) {
    super(message)
  }
}

export function setCsrfToken(value: string): void {
  csrfToken = value
  if (value) sessionStorage.setItem('yuepai_admin_csrf', value)
  else sessionStorage.removeItem('yuepai_admin_csrf')
}

function redirectExpiredSession(path: string): void {
  if (path === '/auth/me' || path === '/auth/login' || location.pathname.endsWith('/login')) return
  const redirect = `${location.pathname.replace(/^\/admin/, '')}${location.search}` || '/dashboard'
  location.assign(`/admin/login?expired=1&redirect=${encodeURIComponent(redirect)}`)
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (options.method && !['GET', 'HEAD'].includes(options.method.toUpperCase()) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      ...options,
      headers,
    })
  } catch {
    throw new ApiError('网络连接失败，请检查服务器状态。', 'NETWORK_ERROR', 0)
  }

  let payload: ApiEnvelope<T> | ApiErrorEnvelope | null = null
  try {
    payload = (await response.json()) as ApiEnvelope<T> | ApiErrorEnvelope
  } catch {
    payload = null
  }
  if (!response.ok || !payload || 'error' in payload) {
    const error = payload && 'error' in payload
      ? payload.error
      : { code: 'HTTP_ERROR', message: response.status >= 500 ? '服务暂时不可用。' : '请求失败。', details: {} }
    const requestId = payload?.request_id || response.headers.get('X-Request-ID') || ''
    if (response.status === 401) {
      setCsrfToken('')
      redirectExpiredSession(path)
    }
    throw new ApiError(error.message, error.code, response.status, requestId, error.details || {})
  }
  return payload.data
}

export const get = <T>(path: string) => api<T>(path)
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const put = <T>(path: string, body: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' })
