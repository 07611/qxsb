<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { contentApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDate, readingMinutes } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'
import PostCard from '@/components/content/PostCard.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const item = ref(null)
const related = ref([])
const loading = ref(true)
const error = ref(null)
const deleting = ref(false)
const sharing = ref(false)

const paragraphs = computed(() => (item.value?.content || '').split(/\n{2,}/).filter(Boolean))
const cover = computed(() => item.value?.coverUrl)
const readMinutes = computed(() => readingMinutes(item.value?.content))

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await contentApi.item(route.params.id)
    item.value = response.data.item
    if (item.value?.category?.slug) {
      const rel = await contentApi.items({ category: item.value.category.slug, pageSize: 4 })
      related.value = (rel.data.items || []).filter((entry) => entry.id !== item.value.id).slice(0, 3)
    }
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

async function share() {
  sharing.value = true
  try {
    const response = await contentApi.share({ targetType: 'item', targetId: item.value.id, expiresInDays: 7 })
    const url = response.data.url
    try {
      await navigator.clipboard.writeText(url)
      ElMessage.success(t('item.shareCreated'))
    } catch {
      ElMessageBox.alert(url, t('item.share'), { confirmButtonText: t('common.close') })
    }
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    sharing.value = false
  }
}

async function remove() {
  try {
    await ElMessageBox.confirm(t('common.confirmDelete'), t('item.delete'), {
      confirmButtonText: t('item.delete'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await contentApi.remove(item.value.id)
    ElMessage.success(t('item.deleted'))
    router.replace('/me')
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page item-page">
    <div class="container">
      <AsyncState :loading="loading" :error="error" @retry="load">
        <article v-if="item" class="item-article">
          <header class="item-header">
            <div class="crumb">
              <router-link to="/discover">{{ t('nav.discover') }}</router-link>
              <span>/</span>
              <router-link v-if="item.category" :to="`/categories/${item.category.slug}`">{{ item.category.name }}</router-link>
              <span v-else>NOTE</span>
            </div>
            <div class="header-grid">
              <div>
                <div class="badges">
                  <span class="eyebrow">{{ t('item.detailEyebrow') }}</span>
                  <span v-if="item.status === 'draft'" class="draft-badge">{{ t('item.draftBadge') }}</span>
                </div>
                <h1>{{ item.title }}</h1>
                <div class="byline">
                  <span class="author-avatar">
                    <img v-if="item.owner?.avatarUrl" :src="item.owner.avatarUrl" alt="" width="34" height="34" />
                    <span v-else>{{ item.owner?.nickname?.slice(0, 1) }}</span>
                  </span>
                  <span>{{ t('item.by', { name: item.owner?.nickname }) }}</span>
                  <span class="dot"></span>
                  <span>{{ formatDate(item.createdAt, locale) }}</span>
                  <span class="dot"></span>
                  <span>{{ t('item.readTime', { minutes: readMinutes }) }}</span>
                </div>
              </div>
              <div class="header-actions">
                <button class="btn ghost" @click="share" :disabled="sharing">
                  <el-icon><Share /></el-icon>{{ t('item.share') }}
                </button>
                <template v-if="item.canEdit">
                  <router-link :to="`/items/new?edit=${item.id}`" class="btn ghost"><el-icon><Edit /></el-icon>{{ t('common.edit') }}</router-link>
                  <button class="btn danger" :disabled="deleting" @click="remove"><el-icon><Delete /></el-icon>{{ t('common.delete') }}</button>
                </template>
              </div>
            </div>
          </header>

          <div v-if="cover" class="hero-cover">
            <img :src="cover" :alt="item.title" width="1600" height="800" />
            <span class="cover-caption mono">MOODWAVE / NOTE {{ String(item.id).padStart(4, '0') }}</span>
          </div>

          <div class="article-layout">
            <div class="article-body">
              <p v-for="(paragraph, index) in paragraphs" :key="index">{{ paragraph }}</p>
              <div class="article-end">
                <span class="mono">END OF NOTE</span>
                <div class="end-line"></div>
                <span class="mono">{{ t('item.commentsOff') }}</span>
              </div>
            </div>
            <aside class="article-aside">
              <div v-if="item.category" class="aside-block">
                <span class="eyebrow">{{ t('item.category') }}</span>
                <router-link :to="`/categories/${item.category.slug}`" class="aside-category">{{ item.category.name }} <el-icon><Right /></el-icon></router-link>
              </div>
              <div v-if="item.tags.length" class="aside-block">
                <span class="eyebrow">{{ t('item.tags') }}</span>
                <div class="aside-tags">
                  <router-link v-for="tag in item.tags" :key="tag.id" :to="`/tags/${tag.slug}`">#{{ tag.name }}</router-link>
                </div>
              </div>
              <div class="aside-block">
                <span class="eyebrow">INFO</span>
                <div class="aside-info">
                  <span>{{ t('status.published') }}</span>
                  <span class="mono">{{ formatDate(item.updatedAt, locale) }}</span>
                </div>
              </div>
              <div class="quote-card">
                <p>“{{ t('emotions.happyNote') }}”</p>
                <span class="mono">MOODWAVE / EDITORIAL</span>
              </div>
            </aside>
          </div>
        </article>

        <section v-if="related.length" class="related-section">
          <div class="section-head">
            <div>
              <p class="eyebrow">KEEP READING</p>
              <h2>{{ t('item.related') }}</h2>
            </div>
          </div>
          <div class="related-grid">
            <PostCard v-for="entry in related" :key="entry.id" :item="entry" />
          </div>
        </section>
      </AsyncState>
    </div>
  </div>
</template>

<style scoped>
.item-page {
  padding-top: 30px;
}
.crumb {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 9px;
  color: var(--muted);
  margin-bottom: 26px;
  font-family: var(--font-mono);
}
.crumb a:hover {
  color: var(--accent);
}
.header-grid {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 26px;
  margin-bottom: 28px;
}
.badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.draft-badge {
  font-size: 8px;
  color: var(--signal);
  border: 1px solid color-mix(in srgb, var(--signal) 30%, var(--line));
  background: var(--signal-soft);
  border-radius: 3px;
  padding: 3px 5px;
}
.item-header h1 {
  font-size: clamp(38px, 5.5vw, 72px);
  max-width: 900px;
  margin: 12px 0 20px;
  line-height: 1.04;
}
.byline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  color: var(--muted);
  font-size: 11px;
}
.author-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 10px;
  color: var(--accent);
}
.author-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--muted-2);
}
.header-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  align-items: center;
}
.header-actions .btn {
  min-height: 36px;
  padding: 0 10px;
  font-size: 11px;
}
.hero-cover {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--line);
  max-height: 520px;
  aspect-ratio: 2 / 1;
  background: var(--surface-2);
}
.hero-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-caption {
  position: absolute;
  bottom: 13px;
  right: 14px;
  font-size: 7px;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.68);
  background: rgba(16, 16, 22, 0.45);
  backdrop-filter: blur(6px);
  padding: 3px 5px;
  border-radius: 2px;
}
.article-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  gap: 60px;
  max-width: 1040px;
  margin: 52px auto 0;
}
.article-body {
  font-size: 17px;
  line-height: 1.85;
  color: var(--ink-2);
  white-space: pre-wrap;
}
.article-body p + p {
  margin-top: 1.35em;
}
.article-body p:first-child::first-letter {
  font-family: var(--font-display);
  font-size: 2.8em;
  float: left;
  line-height: 0.88;
  padding: 0.08em 0.1em 0 0;
  color: var(--ink);
}
.article-end {
  margin-top: 52px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted-2);
}
.article-end .mono {
  font-size: 7px;
  letter-spacing: 0.07em;
}
.end-line {
  flex: 1;
  height: 1px;
  background: var(--line);
}
.article-aside {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.aside-block {
  display: flex;
  flex-direction: column;
  gap: 9px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.aside-category {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 3px;
}
.aside-category:hover {
  color: var(--accent);
}
.aside-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.aside-tags a {
  font-size: 10px;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
}
.aside-tags a:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.aside-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 10px;
  color: var(--muted);
}
.aside-info .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.quote-card {
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface-2);
}
.quote-card p {
  font-family: var(--font-display);
  font-size: 15px;
  line-height: 1.45;
  letter-spacing: -0.02em;
}
.quote-card .mono {
  font-size: 7px;
  color: var(--muted-2);
  display: block;
  margin-top: 10px;
}
.related-section {
  margin-top: 68px;
  border-top: 1px solid var(--line);
  padding-top: 38px;
}
.related-section h2 {
  margin-top: 9px;
  font-size: 34px;
}
.related-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-top: 22px;
}
@media (max-width: 900px) {
  .header-grid {
    flex-direction: column;
    align-items: flex-start;
  }
  .article-layout {
    grid-template-columns: 1fr;
    gap: 26px;
    margin-top: 34px;
  }
  .article-aside {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .quote-card {
    display: none;
  }
  .related-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 600px) {
  .item-page {
    padding-top: 18px;
  }
  .item-header h1 {
    font-size: 36px;
  }
  .header-actions {
    flex-wrap: wrap;
  }
  .hero-cover {
    aspect-ratio: 16 / 10;
  }
  .article-body {
    font-size: 16px;
  }
  .article-aside {
    grid-template-columns: 1fr;
  }
  .related-grid {
    grid-template-columns: 1fr;
  }
}
</style>
