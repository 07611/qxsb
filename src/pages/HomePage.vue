<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useEmotionStore } from '@/stores/emotion'
import { contentApi, emotionApi, socialApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { emotionColor, formatDate, relativeTime } from '@/utils/format'
import EmotionScanner from '@/components/emotion/EmotionScanner.vue'
import RecommendationPanel from '@/components/recommendation/RecommendationPanel.vue'
import PostCard from '@/components/content/PostCard.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const auth = useAuthStore()
const emotionStore = useEmotionStore()

const banners = ref([])
const bannersLoading = ref(true)
const bannerError = ref(null)
const items = ref([])
const itemsLoading = ref(true)
const itemsError = ref(null)
const history = ref([])
const historyLoading = ref(false)
const activeBanner = ref(0)

const heroFaces = [
  { src: '/media/demo/surprised.jpg', emotion: 'surprised', position: 'small-left' },
  { src: '/media/demo/happy.jpg', emotion: 'happy', position: 'main' },
  { src: '/media/demo/sad.jpg', emotion: 'sad', position: 'small-right' },
]

const currentBanner = computed(() => banners.value[activeBanner.value] || null)
const showRecommendations = computed(() => Boolean(emotionStore.result))
const canShowHistory = computed(() => auth.isAuthenticated && history.value.length)

function scrollToScanner() {
  document.querySelector('#scanner')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadBanners() {
  bannersLoading.value = true
  bannerError.value = null
  try {
    const response = await socialApi.banners('home')
    banners.value = response.data.items || []
  } catch (error) {
    bannerError.value = normalizeError(error)
  } finally {
    bannersLoading.value = false
  }
}

async function loadItems() {
  itemsLoading.value = true
  itemsError.value = null
  try {
    const response = await contentApi.items({ page: 1, pageSize: 3 })
    items.value = response.data.items || []
  } catch (error) {
    itemsError.value = normalizeError(error)
  } finally {
    itemsLoading.value = false
  }
}

async function loadHistory() {
  if (!auth.isAuthenticated) return
  historyLoading.value = true
  try {
    const response = await emotionApi.history({ page: 1, pageSize: 4 })
    history.value = response.data.items || []
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

function refreshAll() {
  loadBanners()
  loadItems()
  loadHistory()
}

onMounted(() => {
  loadBanners()
  loadItems()
  loadHistory()
})
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="container hero-grid">
        <div class="hero-copy">
          <div class="hero-eyebrow fade-up">
            <span class="live-mark"><span></span></span>
            {{ t('home.eyebrow') }}
            <span class="eyebrow-rule"></span>
            <span class="mono">V1.0</span>
          </div>
          <h1 class="hero-title fade-up delay-1">
            <span>{{ t('home.titleA') }}</span>
            <span class="title-line">{{ t('home.titleB') }}<i class="title-period"></i></span>
          </h1>
          <p class="hero-lead fade-up delay-2">{{ t('home.lead') }}</p>
          <div class="hero-actions fade-up delay-3">
            <button class="btn primary hero-cta" @click="scrollToScanner">
              <el-icon><Aim /></el-icon>
              {{ t('home.scanCta') }}
            </button>
            <router-link to="/algorithms" class="btn ghost">{{ t('home.howCta') }} <el-icon><ArrowRight /></el-icon></router-link>
          </div>
          <div class="hero-signals fade-up delay-3">
            <div class="signal-item">
              <strong>6</strong>
              <span>{{ t('home.statEmotions') }}</span>
            </div>
            <div class="signal-divider"></div>
            <div class="signal-item">
              <strong>100%</strong>
              <span>{{ t('home.statLocal') }}</span>
            </div>
            <div class="signal-divider"></div>
            <div class="signal-item">
              <strong>∞</strong>
              <span>{{ t('home.statExplain') }}</span>
            </div>
          </div>
        </div>

        <div class="hero-visual fade-up delay-2" aria-hidden="true">
          <div class="visual-bracket top-left"></div>
          <div class="visual-bracket bottom-right"></div>
          <div class="visual-header">
            <span class="mono">EMOTION · LIVE READ</span>
            <span class="local-status"><span></span>ON DEVICE</span>
          </div>
          <div class="face-collage">
            <div class="face-small left">
              <img :src="heroFaces[0].src" alt="" width="300" height="300" />
              <span class="face-label" style="color: #9b6bd6">{{ t('emotions.surprised') }}</span>
            </div>
            <div class="face-main">
              <img :src="heroFaces[1].src" alt="" width="420" height="420" />
              <span class="face-chip">{{ t('emotions.happy') }} · 0.93</span>
              <div class="brackets"><i></i><i></i><i></i><i></i></div>
            </div>
            <div class="face-small right">
              <img :src="heroFaces[2].src" alt="" width="300" height="300" />
              <span class="face-label" style="color: #5b7db1">{{ t('emotions.sad') }}</span>
            </div>
            <span class="visual-orbit orbit-a"></span>
            <span class="visual-orbit orbit-b"></span>
          </div>
          <div class="visual-wave">
            <span v-for="n in 42" :key="n" :style="{ height: `${5 + Math.abs(Math.sin(n * 1.37)) * 28}px` }"></span>
          </div>
          <div class="visual-readout">
            <div>
              <span class="mono">VALENCE</span>
              <strong>0.86</strong>
            </div>
            <div>
              <span class="mono">AROUSAL</span>
              <strong>0.68</strong>
            </div>
            <div>
              <span class="mono">BPM</span>
              <strong>112</strong>
            </div>
            <div class="readout-pulse">
              <span></span><span></span><span></span>
            </div>
          </div>
          <span class="floating-note note-one">YUENT / FER+</span>
          <span class="floating-note note-two">LOCAL INFERENCE</span>
        </div>
      </div>

      <div class="marquee" aria-hidden="true">
        <div class="marquee-track">
          <span>FACE → FEELING → FREQUENCY</span><i>✦</i>
          <span>YUENT · FER+ · KRUMHANSL · THAYER · MMR</span><i>✦</i>
          <span>NO FACE IMAGE LEAVES THIS DEVICE</span><i>✦</i>
          <span>FACE → FEELING → FREQUENCY</span><i>✦</i>
          <span>YUENT · FER+ · KRUMHANSL · THAYER · MMR</span><i>✦</i>
        </div>
      </div>
    </section>

    <section v-if="bannersLoading || currentBanner || bannerError" class="banner-section">
      <div class="container">
        <div v-if="bannersLoading" class="skeleton banner-skeleton"></div>
        <div v-else-if="bannerError" class="banner-error">
          <span class="small muted">{{ bannerError.message }}</span>
          <button class="btn quiet" @click="loadBanners">{{ t('common.retry') }}</button>
        </div>
        <div v-else-if="currentBanner" class="banner-card">
          <router-link v-if="currentBanner.linkUrl" :to="currentBanner.linkUrl" class="banner-link">
            <img :src="currentBanner.imageUrl" :alt="currentBanner.title" width="1600" height="500" />
          </router-link>
          <img v-else :src="currentBanner.imageUrl" :alt="currentBanner.title" width="1600" height="500" />
          <div class="banner-foot">
            <span class="mono">OPERATIONS / HOME · 0{{ activeBanner + 1 }}</span>
            <div class="banner-dots">
              <button
                v-for="(banner, index) in banners"
                :key="banner.id"
                :aria-label="`Banner ${index + 1}`"
                :class="{ active: index === activeBanner }"
                @click="activeBanner = index"
              ></button>
            </div>
            <span class="small muted">{{ currentBanner.subtitle }}</span>
          </div>
        </div>
      </div>
    </section>

    <EmotionScanner />
    <RecommendationPanel v-if="showRecommendations" />

    <section class="movements section">
      <div class="container">
        <div class="movement-head">
          <div>
            <p class="eyebrow">{{ t('home.howEyebrow') }}</p>
            <h2>{{ t('home.howTitle') }}</h2>
          </div>
          <router-link to="/algorithms" class="btn ghost">{{ t('home.learnMore') }}</router-link>
        </div>
        <div class="movement-grid">
          <article class="movement-card">
            <div class="movement-num mono">01</div>
            <div class="movement-icon"><el-icon :size="25"><View /></el-icon></div>
            <h3>{{ t('home.how1Title') }}</h3>
            <p>{{ t('home.how1Body') }}</p>
            <div class="mini-diagram face-diagram" aria-hidden="true">
              <span class="d-face"></span>
              <span class="d-dot d1"></span><span class="d-dot d2"></span>
              <span class="d-line l1"></span><span class="d-line l2"></span>
              <span class="d-scan"></span>
            </div>
            <span class="movement-tag mono">YUNET · FER+ · ONNX</span>
          </article>
          <article class="movement-card">
            <div class="movement-num mono">02</div>
            <div class="movement-icon"><el-icon :size="25"><Headset /></el-icon></div>
            <h3>{{ t('home.how2Title') }}</h3>
            <p>{{ t('home.how2Body') }}</p>
            <div class="mini-diagram wave-diagram" aria-hidden="true">
              <span v-for="n in 26" :key="n" :style="{ height: `${8 + Math.abs(Math.sin(n * 1.3)) * 50}px` }"></span>
            </div>
            <span class="movement-tag mono">BPM · CHROMA · MODE</span>
          </article>
          <article class="movement-card">
            <div class="movement-num mono">03</div>
            <div class="movement-icon"><el-icon :size="25"><Connection /></el-icon></div>
            <h3>{{ t('home.how3Title') }}</h3>
            <p>{{ t('home.how3Body') }}</p>
            <div class="mini-diagram match-diagram" aria-hidden="true">
              <span class="match-node a">FACE</span>
              <span class="match-line"></span>
              <span class="match-node b">SONG</span>
              <span class="match-score">0.87</span>
            </div>
            <span class="movement-tag mono">0.42 · 0.28 · 0.12 · 0.10 · 0.08</span>
          </article>
        </div>
      </div>
    </section>

    <section v-if="canShowHistory" class="recent-section">
      <div class="container recent-grid">
        <div>
          <p class="eyebrow">{{ t('home.recentEyebrow') }}</p>
          <h2>{{ t('home.recentTitle') }}</h2>
          <p class="recent-lead muted">{{ t('algorithms.privacyBody') }}</p>
          <router-link to="/me" class="btn ghost">{{ t('nav.me') }} →</router-link>
        </div>
        <div class="history-list">
          <div v-for="entry in history" :key="entry.id" class="history-item">
            <span class="history-orb" :style="{ '--orb': emotionColor(entry.emotion) }">
              <span>{{ Math.round(entry.confidence * 100) }}</span>
            </span>
            <div>
              <strong>{{ t(`emotions.${entry.emotion}`) }}</strong>
              <p class="small muted">{{ t(`emotions.${entry.emotion}Note`) }}</p>
            </div>
            <span class="history-time mono">{{ relativeTime(entry.createdAt, locale) }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="latest section">
      <div class="container">
        <div class="section-head">
          <div>
            <p class="eyebrow">{{ t('home.latestEyebrow') }}</p>
            <h2>{{ t('home.latestTitle') }}</h2>
            <p class="lead">{{ t('home.latestLead') }}</p>
          </div>
          <router-link to="/discover" class="btn ghost">{{ t('home.viewAll') }}</router-link>
        </div>
        <AsyncState
          :loading="itemsLoading"
          :error="itemsError"
          :empty="!itemsLoading && !itemsError && items.length === 0"
          :empty-text="t('common.empty')"
          :skeleton-rows="2"
          @retry="loadItems"
        >
          <div class="post-grid">
            <PostCard v-for="(item, index) in items" :key="item.id" :item="item" :featured="index === 0" />
          </div>
        </AsyncState>
      </div>
    </section>

    <section class="closing">
      <div class="container closing-inner">
        <p class="eyebrow">READY WHEN YOU ARE</p>
        <h2>{{ t('home.scannerTitle') }}</h2>
        <button class="btn signal" @click="scrollToScanner">{{ t('home.scanCta') }} <el-icon><Up /></el-icon></button>
        <span class="closing-orbit" aria-hidden="true"></span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  padding: 58px 0 0;
  overflow: hidden;
}
.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.03fr) minmax(390px, 0.97fr);
  align-items: center;
  gap: 52px;
  padding-bottom: 64px;
}
.hero-eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
}
.live-mark {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--signal) 30%, var(--line));
  display: grid;
  place-items: center;
}
.live-mark span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--signal);
  animation: heroPulse 2s ease infinite;
}
@keyframes heroPulse {
  50% {
    box-shadow: 0 0 0 5px color-mix(in srgb, var(--signal) 15%, transparent);
  }
}
.eyebrow-rule {
  width: 28px;
  height: 1px;
  background: var(--line-strong);
}
.hero-title {
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  font-size: clamp(54px, 7.4vw, 106px);
  line-height: 0.98;
  letter-spacing: -0.065em;
}
.title-line {
  display: block;
  color: var(--ink);
}
.title-period {
  display: none;
}
.hero-lead {
  max-width: 520px;
  margin-top: 24px;
  color: var(--muted);
  font-size: clamp(15px, 1.5vw, 17px);
  line-height: 1.75;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 28px;
}
.hero-cta {
  min-height: 48px;
  padding-inline: 20px;
}
.hero-signals {
  display: flex;
  align-items: center;
  gap: 22px;
  margin-top: 42px;
}
.signal-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.signal-item strong {
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 560;
  letter-spacing: -0.035em;
}
.signal-item span {
  font-size: 9px;
  color: var(--muted);
  letter-spacing: 0.03em;
}
.signal-divider {
  width: 1px;
  height: 28px;
  background: var(--line);
}
.hero-visual {
  position: relative;
  min-height: 510px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background:
    radial-gradient(ellipse at 50% 40%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 58%),
    linear-gradient(160deg, var(--surface) 0%, var(--surface-2) 100%);
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
}
.visual-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px 12px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
}
.visual-header .mono {
  font-size: 8px;
  letter-spacing: 0.08em;
}
.local-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--success);
}
.local-status span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}
.face-collage {
  position: relative;
  flex: 1;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 0;
}
.face-main {
  position: relative;
  z-index: 2;
  width: 58%;
  aspect-ratio: 1;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--line));
  box-shadow: 0 20px 60px rgba(20, 20, 30, 0.17);
  background: var(--surface-3);
}
.face-main img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.9) contrast(1.02);
}
.face-small {
  position: absolute;
  width: 29%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--surface-3);
  filter: saturate(0.72);
  opacity: 0.86;
}
.face-small.left {
  left: -10px;
  top: 14%;
  transform: rotate(-8deg);
}
.face-small.right {
  right: -10px;
  bottom: 12%;
  transform: rotate(7deg);
}
.face-small img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.face-chip {
  position: absolute;
  left: 10px;
  bottom: 10px;
  padding: 4px 7px;
  border-radius: 4px;
  background: rgba(16, 16, 22, 0.62);
  backdrop-filter: blur(8px);
  font-family: var(--font-mono);
  font-size: 8px;
  color: #fff;
  letter-spacing: 0.04em;
}
.face-label {
  position: absolute;
  bottom: 8px;
  left: 8px;
  font-size: 9px;
  font-weight: 650;
  padding: 3px 6px;
  border-radius: 3px;
  background: rgba(20, 20, 26, 0.62);
  backdrop-filter: blur(6px);
}
.brackets i {
  position: absolute;
  width: 22px;
  height: 22px;
  border-color: rgba(255, 255, 255, 0.8);
  border-style: solid;
}
.brackets i:nth-child(1) {
  top: 12px;
  left: 12px;
  border-width: 1.5px 0 0 1.5px;
}
.brackets i:nth-child(2) {
  top: 12px;
  right: 12px;
  border-width: 1.5px 1.5px 0 0;
}
.brackets i:nth-child(3) {
  bottom: 12px;
  left: 12px;
  border-width: 0 0 1.5px 1.5px;
}
.brackets i:nth-child(4) {
  bottom: 12px;
  right: 12px;
  border-width: 0 1.5px 1.5px 0;
}
.visual-orbit {
  position: absolute;
  border-radius: 50%;
  border: 1px solid var(--line);
  pointer-events: none;
}
.orbit-a {
  width: 330px;
  height: 330px;
  border-style: dashed;
  opacity: 0.6;
  animation: spin 40s linear infinite;
}
.orbit-b {
  width: 420px;
  height: 420px;
  opacity: 0.3;
  border-color: color-mix(in srgb, var(--accent) 24%, var(--line));
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.visual-wave {
  height: 42px;
  display: flex;
  align-items: center;
  gap: 3px;
  overflow: hidden;
  opacity: 0.42;
  padding: 0 5px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.visual-wave span {
  width: 2px;
  background: var(--accent);
  border-radius: 2px;
  flex: 1;
  max-width: 4px;
}
.visual-readout {
  display: flex;
  align-items: center;
  gap: 18px;
  padding-top: 13px;
}
.visual-readout > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.visual-readout .mono {
  font-size: 7px;
  color: var(--muted-2);
  letter-spacing: 0.06em;
}
.visual-readout strong {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 560;
}
.readout-pulse {
  margin-left: auto;
  flex-direction: row !important;
  align-items: center;
  gap: 3px !important;
}
.readout-pulse span {
  width: 3px;
  border-radius: 2px;
  background: var(--signal);
  animation: eq 1s ease infinite;
}
.readout-pulse span:nth-child(1) {
  height: 7px;
}
.readout-pulse span:nth-child(2) {
  height: 16px;
  animation-delay: 0.15s;
}
.readout-pulse span:nth-child(3) {
  height: 10px;
  animation-delay: 0.3s;
}
@keyframes eq {
  50% {
    transform: scaleY(0.4);
  }
}
.visual-bracket {
  position: absolute;
  width: 45px;
  height: 45px;
  pointer-events: none;
}
.visual-bracket.top-left {
  top: -9px;
  left: -9px;
  border-top: 1px solid var(--accent);
  border-left: 1px solid var(--accent);
  border-radius: 10px 0 0 0;
  opacity: 0.45;
}
.visual-bracket.bottom-right {
  bottom: -9px;
  right: -9px;
  border-bottom: 1px solid var(--accent);
  border-right: 1px solid var(--accent);
  border-radius: 0 0 10px 0;
  opacity: 0.45;
}
.floating-note {
  position: absolute;
  font-family: var(--font-mono);
  font-size: 7px;
  letter-spacing: 0.08em;
  color: var(--muted-2);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 4px 6px;
}
.note-one {
  top: 70px;
  right: 4px;
}
.note-two {
  bottom: 96px;
  left: -14px;
}
.marquee {
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  overflow: hidden;
  padding: 10px 0;
  background: color-mix(in srgb, var(--surface-2) 40%, transparent);
}
.marquee-track {
  display: flex;
  gap: 34px;
  width: max-content;
  align-items: center;
  animation: marquee 32s linear infinite;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.12em;
  color: var(--muted);
}
.marquee-track i {
  color: var(--signal);
  font-style: normal;
}
@keyframes marquee {
  to {
    transform: translateX(-50%);
  }
}
.banner-section {
  padding: 48px 0 0;
}
.banner-skeleton {
  width: 100%;
  aspect-ratio: 16 / 5;
  border-radius: var(--radius);
}
.banner-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface);
}
.banner-link {
  display: block;
}
.banner-card img {
  width: 100%;
  aspect-ratio: 16 / 5;
  object-fit: cover;
}
.banner-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 9px 14px;
  border-top: 1px solid var(--line);
}
.banner-foot .mono {
  font-size: 7px;
  letter-spacing: 0.07em;
  color: var(--muted-2);
  white-space: nowrap;
}
.banner-foot .small {
  margin-left: auto;
  font-size: 10px;
}
.banner-dots {
  display: flex;
  gap: 4px;
}
.banner-dots button {
  width: 13px;
  height: 3px;
  border: 0;
  border-radius: 2px;
  background: var(--line-strong);
  padding: 0;
}
.banner-dots button.active {
  background: var(--accent);
}
.banner-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px dashed var(--line);
  border-radius: 8px;
  padding: 12px 16px;
}
.movements {
  border-top: 1px solid var(--line);
}
.movement-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 30px;
}
.movement-head h2 {
  margin-top: 10px;
  font-size: clamp(30px, 3.8vw, 48px);
}
.movement-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.movement-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
  min-height: 360px;
  transition: all 220ms var(--ease);
}
.movement-card:hover {
  border-color: var(--line-strong);
  transform: translateY(-3px);
}
.movement-num {
  font-size: 9px;
  color: var(--muted-2);
  letter-spacing: 0.08em;
}
.movement-icon {
  width: 52px;
  height: 52px;
  border: 1px solid var(--line);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--accent);
  background: var(--surface-2);
  margin-bottom: 6px;
}
.movement-card h3 {
  font-size: 24px;
  line-height: 1.15;
}
.movement-card p {
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}
.movement-tag {
  margin-top: auto;
  padding-top: 15px;
  border-top: 1px solid var(--line);
  font-size: 7px !important;
  color: var(--muted-2) !important;
  letter-spacing: 0.08em;
}
.mini-diagram {
  position: relative;
  height: 86px;
  margin: 8px 0;
  overflow: hidden;
}
.face-diagram .d-face {
  position: absolute;
  width: 60px;
  height: 72px;
  left: 50%;
  top: 8px;
  transform: translateX(-50%);
  border: 1px solid var(--line-strong);
  border-radius: 43% 43% 46% 46%;
}
.d-dot {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  top: 30px;
}
.d1 {
  left: calc(50% - 16px);
}
.d2 {
  left: calc(50% + 12px);
}
.d-line {
  position: absolute;
  height: 1px;
  background: color-mix(in srgb, var(--accent) 40%, var(--line));
  top: 52px;
}
.l1 {
  width: 25px;
  left: calc(50% - 12px);
}
.l2 {
  width: 25px;
  left: calc(50% - 12px);
  transform: rotate(30deg);
  top: 60px;
}
.d-scan {
  position: absolute;
  left: 24%;
  right: 24%;
  height: 1px;
  background: var(--signal);
  top: 44px;
  box-shadow: 0 0 12px var(--signal);
  animation: scanY 3s ease-in-out infinite;
}
@keyframes scanY {
  50% {
    top: 68px;
  }
}
.wave-diagram {
  display: flex;
  align-items: center;
  gap: 4px;
}
.wave-diagram span {
  flex: 1;
  max-width: 4px;
  background: linear-gradient(180deg, var(--accent), var(--signal));
  border-radius: 3px;
  opacity: 0.55;
}
.match-diagram {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
}
.match-node {
  font-family: var(--font-mono);
  font-size: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--muted);
  background: var(--surface-2);
}
.match-node.b {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--line));
  color: var(--accent);
}
.match-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--line), var(--accent));
}
.match-score {
  position: absolute;
  top: 12px;
  right: 5px;
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--success);
}
.recent-section {
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 54px 0;
  background: color-mix(in srgb, var(--surface-2) 40%, transparent);
}
.recent-grid {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 54px;
}
.recent-grid h2 {
  margin: 10px 0 16px;
  font-size: clamp(30px, 3.5vw, 46px);
}
.recent-lead {
  line-height: 1.75;
  font-size: 13px;
  margin-bottom: 20px;
}
.history-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--line);
}
.history-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 15px;
  align-items: center;
  padding: 15px 0;
  border-bottom: 1px solid var(--line);
}
.history-orb {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--orb) 45%, var(--line));
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--orb);
  background: color-mix(in srgb, var(--orb) 7%, var(--surface));
}
.history-item strong {
  font-size: 13px;
}
.history-item p {
  margin-top: 2px;
  font-size: 10px;
  line-height: 1.5;
}
.history-time {
  font-size: 8px;
  color: var(--muted-2);
  white-space: nowrap;
}
.latest {
  border-top: 1px solid var(--line);
}
.post-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr 0.85fr;
  gap: 14px;
}
.closing {
  border-top: 1px solid var(--line);
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 50% 100%, rgba(91, 91, 214, 0.1), transparent 55%),
    var(--surface-2);
}
.closing-inner {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 78px 20px 92px;
  gap: 18px;
}
.closing h2 {
  max-width: 800px;
  font-size: clamp(34px, 4.5vw, 58px);
}
.closing-orbit {
  position: absolute;
  width: 620px;
  height: 620px;
  bottom: -500px;
  border: 1px solid var(--line);
  border-radius: 50%;
  pointer-events: none;
}
.closing-orbit::before {
  content: '';
  position: absolute;
  inset: 60px;
  border: 1px dashed var(--line);
  border-radius: 50%;
}
@media (max-width: 1100px) {
  .hero-grid {
    grid-template-columns: 1fr;
    gap: 36px;
  }
  .hero-visual {
    min-height: 440px;
    max-width: 650px;
  }
  .hero-title {
    font-size: clamp(56px, 10vw, 90px);
  }
  .post-grid {
    grid-template-columns: 1fr 1fr;
  }
  .post-grid > :first-child {
    grid-column: 1 / -1;
  }
}
@media (max-width: 900px) {
  .movement-grid {
    grid-template-columns: 1fr;
  }
  .movement-card {
    min-height: 300px;
  }
  .recent-grid {
    grid-template-columns: 1fr;
    gap: 28px;
  }
}
@media (max-width: 760px) {
  .hero {
    padding-top: 34px;
  }
  .hero-grid {
    gap: 28px;
    padding-bottom: 40px;
  }
  .hero-eyebrow {
    flex-wrap: wrap;
    font-size: 8px;
  }
  .hero-title {
    font-size: clamp(46px, 13vw, 72px);
  }
  .hero-lead {
    margin-top: 18px;
    font-size: 14.5px;
  }
  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .hero-actions .btn {
    justify-content: center;
  }
  .hero-signals {
    margin-top: 28px;
    gap: 16px;
  }
  .hero-visual {
    min-height: 360px;
    padding: 12px;
  }
  .face-collage {
    min-height: 230px;
  }
  .face-main {
    width: 64%;
  }
  .face-small {
    width: 27%;
  }
  .floating-note {
    display: none;
  }
  .visual-readout {
    gap: 12px;
  }
  .visual-readout > div:nth-child(3) {
    display: none;
  }
  .marquee-track {
    font-size: 7px;
    gap: 22px;
  }
  .banner-section {
    padding-top: 32px;
  }
  .banner-foot .small {
    display: none;
  }
  .banner-foot {
    gap: 10px;
  }
  .post-grid {
    grid-template-columns: 1fr;
  }
  .post-grid > :first-child {
    grid-column: auto;
  }
  .movement-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .closing-inner {
    padding: 56px 12px 68px;
  }
}
</style>
