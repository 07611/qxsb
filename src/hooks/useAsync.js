import { ref } from 'vue'
import { normalizeError } from '@/services/http'

export function useAsync(loader, { immediate = false, initial = null } = {}) {
  const data = ref(initial)
  const loading = ref(false)
  const error = ref(null)
  let requestId = 0

  async function run(...args) {
    const current = ++requestId
    loading.value = true
    error.value = null
    try {
      const result = await loader(...args)
      if (current === requestId) data.value = result
      return result
    } catch (err) {
      if (current === requestId) error.value = normalizeError(err)
      throw err
    } finally {
      if (current === requestId) loading.value = false
    }
  }

  if (immediate) run()

  return { data, loading, error, run }
}
