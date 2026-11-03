import api from './http'

export const authApi = {
  async login(payload) {
    return api.post('/auth/login', payload)
  },
  async register(payload) {
    return api.post('/auth/register', payload)
  },
  async refresh() {
    return api.post('/auth/refresh', {})
  },
  async logout() {
    return api.post('/auth/logout', {})
  },
  async me() {
    return api.get('/auth/me')
  },
  async sessions() {
    return api.get('/auth/sessions')
  },
  async revokeSession(id) {
    return api.delete(`/auth/sessions/${id}`)
  },
  async sendCode(payload) {
    return api.post('/auth/code/send', payload)
  },
  async verifyCode(payload) {
    return api.post('/auth/code/verify', payload)
  },
  async forgot(email) {
    return api.post('/auth/password/forgot', { email })
  },
  async reset(payload) {
    return api.post('/auth/password/reset', payload)
  },
  oauthUrl(provider) {
    const base = import.meta.env.VITE_API_ORIGIN || ''
    return `${base}/api/v1/auth/oauth/${provider}`
  },
}

export const userApi = {
  async me() {
    return api.get('/users/me')
  },
  async update(payload) {
    return api.patch('/users/me', payload)
  },
  async uploadAvatar(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/users/me/avatar', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  async permissions() {
    return api.get('/permissions')
  },
  async requestContact(payload) {
    return api.post('/users/me/contact/request', payload)
  },
  async confirmContact(payload) {
    return api.post('/users/me/contact/confirm', payload)
  },
  async changePassword(payload) {
    return api.post('/users/me/password', payload)
  },
  async pushSettings() {
    return api.get('/users/me/push-settings')
  },
  async updatePushSettings(settings) {
    return api.patch('/users/me/push-settings', { settings })
  },
}

