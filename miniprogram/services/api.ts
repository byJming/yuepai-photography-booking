import { API_BASE_URL, CLIENT_VERSION, REQUEST_TIMEOUT_MS } from '../config'
import type { ApiEnvelope, ApiErrorEnvelope } from './types'

const TOKEN_STORAGE_KEY = 'yuepai_customer_session'
let loginPromise: Promise<string> | null = null

interface StoredSession {
  accessToken: string
  expiresAt: number
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  data?: Record<string, any>
  headers?: Record<string, string>
  auth?: boolean
  retryGet?: boolean
  retriedAuth?: boolean
}

export class ApiError extends Error {
  code: string
  status: number
  requestId: string
  details: Record<string, any>

  constructor(
    message: string,
    code = 'REQUEST_FAILED',
    status = 0,
    requestId = '',
    details: Record<string, any> = {}
  ) {
    super(message)
    this.code = code
    this.status = status
    this.requestId = requestId
    this.details = details
  }
}

function requestId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function sdkVersion(): string {
  try {
    if (typeof wx.getAppBaseInfo !== 'function') return 'unknown'
    return String(wx.getAppBaseInfo().SDKVersion || 'unknown')
  } catch (_error) {
    return 'unknown'
  }
}

function readSession(): StoredSession | null {
  const session = wx.getStorageSync(TOKEN_STORAGE_KEY) as StoredSession | undefined
  if (!session || !session.accessToken || session.expiresAt <= Date.now() + 60000) {
    wx.removeStorageSync(TOKEN_STORAGE_KEY)
    return null
  }
  return session
}

function saveSession(accessToken: string, expiresIn: number): void {
  wx.setStorageSync(TOKEN_STORAGE_KEY, {
    accessToken,
    expiresAt: Date.now() + expiresIn * 1000
  })
}

export function clearSession(): void {
  wx.removeStorageSync(TOKEN_STORAGE_KEY)
}

function wxLogin(): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.login({
      timeout: REQUEST_TIMEOUT_MS,
      success(result: any) {
        if (result.code) resolve(result.code)
        else reject(new ApiError('微信登录失败，请稍后重试。', 'WECHAT_LOGIN_FAILED'))
      },
      fail() {
        reject(new ApiError('微信登录失败，请检查网络后重试。', 'NETWORK_ERROR'))
      }
    })
  })
}

function rawRequest<T>(path: string, options: RequestOptions): Promise<T> {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      timeout: REQUEST_TIMEOUT_MS,
      header: {
        'Content-Type': 'application/json',
        'X-Client-Version': CLIENT_VERSION,
        'X-Wechat-SDK-Version': sdkVersion(),
        'X-Request-ID': requestId(),
        ...(options.headers || {})
      },
      success(response: any) {
        const payload = response.data as ApiEnvelope<T> | ApiErrorEnvelope
        if (response.statusCode >= 200 && response.statusCode < 300 && payload && 'data' in payload) {
          resolve(payload.data)
          return
        }
        const errorPayload = payload && 'error' in payload ? payload : null
        reject(new ApiError(
          errorPayload?.error.message || '请求失败，请稍后重试。',
          errorPayload?.error.code || 'HTTP_ERROR',
          response.statusCode,
          errorPayload?.request_id || response.header?.['X-Request-ID'] || '',
          errorPayload?.error.details || {}
        ))
      },
      fail() {
        reject(new ApiError('网络连接失败，请检查网络后重试。', 'NETWORK_ERROR'))
      }
    })
  })
}

export async function ensureSession(force = false): Promise<string> {
  if (!force) {
    const session = readSession()
    if (session) return session.accessToken
  }
  if (loginPromise) return loginPromise
  loginPromise = (async () => {
    clearSession()
    const code = await wxLogin()
    const result = await rawRequest<{ access_token: string; expires_in: number }>(
      '/auth/wechat-login',
      { method: 'POST', data: { code } }
    )
    saveSession(result.access_token, result.expires_in)
    return result.access_token
  })()
  try {
    return await loginPromise
  } finally {
    loginPromise = null
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = { ...(options.headers || {}) }
  if (options.auth) {
    headers.Authorization = `Bearer ${await ensureSession()}`
  }
  try {
    return await rawRequest<T>(path, { ...options, headers })
  } catch (error) {
    const apiError = error as ApiError
    if (options.auth && apiError.status === 401 && !options.retriedAuth) {
      clearSession()
      const token = await ensureSession(true)
      return rawRequest<T>(path, {
        ...options,
        retriedAuth: true,
        headers: { ...headers, Authorization: `Bearer ${token}` }
      })
    }
    if ((options.method || 'GET') === 'GET' && options.retryGet !== false && apiError.code === 'NETWORK_ERROR') {
      await new Promise((resolve) => setTimeout(resolve, 350))
      return rawRequest<T>(path, { ...options, retryGet: false, headers })
    }
    throw apiError
  }
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST', auth: true })
  } finally {
    clearSession()
  }
}

export function createIdempotencyKey(): string {
  return `booking-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}
