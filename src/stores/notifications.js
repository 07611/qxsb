import { ref } from 'vue'
import { defineStore } from 'pinia'
import { socialApi } from '@/services/api'

export const useNotificationStore = defineStore('notifications', () => {
  const unread = ref(0)
  const loading = ref(false)

  async function fetchUnread() {
    loading.value = true
    try {
      const result = await socialApi.unreadCount()
      unread.value = result.data.count
      return unread.value
    } catch {
      unread.value = 0
      return 0
    } finally {
      loading.value = false
    }
  }

  function decrement(count = 1) {
    unread.value = Math.max(0, unread.value - count)
  }

  function setUnread(count) {
    unread.value = Math.max(0, Number(count) || 0)
  }

  function clear() {
    unread.value = 0
  }

  return { unread, loading, fetchUnread, decrement, setUnread, clear }
})
