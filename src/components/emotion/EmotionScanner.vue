<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEmotionStore } from '@/stores/emotion'
import { emotionApi } from '@/services/api'
import { validateImage, captureFrame } from '@/utils/image'
import { emotionColor } from '@/utils/format'
import EmotionDial from './EmotionDial.vue'

const { t } = useI18n()
const store = useEmotionStore()

const mode = ref('image')
const demos = ref([])
const demosLoading = ref(true)
const dragOver = ref(false)
const fileInput = ref(null)
const videoInput = ref(null)
const videoEl = ref(null)
const videoFile = ref(null)
const videoUrl = ref('')
const cameraOn = ref(false)
const liveScan = ref(false)
const cameraBusy = ref(false)
const cameraError = ref('')
const localFileError = ref('')
const liveTimer = ref(null)
let cameraStream = null
let videoScanTimer = null

const scores = computed(() => store.result?.scores || {})
const orderedScores = computed(() =>
  ['happy', 'sad', 'angry', 'surprised', 'fear', 'neutral']
    .map((key) => ({ key, value: scores.value[key] || 0, color: emotionColor(key) }))
    .sort((a, b) => b.value - a.value),
)
const hasPreview = computed(() => Boolean(store.sourcePreview))
const resultColor = computed(() => emotionColor(store.result?.emotion))
const aspect = computed(() => {
  if (!store.result?.imageWidth || !store.result?.imageHeight) return '4 / 3'
  return `${store.result.imageWidth} / ${store.result.imageHeight}`
})
const canScrollToRecommendations = computed(() => Boolean(store.result?.emotion))
const box = computed(() => store.result?.box || null)

async function loadDemos() {
  demosLoading.value = true
  try {
    const response = await emotionApi.demos()
    demos.value = response.data.items || []
  } catch {
    demos.value = []
  } finally {
    demosLoading.value = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function handleFile(file) {
  localFileError.value = ''
  const error = validateImage(file)
  if (error) {
    localFileError.value = error
    return
  }
  mode.value = 'image'
  await store.analyzeFile(file, { source: 'upload' })
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (file) handleFile(file)
  event.target.value = ''
}

function onDrop(event) {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) handleFile(file)
}

async function chooseDemo(demo) {
  stopCamera()
  stopVideoAuto()
  mode.value = 'image'
  localFileError.value = ''
  await store.analyzeDemo(demo)
}

async function startCamera() {
  cameraError.value = ''
  if (cameraOn.value) return
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraError.value = t('viewer.cameraError')
    return
  }
  cameraBusy.value = true
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    })
    cameraOn.value = true
    await nextTick()
    if (videoEl.value) {
      videoEl.value.srcObject = cameraStream
      await videoEl.value.play()
    }
  } catch {
    cameraError.value = t('viewer.cameraError')
    cameraOn.value = false
  } finally {
    cameraBusy.value = false
  }
}

function stopCamera() {
  stopLive()
  liveScan.value = false
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop())
    cameraStream = null
  }
  if (videoEl.value) videoEl.value.srcObject = null
  cameraOn.value = false
}

async function snapshot(source = 'camera') {
  if (!videoEl.value || !cameraOn.value) return
  try {
    const frame = await captureFrame(videoEl.value)
    mode.value = 'camera'
    await store.analyzeFile(frame, { source })
  } catch (error) {
    localFileError.value = error.message || t('viewer.cameraError')
  }
}

function startLive() {
  liveScan.value = true
  if (liveTimer.value) clearInterval(liveTimer.value)
  snapshot('camera')
  liveTimer.value = setInterval(() => {
    if (!store.analyzing && cameraOn.value) snapshot('camera')
  }, 5200)
}

function stopLive() {
  liveScan.value = false
  if (liveTimer.value) {
    clearInterval(liveTimer.value)
    liveTimer.value = null
  }
}

function onVideoChoose(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!['video/mp4', 'video/webm'].includes(file.type)) {
    localFileError.value = t('extra.invalidVideo')
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    localFileError.value = t('extra.videoTooLarge')
    return
  }
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoFile.value = file
  videoUrl.value = URL.createObjectURL(file)
  localFileError.value = ''
  stopCamera()
}

