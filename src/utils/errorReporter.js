import { getLastRequestId } from '@/services/http'

let installed = false
let reported = 0
const limitWindow = 60_000
let windowStart = Date.now()

function shouldReport() {
  const now = Date.now()
  if (now - windowStart > limitWindow) {
    windowStart = now
    reported = 0
  }
  if (reported >= 5) return false
  reported += 1
  return true
}

function report(payload) {
  if (!shouldReport()) return
  try {
    const body = JSON.stringify({
      level: 'error',
      route: window.location.pathname + window.location.search,
      requestId: getLastRequestId(),
      ...payload,
    })
    fetch('/api/v1/logs/client', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {})
  } catch {
    // 忽略上报失败，禁止形成错误递归
  }
}

export function installErrorReporting(app) {
  if (installed) return
  installed = true

  app.config.errorHandler = (error, instance, info) => {
    console.error('[Moodwave] Vue error:', error, info)
    report({
      message: String(error?.message || error || 'Vue error'),
      stack: error?.stack,
      context: { info, component: instance?.$options?.name || instance?.$options?.__name || 'unknown' },
    })
  }

  window.addEventListener('error', (event) => {
    if (!event.error && !event.message) return
    report({
      message: event.message || 'Window error',
      stack: event.error?.stack,
      context: { source: event.filename, line: event.lineno, column: event.colno },
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    report({
      message: String(reason?.message || reason || 'Unhandled rejection'),
      stack: reason?.stack,
      context: { type: 'unhandledrejection' },
    })
  })
}
