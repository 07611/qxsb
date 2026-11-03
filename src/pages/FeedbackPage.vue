<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { socialApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDateTime, statusType } from '@/utils/format'
import PageHeader from '@/components/ui/PageHeader.vue'
import AsyncState from '@/components/ui/AsyncState.vue'
import ImageUploader from '@/components/content/ImageUploader.vue'

const { t, locale } = useI18n()
const formRef = ref(null)
const form = reactive({ type: 'bug', content: '', images: [], contact: '' })
const submitting = ref(false)
const formError = ref('')
const tickets = ref([])
const pagination = ref(null)
const loading = ref(true)
const error = ref(null)
const page = ref(1)
const supplementOpen = ref(false)
const supplementText = ref('')
const activeTicket = ref(null)
const supplementing = ref(false)

const typeOptions = ['bug', 'feature', 'experience', 'other']
const rules = {
  content: [
    { required: true, message: t('feedback.content'), trigger: 'blur' },
    { min: 5, max: 3000, message: '5–3000', trigger: 'blur' },
  ],
}

const imageUrls = computed(() => form.images.map((item) => item.url))

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await socialApi.myFeedback({ page: page.value, pageSize: 10 })
    tickets.value = response.data.items || []
    pagination.value = response.data.pagination
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

async function submit() {
  formError.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const response = await socialApi.feedback({
      type: form.type,
      content: form.content.trim(),
      images: imageUrls.value,
      contact: form.contact.trim() || undefined,
    })
    ElMessage.success(t('feedback.submitted', { ticket: response.data.feedback.ticketNo }))
    form.content = ''
    form.images = []
    form.contact = ''
    form.type = 'bug'
    formRef.value?.clearValidate()
    page.value = 1
    await load()
  } catch (error) {
    formError.value = normalizeError(error).message
  } finally {
    submitting.value = false
  }
}

function openSupplement(ticket) {
  activeTicket.value = ticket
  supplementText.value = ''
  supplementOpen.value = true
}

async function addSupplement() {
  if (!supplementText.value.trim()) return
  supplementing.value = true
  try {
    const response = await socialApi.supplement(activeTicket.value.id, supplementText.value.trim())
    const index = tickets.value.findIndex((item) => item.id === activeTicket.value.id)
    if (index >= 0) tickets.value[index] = response.data.feedback
    supplementOpen.value = false
    ElMessage.success(t('feedback.supplementAdded'))
  } catch (error) {
    ElMessage.error(normalizeError(error).message)
  } finally {
    supplementing.value = false
  }
}