export const emotionApi = {
  async demos() {
    return api.get('/emotion/demos')
  },
  async analyze({ file, demoId, source = 'upload' }) {
    const form = new FormData()
    if (file) form.append('file', file)
    if (demoId) form.append('demoId', demoId)
    form.append('source', source)
    return api.post('/emotion/analyze', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
  },
  async recommendations(emotion, { limit = 8, includeOnline = true } = {}) {
    return api.get('/music/recommendations', { params: { emotion, limit, includeOnline } })
  },
  async algorithm() {
    return api.get('/music/algorithm')
  },
  async emotions() {
    return api.get('/music/emotions')
  },
  async history(params = {}) {
    return api.get('/emotion/history', { params })
  },
  async favorites() {
    return api.get('/music/favorites')
  },
  async favorite(trackId) {
    return api.post(`/music/${trackId}/favorite`)
  },
  async unfavorite(trackId) {
    return api.delete(`/music/${trackId}/favorite`)
  },
  async feedback(trackId, rating) {
    return api.post(`/music/${trackId}/feedback`, { rating })
  },
  async play(trackId) {
    return api.post(`/music/${trackId}/play`)
  },
  async recommendationHistory(params = {}) {
    return api.get('/music/history', { params })
  },
  async online(mood) {
    return api.get('/music/online', { params: { mood } })
  },
  async local(params = {}) {
    return api.get('/music/local', { params })
  },
}

export const contentApi = {
  async items(params = {}) {
    return api.get('/items', { params })
  },
  async item(id) {
    return api.get(`/items/${id}`)
  },
  async create(payload) {
    return api.post('/items', payload)
  },
  async update(id, payload) {
    return api.put(`/items/${id}`, payload)
  },
  async remove(id) {
    return api.delete(`/items/${id}`)
  },
  async categories() {
    return api.get('/categories')
  },
  async category(slug) {
    return api.get(`/categories/${slug}`)
  },
  async tags(params = {}) {
    return api.get('/tags', { params })
  },
  async tag(slug) {
    return api.get(`/tags/${slug}`)
  },
  async createCategory(payload) {
    return api.post('/admin/categories', payload)
  },
  async search(params) {
    return api.get('/search', { params })
  },
  async hotSearch() {
    return api.get('/search/hot')
  },
  async share(payload) {
    return api.post('/shares', payload)
  },
  async getShare(code) {
    return api.get(`/shares/${code}`)
  },
}

export const uploadApi = {
  async presign(payload) {
    return api.post('/upload/presign', payload)
  },
  async register(payload) {
    return api.post('/attachments', payload)
  },
  async remove(id) {
    return api.delete(`/attachments/${id}`)
  },
  async put(uploadUrl, file, mime) {
    const relative = uploadUrl.startsWith('/api/v1') ? uploadUrl.slice(7) : uploadUrl
    return api.put(relative, file, { headers: { 'Content-Type': mime }, timeout: 60000 })
  },
}

export const socialApi = {
  async notifications(params = {}) {
    return api.get('/notifications', { params })
  },
  async unreadCount() {
    return api.get('/notifications/unread-count')
  },
  async markRead(id) {
    return api.patch(`/notifications/${id}/read`)
  },
  async markAllRead() {
    return api.patch('/notifications/read-all')
  },
  async banners(position = 'home') {
    return api.get('/banners', { params: { position } })
  },
  async feedback(payload) {
    return api.post('/feedback', payload)
  },
  async myFeedback(params = {}) {
    return api.get('/users/me/feedback', { params })
  },
  async supplement(id, content) {
    return api.post(`/feedback/${id}/supplement`, { content })
  },
  async meta() {
    return api.get('/meta')
  },
  async i18n(locale) {
    return api.get(`/i18n/${locale}`)
  },
  async reportClientLog(payload) {
    return api.post('/logs/client', payload)
  },
  async track(payload) {
    return api.post('/track', payload)
  },
}

export const adminApi = {
  async stats() {
    return api.get('/admin/stats')
  },
  async users(params = {}) {
    return api.get('/admin/users', { params })
  },
  async changeRole(id, role) {
    return api.patch(`/admin/users/${id}/role`, { role })
  },
  async approve(id, approved = true, reason = '') {
    return api.patch(`/admin/users/${id}/approve`, { approved, reason })
  },
  async inviteCodes() {
    return api.get('/admin/invite-codes')
  },
  async createInvite(payload) {
    return api.post('/admin/invite-codes', payload)
  },
  async feedback(params = {}) {
    return api.get('/admin/feedback', { params })
  },
  async replyFeedback(id, payload) {
    return api.patch(`/admin/feedback/${id}`, payload)
  },
  async emailTest(to) {
    return api.post('/admin/emails/test', { to })
  },
  async emailLogs(params = {}) {
    return api.get('/admin/emails', { params })
  },
  async push(payload) {
    return api.post('/admin/push/send', payload)
  },
  async pushChannels() {
    return api.get('/admin/push/channels')
  },
  async banners() {
    return api.get('/admin/banners')
  },
  async createBanner(payload) {
    return api.post('/admin/banners', payload)
  },
  async updateBanner(id, payload) {
    return api.patch(`/admin/banners/${id}`, payload)
  },
  async deleteBanner(id) {
    return api.delete(`/admin/banners/${id}`)
  },
  async report(type, params = {}) {
    return api.get(`/reports/${type}`, { params, responseType: params.responseType })
  },
  async reportCsv(type, params = {}) {
    return api.get(`/reports/${type}`, { params: { ...params, format: 'csv' }, responseType: 'blob' })
  },
  async analyticsSummary(params = {}) {
    return api.get('/admin/analytics/summary', { params })
  },
  async funnels() {
    return api.get('/admin/analytics/funnels')
  },
  async createFunnel(payload) {
    return api.post('/admin/analytics/funnels', payload)
  },
  async funnel(params = {}) {
    return api.get('/admin/analytics/funnel', { params })
  },
  async retention(params = {}) {
    return api.get('/admin/analytics/retention', { params })
  },
  async events(params = {}) {
    return api.get('/admin/analytics/events', { params })
  },
  async definitions() {
    return api.get('/admin/analytics/definitions')
  },
  async auditLogs(params = {}) {
    return api.get('/admin/audit-logs', { params })
  },
  async clientErrors(params = {}) {
    return api.get('/admin/client-errors', { params })
  },
}
