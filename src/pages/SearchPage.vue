<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { contentApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { usePlayerStore } from '@/stores/player'
import { emotionColor, formatDate } from '@/utils/format'
import PageHeader from '@/components/ui/PageHeader.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const query = ref(String(route.query.q || ''))
const type = ref(String(route.query.type || 'all'))
const page = ref(Number(route.query.page || 1))
const results = ref(null)
const pagination = ref(null)
const loading = ref(false)
const error = ref(null)
const hot = ref([])
const searched = ref(false)

async function loadHot() {
  try {
    const response = await contentApi.hotSearch()
    hot.value = response.data.keywords || []
  } catch {
    hot.value = []
  }
}

async function load() {
  if (!query.value.trim()) {
    results.value = null
    searched.value = false
    return
  }
  loading.value = true
  error.value = null
  searched.value = true
  try {
    const response = await contentApi.search({ q: query.value.trim(), type: type.value, page: page.value, pageSize: 10 })
    results.value = response.data
    pagination.value = response.data.pagination
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function submit() {
  page.value = 1
  router.replace({ path: '/search', query: { q: query.value.trim(), type: type.value, page: 1 } })
  load()
}

function setType(next) {
  type.value = next
  page.value = 1
  router.replace({ path: '/search', query: { ...route.query, type: next, page: 1 } })
  load()
}

function onPage(next) {
  page.value = next
  router.replace({ path: '/search', query: { ...route.query, page: next } })
  load()
}

function useHot(keyword) {
  query.value = keyword
  submit()
}

function play(track) {
  player.play(track, results.value?.results.tracks || [])
}

watch(
  () => route.query,
  (next) => {
    query.value = String(next.q || '')
    type.value = String(next.type || 'all')
    page.value = Number(next.page || 1)
    load()
  },
)

onMounted(() => {
  loadHot()
  load()
})
</script>

<template>
  <div class="page search-page">
    <div class="container">
      <PageHeader eyebrow="SEARCH" :title="t('search.title')">
        <template #actions>
          <form class="search-form" @submit.prevent="submit">
            <el-icon><Search /></el-icon>
            <input v-model="query" type="search" :placeholder="t('search.placeholder')" autofocus />
            <button class="btn primary" type="submit">{{ t('common.search') }}</button>
          </form>
        </template>
      </PageHeader>

      <div class="hot-row">
        <span class="eyebrow">{{ t('search.hot') }}</span>
        <button v-for="word in hot" :key="word.keyword" class="chip" @click="useHot(word.keyword)">
          {{ word.keyword }}<span v-if="word.count" class="mono">{{ word.count }}</span>
        </button>
      </div>

      <div v-if="searched" class="result-toolbar">
        <div class="type-tabs">
          <button
            v-for="item in [
              { key: 'all', label: t('search.tabs.all') },
              { key: 'items', label: t('search.tabs.items') },
              { key: 'tracks', label: t('search.tabs.tracks') },
            ]"
            :key="item.key"
            :class="{ active: type === item.key }"
            @click="setType(item.key)"
          >
            {{ item.label }}
          </button>
        </div>
        <span v-if="pagination" class="small muted">{{ t('search.total', { total: pagination.total }) }}</span>
      </div>

      <AsyncState
        :loading="loading"
        :error="error"
        :empty="searched && !loading && !error && !(results?.results.items.length || results?.results.tracks.length)"
        :empty-text="t('search.empty')"
        :skeleton-rows="4"
        @retry="load"
      >
        <div v-if="results" class="results-wrap">
          <p class="result-caption">{{ t('search.resultFor', { q: results.keyword }) }}</p>

          <section v-if="results.results.items.length" class="result-section">
            <div class="section-label">
              <span class="eyebrow">{{ t('search.tabs.items') }}</span>
              <span class="mono">{{ String(results.pagination.itemTotal).padStart(2, '0') }}</span>
            </div>
            <router-link v-for="item in results.results.items" :key="item.id" :to="`/items/${item.id}`" class="item-result">
              <div class="result-cover">
                <img v-if="item.coverThumbUrl" :src="item.coverThumbUrl" :alt="item.title" width="200" height="125" loading="lazy" />
                <span v-else class="cover-ph">NOTE</span>
              </div>
              <div class="result-info">
                <div class="result-meta">
                  <span v-if="item.category">{{ item.category.name }}</span>
                  <span>{{ formatDate(item.createdAt, locale) }}</span>
                  <span>{{ item.owner?.nickname }}</span>
                </div>
                <h3>{{ item.title }}</h3>
                <p class="highlight" v-html="item.highlight"></p>
                <div class="result-tags">
                  <span v-for="tag in item.tags.slice(0, 4)" :key="tag.id">#{{ tag.name }}</span>
                </div>
              </div>
              <span class="result-arrow"><el-icon><Right /></el-icon></span>
            </router-link>
          </section>

          <section v-if="results.results.tracks.length" class="result-section">
            <div class="section-label">
              <span class="eyebrow">{{ t('search.tabs.tracks') }}</span>
              <span class="mono">{{ String(results.pagination.trackTotal).padStart(2, '0') }}</span>
            </div>
            <button
              v-for="track in results.results.tracks"
              :key="track.id"
              class="track-result"
              @click="play(track)"
            >
              <img v-if="track.coverUrl" :src="track.coverUrl" :alt="track.title" width="56" height="56" loading="lazy" />
              <span class="result-info">
                <strong>{{ track.title }}</strong>
                <span class="small muted">{{ track.artist }}</span>
                <span class="highlight small" v-html="track.highlight"></span>
              </span>
              <span class="mood-badge" :style="{ color: emotionColor(track.mood), borderColor: emotionColor(track.mood) }">
                {{ t(`emotions.${track.mood}`) }}
              </span>
              <el-icon><VideoPlay /></el-icon>
            </button>
          </section>

          <div v-if="pagination && pagination.pages > 1" class="search-pagination">
            <el-pagination
              background
              layout="prev, pager, next"
              :current-page="pagination.page"
              :page-size="pagination.pageSize"
              :total="pagination.total"
              @current-change="onPage"
            />
          </div>
        </div>
      </AsyncState>

      <div v-if="!searched" class="search-idle">
        <span class="idle-glyph">⌕</span>
        <p>{{ t('search.placeholder') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  min-height: 70vh;
}
.search-form {
  display: flex;
  align-items: center;
  gap: 9px;
  width: min(560px, 100%);
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 5px 5px 5px 13px;
  background: var(--surface);
  color: var(--muted);
}
.search-form:focus-within {
  border-color: var(--accent);
}
.search-form input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 15px;
  height: 38px;
}
.search-form .btn {
  min-height: 38px;
  font-size: 12px;
}
.hot-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding-bottom: 28px;
  border-bottom: 1px solid var(--line);
}
.hot-row .chip {
  gap: 5px;
}
.hot-row .chip .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
}
.type-tabs {
  display: flex;
  gap: 2px;
}
.type-tabs button {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  padding: 7px 11px;
  border-radius: 5px;
}
.type-tabs button.active {
  background: var(--surface-2);
  color: var(--ink);
  font-weight: 650;
}
.result-caption {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.05em;
  margin-bottom: 16px;
}
.result-section {
  margin-bottom: 28px;
}
.section-label {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 9px;
  margin-bottom: 5px;
}
.section-label .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.item-result {
  display: grid;
  grid-template-columns: 180px 1fr auto;
  gap: 18px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
  transition: all 160ms;
}
.item-result:hover {
  padding-left: 5px;
  background: color-mix(in srgb, var(--surface-2) 40%, transparent);
}
.result-cover {
  aspect-ratio: 16 / 10;
  border-radius: 6px;
  overflow: hidden;
  background: var(--surface-2);
}
.result-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-ph {
  display: grid;
  place-items: center;
  height: 100%;
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.12em;
}
.result-meta {
  display: flex;
  gap: 8px;
  font-size: 9px;
  color: var(--muted);
  margin-bottom: 4px;
}
.result-info h3 {
  font-size: 20px;
  margin-bottom: 5px;
}
.highlight {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.highlight :deep(mark) {
  color: var(--ink);
  background: color-mix(in srgb, var(--signal) 22%, transparent);
  padding: 0 2px;
  border-radius: 2px;
}
.result-tags {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  font-size: 9px;
  color: var(--muted-2);
}
.result-arrow {
  color: var(--muted-2);
}
.track-result {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 9px 6px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: inherit;
  text-align: left;
}
.track-result:hover {
  background: var(--surface-2);
}
.track-result > img {
  width: 50px;
  height: 50px;
  border-radius: 6px;
  object-fit: cover;
}
.track-result .result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.track-result strong {
  font-size: 13px;
}
.track-result .highlight {
  -webkit-line-clamp: 1;
  margin-top: 2px;
}
.mood-badge {
  font-size: 9px;
  border: 1px solid;
  border-radius: 999px;
  padding: 2px 7px;
}
.track-result > .el-icon {
  color: var(--muted);
}
.search-pagination {
  display: flex;
  justify-content: center;
  margin-top: 28px;
}
.search-idle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  padding: 70px 20px;
}
.idle-glyph {
  font-size: 44px;
  color: var(--line-strong);
}
@media (max-width: 700px) {
  .item-result {
    grid-template-columns: 100px 1fr;
    gap: 11px;
    align-items: start;
  }
  .result-cover {
    aspect-ratio: 1;
  }
  .result-arrow {
    display: none;
  }
  .result-info h3 {
    font-size: 16px;
  }
  .result-meta {
    flex-wrap: wrap;
    font-size: 8px;
  }
  .highlight {
    -webkit-line-clamp: 1;
  }
}
</style>
