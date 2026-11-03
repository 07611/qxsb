<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { contentApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/hooks/useAsync'
import PageHeader from '@/components/ui/PageHeader.vue'
import AsyncState from '@/components/ui/AsyncState.vue'
import ImageUploader from '@/components/content/ImageUploader.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const categories = ref([])
const tagOptions = ref([])
const cover = ref(null)
const submitting = ref(false)
const errorMessage = ref('')
const loadingEdit = ref(false)
const editingId = computed(() => (route.query.edit ? Number(route.query.edit) : null))
const isEditing = computed(() => Boolean(editingId.value))

const form = reactive({
  title: '',
  content: '',
  categoryId: null,
  tags: [],
  status: 'published',
})

const rules = {
  title: [
    { required: true, message: t('item.title'), trigger: 'blur' },
    { min: 2, max: 120, message: t('extra.charRange120'), trigger: 'blur' },
  ],
  content: [
    { required: true, message: t('item.content'), trigger: 'blur' },
    { min: 1, max: 20000, message: t('extra.charRange20000'), trigger: 'blur' },
  ],
}

const categoryTree = computed(() => categories.value)
const flatCategories = computed(() => {
  const list = []
  for (const root of categories.value) {
    for (const child of root.children || []) list.push(child)
  }
  return list
})
const selectedCategory = computed(() => {
  if (!form.categoryId) return null
  for (const root of categories.value) {
    if (root.id === form.categoryId) return root
    const child = root.children?.find((entry) => entry.id === form.categoryId)
    if (child) return child
  }
  return null
})
const coverPayload = computed(() => (cover.value?.url ? cover.value.url : null))
const previewTags = computed(() => form.tags.filter(Boolean).slice(0, 8))

async function loadTaxonomy() {
  try {
    const [categoryResponse, tagResponse] = await Promise.all([
      contentApi.categories(),
      contentApi.tags({ sort: 'hot', pageSize: 100 }),
    ])
    categories.value = categoryResponse.data.categories || []
    tagOptions.value = tagResponse.data.tags || []
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  }
}

async function loadExisting() {
  if (!editingId.value) return
  loadingEdit.value = true
  try {
    const response = await contentApi.item(editingId.value)
    const item = response.data.item
    if (!response.data.item.canEdit) {
      errorMessage.value = t('item.ownerOnly')
      return
    }
    form.title = item.title
    form.content = item.content
    form.categoryId = item.category?.id || null
    form.tags = item.tags.map((tag) => tag.name)
    form.status = item.status === 'draft' ? 'draft' : 'published'
    if (item.coverUrl) cover.value = { url: item.coverUrl, thumbUrl: item.coverThumbUrl || item.coverUrl }
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    loadingEdit.value = false
  }
}

async function save(status) {
  errorMessage.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      categoryId: form.categoryId || null,
      tags: form.tags.filter(Boolean).slice(0, 8),
      coverUrl: cover.value?.url || null,
      coverThumbUrl: cover.value?.thumbUrl || cover.value?.url || null,
      status,
    }
    let response
    if (editingId.value) response = await contentApi.update(editingId.value, payload)
    else response = await contentApi.create(payload)
    ElMessage.success(status === 'draft' ? t('item.draftSaved') : isEditing.value ? t('item.updated') : t('item.created'))
    router.push(`/items/${response.data.item.id}`)
  } catch (error) {
    const normalized = normalizeError(error)
    errorMessage.value = normalized.message
  } finally {
    submitting.value = false
  }
}

function onCover(value) {
  cover.value = value
}

onMounted(async () => {
  await loadTaxonomy()
  await loadExisting()
})
</script>

