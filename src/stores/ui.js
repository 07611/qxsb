import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import i18n from '@/i18n'
import { useAuthStore } from './auth'
import { userApi } from '@/services/api'

export const useUiStore = defineStore('ui', () => {
  const storedTheme = localStorage.getItem('mw.theme') || 'light'
  const theme = ref(storedTheme)
  const locale = ref(localStorage.getItem('mw.locale') || i18n.global.locale.value)
  const searchOpen = ref(false)

  const isDark = computed(() => theme.value === 'dark')

  function applyTheme() {
    document.documentElement.dataset.theme = theme.value
    document.documentElement.style.colorScheme = theme.value === 'dark' ? 'dark' : 'light'
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', theme.value === 'dark' ? '#141416' : '#FBFAF7')
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('mw.theme', theme.value)
    applyTheme()
  }

  async function setLocale(next) {
    if (!['zh-CN', 'en-US'].includes(next)) return
    locale.value = next
    i18n.global.locale.value = next
    localStorage.setItem('mw.locale', next)
    document.documentElement.lang = next
    const auth = useAuthStore()
    if (auth.isAuthenticated) {
      try {
        const result = await userApi.update({ locale: next })
        auth.setUser(result.data.user)
      } catch {
        // 语言偏好已本地持久化，服务端同步失败不阻塞切换
      }
    }
  }

  function init() {
    applyTheme()
    document.documentElement.lang = locale.value
    i18n.global.locale.value = locale.value
  }

  return { theme, locale, isDark, searchOpen, init, toggleTheme, setLocale }
})
