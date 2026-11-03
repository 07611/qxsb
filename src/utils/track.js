import { getAccessToken } from '@/services/http'

const STORAGE_KEY = 'mw.session.id'
const MAX_QUEUE = 80
const FLUSH_MS = 2400

function createSessionId() {
  const bytes = new Uint8Array(12)
  crypto.getRandomValues(bytes)
  return `s_${Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')}`
}

function getSessionId() {
  let id = sessionStorage.getItem(STORAGE_KEY)
  if (!id) {
    id = createSessionId()
    sessionStorage.setItem(STORAGE_KEY, id)
  }
  return id
}

let queue = []
let timer = null
let flushing = false

function payload(events) {
  return { events }
}

async function flush(useBeacon = false) {
  if (!queue.length || flushing) return
  const batch = queue.splice(0, 100)
  const body = payload(batch)
  if (useBeacon && navigator.sendBeacon) {
    try {
      navigator.sendBeacon('/api/v1/track', new Blob([JSON.stringify(body)], { type: 'application/json' }))
      return
    } catch {
      // fall through to fetch
    }
  }
  flushing = true
  try {
    const headers = { 'Content-Type': 'application/json' }
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch('/api/v1/track', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      keepalive: true,
    })
    if (!response.ok) {
      queue = batch.concat(queue).slice(0, MAX_QUEUE)
    }
  } catch {
    queue = batch.concat(queue).slice(0, MAX_QUEUE)
  } finally {
    flushing = false
  }
}

function schedule() {
  if (timer) return
  timer = setTimeout(() => {
    timer = null
    flush()
  }, FLUSH_MS)
}

export function track(eventKey, props = {}) {
  if (!eventKey || typeof eventKey !== 'string') return
  const event = {
    eventKey,
    sessionId: getSessionId(),
    occurredAt: new Date().toISOString(),
    page: 0,
    props: {
      ...props,
      route: window.location.pathname,
    },
  }
  queue.push(event)
  if (queue.length > MAX_QUEUE) queue = queue.slice(-MAX_QUEUE)
  schedule()
}

export function trackPageview(path) {
  track('page_view', { path })
}

export function flushTracking() {
  return flush(true)
}

window.addEventListener('pagehide', () => {
  flush(true)
})
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flush(true)
})
