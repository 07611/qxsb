import axios from 'axios'
import { ElMessage } from 'element-plus'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

let accessToken = ''
let refreshPromise = null
let lastRequestId = ''

export function setAccessToken(token) {
  accessToken = token || ''
}

export function getAccessToken() {
  return accessToken
}

export function getLastRequestId() {
  return lastRequestId
}

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  timeout: 25000,
  headers: { Accept: 'application/json' },
})

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  if (['post', 'put', 'patch', 'delete'].includes((config.method || '').toLowerCase())) {
    if (!config.headers['X-Idempotency-Key']) {
      config.headers['X-Idempotency-Key'] = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`
    }
  }
  return config
})

export function normalizeError(error) {
  if (!error) return { message: 'UNKNOWN', status: 0 }
  if (error.__normalized) return error
  const response = error.response
  const payload = response?.data
  let message = payload?.message || error.message || '请求失败'
  if (!response) {
    message = error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络连接失败，请检查网络后重试'
  }
  const normalized = {
    message,
    status: response?.status || 0,
    code: payload?.code,
    data: payload?.data,
    fieldErrors: {},
    requestId: payload?.requestId || response?.headers?.['x-request-id'] || '',
    retryAfter: response?.headers?.['retry-after'] || payload?.data?.retryAfter,
    __normalized: true,
  }
  for (const item of payload?.data?.errors || []) {
    if (item.field) normalized.fieldErrors[item.field] = item.message
  }
  return normalized
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true, timeout: 12000 })
      .then((response) => {
        const payload = response.data?.data
        if (!payload?.accessToken) throw new Error('missing access token')
        setAccessToken(payload.accessToken)
        window.dispatchEvent(new CustomEvent('mw:session-refreshed', { detail: payload }))
        return payload
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export { refreshAccessToken }

api.interceptors.response.use(
  (response) => {
    lastRequestId = response.headers?.['x-request-id'] || lastRequestId
    return response.data
  },
  async (error) => {
    const response = error.response
    lastRequestId = response?.headers?.['x-request-id'] || lastRequestId
    const config = error.config || {}
    const isAuthRequest = /\/auth\/(login|register|refresh|logout|password)/.test(config.url || '')
    if (response?.status === 401 && !config._retried && !isAuthRequest) {
      config._retried = true
      try {
        const refreshed = await refreshAccessToken()
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${refreshed.accessToken}`
        return api.request(config)
      } catch {
        setAccessToken('')
        window.dispatchEvent(new CustomEvent('mw:session-expired'))
      }
    }
    return Promise.reject(normalizeError(error))
  },
)

export function toastError(error, fallback = '操作失败') {
  const normalized = normalizeError(error)
  ElMessage.error(normalized.message && normalized.message !== 'UNKNOWN' ? normalized.message : fallback)
  return normalized
}

export default api
