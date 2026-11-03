<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { emotionApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { emotionColor } from '@/utils/format'
import PageHeader from '@/components/ui/PageHeader.vue'

const { t } = useI18n()
const emotions = ref([])
const tracks = ref([])
const loading = ref(true)
const error = ref(null)

const fallbackEmotions = [
  { code: 'happy', label: '愉悦', color: '#E8A23B', target: { valence: 0.85, arousal: 0.65 } },
  { code: 'sad', label: '低落', color: '#5B7DB1', target: { valence: 0.2, arousal: 0.35 } },
  { code: 'angry', label: '愤怒', color: '#E8552F', target: { valence: 0.2, arousal: 0.8 } },
  { code: 'fear', label: '不安', color: '#4F8C86', target: { valence: 0.3, arousal: 0.55 } },
  { code: 'surprised', label: '惊喜', color: '#9B6BD6', target: { valence: 0.65, arousal: 0.8 } },
  { code: 'neutral', label: '平静', color: '#8C897F', target: { valence: 0.55, arousal: 0.45 } },
]

const scatterEmotions = computed(() => (emotions.value.length ? emotions.value : fallbackEmotions))
const trackPoints = computed(() =>
  tracks.value
    .filter((track) => track.audioFeatures?.valence !== undefined && track.audioFeatures?.arousal !== undefined)
    .map((track) => ({
      ...track,
      x: Number(track.audioFeatures.valence) * 100,
      y: (1 - Number(track.audioFeatures.arousal)) * 100,
      color: emotionColor(track.mood),
    })),
)

const weights = [
  { label: 'P(emotion)', value: 42, color: 'var(--accent)' },
  { label: 'Affinity', value: 28, color: '#9B6BD6' },
  { label: 'Preference', value: 12, color: '#4F8C86' },
  { label: 'Novelty', value: 10, color: '#E8A23B' },
  { label: 'Popularity', value: 8, color: '#E8552F' },
]

async function load() {
  loading.value = true
  error.value = null
  try {
    const [emotionResponse, trackResponse] = await Promise.all([emotionApi.emotions(), emotionApi.local({ pageSize: 12 })])
    emotions.value = emotionResponse.data.items || []
    tracks.value = trackResponse.data.items || []
  } catch (err) {
    error.value = normalizeError(err)
    emotions.value = fallbackEmotions
    tracks.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page algorithms-page">
    <div class="container">
      <PageHeader eyebrow="THE METHOD" :title="t('algorithms.title')" :lead="t('algorithms.lead')">
        <template #actions>
          <router-link to="/#scanner" class="btn primary">{{ t('home.scanCta') }}</router-link>
          <a href="https://github.com/onnx/models/tree/main/validated/vision/body_analysis/emotion_ferplus" target="_blank" rel="noopener" class="btn ghost">FER+ ↗</a>
        </template>
      </PageHeader>

      <div v-if="error" class="algo-error">
        <span><el-icon><Warning /></el-icon> {{ error.message }}</span>
        <button class="btn quiet" @click="load">{{ t('common.retry') }}</button>
      </div>

      <section class="algo-hero card">
        <div class="algo-hero-copy">
          <p class="eyebrow">PIPELINE / 01</p>
          <h2>{{ t('algorithms.faceTitle') }}</h2>
          <p class="sub">{{ t('algorithms.faceSubtitle') }}</p>
          <p>{{ t('algorithms.faceStep1') }}</p>
          <div class="engine-status">
            <span class="status-dot"></span>
            {{ t('viewer.engine') }} · YuNet + FER+
            <span class="mono">{{ loading ? 'PING…' : 'READY' }}</span>
          </div>
        </div>
        <div class="face-pipeline" aria-hidden="true">
          <div class="pipeline-node image">
            <img :src="'/media/demo/surprised.jpg'" alt="" width="180" height="180" />
            <span class="node-label">INPUT</span>
          </div>
          <span class="pipe-line"><i></i></span>
          <div class="pipeline-node mesh">
            <span class="mesh-face"></span>
            <span class="lm l1"></span><span class="lm l2"></span><span class="lm l3"></span><span class="lm l4"></span><span class="lm l5"></span>
            <span class="node-label">LANDMARKS</span>
          </div>
          <span class="pipe-line"><i></i></span>
          <div class="pipeline-node tensor">
            <span class="tensor-grid">
              <i v-for="n in 16" :key="n" :style="{ opacity: 0.22 + (n % 7) * 0.1 }"></i>
            </span>
            <span class="node-label">64 × 64</span>
          </div>
          <span class="pipe-line"><i></i></span>
          <div class="pipeline-node output">
            <span class="out-label" style="color: #9b6bd6">SURPRISE</span>
            <strong>0.80</strong>
            <span class="out-bars"><i v-for="n in 6" :key="n" :style="{ height: `${8 + n * 5}px` }"></i></span>
            <span class="node-label">SOFTMAX</span>
          </div>
        </div>
      </section>

      <section class="algo-block">
        <div class="block-label">
          <span class="mono">01 / FACE</span>
          <h3>{{ t('algorithms.faceSubtitle') }}</h3>
        </div>
        <div class="step-list">
          <div class="step-item">
            <span class="step-num mono">01</span>
            <div><strong>Detect</strong><p>{{ t('algorithms.faceStep1') }}</p></div>
            <span class="step-tag">YuNet</span>
          </div>
          <div class="step-item">
            <span class="step-num mono">02</span>
            <div><strong>Classify</strong><p>{{ t('algorithms.faceStep2') }}</p></div>
            <span class="step-tag">FER+ ONNX</span>
          </div>
          <div class="step-item">
            <span class="step-num mono">03</span>
            <div><strong>Calibrate</strong><p>{{ t('algorithms.faceStep3') }}</p></div>
            <span class="step-tag">Geometry</span>
          </div>
          <div class="step-item">
            <span class="step-num mono">04</span>
            <div><strong>Normalize</strong><p>{{ t('algorithms.faceStep4') }}</p></div>
            <span class="step-tag">6 labels</span>
          </div>
        </div>
        <p class="limit-note"><el-icon><Warning /></el-icon> {{ t('algorithms.faceLimit') }}</p>
      </section>

      <section class="algo-block music-block">
        <div class="block-label">
          <span class="mono">02 / MUSIC</span>
          <h3>{{ t('algorithms.musicTitle') }}</h3>
          <p class="sub">{{ t('algorithms.musicSubtitle') }}</p>
        </div>
        <div class="music-grid">
          <div class="scatter-wrap">
            <div class="scatter-head">
              <span class="eyebrow">THAYER PLANE</span>
              <span class="mono">VALENCE → / AROUSAL ↑</span>
            </div>
            <div class="scatter">
              <div class="scatter-grid-h"></div>
              <div class="scatter-grid-v"></div>
              <span class="axis-x">VALENCE</span>
              <span class="axis-y">AROUSAL</span>
              <span
                v-for="emotion in scatterEmotions"
                :key="emotion.code"
                class="target-point"
                :style="{ left: `${emotion.target.valence * 100}%`, top: `${(1 - emotion.target.arousal) * 100}%`, '--pt': emotion.color }"
              >
                <i></i><span>{{ t(`emotions.${emotion.code}`) }}</span>
              </span>
              <span
                v-for="track in trackPoints"
                :key="track.id"
                class="track-point"
                :style="{ left: `${track.x}%`, top: `${track.y}%`, '--pt': track.color }"
                :title="`${track.title} · ${Math.round(track.audioFeatures.valence * 100)} / ${Math.round(track.audioFeatures.arousal * 100)}`"
              ></span>
              <span class="origin-label mono">(0,0)</span>
            </div>
            <p class="scatter-note">{{ t('algorithms.musicNote') }}</p>
          </div>
          <div class="music-steps">
            <div v-for="(step, index) in [t('algorithms.musicStep1'), t('algorithms.musicStep2'), t('algorithms.musicStep3')]" :key="index" class="music-step">
              <span class="mono">0{{ index + 1 }}</span>
              <p>{{ step }}</p>
            </div>
            <div class="feature-chips">
              <span>BPM</span><span>RMS</span><span>CHROMA</span><span>KEY</span><span>CENTROID</span><span>ZCR</span>
            </div>
          </div>
        </div>
      </section>

      <section class="algo-block rec-block">
        <div class="block-label">
          <span class="mono">03 / MATCH</span>
          <h3>{{ t('algorithms.recTitle') }}</h3>
          <p class="sub">{{ t('algorithms.recSubtitle') }}</p>
        </div>
        <div class="rec-grid">
          <div class="weights">
            <p class="eyebrow">{{ t('algorithms.formula') }}</p>
            <div v-for="weight in weights" :key="weight.label" class="weight-row">
              <span class="weight-label">{{ weight.label }}</span>
              <span class="weight-track"><i :style="{ width: `${weight.value * 2}%`, background: weight.color }"></i></span>
              <span class="weight-value mono">{{ weight.value }}%</span>
            </div>
          </div>
          <div class="rec-steps">
            <div v-for="(step, index) in [t('algorithms.recStep1'), t('algorithms.recStep2'), t('algorithms.recStep3')]" :key="index" class="rec-step">
              <span class="rec-dot">{{ index + 1 }}</span>
              <p>{{ step }}</p>
            </div>
            <div class="mmr-note">
              <span class="mono">MMR</span>
              <p>MAX 2 TRACKS / ARTIST<br />DIVERSITY BEFORE POPULARITY</p>
            </div>
          </div>
        </div>
      </section>

      <section class="privacy-block">
        <div class="privacy-icon"><el-icon :size="26"><Lock /></el-icon></div>
        <div>
          <p class="eyebrow">PRIVACY / BOUNDARIES</p>
          <h3>{{ t('algorithms.privacyTitle') }}</h3>
          <p>{{ t('algorithms.privacyBody') }}</p>
          <p class="mono">{{ t('algorithms.openSource') }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.algorithms-page {
  padding-top: 46px;
}
.algo-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--danger) 20%, var(--line));
  background: color-mix(in srgb, var(--danger) 5%, var(--surface));
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 18px;
  color: var(--danger);
  font-size: 12px;
}
.algo-error span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.algo-hero {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 20px;
  padding: 30px;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 80% 40%, rgba(91, 91, 214, 0.07), transparent 55%),
    var(--surface);
}
.algo-hero-copy {
  display: flex;
  flex-direction: column;
  gap: 14px;
  justify-content: center;
}
.algo-hero-copy h2 {
  font-size: clamp(32px, 4vw, 46px);
}
.algo-hero-copy > p:not(.eyebrow) {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.7;
}
.algo-hero-copy .sub {
  font-family: var(--font-mono);
  font-size: 9px !important;
  color: var(--accent) !important;
  letter-spacing: 0.03em;
}
.engine-status {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
  padding-top: 13px;
  border-top: 1px solid var(--line);
  font-size: 10px;
  color: var(--success);
}
.engine-status .mono {
  margin-left: auto;
  color: var(--muted-2);
  font-size: 8px;
}
.face-pipeline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 5px;
  min-height: 230px;
}
.pipeline-node {
  position: relative;
  flex: 1;
  min-width: 0;
  aspect-ratio: 1;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface-2);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.pipeline-node.image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.8;
}
.node-label {
  position: absolute;
  left: 6px;
  bottom: 5px;
  font-family: var(--font-mono);
  font-size: 7px;
  letter-spacing: 0.06em;
  color: var(--muted);
  background: color-mix(in srgb, var(--surface) 74%, transparent);
  padding: 2px 3px;
  border-radius: 2px;
}
.mesh-face {
  width: 48%;
  aspect-ratio: 0.8;
  border: 1px solid var(--line-strong);
  border-radius: 42% 42% 45% 45%;
}
.lm {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
}
.l1 {
  left: 34%;
  top: 44%;
}
.l2 {
  right: 34%;
  top: 44%;
}
.l3 {
  left: 49%;
  top: 56%;
}
.l4 {
  left: 37%;
  top: 70%;
}
.l5 {
  right: 37%;
  top: 70%;
}
.tensor-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3px;
  width: 52%;
  aspect-ratio: 1;
}
.tensor-grid i {
  border-radius: 1px;
  background: var(--accent);
}

