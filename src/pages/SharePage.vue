<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { contentApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDate } from '@/utils/format'

const route = useRoute()
const { t, locale } = useI18n()
const data = ref(null)
const loading = ref(true)
const error = ref(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await contentApi.getShare(route.params.code)
    data.value = response.data
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="share-page">
    <div class="container share-inner">
      <div class="share-brand mono">MOODWAVE · SHARED NOTE</div>
      <div v-if="loading" class="share-card loading-card">
        <div class="skeleton" style="aspect-ratio: 16/8"></div>
        <div class="skeleton" style="height: 32px; margin-top: 24px"></div>
        <div class="skeleton" style="height: 14px; margin-top: 12px; width: 70%"></div>
      </div>
      <div v-else-if="error" class="share-card error-card">
        <div class="error-mark">◌</div>
        <h1>{{ error.message }}</h1>
        <p class="muted">{{ t('errors.notFound') }}</p>
        <router-link to="/" class="btn primary">{{ t('nav.home') }}</router-link>
      </div>
      <article v-else class="share-card">
        <div class="share-cover" :style="{ aspectRatio: '16 / 8' }">
          <img v-if="data.coverUrl" :src="data.coverUrl" :alt="data.title" width="1200" height="600" />
          <div v-else class="share-placeholder">MOODWAVE</div>
        </div>
        <div class="share-body">
          <div class="share-meta">
            <span class="chip">SHARE CODE · {{ data.code }}</span>
            <span>{{ data.owner?.nickname }}</span>
            <span>{{ t('extra.expiresOn', { date: formatDate(data.expiresAt, locale) }) }}</span>
          </div>
          <h1>{{ data.title }}</h1>
          <p class="excerpt">{{ data.excerpt }}</p>
          <router-link :to="`/items/${data.itemId}`" class="btn primary">{{ t('item.detailEyebrow') }} →</router-link>
        </div>
      </article>
      <p class="share-note mono">SERVER-RENDERED OPEN GRAPH · {{ data?.viewCount || 0 }} VIEWS</p>
    </div>
  </div>
</template>

<style scoped>
.share-page {
  min-height: 100vh;
  padding: 44px 0 80px;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(91, 91, 214, 0.08), transparent 40%),
    var(--bg);
}
.share-inner {
  max-width: 840px;
}
.share-brand {
  font-size: 9px;
  letter-spacing: 0.16em;
  color: var(--muted);
  margin-bottom: 20px;
}
.share-card {
  border: 1px solid var(--line);
  border-radius: 16px;
  overflow: hidden;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
.loading-card,
.error-card {
  padding: 26px;
}
.error-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  min-height: 280px;
  justify-content: center;
}
.error-card h1 {
  font-size: clamp(30px, 4vw, 44px);
}
.error-mark {
  font-size: 38px;
  color: var(--muted);
}
.share-cover {
  width: 100%;
  overflow: hidden;
  background: var(--surface-2);
}
.share-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.share-placeholder {
  height: 100%;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 40px;
  letter-spacing: 0.1em;
  color: var(--muted-2);
}
.share-body {
  padding: clamp(24px, 5vw, 52px);
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.share-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  color: var(--muted);
  font-size: 11px;
}
.share-body h1 {
  font-size: clamp(34px, 6vw, 56px);
  line-height: 1.1;
}
.excerpt {
  color: var(--muted);
  line-height: 1.8;
  font-size: 16px;
  max-width: 650px;
}
.share-body .btn {
  align-self: flex-start;
}
.share-note {
  margin-top: 18px;
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.08em;
}
@media (max-width: 600px) {
  .share-page {
    padding-top: 20px;
  }
}
</style>
