import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { emotionApi } from '@/services/api'
import { track } from '@/utils/track'

export const usePlayerStore = defineStore('player', () => {
  const current = ref(null)
  const queue = ref([])
  const index = ref(-1)
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const volume = ref(Number(localStorage.getItem('mw.volume') || 0.72))
  const error = ref('')

  const hasTrack = computed(() => Boolean(current.value?.audioUrl))
  const progress = computed(() => (duration.value ? (currentTime.value / duration.value) * 100 : 0))
  const isLocal = computed(() => current.value?.source === 'local' && Number.isInteger(Number(current.value?.id)))

  function setMeta({ currentTime: time, duration: total }) {
    if (typeof time === 'number') currentTime.value = time
    if (typeof total === 'number') duration.value = total
  }

  function setVolume(next) {
    volume.value = Math.min(1, Math.max(0, Number(next)))
    localStorage.setItem('mw.volume', String(volume.value))
  }

  async function play(trackItem, trackQueue = null) {
    if (!trackItem?.audioUrl) return
    if (current.value?.id === trackItem.id && current.value?.source === trackItem.source && isPlaying.value) {
      return
    }
    error.value = ''
    current.value = trackItem
    if (trackQueue) queue.value = trackQueue
    else if (!queue.value.length) queue.value = [trackItem]
    index.value = queue.value.findIndex((item) => String(item.id) === String(trackItem.id) && item.source === trackItem.source)
    isPlaying.value = true
    if (isLocal.value) {
      try {
        await emotionApi.play(Number(trackItem.id))
      } catch {
        // 播放统计失败不阻塞音频
      }
    }
    track('music_play', { trackId: String(trackItem.id), source: trackItem.source, mood: trackItem.mood })
  }

  function toggle() {
    if (!current.value) return
    isPlaying.value = !isPlaying.value
  }

  function pause() {
    isPlaying.value = false
  }

  function next() {
    if (!queue.value.length) return
    const nextIndex = (index.value + 1) % queue.value.length
    const item = queue.value[nextIndex]
    index.value = nextIndex
    current.value = item
    isPlaying.value = true
  }

  function previous() {
    if (!queue.value.length) return
    const nextIndex = (index.value - 1 + queue.value.length) % queue.value.length
    const item = queue.value[nextIndex]
    index.value = nextIndex
    current.value = item
    isPlaying.value = true
  }

  function close() {
    current.value = null
    isPlaying.value = false
    currentTime.value = 0
    duration.value = 0
  }

  function reportError(message = '音频加载失败') {
    error.value = message
    isPlaying.value = false
  }

  return {
    current,
    queue,
    index,
    isPlaying,
    currentTime,
    duration,
    volume,
    error,
    hasTrack,
    progress,
    play,
    toggle,
    pause,
    next,
    previous,
    close,
    setMeta,
    setVolume,
    reportError,
  }
})