async function analyzeVideoFrame() {
  if (!videoEl.value || !videoUrl.value) return
  try {
    const frame = await captureFrame(videoEl.value)
    await store.analyzeFile(frame, { source: 'video' })
  } catch (error) {
    localFileError.value = error.message || t('extra.videoFrameError')
  }
}

function startVideoAuto() {
  if (!videoUrl.value) return
  analyzeVideoFrame()
  if (videoScanTimer) clearInterval(videoScanTimer)
  videoScanTimer = setInterval(() => {
    if (!store.analyzing && !videoEl.value?.paused) analyzeVideoFrame()
  }, 5200)
}

function stopVideoAuto() {
  if (videoScanTimer) {
    clearInterval(videoScanTimer)
    videoScanTimer = null
  }
}

function onVideoPlay() {
  if (videoFile.value) startVideoAuto()
}

function onVideoPause() {
  stopVideoAuto()
}

function switchMode(next) {
  mode.value = next
  localFileError.value = ''
  if (next !== 'camera') stopLive()
  if (next !== 'video') {
    videoEl.value?.pause()
    stopVideoAuto()
  }
}

function scrollToRecommendations() {
  document.querySelector('#recommendations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function resetResult() {
  store.clear()
  localFileError.value = ''
}

watch(
  () => mode.value,
  (value) => {
    if (value === 'camera' && !cameraOn.value) startCamera()
  },
)

onMounted(loadDemos)
onBeforeUnmount(() => {
  stopCamera()
  stopVideoAuto()
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})
</script>

<template>
  <section id="scanner" class="scanner-section" :aria-label="t('viewer.aria')">
    <div class="container">
      <div class="scanner-heading fade-up">
        <div>
          <p class="eyebrow">{{ t('home.scannerEyebrow') }}</p>
          <h2>{{ t('home.scannerTitle') }}</h2>
        </div>
        <div class="privacy-badge">
          <span class="status-dot"></span>
          {{ t('home.privacy') }}
        </div>
      </div>

      <div class="lab-panel fade-up delay-1">
        <div class="lab-top">
          <div class="mode-tabs" role="tablist">
            <button
              v-for="item in [
                { key: 'image', icon: 'Picture', label: t('viewer.modes.image') },
                { key: 'camera', icon: 'Camera', label: t('viewer.modes.camera') },
                { key: 'video', icon: 'VideoCamera', label: t('viewer.modes.video') },
              ]"
              :key="item.key"
              class="mode-tab"
              :class="{ active: mode === item.key }"
              role="tab"
              :aria-selected="mode === item.key"
              @click="switchMode(item.key)"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </button>
          </div>
          <div class="lab-status mono">
            <span class="live-dot" :class="{ on: cameraOn && liveScan }"></span>
            {{ cameraOn && liveScan ? 'LIVE' : 'STANDBY' }}
            <span class="divider-dot">·</span>
            LOCAL ONLY
          </div>
        </div>

        <div class="lab-body">
          <div class="preview-stage">
            <div v-if="mode === 'image'" class="image-stage" :class="{ 'has-image': hasPreview, dragging: dragOver }">
              <template v-if="hasPreview">
                <div class="image-frame" :style="{ aspectRatio: aspect }">
                  <img :src="store.sourcePreview" :alt="t('viewer.faceAlt')" width="1280" height="960" />
                  <div v-if="box" class="face-box" :style="{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }">
                    <span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
                    <span class="face-tag" :style="{ background: resultColor }">
                      {{ store.result ? t(`emotions.${store.result.emotion}`) : '…' }}
                    </span>
                  </div>
                  <div v-if="store.analyzing" class="scan-overlay">
                    <span class="scan-line"></span>
                    <span class="scan-label">{{ t('viewer.scanning') }}</span>
                  </div>
                </div>
              </template>
              <button
                v-else
                class="upload-zone"
                type="button"
                @click="openFilePicker"
                @dragover.prevent="dragOver = true"
                @dragleave.prevent="dragOver = false"
                @drop.prevent="onDrop"
              >
                <span class="upload-glyph"><el-icon :size="28"><UploadFilled /></el-icon></span>
                <strong>{{ t('viewer.uploadTitle') }}</strong>
                <span class="small muted">{{ t('viewer.uploadBody') }}</span>
                <span class="upload-cta">{{ t('common.preview') }} <el-icon><ArrowRight /></el-icon></span>
              </button>
              <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onFileChange" />
              <div v-if="hasPreview" class="image-actions">
                <button class="btn ghost small-btn" @click="openFilePicker">
                  <el-icon><Refresh /></el-icon>{{ t('viewer.rescan') }}
                </button>
                <button v-if="store.result" class="btn primary small-btn" @click="scrollToRecommendations">
                  {{ t('viewer.recommended') }}<el-icon><ArrowDown /></el-icon>
                </button>
              </div>
            </div>

            <div v-else-if="mode === 'camera'" class="camera-stage">
              <video
                ref="videoEl"
                class="camera-video"
                autoplay
                muted
                playsinline
                :class="{ visible: cameraOn }"
              ></video>
              <div v-if="!cameraOn" class="camera-placeholder">
                <span class="camera-glyph pulsing"><el-icon :size="30"><Camera /></el-icon></span>
                <strong>{{ cameraBusy ? t('common.loading') : t('viewer.cameraIdle') }}</strong>
                <p class="small muted">{{ t('viewer.cameraHint') }}</p>
                <button class="btn primary" :disabled="cameraBusy" @click="startCamera">
                  {{ cameraBusy ? t('common.loading') : t('viewer.startCamera') }}
                </button>
              </div>
              <template v-else>
                <div class="camera-hud" aria-hidden="true">
                  <span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
                  <span class="hud-label">{{ liveScan ? 'LIVE FACE TRACKING' : 'CAMERA READY' }}</span>
                </div>
                <div class="camera-controls">
                  <button class="btn ghost" @click="stopCamera">{{ t('viewer.stopCamera') }}</button>
                  <button class="shutter" :aria-label="t('viewer.snapshot')" @click="snapshot('camera')">
                    <span></span>
                  </button>
                  <button class="btn" :class="liveScan ? 'signal' : 'ghost'" @click="liveScan ? stopLive() : startLive()">
                    {{ liveScan ? t('viewer.stopCamera') : t('viewer.liveScan') }}
                  </button>
                </div>
              </template>
            </div>

            <div v-else class="video-stage">
              <template v-if="videoUrl">
                <video ref="videoEl" class="video-player" :src="videoUrl" controls @play="onVideoPlay" @pause="onVideoPause"></video>
                <div class="video-controls">
                  <button class="btn ghost" @click="videoInput?.click()">
                    <el-icon><Refresh /></el-icon>{{ t('viewer.videoChoose') }}
                  </button>
                  <button class="btn primary" @click="analyzeVideoFrame">{{ t('viewer.analyzeFrame') }}</button>
                </div>
              </template>
              <button v-else class="upload-zone" type="button" @click="videoInput?.click()">
                <span class="upload-glyph"><el-icon :size="28"><VideoCamera /></el-icon></span>
                <strong>{{ t('viewer.videoChoose') }}</strong>
                <span class="small muted">{{ t('viewer.videoHint') }}</span>
              </button>
              <input ref="videoInput" type="file" accept="video/mp4,video/webm" hidden @change="onVideoChoose" />
            </div>

            <p v-if="localFileError || cameraError" class="inline-error">
              {{ localFileError || cameraError }}
            </p>
            <p v-if="store.error" class="inline-error">
              {{ store.error.message }}
              <button class="text-btn" @click="resetResult">{{ t('common.retry') }}</button>
            </p>
            <div v-if="mode === 'image' && !hasPreview" class="compression-note">
              <el-icon><Lock /></el-icon>
              <span>{{ t('viewer.compressNote') }} {{ t('home.privacy') }}</span>
            </div>
          </div>

          <aside class="result-stage" :class="{ 'has-result': store.result }">
            <div v-if="store.analyzing && !store.result" class="result-loading">
              <div class="orbit-loader"><span></span><span></span><span></span></div>
              <p class="eyebrow">{{ t('viewer.resultEyebrow') }}</p>
              <strong>{{ t('viewer.scanning') }}</strong>
              <div class="mini-bars">
                <span></span><span></span><span></span><span></span><span></span><span></span>
              </div>
            </div>
            <template v-else-if="store.result">
              <div class="result-head">
                <div>
                  <p class="eyebrow">{{ t('viewer.resultEyebrow') }}</p>
                  <h3 :style="{ color: resultColor }">{{ t(`emotions.${store.result.emotion}`) }}</h3>
                  <p class="result-note small">{{ t(`emotions.${store.result.emotion}Note`) }}</p>
                </div>
                <EmotionDial :emotion="store.result.emotion" :score="store.result.confidence" :color="resultColor" :size="104" />
              </div>
              <div class="score-list">
                <div v-for="item in orderedScores" :key="item.key" class="score-row">
                  <span class="score-name">{{ t(`emotions.${item.key}`) }}</span>
                  <span class="score-track"><i :style="{ width: `${Math.max(2, item.value * 100)}%`, background: item.color }"></i></span>
                  <span class="score-value mono">{{ Math.round(item.value * 100) }}%</span>
                </div>
              </div>
              <div class="result-meta small muted">
                <span>{{ t('viewer.faceCount', { count: store.result.faceCount }) }}</span>
                <span>{{ t('viewer.inference', { ms: store.result.inferenceMs }) }}</span>
              </div>
              <div class="engine-line mono">
                <span class="status-dot"></span>
                {{ store.result.engine }}
              </div>
              <button class="btn signal result-cta" @click="scrollToRecommendations">
                {{ t('viewer.recommended') }}
                <el-icon><Right /></el-icon>
              </button>
            </template>
            <div v-else class="result-idle">
              <div class="idle-visual">
                <span class="idle-ring r1"></span>
                <span class="idle-ring r2"></span>
                <span class="idle-ring r3"></span>
                <span class="idle-core"><el-icon :size="24"><MagicStick /></el-icon></span>
              </div>
              <p class="eyebrow">SIX DIMENSIONS</p>
              <h3>{{ t('home.scannerTitle') }}</h3>
              <p class="small muted">{{ t('home.lead') }}</p>
              <div class="idle-steps">
                <span>01 · Detect</span><span>02 · Read</span><span>03 · Match</span>
              </div>
              <div class="ai-note">
                <el-icon><Cpu /></el-icon>
                <span>{{ t('home.privacy') }}</span>
              </div>
            </div>
          </aside>
        </div>

        <div class="demo-rail">
          <div class="demo-head">
            <div>
              <p class="eyebrow">{{ t('viewer.demoTitle') }}</p>
              <p class="small muted">{{ t('viewer.demoHint') }}</p>
            </div>
            <span class="mono demo-count">06 / SAMPLES</span>
          </div>
          <div class="demo-grid">
            <button
              v-for="demo in demos"
              :key="demo.id"
              class="demo-card"
              :class="{ active: store.result?.logId && store.sourceKind === 'demo' && store.result.emotion === demo.emotion }"
              @click="chooseDemo(demo)"
            >
              <span class="demo-img-wrap">
                <img :src="demo.url" :alt="demo.title" width="120" height="120" loading="lazy" />
                <span class="demo-emoji" :style="{ color: `var(--${demo.emotion})` }">{{ t(`emotions.${demo.emotion}`) }}</span>
              </span>
              <span class="demo-title">{{ demo.title }}</span>
            </button>
            <template v-if="demosLoading">
              <div v-for="i in 6" :key="`s${i}`" class="skeleton demo-skeleton"></div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.scanner-section {
  padding: 56px 0 58px;
  scroll-margin-top: 88px;
}
.scanner-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.scanner-heading h2 {
  margin-top: 10px;
  font-size: clamp(28px, 3.4vw, 44px);
}
.privacy-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 11px;
  background: color-mix(in srgb, var(--surface) 70%, transparent);
}
.privacy-badge .status-dot {
  color: var(--success);
}
.lab-panel {
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  border: 1px solid var(--line);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(12px);
}
.lab-top {
  height: 58px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--surface-2) 52%, transparent);
}
.mode-tabs {
  display: flex;
  gap: 3px;
}
.mode-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 560;
  transition: all 160ms;
}
.mode-tab:hover {
  color: var(--ink);
  background: var(--surface-2);
}
.mode-tab.active {
  color: var(--ink);
  background: var(--surface);
  border-color: var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.lab-status {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 7px;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted-2);
}
.live-dot.on {
  background: var(--signal);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--signal) 18%, transparent);
  animation: pulse 1.8s infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}
