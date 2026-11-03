export const EMOTION_COLORS = {
  happy: '#E8A23B',
  sad: '#5B7DB1',
  angry: '#E8552F',
  surprised: '#9B6BD6',
  fear: '#4F8C86',
  neutral: '#8C897F',
}

export const EMOTIONS = ['happy', 'sad', 'angry', 'surprised', 'fear', 'neutral']

export function emotionColor(emotion) {
  return EMOTION_COLORS[emotion] || 'var(--accent)'
}

export function formatDate(value, locale = 'zh-CN', options = {}) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  }).format(date)
}

export function formatDateTime(value, locale = 'zh-CN') {
  return formatDate(value, locale, { hour: '2-digit', minute: '2-digit' })
}

export function formatNumber(value, locale = 'zh-CN') {
  return new Intl.NumberFormat(locale).format(Number(value || 0))
}

export function formatPercent(value, digits = 1) {
  return `${Number(value || 0).toFixed(digits)}%`
}

export function formatDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds || 0)))
  const mins = Math.floor(value / 60)
  const secs = value % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
}

export function relativeTime(value, locale = 'zh-CN') {
  if (!value) return '—'
  const date = new Date(value)
  const diff = date.getTime() - Date.now()
  const abs = Math.abs(diff)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  if (abs < 60_000) return rtf.format(Math.round(diff / 1000), 'second')
  if (abs < 3_600_000) return rtf.format(Math.round(diff / 60_000), 'minute')
  if (abs < 86_400_000) return rtf.format(Math.round(diff / 3_600_000), 'hour')
  if (abs < 2_592_000_000) return rtf.format(Math.round(diff / 86_400_000), 'day')
  return formatDate(value, locale)
}

export function statusType(status) {
  return {
    active: 'success',
    published: 'success',
    resolved: 'success',
    open: 'warning',
    pending: 'warning',
    processing: 'primary',
    draft: 'info',
    closed: 'info',
    disabled: 'danger',
    deleted: 'info',
  }[status] || 'info'
}

export function truncate(text, length = 120) {
  if (!text) return ''
  return text.length > length ? `${text.slice(0, length)}…` : text
}

export function debounce(fn, delay = 320) {
  let timer
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

export function readingMinutes(text) {
  return Math.max(1, Math.round((text || '').length / 380))
}

export function parseUserIds(value) {
  return String(value || '')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((id) => Number.isInteger(id) && id > 0)
}

export function toDateString(date) {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
