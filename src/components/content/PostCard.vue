<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatDate } from '@/utils/format'

const props = defineProps({
  item: { type: Object, required: true },
  featured: Boolean,
})
const { t, locale } = useI18n()
const cover = computed(() => props.item.coverThumbUrl || props.item.coverUrl)
const gradient = computed(() => {
  const seed = Number(props.item.id || 1)
  const palettes = [
    'linear-gradient(135deg,#5B5BD6,#2E3A56)',
    'linear-gradient(135deg,#E8A23B,#E8552F)',
    'linear-gradient(135deg,#4F8C86,#2E4B46)',
    'linear-gradient(135deg,#9B6BD6,#443252)',
  ]
  return palettes[seed % palettes.length]
})
</script>

<template>
  <router-link :to="`/items/${item.id}`" class="post-card" :class="{ featured }">
    <div class="post-cover" :style="cover ? {} : { background: gradient }">
      <img v-if="cover" :src="cover" :alt="item.title" width="720" height="420" loading="lazy" />
      <div v-else class="cover-type">PLAYLIST NOTE</div>
      <div class="cover-overlay">
        <span v-if="item.category" class="category-chip">{{ item.category.name }}</span>
        <span v-if="item.status === 'draft'" class="draft-chip">{{ t('item.draftBadge') }}</span>
      </div>
    </div>
    <div class="post-body">
      <div class="post-meta">
        <span class="mono">{{ formatDate(item.createdAt, locale, { year: undefined }) }}</span>
        <span class="meta-dot"></span>
        <span>{{ item.owner?.nickname }}</span>
      </div>
      <h3 class="post-title">{{ item.title }}</h3>
      <p class="post-excerpt">{{ item.excerpt }}</p>
      <div class="post-foot">
        <div class="post-tags">
          <span v-for="tag in (item.tags || []).slice(0, 3)" :key="tag.id" class="mini-tag">#{{ tag.name }}</span>
        </div>
        <span class="read-arrow"><el-icon><ArrowRight /></el-icon></span>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
.post-card {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
  transition: all 260ms var(--ease);
}
.post-card:hover {
  border-color: var(--line-strong);
  transform: translateY(-4px);
  box-shadow: var(--shadow-sm);
}
.post-cover {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: linear-gradient(135deg, var(--surface-2), var(--surface-3));
}
.post-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 700ms var(--ease);
}
.post-card:hover .post-cover img {
  transform: scale(1.035);
}
.cover-type {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.2em;
  font-size: 9px;
}
.cover-overlay {
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  justify-content: space-between;
}
.category-chip,
.draft-chip {
  font-size: 9.5px;
  font-weight: 650;
  padding: 4px 8px;
  border-radius: 4px;
  color: #fff;
  background: rgba(20, 20, 26, 0.54);
  backdrop-filter: blur(8px);
}
.draft-chip {
  background: var(--signal);
}
.post-body {
  padding: 17px 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.post-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 9px;
  color: var(--muted);
}
.post-meta .mono {
  font-size: 8px;
  letter-spacing: 0.04em;
}
.meta-dot {
  width: 3px;
  height: 3px;
  background: var(--muted-2);
  border-radius: 50%;
}
.post-title {
  font-size: clamp(19px, 1.8vw, 24px);
  line-height: 1.25;
  letter-spacing: -0.035em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.post-excerpt {
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.post-foot {
  margin-top: auto;
  padding-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.post-tags {
  display: flex;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}
.mini-tag {
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
}
.read-arrow {
  color: var(--muted-2);
  transition: transform 180ms;
}
.post-card:hover .read-arrow {
  color: var(--accent);
  transform: translateX(3px);
}
.post-card.featured .post-cover {
  aspect-ratio: 16 / 10;
}
.post-card.featured .post-title {
  font-size: clamp(22px, 2.4vw, 32px);
}
</style>