.divider-dot {
  opacity: 0.4;
}
.lab-body {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(330px, 0.75fr);
  min-height: 470px;
}
.preview-stage {
  padding: 18px;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 12px;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(91, 91, 214, 0.04), transparent 55%),
    color-mix(in srgb, var(--surface-2) 35%, transparent);
}
.image-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 330px;
}
.image-frame {
  position: relative;
  width: 100%;
  max-height: 455px;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: #0f1014;
}
.image-frame img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.face-box {
  position: absolute;
  border: 1.5px solid v-bind(resultColor);
  border-radius: 6px;
  box-shadow: 0 0 0 9999px rgba(9, 9, 14, 0.18);
}
.corner {
  position: absolute;
  width: 15px;
  height: 15px;
  border-color: v-bind(resultColor);
  border-style: solid;
}
.corner.tl {
  top: -1px;
  left: -1px;
  border-width: 2px 0 0 2px;
}
.corner.tr {
  top: -1px;
  right: -1px;
  border-width: 2px 2px 0 0;
}
.corner.bl {
  bottom: -1px;
  left: -1px;
  border-width: 0 0 2px 2px;
}
.corner.br {
  bottom: -1px;
  right: -1px;
  border-width: 0 2px 2px 0;
}
.face-tag {
  position: absolute;
  left: 0;
  bottom: -24px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 7px;
  border-radius: 3px;
  white-space: nowrap;
}
.scan-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: rgba(10, 10, 16, 0.26);
  backdrop-filter: blur(1px);
}
.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  box-shadow: 0 0 18px var(--accent);
  animation: scan 2s var(--ease) infinite;
}
@keyframes scan {
  0% {
    top: 8%;
  }
  50% {
    top: 92%;
  }
  100% {
    top: 8%;
  }
}
.scan-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #fff;
  padding: 6px 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: rgba(12, 12, 18, 0.45);
}
.upload-zone {
  flex: 1;
  min-height: 330px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1.5px dashed var(--line-strong);
  border-radius: 12px;
  background:
    radial-gradient(circle at center, rgba(91, 91, 214, 0.06), transparent 60%),
    color-mix(in srgb, var(--surface) 55%, transparent);
  color: var(--ink-2);
  transition: all 200ms var(--ease);
  padding: 30px;
  text-align: center;
}
.upload-zone:hover,
.image-stage.dragging .upload-zone {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.upload-zone strong {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: -0.03em;
}
.upload-glyph {
  width: 62px;
  height: 62px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--accent);
  margin-bottom: 6px;
}
.upload-cta {
  margin-top: 10px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 650;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.image-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.small-btn {
  min-height: 38px;
  font-size: 12.5px;
}
.compression-note {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted-2);
  font-size: 10px;
}
.camera-stage,
.video-stage {
  flex: 1;
  min-height: 380px;
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: #101116;
  display: flex;
  flex-direction: column;
}
.camera-video,
.video-player {
  width: 100%;
  height: 100%;
  max-height: 455px;
  object-fit: cover;
  flex: 1;
  background: #101116;
}
.camera-video:not(.visible) {
  display: none;
}
.camera-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 26px;
  text-align: center;
  color: var(--ink-2);
  background:
    radial-gradient(circle at center, rgba(91, 91, 214, 0.08), transparent 60%),
    #17181e;
}
.camera-placeholder strong {
  color: #f5f3ed;
  font-family: var(--font-display);
  font-size: 21px;
}
.camera-placeholder .muted {
  color: #9d9a94;
  max-width: 360px;
}
.camera-glyph {
  width: 66px;
  height: 66px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #e9e4da;
  margin-bottom: 6px;
}
.camera-hud {
  position: absolute;
  inset: 18px;
  pointer-events: none;
}
.camera-hud .corner {
  position: absolute;
  width: 26px;
  height: 26px;
  border-color: rgba(255, 255, 255, 0.65);
}
.camera-hud .tl {
  top: 0;
  left: 0;
  border-width: 1px 0 0 1px;
}
.camera-hud .tr {
  top: 0;
  right: 0;
  border-width: 1px 1px 0 0;
}
.camera-hud .bl {
  bottom: 0;
  left: 0;
  border-width: 0 0 1px 1px;
}
.camera-hud .br {
  bottom: 0;
  right: 0;
  border-width: 0 1px 1px 0;
}
.hud-label {
  position: absolute;
  top: 8px;
  left: 38px;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.7);
}
.camera-controls {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px;
  border-radius: 999px;
  background: rgba(20, 20, 26, 0.64);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(14px);
}
.camera-controls .btn {
  min-height: 36px;
  font-size: 12px;
  color: #fff;
  border-color: rgba(255, 255, 255, 0.18);
}
.camera-controls .btn.ghost {
  background: transparent;
}
.camera-controls .btn.signal {
  background: var(--signal);
  border-color: var(--signal);
}
.shutter {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.9);
  background: transparent;
  display: grid;
  place-items: center;
  padding: 4px;
}
.shutter span {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #fff;
  transition: transform 120ms;
}
.shutter:active span {
  transform: scale(0.9);
}
.video-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px;
  background: #17181e;
}
.video-controls .btn.ghost {
  color: #d8d4ca;
  border-color: rgba(255, 255, 255, 0.15);
}
.inline-error {
  color: var(--danger);
  font-size: 12.5px;
  padding: 9px 11px;
  background: color-mix(in srgb, var(--danger) 7%, var(--surface));
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--danger) 20%, var(--line));
}
.text-btn {
  border: 0;
  background: none;
  color: var(--danger);
  text-decoration: underline;
  font-size: 12px;
  margin-left: 6px;
}
.result-stage {
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 400px;
  background:
    radial-gradient(circle at 70% 20%, color-mix(in srgb, var(--accent) 6%, transparent), transparent 56%),
    var(--surface);
}
.result-stage.has-result {
  justify-content: flex-start;
  gap: 18px;
}
.result-idle {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 330px;
}
.idle-visual {
  position: relative;
  width: 84px;
  height: 84px;
  margin-bottom: 4px;
}
.idle-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid var(--line);
}
.r1 {
  inset: 0;
  animation: rotate 16s linear infinite;
  border-style: dashed;
}
.r2 {
  inset: 12px;
  border-color: color-mix(in srgb, var(--accent) 28%, var(--line));
}
.r3 {
  inset: 24px;
  border-color: var(--line-strong);
}
.idle-core {
  position: absolute;
  inset: 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
}
@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}
.result-idle h3 {
  font-size: 25px;
  line-height: 1.2;
}
.idle-steps {
  display: flex;
  gap: 10px;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.08em;
  color: var(--muted-2);
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.ai-note {
  display: flex;
  gap: 8px;
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--muted);
  padding: 10px;
  background: var(--surface-2);
  border-radius: 7px;
}
.ai-note .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--accent);
}
.result-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}
.orbit-loader {
  width: 80px;
  height: 80px;
  position: relative;
  border: 1px solid var(--line);
  border-radius: 50%;
  margin-bottom: 6px;
}
.orbit-loader span {
  position: absolute;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
}
.orbit-loader span:nth-child(1) {
  top: 8px;
  left: 36px;
  animation: orbit 1.8s linear infinite;
  transform-origin: 3px 32px;
}
.orbit-loader span:nth-child(2) {
  top: 36px;
  left: 8px;
  background: var(--signal);
  animation: orbit 2.6s linear infinite reverse;
  transform-origin: 32px 3px;
}
.orbit-loader span:nth-child(3) {
  top: 58px;
  left: 58px;
  background: var(--happy);
  animation: orbit 2.2s linear infinite;
  transform-origin: -18px -18px;
}
@keyframes orbit {
  to {
    transform: rotate(360deg);
  }
}
.mini-bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 24px;
}
.mini-bars span {
  width: 4px;
  background: var(--accent);
  border-radius: 2px;
  animation: bar 1.1s ease-in-out infinite;
}
.mini-bars span:nth-child(1) {
  height: 8px;
}
.mini-bars span:nth-child(2) {
  height: 16px;
  animation-delay: 0.1s;
}
.mini-bars span:nth-child(3) {
  height: 22px;
  animation-delay: 0.2s;
}
.mini-bars span:nth-child(4) {
  height: 12px;
  animation-delay: 0.3s;
}
.mini-bars span:nth-child(5) {
  height: 18px;
  animation-delay: 0.4s;
}
.mini-bars span:nth-child(6) {
  height: 7px;
  animation-delay: 0.5s;
}
@keyframes bar {
  50% {
    transform: scaleY(0.45);
  }
}
.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.result-head h3 {
  font-size: clamp(38px, 4.5vw, 54px);
  margin: 7px 0 8px;
}
.result-note {
  max-width: 260px;
  line-height: 1.55;
  color: var(--muted);
}
.score-list {
  display: grid;
  gap: 8px;
}
.score-row {
  display: grid;
  grid-template-columns: 42px 1fr 36px;
  align-items: center;
  gap: 8px;
}
.score-name {
  font-size: 11px;
  color: var(--muted);
}
.score-track {
  height: 3px;
  border-radius: 3px;
  background: var(--surface-3);
  overflow: hidden;
}
.score-track i {
  display: block;
  height: 100%;
  border-radius: 3px;
  transition: width 700ms var(--ease);
}
.score-value {
  font-size: 9px;
  color: var(--muted);
  text-align: right;
}
.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.engine-line {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 8px;
  letter-spacing: 0.04em;
}
.engine-line .status-dot {
  color: var(--success);
}
.result-cta {
  width: 100%;
  margin-top: auto;
}
.demo-rail {
  border-top: 1px solid var(--line);
  padding: 18px;
  background: color-mix(in srgb, var(--surface-2) 35%, transparent);
}
.demo-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.demo-head .eyebrow {
  margin-bottom: 3px;
}
.demo-count {
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.1em;
  white-space: nowrap;
}
.demo-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 9px;
}
.demo-card {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 5px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  transition: all 180ms var(--ease);
}
.demo-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}
.demo-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.demo-img-wrap {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  background: var(--surface-2);
}
.demo-img-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.82);
  transition: filter 200ms;
}
.demo-card:hover .demo-img-wrap img {
  filter: saturate(1);
}
.demo-emoji {
  position: absolute;
  left: 4px;
  bottom: 4px;
  padding: 2px 5px;
  border-radius: 3px;
  background: rgba(20, 20, 24, 0.64);
  backdrop-filter: blur(6px);
  font-size: 8px;
  font-weight: 700;
  color: var(--happy);
}
.demo-title {
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.demo-skeleton {
  aspect-ratio: 0.85;
}
@media (max-width: 1000px) {
  .lab-body {
    grid-template-columns: 1fr;
  }
  .preview-stage {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .result-stage {
    min-height: 320px;
  }
  .demo-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 640px) {
  .scanner-section {
    padding-top: 34px;
  }
  .scanner-heading {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .privacy-badge {
    font-size: 9.5px;
  }
  .lab-top {
    height: auto;
    padding: 10px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .mode-tab {
    padding: 0 9px;
    font-size: 12px;
  }
  .lab-status {
    display: none;
  }
  .preview-stage {
    padding: 10px;
  }
  .upload-zone {
    min-height: 280px;
    padding: 22px 16px;
  }
  .upload-zone strong {
    font-size: 19px;
  }
  .camera-controls {
    width: calc(100% - 20px);
    justify-content: center;
    bottom: 10px;
  }
  .camera-controls .btn {
    padding-inline: 10px;
    font-size: 10px;
  }
  .shutter {
    flex-shrink: 0;
  }
  .result-stage {
    padding: 18px;
    min-height: auto;
  }
  .result-head {
    align-items: flex-start;
  }
  .result-head h3 {
    font-size: 38px;
  }
  .demo-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .demo-rail {
    padding: 14px 10px;
  }
  .image-actions {
    justify-content: space-between;
  }
}
</style>