function changePage(next) {
  page.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="page feedback-page">
    <div class="container">
      <PageHeader eyebrow="FEEDBACK" :title="t('feedback.title')" :lead="t('feedback.lead')" />

      <div class="feedback-layout">
        <div class="feedback-form card">
          <div class="form-head">
            <span class="mono">NEW TICKET</span>
            <span class="mono">{{ new Date().getFullYear() }}</span>
          </div>
          <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
            <el-form-item :label="t('feedback.type')">
              <div class="type-picker">
                <button
                  v-for="type in typeOptions"
                  :key="type"
                  type="button"
                  :class="{ active: form.type === type }"
                  @click="form.type = type"
                >
                  {{ t(`feedback.types.${type}`) }}
                </button>
              </div>
            </el-form-item>
            <el-form-item :label="t('feedback.content')" prop="content">
              <el-input v-model="form.content" type="textarea" :rows="7" maxlength="3000" show-word-limit :placeholder="t('feedback.contentPlaceholder')" />
            </el-form-item>
            <el-form-item :label="t('feedback.images')">
              <ImageUploader v-model="form.images" multiple :max="3" biz-type="feedback" aspect="16 / 10" :hint="t('feedback.imagesHint')" />
            </el-form-item>
            <el-form-item :label="t('feedback.contact')">
              <el-input v-model="form.contact" maxlength="255" :placeholder="t('extra.contactPlaceholder')" />
            </el-form-item>
            <el-alert v-if="formError" type="error" :closable="false" show-icon class="mb">{{ formError }}</el-alert>
            <div class="form-actions">
              <button class="btn primary" type="button" :disabled="submitting" @click="submit">
                {{ submitting ? t('common.processing') : t('feedback.submit') }}
                <el-icon><Promotion /></el-icon>
              </button>
            </div>
          </el-form>
          <p class="lock-note"><el-icon><Lock /></el-icon> {{ t('feedback.originalLocked') }} · {{ t('feedback.lead') }}</p>
        </div>

        <aside class="ticket-panel">
          <div class="ticket-head">
            <div>
              <p class="eyebrow">MY TICKETS</p>
              <h3>{{ t('feedback.myTickets') }}</h3>
            </div>
            <span v-if="pagination" class="mono">{{ String(pagination.total).padStart(2, '0') }}</span>
          </div>
          <AsyncState :loading="loading" :error="error" :empty="!loading && !tickets.length" :empty-text="t('feedback.empty')" :skeleton-rows="3" @retry="load">
            <div class="ticket-list">
              <button v-for="ticket in tickets" :key="ticket.id" class="ticket-card" @click="openSupplement(ticket)">
                <div class="ticket-top">
                  <span class="mono">{{ ticket.ticketNo }}</span>
                  <el-tag :type="statusType(ticket.status)" size="small">{{ t(`feedback.statuses.${ticket.status}`) }}</el-tag>
                </div>
                <div class="ticket-type">{{ t(`feedback.types.${ticket.type}`) }}</div>
                <p class="ticket-content">{{ ticket.content }}</p>
                <div v-if="ticket.reply" class="ticket-reply">
                  <span class="mono">↳ REPLY</span>
                  <p>{{ ticket.reply }}</p>
                </div>
                <div class="ticket-foot">
                  <span>{{ formatDateTime(ticket.createdAt, locale) }}</span>
                  <span>{{ ticket.supplementary?.length || 0 }} {{ t('feedback.supplement') }}</span>
                </div>
              </button>
            </div>
          </AsyncState>
          <div v-if="pagination && pagination.pages > 1" class="ticket-pagination">
            <el-pagination
              small
              background
              layout="prev, pager, next"
              :current-page="pagination.page"
              :page-size="pagination.pageSize"
              :total="pagination.total"
              @current-change="changePage"
            />
          </div>
        </aside>
      </div>
    </div>

    <el-drawer v-model="supplementOpen" :title="activeTicket?.ticketNo" size="min(520px, 92vw)">
      <div v-if="activeTicket" class="drawer-content">
        <div class="drawer-meta">
          <el-tag :type="statusType(activeTicket.status)">{{ t(`feedback.statuses.${activeTicket.status}`) }}</el-tag>
          <span class="mono">{{ formatDateTime(activeTicket.createdAt, locale) }}</span>
        </div>
        <div class="original-message">
          <span class="eyebrow">{{ t('feedback.content') }}</span>
          <p>{{ activeTicket.content }}</p>
          <span class="lock-label"><el-icon><Lock /></el-icon>{{ t('feedback.originalLocked') }}</span>
        </div>
        <div v-if="activeTicket.images?.length" class="drawer-images">
          <img v-for="(image, index) in activeTicket.images" :key="index" :src="image.thumbUrl || image.url || image" alt="" width="240" height="150" />
        </div>
        <div v-if="activeTicket.reply" class="official-reply">
          <span class="eyebrow">{{ t('feedback.reply') }}</span>
          <p>{{ activeTicket.reply }}</p>
        </div>
        <div v-if="activeTicket.supplementary?.length" class="supplements">
          <span class="eyebrow">{{ t('feedback.supplement') }}</span>
          <div v-for="(entry, index) in activeTicket.supplementary" :key="index" class="supplement-entry">
            <p>{{ entry.content }}</p>
            <span class="mono">{{ formatDateTime(entry.createdAt, locale) }}</span>
          </div>
        </div>
        <div v-if="activeTicket.status !== 'closed'" class="supplement-form">
          <el-input v-model="supplementText" type="textarea" :rows="3" maxlength="1000" :placeholder="t('feedback.supplementPlaceholder')" />
          <button class="btn primary" :disabled="supplementing || !supplementText.trim()" @click="addSupplement">
            {{ supplementing ? t('common.saving') : t('feedback.supplement') }}
          </button>
        </div>
        <p v-else class="closed-note">{{ t('feedback.closed') }}</p>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.feedback-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 22px;
  align-items: start;
}
.feedback-form {
  padding: 26px;
}
.form-head {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 11px;
  margin-bottom: 18px;
}
.form-head .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.type-picker {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.type-picker button {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  min-height: 34px;
  padding: 0 12px;
  font-size: 11px;
  transition: all 150ms;
}
.type-picker button.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.form-actions {
  display: flex;
  justify-content: flex-end;
}
.mb {
  margin-bottom: 14px;
}
.lock-note {
  display: flex;
  gap: 7px;
  align-items: flex-start;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 15px;
  color: var(--muted-2);
  font-size: 9px;
  line-height: 1.6;
}
.ticket-panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 17px;
}
.ticket-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
  margin-bottom: 4px;
}
.ticket-head h3 {
  margin-top: 5px;
  font-size: 22px;
}
.ticket-head .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.ticket-list {
  display: flex;
  flex-direction: column;
}
.ticket-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  text-align: left;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--line);
  color: inherit;
  padding: 12px 4px;
}
.ticket-card:hover {
  background: var(--surface-2);
}
.ticket-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ticket-top .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.ticket-type {
  font-size: 9px;
  font-weight: 650;
  color: var(--accent);
}
.ticket-content {
  font-size: 11.5px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ticket-reply {
  background: var(--surface-2);
  border-left: 2px solid var(--accent);
  padding: 6px 8px;
  margin-top: 3px;
}
.ticket-reply .mono {
  font-size: 6.5px;
  color: var(--muted-2);
}
.ticket-reply p {
  font-size: 10px;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 2px;
}
.ticket-foot {
  display: flex;
  justify-content: space-between;
  font-size: 8px;
  color: var(--muted-2);
  margin-top: 3px;
}
.ticket-pagination {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.drawer-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.drawer-meta .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.original-message {
  background: var(--surface-2);
  border-radius: 7px;
  padding: 14px;
}
.original-message p {
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}
.lock-label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--muted-2);
  font-size: 8px;
}
.drawer-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.drawer-images img {
  width: calc(50% - 3px);
  height: auto;
  aspect-ratio: 16/10;
  object-fit: cover;
  border-radius: 5px;
  border: 1px solid var(--line);
}
.official-reply {
  border-left: 2px solid var(--accent);
  padding-left: 12px;
}
.official-reply p {
  font-size: 12px;
  line-height: 1.7;
  margin-top: 6px;
}
.supplements {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.supplement-entry {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px;
}
.supplement-entry p {
  font-size: 11px;
  line-height: 1.65;
}
.supplement-entry .mono {
  font-size: 7px;
  color: var(--muted-2);
  display: block;
  margin-top: 5px;
}
.supplement-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
.closed-note {
  font-size: 10px;
  color: var(--muted);
  padding: 10px;
  background: var(--surface-2);
  border-radius: 5px;
}
@media (max-width: 950px) {
  .feedback-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .feedback-form {
    padding: 18px;
  }
  .type-picker button {
    flex: 1;
  }
  .form-actions .btn {
    width: 100%;
  }
}
</style>
