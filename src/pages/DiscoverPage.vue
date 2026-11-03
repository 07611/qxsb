<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { contentApi, emotionApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { emotionColor, formatNumber } from '@/utils/format'
import PageHeader from '@/components/ui/PageHeader.vue'
import AsyncState from '@/components/ui/AsyncState.vue'
import PostCard from '@/components/content/PostCard.vue'
import { usePlayerStore } from '@/stores/player'

const { t, locale } = useI18n()
const player = usePlayerStore()
const categories = ref([])
const tags = ref([])
const tracks = ref([])
const items = ref([])
const loading = ref(true)
const error = ref(null)
const mood = ref('')
const trackLoading = ref(false)

const moods = ['happy', 'sad', 'angry', 'surprised', 'fear', 'neutral']

async function loadAll() {
  loading.value = true
  error.value = null
  try {
    const [categoryResponse, tagResponse, trackResponse, itemResponse] = await Promise.all([
      contentApi.categories(),
      contentApi.tags({ sort: 'hot', pageSize: 20 }),
      emotionApi.local({ pageSize: 12 }),
      contentApi.items({ pageSize: 6 }),
    ])
    categories.value = categoryResponse.data.categories || []
    tags.value = tagResponse.data.tags || []
    tracks.value = trackResponse.data.items || []
    items.value = itemResponse.data.items || []
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

async function filterMood(next) {
  mood.value = next
  trackLoading.value = true
  try {
    const response = await emotionApi.local({ mood: next || undefined, pageSize: 12 })
    tracks.value = response.data.items || []
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    trackLoading.value = false
  }
}

function play(track) {
  player.play(track, tracks.value)
}

onMounted(loadAll)
</script>

<template>
  <div class="page discover-page">
    <div class="container">
      <PageHeader eyebrow="DISCOVER" :title="t('discover.title')" :lead="t('discover.lead')">
        <template #actions>
          <router-link to="/search" class="btn ghost"><el-icon><Search /></el-icon>{{ t('common.search') }}</router-link>
          <router-link v-if="$route.query.admin" to="/admin" class="btn ghost">{{ t('nav.admin') }}</router-link>
        </template>
      </PageHeader>

      <AsyncState :loading="loading" :error="error" :empty="false" @retry="loadAll">
        <div class="discover-layout">
          <section class="taxonomy-section">
            <div class="section-label"><span class="eyebrow">{{ t('discover.categories') }}</span><span class="mono">01</span></div>
            <div class="category-list">
              <div v-for="category in categories" :key="category.id" class="category-group">
                <router-link :to="`/categories/${category.slug}`" class="category-root">
                  <span>{{ category.name }}</span><span class="category-count mono">{{ category.postCount }}</span>
                </router-link>
                <div v-if="category.children?.length" class="category-children">
                  <router-link v-for="child in category.children" :key="child.id" :to="`/categories/${child.slug}`">
                    {{ child.name }}<span class="mono">{{ child.postCount }}</span>
                  </router-link>
                </div>
              </div>
            </div>
            <div class="tag-cloud">
              <div class="section-label"><span class="eyebrow">{{ t('discover.hotTags') }}</span><span class="mono">02</span></div>
              <router-link v-for="tag in tags" :key="tag.id" :to="`/tags/${tag.slug}`" class="tag-cloud-item">
                #{{ tag.name }}<span>{{ tag.postCount }}</span>
              </router-link>
            </div>
          </section>

          <section class="library-section">
            <div class="section-label">
              <span class="eyebrow">{{ t('discover.tracks') }}</span>
              <span class="mono">03 / LOCAL</span>
            </div>
            <div class="mood-filters">
              <button class="chip" :class="{ active: !mood }" @click="filterMood('')">{{ t('discover.moodAll') }}</button>
              <button
                v-for="item in moods"
                :key="item"
                class="chip"
                :class="{ active: mood === item }"
                @click="filterMood(item)"
              >
                <span class="mood-dot" :style="{ background: emotionColor(item) }"></span>
                {{ t(`emotions.${item}`) }}
              </button>
            </div>
            <div v-if="trackLoading" class="track-grid">
              <div v-for="i in 4" :key="i" class="skeleton" style="height: 82px"></div>
            </div>
            <AsyncState v-else :empty="!tracks.length" :empty-text="t('recommendation.empty')">
              <div class="track-grid">
                <button
                  v-for="(track, index) in tracks"
                  :key="track.id"
                  class="library-track"
                  :class="{ playing: player.current?.id === track.id && player.isPlaying }"
                  @click="play(track)"
                >
                  <span class="library-cover">
                    <img v-if="track.coverUrl" :src="track.coverUrl" :alt="track.title" width="76" height="76" loading="lazy" />
                    <span class="library-play"><el-icon><VideoPlay /></el-icon></span>
                  </span>
                  <span class="library-info">
                    <span class="library-title">{{ track.title }}</span>
                    <span class="library-artist">{{ track.artist }}</span>
                    <span class="library-meta">
                      <span :style="{ color: emotionColor(track.mood) }">{{ t(`emotions.${track.mood}`) }}</span>
                      <span v-if="track.audioFeatures?.tempo">{{ Math.round(track.audioFeatures.tempo) }} BPM</span>
                      <span>{{ track.duration }}s</span>
                    </span>
                  </span>
                  <span class="library-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
                </button>
              </div>
            </AsyncState>
          </section>
        </div>

        <section class="latest-items">
          <div class="section-head">
            <div>
              <p class="eyebrow">COMMUNITY NOTES</p>
              <h2>{{ t('discover.items') }}</h2>
            </div>
            <router-link to="/search" class="btn ghost">{{ t('common.more') }}</router-link>
          </div>
          <AsyncState :empty="!items.length">
            <div class="post-grid">
              <PostCard v-for="item in items" :key="item.id" :item="item" />
            </div>
          </AsyncState>
        </section>
      </AsyncState>
    </div>
  </div>
</template>

<style scoped>
.discover-page {
  padding-top: 46px;
}
.discover-layout {
  display: grid;
  grid-template-columns: 0.7fr 1.3fr;
  gap: 54px;
  border-top: 1px solid var(--line);
  padding-top: 34px;
}
.section-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-label .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.category-list {
  display: flex;
  flex-direction: column;
}
.category-group {
  border-top: 1px solid var(--line);
  padding: 12px 0;
}
.category-root {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-display);
  font-size: 20px;
  letter-spacing: -0.03em;
  padding: 4px 0;
}
.category-root:hover {
  color: var(--accent);
}
.category-count {
  color: var(--muted-2);
  font-size: 8px;
}
.category-children {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 7px;
  padding-left: 12px;
  border-left: 1px solid var(--line);
}
.category-children a {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--muted);
  padding: 4px 0;
}
.category-children a:hover {
  color: var(--ink);
}
.category-children .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.tag-cloud {
  margin-top: 38px;
}
.tag-cloud .section-label {
  margin-bottom: 12px;
}
.tag-cloud-item {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 5px 9px;
  margin: 0 4px 4px 0;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 11px;
  color: var(--muted);
}
.tag-cloud-item span {
  font-size: 8px;
  color: var(--muted-2);
}
.tag-cloud-item:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.mood-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 14px;
}
.mood-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.track-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}
.library-track {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  text-align: left;
  color: inherit;
  transition: all 180ms var(--ease);
}
.library-track:hover,
.library-track.playing {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.library-cover {
  position: relative;
  width: 58px;
  height: 58px;
  border-radius: 7px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surface-2);
}
.library-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.library-play {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(15, 15, 20, 0.36);
  opacity: 0;
}
.library-track:hover .library-play {
  opacity: 1;
}
.library-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.library-title {
  font-size: 12.5px;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.library-artist {
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.library-meta {
  display: flex;
  gap: 6px;
  font-size: 8px;
  color: var(--muted-2);
  margin-top: 3px;
}
.library-index {
  margin-left: auto;
  color: var(--muted-2);
  font-size: 8px;
}
.latest-items {
  margin-top: 62px;
  padding-top: 40px;
  border-top: 1px solid var(--line);
}
.latest-items h2 {
  margin-top: 9px;
}
.post-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-top: 24px;
}
@media (max-width: 1000px) {
  .discover-layout {
    grid-template-columns: 1fr;
    gap: 34px;
  }
  .track-grid {
    grid-template-columns: 1fr;
  }
  .post-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 640px) {
  .post-grid {
    grid-template-columns: 1fr;
  }
  .latest-items {
    margin-top: 36px;
  }
  .tag-cloud {
    margin-top: 26px;
  }
}
</style>
