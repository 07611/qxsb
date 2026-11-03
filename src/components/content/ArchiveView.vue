<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { contentApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDate } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'
import PostCard from '@/components/content/PostCard.vue'

const props = defineProps({ kind: { type: String, required: true } })
const route = useRoute()
const { t, locale } = useI18n()
const taxonomy = ref(null)
const items = ref([])
const pagination = ref(null)
const loading = ref(true)
const error = ref(null)
const page = ref(1)

const slug = computed(() => String(route.params.slug || ''))
const title = computed(() => {
  if (!taxonomy.value) return slug.value
  return props.kind === 'category' ? taxonomy.value.category?.name : taxonomy.value.tag?.name
})
const eyebrow = computed(() => (props.kind === 'category' ? `CATEGORY / ${t('extra.category')}` : `TAG / ${t('extra.tag')}`))
const description = computed(() =>
  props.kind === 'category' ? taxonomy.value?.category?.description : t('extra.tagArchive', { name: title.value }),
)

async function load(nextPage = 1) {
  loading.value = true
  error.value = null
  page.value = nextPage
  try {
    const [taxResponse, itemResponse] = await Promise.all([
      props.kind === 'category' ? contentApi.category(slug.value) : contentApi.tag(slug.value),
      contentApi.items({
        [props.kind]: slug.value,
        page: nextPage,
        pageSize: 9,
      }),
    ])
    taxonomy.value = taxResponse.data
    items.value = itemResponse.data.items || []
    pagination.value = itemResponse.data.pagination
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(slug, () => load(1))
</script>

<template>
  <div class="page archive-page">
    <div class="container">
      <AsyncState :loading="loading && !taxonomy" :error="error" @retry="load(page)">
        <header class="archive-head">
          <div class="archive-index">
            <span class="mono">{{ kind === 'category' ? 'CAT' : 'TAG' }}</span>
            <span class="hash">#</span>
          </div>
          <div>
            <p class="eyebrow">{{ eyebrow }}</p>
            <h1>{{ title }}</h1>
            <p class="lead">{{ description }}</p>
            <div class="archive-meta">
              <span class="mono">{{ pagination?.total || 0 }} NOTES</span>
              <span v-if="kind === 'category' && taxonomy?.category?.children?.length" class="mono">
                {{ taxonomy.category.children.length }} SUB-CATEGORIES
              </span>
            </div>
          </div>
        </header>

        <div v-if="kind === 'category' && taxonomy?.category?.children?.length" class="children-row">
          <router-link v-for="child in taxonomy.category.children" :key="child.id" :to="`/categories/${child.slug}`" class="chip">
            {{ child.name }} <span class="mono">{{ child.postCount }}</span>
          </router-link>
        </div>

        <div class="archive-divider"></div>
        <AsyncState :loading="loading" :error="error" :empty="!loading && !items.length" :empty-text="t('common.empty')" @retry="load(page)">
          <div class="archive-grid">
            <PostCard v-for="item in items" :key="item.id" :item="item" />
          </div>
        </AsyncState>

        <div v-if="pagination && pagination.pages > 1" class="archive-pagination">
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="pagination.page"
            :page-size="pagination.pageSize"
            :total="pagination.total"
            @current-change="load"
          />
        </div>
      </AsyncState>
    </div>
  </div>
</template>

<style scoped>
.archive-head {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 26px;
  align-items: start;
  padding-bottom: 32px;
}
.archive-index {
  display: flex;
  Flex-direction: column;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px;
  aspect-ratio: 1;
  justify-content: center;
  background: var(--surface);
}
.archive-index .mono {
  font-size: 8px;
  color: var(--muted-2);
  letter-spacing: 0.1em;
}
.hash {
  font-family: var(--font-display);
  font-size: 30px;
  color: var(--accent);
  line-height: 1;
  margin-top: 4px;
}
h1 {
  font-size: clamp(46px, 7vw, 82px);
  margin: 10px 0 13px;
}
.lead {
  color: var(--muted);
  max-width: 650px;
  line-height: 1.7;
}
.archive-meta {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  color: var(--muted-2);
}
.archive-meta .mono {
  font-size: 8px;
  letter-spacing: 0.04em;
}
.children-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-bottom: 20px;
}
.archive-divider {
  border-top: 1px solid var(--line);
  margin-bottom: 22px;
}
.archive-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.archive-pagination {
  display: flex;
  justify-content: center;
  margin-top: 30px;
}
@media (max-width: 900px) {
  .archive-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 600px) {
  .archive-head {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .archive-index {
    width: 52px;
    aspect-ratio: auto;
    padding: 8px;
  }
  .hash {
    font-size: 22px;
  }
  .archive-grid {
    grid-template-columns: 1fr;
  }
}
</style>
