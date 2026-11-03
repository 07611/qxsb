<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { usePlayerStore } from '@/stores/player'
import { useNotificationStore } from '@/stores/notifications'
import { contentApi, emotionApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { emotionColor, formatDate, relativeTime } from '@/utils/format'
import { track } from '@/utils/track'
import AsyncState from '@/components/ui/AsyncState.vue'
import PostCard from '@/components/content/PostCard.vue'
import TrackRow from '@/components/recommendation/TrackRow.vue'

const { t, locale } = useI18n()
const auth = useAuthStore()
const player = usePlayerStore()
const notifications = useNotificationStore()

const activeTab = ref('favorites')
const loading = ref(true)
const error = ref(null)
const favorites = ref([])
const emotions = ref([])
const recommendations = ref([])
const myItems = ref([])
const tabLoading = ref(false)
const busy = reactive({})

const tabs = computed(() => [
  { key: 'favorites', label: t('extra.meFavorites') },
  { key: 'emotions', label: t('extra.meEmotions') },
  { key: 'recommendations', label: t('extra.meRecommendations') },
  { key: 'items', label: t('extra.meItems') },
])

const profile = computed(() => auth.user || {})
const stats = computed(() => [
  { label: t('recommendation.favorite'), value: favorites.value.length },
  { label: t('me.emotionRecords'), value: emotions.value.length },
  { label: t('me.myNotes'), value: myItems.value.length },
])

async function loadBase() {
  loading.value = true
  error.value = null
  try {
    await auth.refreshProfile()
    notifications.fetchUnread()
    const [favoriteResponse, emotionResponse, recommendationResponse, itemResponse] = await Promise.all([
      emotionApi.favorites(),
      emotionApi.history({ pageSize: 12 }),
      emotionApi.recommendationHistory({ pageSize: 12 }),
      contentApi.items({ mine: true, pageSize: 12 }),
    ])
    favorites.value = favoriteResponse.data.items || []
    emotions.value = emotionResponse.data.items || []
    recommendations.value = recommendationResponse.data.items || []
    myItems.value = itemResponse.data.items || []
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function play(track) {
  player.play(track, favorites.value)
}

async function unfavorite(track) {
  if (busy[track.id]) return
  busy[track.id] = true
  try {
    await emotionApi.unfavorite(track.id)
    favorites.value = favorites.value.filter((item) => item.id !== track.id)
    track('favorite_removed', { trackId: track.id })
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    busy[track.id] = false
  }
}

onMounted(loadBase)
</script>

<template>
  <div class="page me-page">
    <div class="container">
      <AsyncState :loading="loading" :error="error" @retry="loadBase">
        <header class="me-header">
          <div class="profile-block">
            <div class="profile-avatar">
              <img v-if="profile.avatarUrl" :src="profile.avatarUrl" alt="" width="120" height="120" />
              <span v-else class="avatar-fallback">{{ (profile.nickname || 'M').slice(0, 1) }}</span>
              <span class="status-chip">{{ profile.role === 'admin' ? t('admin.roles.admin') : t('admin.roles.user') }}</span>
            </div>
            <div>
              <p class="eyebrow">LISTENER PROFILE</p>
              <h1>{{ profile.nickname }}</h1>
              <p class="bio">{{ profile.bio || t('settings.bioPlaceholder') }}</p>
              <div class="profile-meta">
                <span>{{ profile.email }}</span>
                <span class="dot"></span>
                <span>{{ formatDate(profile.createdAt, locale) }}</span>
                <span class="dot"></span>
                <router-link to="/settings/profile">{{ t('common.edit') }} →</router-link>
              </div>
            </div>
          </div>
          <div class="header-actions">
            <router-link to="/items/new" class="btn primary"><el-icon><EditPen /></el-icon>{{ t('nav.create') }}</router-link>
            <router-link to="/settings/security" class="btn ghost">{{ t('nav.security') }}</router-link>
          </div>
        </header>

        <div class="profile-stats">
          <div v-for="stat in stats" :key="stat.label" class="stat-card">
            <strong>{{ String(stat.value).padStart(2, '0') }}</strong>
            <span>{{ stat.label }}</span>
          </div>
          <div class="stat-card stat-quote">
            <p>“{{ t('emotions.neutralNote') }}”</p>
            <span class="mono">MOODWAVE / DAILY SIGNAL</span>
          </div>
        </div>

        <div class="me-tabs">
          <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
            {{ tab.label }}
          </button>
        </div>

        <AsyncState :loading="tabLoading" :empty="false">
          <section v-if="activeTab === 'favorites'" class="tab-panel">
            <AsyncState :empty="!favorites.length" :empty-text="t('extra.meEmptyFavorites')">
              <div class="favorite-list">
                <TrackRow
                  v-for="(track, index) in favorites"
                  :key="track.id"
                  :track="track"
                  :index="index"
                  :saved="true"
                  :playing="player.current?.id === track.id && player.isPlaying"
                  @play="play"
                  @favorite="unfavorite"
                />
              </div>
            </AsyncState>
          </section>

          <section v-else-if="activeTab === 'emotions'" class="tab-panel">
            <AsyncState :empty="!emotions.length" :empty-text="t('extra.meEmptyEmotions')">
              <div class="emotion-timeline">
                <div v-for="entry in emotions" :key="entry.id" class="timeline-row">
                  <span class="timeline-dot" :style="{ background: emotionColor(entry.emotion) }"></span>
                  <div class="timeline-main">
                    <div class="timeline-head">
                      <strong :style="{ color: emotionColor(entry.emotion) }">{{ t(`emotions.${entry.emotion}`) }}</strong>
                      <span class="mono">{{ Math.round(entry.confidence * 100) }}%</span>
                    </div>
                    <div class="score-line">
                      <i v-for="(value, key) in entry.scores" :key="key" :style="{ width: `${value * 100}%`, background: emotionColor(key), opacity: key === entry.emotion ? 1 : 0.22 }"></i>
                    </div>
                    <p class="small muted">{{ t(`emotions.${entry.emotion}Note`) }}</p>
                  </div>
                  <span class="timeline-time mono">{{ relativeTime(entry.createdAt, locale) }}</span>
                </div>
              </div>
            </AsyncState>
          </section>

          <section v-else-if="activeTab === 'recommendations'" class="tab-panel">
            <AsyncState :empty="!recommendations.length" :empty-text="t('extra.meEmptyRecommendations')">
              <div class="rec-history">
                <div v-for="entry in recommendations" :key="`${entry.id}-${entry.recommendedAt}`" class="rec-history-row">
                  <span class="rec-mood" :style="{ color: emotionColor(entry.recommendedFor) }">{{ t(`emotions.${entry.recommendedFor}`) }}</span>
                  <div>
                    <strong>{{ entry.title }}</strong>
                    <p class="small muted">{{ entry.reason }}</p>
                  </div>
                  <span class="mono">{{ Math.round((entry.score || 0) * 100) }}%</span>
                </div>
              </div>
            </AsyncState>
          </section>

          <section v-else class="tab-panel">
            <div class="items-head">
              <p class="small muted">{{ t('extra.meNoteCount', { count: myItems.length }) }}</p>
              <router-link to="/items/new" class="btn ghost">{{ t('nav.create') }}</router-link>
            </div>
            <AsyncState :empty="!myItems.length" :empty-text="t('extra.meEmptyItems')">
              <div class="items-grid">
                <PostCard v-for="item in myItems" :key="item.id" :item="item" />
              </div>
            </AsyncState>
          </section>
        </AsyncState>
      </AsyncState>
    </div>
  </div>
</template>

<style scoped>
.me-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  padding-bottom: 28px;
}
.profile-block {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.profile-avatar {
  position: relative;
  width: 118px;
  height: 118px;
  flex-shrink: 0;
}
.profile-avatar > img,
.profile-avatar .avatar-fallback {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 44px;
  color: var(--accent);
  background: var(--surface-2);
  border: 1px solid var(--line);
}
.profile-avatar > img {
  display: block;
}
.status-chip {
  position: absolute;
  bottom: -3px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink);
  color: var(--bg);
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 8px;
  white-space: nowrap;
}
.profile-block h1 {
  font-size: clamp(38px, 5vw, 62px);
  margin: 7px 0 8px;
}
.bio {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
  max-width: 460px;
}
.profile-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
  color: var(--muted-2);
  font-size: 10px;
}
.profile-meta a {
  color: var(--accent);
}
.dot {
  width: 3px;
  height: 3px;
  background: var(--muted-2);
  border-radius: 50%;
}
.header-actions {
  display: flex;
  gap: 6px;
}
.profile-stats {
  display: grid;
  grid-template-columns: repeat(3, 0.5fr) 1.5fr;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.stat-card {
  min-height: 95px;
  padding: 17px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 5px;
  justify-content: center;
}
.stat-card strong {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 540;
  letter-spacing: -0.04em;
}
.stat-card span {
  color: var(--muted);
  font-size: 10px;
}
.stat-quote {
  background: var(--surface-2);
  justify-content: center;
}
.stat-quote p {
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.3;
  letter-spacing: -0.02em;
}
.stat-quote .mono {
  font-size: 7px;
  color: var(--muted-2);
  margin-top: 5px;
}
.me-tabs {
  display: flex;
  gap: 2px;
  margin: 35px 0 18px;
  border-bottom: 1px solid var(--line);
}
.me-tabs button {
  background: transparent;
  border: 0;
  padding: 10px 13px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  position: relative;
}
.me-tabs button.active {
  color: var(--ink);
}
.me-tabs button.active::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  background: var(--accent);
}
.favorite-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}
.emotion-timeline {
  display: flex;
  flex-direction: column;
}
.timeline-row {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 15px;
  border-top: 1px solid var(--line);
  padding: 15px 0;
  align-items: start;
}
.timeline-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-top: 5px;
}
.timeline-head {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.timeline-head strong {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 560;
}
.timeline-head .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.score-line {
  display: flex;
  gap: 2px;
  height: 3px;
  max-width: 280px;
  margin: 8px 0;
}
.score-line i {
  border-radius: 2px;
}
.timeline-header p {
  font-size: 11px;
}
.timeline-time {
  font-size: 8px;
  color: var(--muted-2);
  white-space: nowrap;
  padding-top: 5px;
}
.rec-history {
  display: flex;
  flex-direction: column;
}
.rec-history-row {
  display: grid;
  grid-template-columns: 60px 1fr auto;
  gap: 15px;
  border-top: 1px solid var(--line);
  padding: 13px 0;
  align-items: center;
}
.rec-mood {
  font-family: var(--font-mono);
  font-size: 9px;
}
.rec-history-row strong {
  font-size: 13px;
}
.rec-history-row .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.items-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.items-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (max-width: 950px) {
  .me-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .profile-stats {
    grid-template-columns: repeat(3, 1fr);
  }
  .stat-quote {
    display: none;
  }
  .items-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 700px) {
  .profile-block {
    flex-direction: column;
    gap: 16px;
  }
  .profile-avatar {
    width: 88px;
    height: 88px;
  }
  .profile-block h1 {
    font-size: 38px;
  }
  .favorite-list {
    grid-template-columns: 1fr;
  }
  .me-tabs {
    overflow-x: auto;
    white-space: nowrap;
  }
  .timeline-row {
    grid-template-columns: 8px 1fr;
  }
  .timeline-time {
    display: none;
  }
  .items-grid {
    grid-template-columns: 1fr;
  }
  .header-actions {
    width: 100%;
  }
  .header-actions .btn {
    flex: 1;
  }
}
</style>
