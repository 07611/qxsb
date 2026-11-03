import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi, userApi } from '@/services/api'
import { setAccessToken } from '@/services/http'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)
  const loading = ref(false)
  const lastError = ref(null)
  let bootstrapPromise = null

  const isAuthenticated = computed(() => Boolean(user.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isPending = computed(() => user.value?.status === 'pending')

  function applySession(payload) {
    if (!payload) return
    if (payload.accessToken) setAccessToken(payload.accessToken)
    if (payload.user) user.value = payload.user
  }

  function clearSession() {
    setAccessToken('')
    user.value = null
  }

  async function ensureSession() {
    if (initialized.value) return user.value
    if (bootstrapPromise) return bootstrapPromise
    bootstrapPromise = (async () => {
      loading.value = true
      try {
        const result = await authApi.refresh()
        applySession(result.data)
        return user.value
      } catch {
        clearSession()
        return null
      } finally {
        initialized.value = true
        loading.value = false
        bootstrapPromise = null
      }
    })()
    return bootstrapPromise
  }

  async function login(payload) {
    loading.value = true
    lastError.value = null
    try {
      const result = await authApi.login(payload)
      applySession(result.data)
      initialized.value = true
      return result.data
    } finally {
      loading.value = false
    }
  }

  async function register(payload) {
    loading.value = true
    lastError.value = null
    try {
      const result = await authApi.register(payload)
      applySession(result.data)
      initialized.value = true
      return result.data
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      clearSession()
      initialized.value = true
    }
  }

  async function refreshProfile() {
    if (!user.value) return null
    const result = await authApi.me()
    user.value = result.data.user
    return user.value
  }

  async function updateProfile(payload) {
    const result = await userApi.update(payload)
    user.value = result.data.user
    return user.value
  }

  function setUser(next) {
    user.value = next
  }

  window.addEventListener('mw:session-expired', () => {
    clearSession()
    initialized.value = true
  })
  window.addEventListener('mw:session-refreshed', (event) => {
    if (event.detail?.user) user.value = event.detail.user
    if (event.detail?.accessToken) setAccessToken(event.detail.accessToken)
  })

  return {
    user,
    initialized,
    loading,
    lastError,
    isAuthenticated,
    isAdmin,
    isPending,
    ensureSession,
    login,
    register,
    logout,
    refreshProfile,
    updateProfile,
    setUser,
    clearSession,
  }
})
