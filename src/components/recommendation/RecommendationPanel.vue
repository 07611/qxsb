<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useEmotionStore } from '@/stores/emotion'
import { useAuthStore } from '@/stores/auth'
import { usePlayerStore } from '@/stores/player'
import { emotionApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { emotionColor } from '@/utils/format'
import { track } from '@/utils/track'
import TrackRow from './TrackRow.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t } = useI18n()
const store = useEmotionStore()
const auth = useAuthStore()
const player = usePlayerStore()
const router = useRouter()

const favoriteIds = ref(new Set())
const ratings = reactive({})
const busyIds = reactive({})

const recommendation = computed(() => store.recommendations)
const local = computed(() => recommendation.value?.local || [])
const online = computed(() => recommendation.value?.online || [])
const currentEmotion = computed(() => store.result?.emotion || recommendation.value?.emotion || 'neutral')
const accent = computed(() => emotionColor(currentEmotion.value))
const playQueue = computed(() => [...local.value, ...online.value])
const isLoading = computed(() => store.loadingRecommendations)
const hasAny = computed(() => local.value.length || online.value.length)
const isCurrent = (track) => player.current?.id === track.id && player.current?.source === track.source

async function loadFavorites() {
  if (!auth.isAuthenticated) {
    favoriteIds.value = new Set()
    return
  }
  try {
    const response = await emotionApi.favorites()
    favoriteIds.value = new Set((response.data.items || []).map((item) => Number(item.id)))
  } catch {
    favoriteIds.value = new Set()
  }
}

function requireLogin() {
  if (auth.isAuthenticated) return true
  ElMessage.info(t('recommendation.loginToSave'))
  router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
  return false
}

function play(trackItem) {
  if (isCurrent(trackItem) && player.isPlaying) {
    player.toggle()
    return
  }
  player.play(trackItem, playQueue.value)
}

async function toggleFavorite(trackItem) {
  if (!requireLogin()) return
  if (busyIds[trackItem.id]) return
  busyIds[trackItem.id] = true
  const wasSaved = favoriteIds.value.has(Number(trackItem.id))
  try {
    if (wasSaved) {
      await emotionApi.unfavorite(trackItem.id)
      favoriteIds.value.delete(Number(trackItem.id))
    } else {
      await emotionApi.favorite(trackItem.id)
      favoriteIds.value.add(Number(trackItem.id))
      track('favorite_added', { trackId: Number(trackItem.id) })
    }
    // 重新赋值触发 Set 依赖更新
    favoriteIds.value = new Set(favoriteIds.value)
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    busyIds[trackItem.id] = false
  }
}

async function rate(trackItem, rating) {
  if (!requireLogin()) return
  if (busyIds[trackItem.id]) return
  busyIds[trackItem.id] = true
  try {
    await emotionApi.feedback(trackItem.id, rating)
    ratings[trackItem.id] = rating
    ElMessage.success(t('recommendation.feedbackSaved'))
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    busyIds[trackItem.id] = false
  }
}

function retry() {
  store.loadRecommendations(currentEmotion.value)
}

watch(
  () => auth.user?.id,
  () => loadFavorites(),
)

onMounted(loadFavorites)
</script>

<template>
  <section id="recommendations" class="recommendation-section">
    <div class="container">
      <div class="rec-head">
        <div>
          <p class="eyebrow">{{ t('recommendation.eyebrow') }} · {{ currentEmotion.toUpperCase() }}</p>
          <h2>
            {{ t('recommendation.title', { emotion: t(`emotions.${currentEmotion}`) }) }}
            <span class="emotion-underline" :style="{ background: accent }"></span>
          </h2>
          <p class="lead">{{ t('recommendation.lead') }}</p>
        </div>
        <div class="formula-card">
          <span class="mono">SCORING</span>
          <p>{{ recommendation?.algorithm?.formula || t('recommendation.algorithmNote') }}</p>
        </div>
      </div>

      <AsyncState
        v-if="isLoading"
        :loading="true"
        :skeleton-rows="4"
      />
      <div v-else-if="store.recommendationError" class="rec-error card">
        <div>
          <strong>{{ t('common.loadFailed') }}</strong>
          <p class="small muted">{{ store.recommendationError.message }}</p>
        </div>
        <button class="btn ghost" @click="retry">{{ t('common.retry') }}</button>
      </div>
      <div v-else-if="!hasAny" class="rec-empty card">
        <div class="empty-mark">♫</div>
        <strong>{{ t('recommendation.empty') }}</strong>
        <button class="btn ghost" @click="retry">{{ t('common.retry') }}</button>
      </div>
      <div v-else class="rec-layout">
        <div class="local-column">
          <div class="column-head">
            <span class="column-title">{{ t('recommendation.local') }}</span>
            <span class="mono">{{ String(local.length).padStart(2, '0') }} TRACKS</span>
          </div>
          <div class="track-list">
            <TrackRow
              v-for="(item, index) in local"
              :key="`${item.source}-${item.id}`"
              :track="item"
              :index="index"
              :playing="player.current?.id === item.id && player.current?.source === item.source && player.isPlaying"
              :saved="favoriteIds.has(Number(item.id))"
              :rating="ratings[item.id] || 0"
              @play="play"
              @favorite="toggleFavorite"
              @rate="rate"
            />
          </div>
          <div v-if="auth.isAuthenticated" class="preference-note">
            <el-icon><MagicStick /></el-icon>
            <span>{{ t('recommendation.feedbackSaved') }}</span>
          </div>
        </div>

        <aside class="online-column">
          <div class="online-head">
            <div>
              <span class="column-title">{{ t('recommendation.online') }}</span>
              <p class="small muted">iTunes Search · 30 sec preview</p>
            </div>
            <span class="online-badge">ONLINE</span>
          </div>
          <div v-if="online.length" class="online-list">
            <button
              v-for="item in online"
              :key="item.id"
              class="online-track"
              :class="{ active: player.current?.id === item.id }"
              @click="play(item)"
            >
              <span class="online-cover">
                <img v-if="item.coverUrl" :src="item.coverUrl" :alt="item.title" width="52" height="52" loading="lazy" />
                <span class="online-play"><el-icon><VideoPlay /></el-icon></span>
              </span>
              <span class="online-info">
                <strong>{{ item.title }}</strong>
                <span>{{ item.artist }}</span>
              </span>
              <el-icon class="online-arrow"><TopRight /></el-icon>
            </button>
          </div>
          <p v-else class="online-empty small muted">
            {{ recommendation?.onlineNotice || t('recommendation.onlineEmpty') }}
          </p>
          <div class="online-footer">
            <span class="mono">SOURCE · APPLE MUSIC API</span>
            <span class="small">{{ t('player.onlineNotice') }}</span>
          </div>
        </aside>
      </div>

      <div class="algorithm-strip">
        <span class="eyebrow">{{ t('algorithms.recTitle') }}</span>
        <p>{{ t('recommendation.algorithmNote') }}</p>
        <router-link to="/algorithms" class="link">{{ t('algorithms.recSubtitle') }} →</router-link>
      </div>
    </div>
  </section>
</template>

<style scoped>
.recommendation-section {
  padding: 74px 0;
  scroll-margin-top: 86px;
  border-top: 1px solid var(--line);
  background:
    radial-gradient(ellipse at 80% 12%, color-mix(in srgb, var(--accent) 5%, transparent), transparent 48%),
    color-mix(in srgb, var(--surface-2) 42%, transparent);
}
.rec-head {
  display: grid;
  grid-template-columns: 1.35fr 0.65fr;
  gap: 32px;
  align-items: end;
  margin-bottom: 34px;
}
.rec-head h2 {
  margin-top: 10px;
  font-size: clamp(32px, 4vw, 52px);
  position: relative;
  display: inline-block;
}
.emotion-underline {
  position: absolute;
  left: 0;
  right: 12%;
  bottom: -7px;
  height: 3px;
  opacity: 0.42;
  border-radius: 3px;
}
.rec-head .lead {
  margin-top: 18px;
  color: var(--muted);
  max-width: 580px;
}
.formula-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 16px;
}
.formula-card .mono {
  font-size: 8px;
  color: var(--accent);
  letter-spacing: 0.12em;
}
.formula-card p {
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.7;
  margin-top: 7px;
}
.rec-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(290px, 0.7fr);
  gap: 22px;
}
.column-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.column-head .mono {
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.08em;
}
.column-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.track-list {
  display: grid;
  gap: 7px;
}
.preference-note {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 14px;
  font-size: 10px;
  color: var(--muted);
}
.preference-note .el-icon {
  color: var(--accent);
}
.online-column {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.online-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}
.online-head p {
  margin-top: 4px;
  font-size: 10px;
}
.online-badge {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.08em;
  color: var(--signal);
  background: var(--signal-soft);
  padding: 4px 6px;
  border-radius: 4px;
}
.online-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
}
.online-track {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 7px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  color: inherit;
  transition: background 150ms;
}
.online-track:hover,
.online-track.active {
  background: var(--surface-2);
}
.online-cover {
  width: 42px;
  height: 42px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
  background: var(--surface-3);
}
.online-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.online-play {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(10, 10, 15, 0.3);
  opacity: 0;
  transition: opacity 150ms;
  font-size: 14px;
}
.online-track:hover .online-play {
  opacity: 1;
}
.online-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.online-info strong {
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.online-info span {
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.online-arrow {
  margin-left: auto;
  color: var(--muted-2);
  font-size: 13px;
}
.online-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.online-footer .mono {
  font-size: 7px;
  letter-spacing: 0.08em;
  color: var(--muted-2);
}
.online-footer .small {
  font-size: 9px;
  color: var(--muted);
}
.online-empty {
  padding: 22px 0;
  line-height: 1.7;
}
.algorithm-strip {
  margin-top: 24px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 18px;
  padding: 13px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface) 50%, transparent);
}
.algorithm-strip p {
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.6;
}
.algorithm-strip .link {
  font-size: 10px;
  white-space: nowrap;
}
.rec-error,
.rec-empty {
  padding: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.rec-empty {
  flex-direction: column;
  text-align: center;
  justify-content: center;
  min-height: 220px;
}
.empty-mark {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 24px;
  color: var(--muted);
  border: 1px solid var(--line);
}
@media (max-width: 1000px) {
  .rec-head {
    grid-template-columns: 1fr;
  }
  .formula-card {
    display: none;
  }
  .rec-layout {
    grid-template-columns: 1fr;
  }
  .algorithm-strip {
    grid-template-columns: 1fr;
    gap: 7px;
  }
}
@media (max-width: 640px) {
  .recommendation-section {
    padding: 48px 0;
  }
  .rec-head h2 {
    font-size: 34px;
  }
  .track-list {
    gap: 6px;
  }
  .online-column {
    padding: 13px;
  }
}
</style>