.output {
  gap: 3px;
}
.out-label {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.04em;
}
.output strong {
  font-family: var(--font-display);
  font-size: 25px;
  letter-spacing: -0.06em;
  font-weight: 560;
}
.out-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 40px;
  margin-top: 2px;
}
.out-bars i {
  width: 4px;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.6;
}
.pipe-line {
  width: 17px;
  height: 1px;
  background: var(--line-strong);
  position: relative;
  flex-shrink: 0;
}
.pipe-line i {
  position: absolute;
  top: -2px;
  left: 0;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  animation: pipe 2s linear infinite;
}
@keyframes pipe {
  to {
    transform: translateX(14px);
    opacity: 0;
  }
}
.algo-block {
  border-top: 1px solid var(--line);
  margin-top: 68px;
  padding-top: 36px;
  display: grid;
  grid-template-columns: 0.55fr 1.45fr;
  gap: 52px;
}
.block-label h3 {
  margin-top: 10px;
  font-size: clamp(26px, 3vw, 38px);
}
.block-label .sub {
  margin-top: 9px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--accent);
  line-height: 1.5;
}
.step-list {
  display: flex;
  flex-direction: column;
}
.step-item {
  display: grid;
  grid-template-columns: 28px 1fr auto;
  gap: 14px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
  align-items: start;
}
.step-num {
  color: var(--muted-2);
  font-size: 8px;
  padding-top: 3px;
}
.step-item strong {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  text-transform: uppercase;
  color: var(--ink-2);
  letter-spacing: 0.04em;
}
.step-item p {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
  margin-top: 5px;
}
.step-tag {
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--muted-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 3px 5px;
  white-space: nowrap;
}
.limit-note {
  grid-column: 2;
  display: flex;
  gap: 8px;
  color: var(--warning);
  background: color-mix(in srgb, var(--warning) 6%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--warning) 20%, var(--line));
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 10.5px;
  line-height: 1.6;
}
.music-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 20px;
}
.scatter-wrap {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 14px;
  background: var(--surface);
}
.scatter-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.scatter-head .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.scatter {
  position: relative;
  aspect-ratio: 1.55;
  border-left: 1px solid var(--line-strong);
  border-bottom: 1px solid var(--line-strong);
  margin: 0 10px 20px 28px;
  background:
    linear-gradient(to right, transparent 49.7%, var(--line) 49.7%, var(--line) 50.3%, transparent 50.3%),
    linear-gradient(to top, transparent 49.7%, var(--line) 49.7%, var(--line) 50.3%, transparent 50.3%);
}
.axis-x {
  position: absolute;
  bottom: -19px;
  right: 0;
  font-family: var(--font-mono);
  font-size: 6px;
  color: var(--muted-2);
  letter-spacing: 0.06em;
}
.axis-y {
  position: absolute;
  top: -9px;
  left: -28px;
  transform: rotate(-90deg);
  font-family: var(--font-mono);
  font-size: 6px;
  color: var(--muted-2);
  letter-spacing: 0.06em;
}
.target-point {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 3px;
  z-index: 2;
}
.target-point i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--pt);
  border: 1px solid var(--surface);
}
.target-point span {
  font-size: 7px;
  color: var(--muted);
  white-space: nowrap;
}
.track-point {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--pt);
  opacity: 0.38;
  transform: translate(-50%, -50%);
  z-index: 1;
}
.track-point:hover {
  opacity: 1;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--pt) 18%, transparent);
}
.origin-label {
  position: absolute;
  left: -14px;
  bottom: -18px;
  font-size: 6px;
  color: var(--muted-2);
}
.scatter-note {
  color: var(--muted);
  font-size: 9px;
  line-height: 1.6;
  border-top: 1px solid var(--line);
  padding-top: 8px;
}
.music-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.music-step {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 9px;
  border-top: 1px solid var(--line);
  padding: 11px 0;
}
.music-step .mono {
  font-size: 7px;
  color: var(--muted-2);
  padding-top: 2px;
}
.music-step p {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.7;
}
.feature-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 10px;
}
.feature-chips span {
  font-family: var(--font-mono);
  font-size: 7px;
  border: 1px solid var(--line);
  color: var(--muted);
  border-radius: 3px;
  padding: 3px 5px;
}
.rec-block {
  display: block;
}
.rec-grid {
  margin-top: 26px;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 38px;
}
.weights {
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
.weights .eyebrow {
  margin-bottom: 16px;
  line-height: 1.5;
  color: var(--accent);
}
.weight-row {
  display: grid;
  grid-template-columns: 80px 1fr 36px;
  align-items: center;
  gap: 10px;
  margin-bottom: 11px;
}
.weight-label {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--muted);
}
.weight-track {
  height: 6px;
  background: var(--surface-3);
  border-radius: 3px;
  overflow: hidden;
}
.weight-track i {
  display: block;
  height: 100%;
  border-radius: 3px;
}
.weight-value {
  font-size: 8px;
  color: var(--muted);
  text-align: right;
}
.rec-steps {
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
.rec-step {
  display: flex;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}
.rec-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: 1px solid var(--line);
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--accent);
}
.rec-step p {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.7;
}
.mmr-note {
  margin-top: 16px;
  padding: 12px;
  background: var(--surface-2);
  border: 1px dashed var(--line-strong);
  border-radius: 5px;
}
.mmr-note .mono {
  color: var(--signal);
  font-size: 8px;
  letter-spacing: 0.1em;
}
.mmr-note p {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--muted);
  line-height: 1.5;
  margin-top: 5px;
}
.privacy-block {
  margin: 68px 0 10px;
  display: flex;
  gap: 20px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 25px;
  background: color-mix(in srgb, var(--surface-2) 40%, var(--surface));
}
.privacy-icon {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  color: var(--accent);
}
.privacy-block h3 {
  margin: 8px 0 10px;
  font-size: 22px;
}
.privacy-block p {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.75;
  max-width: 780px;
}
.privacy-block .mono {
  margin-top: 14px;
  font-size: 8px;
  color: var(--muted-2);
}
@media (max-width: 1000px) {
  .algo-hero {
    grid-template-columns: 1fr;
  }
  .face-pipeline {
    min-height: 190px;
  }
  .algo-block {
    grid-template-columns: 1fr;
    gap: 22px;
    margin-top: 44px;
  }
  .limit-note {
    grid-column: 1;
  }
  .music-grid {
    grid-template-columns: 1fr;
  }
  .rec-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
}
@media (max-width: 640px) {
  .algo-hero {
    padding: 20px;
  }
  .face-pipeline {
    gap: 2px;
  }
  .pipe-line {
    width: 6px;
  }
  .pipeline-node {
    border-radius: 6px;
  }
  .target-point span {
    display: none;
  }
  .scatter-wrap {
    padding: 9px;
  }
  .privacy-block {
    flex-direction: column;
    padding: 20px;
  }
}
</style>
