import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { emotionApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { compressImage } from '@/utils/image'
import { track } from '@/utils/track'

export const useEmotionStore = defineStore('emotion', () => {
  const result = ref(null)
  const recommendations = ref(null)
  const analyzing = ref(false)
  const loadingRecommendations = ref(false)
  const error = ref(null)
  const recommendationError = ref(null)
  const sourcePreview = ref('')
  const sourceKind = ref('upload')
  let sequence = 0

  const emotion = computed(() => result.value?.emotion || '')
  const scores = computed(() => result.value?.scores || {})
  const topTracks = computed(() => {
    if (!recommendations.value) return []
    return [...(recommendations.value.local || []), ...(recommendations.value.online || [])]
  })

  async function loadRecommendations(emotionCode) {
    if (!emotionCode) return
    loadingRecommendations.value = true
    recommendationError.value = null
    try {
      const response = await emotionApi.recommendations(emotionCode, { limit: 8, includeOnline: true })
      recommendations.value = response.data
      track('recommendation_viewed', {
        emotion: emotionCode,
        localCount: response.data.local?.length || 0,
        onlineCount: response.data.online?.length || 0,
      })
      return response.data
    } catch (err) {
      recommendationError.value = normalizeError(err)
      recommendations.value = null
      return null
    } finally {
      loadingRecommendations.value = false
    }
  }

  async function analyzeFile(file, { source = 'upload' } = {}) {
    const current = ++sequence
    analyzing.value = true
    error.value = null
    recommendationError.value = null
    sourceKind.value = source
    sourcePreview.value = ''
    try {
      const compressed = await compressImage(file, { maxSide: 1280, quality: 0.87 })
      sourcePreview.value = URL.createObjectURL(compressed)
      track('emotion_scan_started', { source })
      const response = await emotionApi.analyze({ file: compressed, source })
      if (current !== sequence) return null
      result.value = response.data
      track('emotion_detected', {
        emotion: response.data.emotion,
        confidence: response.data.confidence,
        source,
        inferenceMs: response.data.inferenceMs,
      })
      await loadRecommendations(response.data.emotion)
      return response.data
    } catch (err) {
      if (current === sequence) error.value = normalizeError(err)
      return null
    } finally {
      if (current === sequence) analyzing.value = false
    }
  }

  async function analyzeDemo(demo) {
    const current = ++sequence
    analyzing.value = true
    error.value = null
    recommendationError.value = null
    sourceKind.value = 'demo'
    sourcePreview.value = demo.url
    try {
      track('emotion_scan_started', { source: 'demo', demoId: demo.id })
      const response = await emotionApi.analyze({ demoId: demo.id, source: 'demo' })
      if (current !== sequence) return null
      result.value = response.data
      track('emotion_detected', {
        emotion: response.data.emotion,
        confidence: response.data.confidence,
        source: 'demo',
        demoId: demo.id,
      })
      await loadRecommendations(response.data.emotion)
      return response.data
    } catch (err) {
      if (current === sequence) error.value = normalizeError(err)
      return null
    } finally {
      if (current === sequence) analyzing.value = false
    }
  }

  function clear() {
    sequence += 1
    result.value = null
    recommendations.value = null
    error.value = null
    recommendationError.value = null
    analyzing.value = false
    loadingRecommendations.value = false
    if (sourcePreview.value?.startsWith('blob:')) URL.revokeObjectURL(sourcePreview.value)
    sourcePreview.value = ''
  }

  return {
    result,
    recommendations,
    analyzing,
    loadingRecommendations,
    error,
    recommendationError,
    sourcePreview,
    sourceKind,
    emotion,
    scores,
    topTracks,
    analyzeFile,
    analyzeDemo,
    loadRecommendations,
    clear,
  }
})