<template>
  <div class="page editor-page">
    <div class="container">
      <PageHeader
        :eyebrow="t('item.newEyebrow')"
        :title="isEditing ? t('item.editTitle') : t('item.newTitle')"
        :lead="t('item.coverHint')"
      >
        <template #actions>
          <router-link to="/discover" class="btn quiet">← {{ t('common.cancel') }}</router-link>
        </template>
      </PageHeader>

      <AsyncState :loading="loadingEdit" :error="errorMessage ? { message: errorMessage } : null" @retry="loadExisting">
        <div class="editor-layout">
          <div class="editor-form card">
            <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
              <el-form-item :label="t('item.title')" prop="title">
                <el-input v-model="form.title" :placeholder="t('item.titlePlaceholder')" maxlength="120" show-word-limit />
              </el-form-item>
              <el-form-item :label="t('item.content')" prop="content">
                <el-input
                  v-model="form.content"
                  type="textarea"
                  :rows="14"
                  maxlength="20000"
                  show-word-limit
                  :placeholder="t('item.contentPlaceholder')"
                />
              </el-form-item>
              <div class="two-col">
                <el-form-item :label="t('item.category')">
                  <el-select v-model="form.categoryId" clearable :placeholder="t('common.select')">
                    <el-option-group v-for="root in categoryTree" :key="root.id" :label="root.name">
                      <el-option :label="root.name" :value="root.id" />
                      <el-option v-for="child in root.children" :key="child.id" :label="`  ${child.name}`" :value="child.id" />
                    </el-option-group>
                  </el-select>
                </el-form-item>
                <el-form-item :label="t('item.tags')">
                  <el-select
                    v-model="form.tags"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    :multiple-limit="8"
                    :placeholder="t('item.tagsPlaceholder')"
                  >
                    <el-option v-for="tag in tagOptions" :key="tag.id" :label="tag.name" :value="tag.name" />
                  </el-select>
                </el-form-item>
              </div>
              <el-form-item :label="t('item.cover')">
                <ImageUploader :model-value="cover" biz-type="item_cover" aspect="16 / 8" :hint="t('item.coverHint')" @update:model-value="onCover" />
              </el-form-item>

              <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="editor-error">
                {{ errorMessage }}
              </el-alert>

              <div class="editor-actions">
                <button type="button" class="btn ghost" :disabled="submitting" @click="save('draft')">{{ t('item.saveDraft') }}</button>
                <button type="button" class="btn primary" :disabled="submitting" @click="save('published')">
                  {{ submitting ? t('common.saving') : isEditing ? t('item.update') : t('item.publish') }}
                  <el-icon><Right /></el-icon>
                </button>
              </div>
            </el-form>
          </div>

          <aside class="preview-panel">
            <div class="preview-label">
              <span class="eyebrow">LIVE PREVIEW</span>
              <span class="mono">DRAFT</span>
            </div>
            <div class="preview-card">
              <div class="preview-cover" :style="cover ? {} : { background: 'linear-gradient(135deg,#5B5BD6,#E8552F)' }">
                <img v-if="cover?.thumbUrl" :src="cover.thumbUrl" alt="" width="720" height="420" />
                <span v-else class="mono">PLAYLIST NOTE</span>
              </div>
              <div class="preview-body">
                <p class="mono preview-meta">{{ selectedCategory?.name || 'UNCATEGORIZED' }} · {{ auth.user?.nickname }}</p>
                <h3>{{ form.title || t('item.titlePlaceholder') }}</h3>
                <p class="preview-excerpt">{{ form.content ? form.content.slice(0, 150) + (form.content.length > 150 ? '…' : '') : t('item.contentPlaceholder') }}</p>
                <div class="preview-tags">
                  <span v-for="tag in previewTags" :key="tag">#{{ tag }}</span>
                </div>
              </div>
            </div>
            <div class="editor-tip">
              <el-icon><InfoFilled /></el-icon>
              <p>{{ t('item.coverHint') }}</p>
            </div>
            <div class="draft-meta">
              <div><span class="mono">TITLE</span><strong>{{ form.title.length }}/120</strong></div>
              <div><span class="mono">BODY</span><strong>{{ form.content.length }}/20000</strong></div>
              <div><span class="mono">TAGS</span><strong>{{ form.tags.length }}/8</strong></div>
            </div>
          </aside>
        </div>
      </AsyncState>
    </div>
  </div>
</template>

<style scoped>
.editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.55fr);
  gap: 22px;
  align-items: start;
}
.editor-form {
  padding: 26px;
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.editor-error {
  margin-bottom: 16px;
}
.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}
.preview-panel {
  position: sticky;
  top: 92px;
}
.preview-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.preview-label .mono {
  font-size: 7px;
  color: var(--muted-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 2px 4px;
}
.preview-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface);
}
.preview-cover {
  aspect-ratio: 16 / 9;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: var(--surface-2);
}
.preview-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.preview-cover .mono {
  color: rgba(255, 255, 255, 0.6);
  font-size: 8px;
  letter-spacing: 0.1em;
}
.preview-body {
  padding: 16px;
}
.preview-meta {
  font-size: 7px;
  color: var(--muted-2);
  letter-spacing: 0.05em;
}
.preview-body h3 {
  margin: 8px 0;
  font-size: 22px;
  line-height: 1.22;
}
.preview-excerpt {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.65;
  min-height: 38px;
}
.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
  font-size: 9px;
  color: var(--accent);
}
.editor-tip {
  display: flex;
  gap: 8px;
  padding: 11px;
  margin-top: 12px;
  border: 1px dashed var(--line);
  border-radius: 6px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.6;
}
.editor-tip .el-icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.draft-meta {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--line);
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}
.draft-meta > div {
  background: var(--surface-2);
  padding: 9px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.draft-meta .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.draft-meta strong {
  font-size: 10px;
  color: var(--muted);
}
@media (max-width: 1000px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
  .preview-panel {
    position: static;
    display: none;
  }
}
@media (max-width: 600px) {
  .two-col {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .editor-form {
    padding: 18px;
  }
  .editor-actions {
    flex-direction: column-reverse;
  }
  .editor-actions .btn {
    width: 100%;
  }
}
</style>
