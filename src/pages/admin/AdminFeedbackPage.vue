<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDateTime, statusType } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const items = ref([])
const pagination = ref(null)
const summary = ref({})
const loading = ref(true)
const error = ref(null)
const status = ref('')
const query = ref('')
const page = ref(1)
const drawerOpen = ref(false)
const active = ref(null)
const reply = ref('')
const nextStatus = ref('')
const saving = ref(false)

const statuses = ['open', 'processing', 'resolved', 'closed']
const allowedNext = {
  open: ['processing', 'resolved', 'closed'],
  processing: ['resolved', 'closed'],
  resolved: ['closed'],
  closed: [],
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await adminApi.feedback({
      status: status.value || undefined,
      q: query.value || undefined,
      page: page.value,
      pageSize: 15,
    })
    items.value = response.data.items || []
    pagination.value = response.data.pagination
    summary.value = response.data.summary || {}
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function filter(next) {
  status.value = next
  page.value = 1
  load()
}

function openTicket(ticket) {
  active.value = ticket
  reply.value = ticket.reply || ''
  nextStatus.value = ticket.status
  drawerOpen.value = true
}

async function save() {
  if (!active.value) return
  saving.value = true
  try {
    const payload = {}
    if (reply.value.trim() && reply.value !== active.value.reply) payload.reply = reply.value.trim()
    if (nextStatus.value !== active.value.status) payload.status = nextStatus.value
    if (!Object.keys(payload).length) {
      drawerOpen.value = false
      return
    }
    const response = await adminApi.replyFeedback(active.value.id, payload)
    const index = items.value.findIndex((item) => item.id === active.value.id)
    if (index >= 0) items.value[index] = response.data.feedback
    active.value = response.data.feedback
    ElMessage.success(t('admin.replied'))
    await load()
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    saving.value = false
  }
}

function changePage(next) {
  page.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="admin-feedback-page">
    <div class="page-title">
      <div>
        <p class="eyebrow">SUPPORT DESK</p>
        <h1>{{ t('admin.feedbackTitle') }}</h1>
      </div>
      <span class="mono">{{ pagination?.total || 0 }} TICKETS</span>
    </div>

    <div class="summary-row">
      <button v-for="entry in statuses" :key="entry" class="summary-cell" :class="{ active: status === entry }" @click="filter(entry === status ? '' : entry)">
        <span class="mono">{{ entry.toUpperCase() }}</span>
        <strong>{{ summary[entry] || 0 }}</strong>
      </button>
      <button class="summary-cell all" :class="{ active: !status }" @click="filter('')">
        <span class="mono">ALL</span>
        <strong>{{ Object.values(summary).reduce((a, b) => a + b, 0) }}</strong>
      </button>
    </div>

    <div class="filter-bar">
      <el-input v-model="query" placeholder="ticket / content" clearable @keyup.enter="load" />
      <button class="btn ghost small" @click="load">{{ t('common.search') }}</button>
    </div>

    <AsyncState :loading="loading" :error="error" :empty="!loading && !items.length" @retry="load">
      <div class="table-wrap">
        <el-table :data="items">
          <el-table-column label="TICKET" width="170">
            <template #default="{ row }">
              <button class="ticket-link" @click="openTicket(row)">{{ row.ticketNo }}</button>
              <span class="mono user-id">USER #{{ row.userId }}</span>
            </template>
          </el-table-column>
          <el-table-column label="TYPE" width="85">
            <template #default="{ row }">{{ t(`feedback.types.${row.type}`) }}</template>
          </el-table-column>
          <el-table-column label="CONTENT" min-width="280">
            <template #default="{ row }">
              <p class="content-cell">{{ row.content }}</p>
            </template>
          </el-table-column>
          <el-table-column :label="t('feedback.status')" width="95">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ t(`feedback.statuses.${row.status}`) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="CREATED" width="125">
            <template #default="{ row }"><span class="mono date-cell">{{ formatDateTime(row.createdAt, locale) }}</span></template>
          </el-table-column>
          <el-table-column label="" width="70" fixed="right">
            <template #default="{ row }">
              <button class="open-btn" @click="openTicket(row)">OPEN</button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="pagination-row">
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @current-change="changePage"
        />
      </div>
    </AsyncState>

    <el-drawer v-model="drawerOpen" :title="active?.ticketNo" size="min(560px, 94vw)">
      <div v-if="active" class="ticket-drawer">
        <div class="drawer-meta">
          <el-tag :type="statusType(active.status)">{{ t(`feedback.statuses.${active.status}`) }}</el-tag>
          <span class="mono">{{ formatDateTime(active.createdAt, locale) }}</span>
        </div>
        <div class="drawer-section">
          <p class="eyebrow">ORIGINAL</p>
          <p class="drawer-content">{{ active.content }}</p>
        </div>
        <div v-if="active.images?.length" class="drawer-images">
          <img v-for="(image, index) in active.images" :key="index" :src="image.thumbUrl || image.url || image" alt="" width="260" height="160" />
        </div>
        <div class="drawer-section">
          <p class="eyebrow">STATUS</p>
          <el-select v-model="nextStatus" size="small">
            <el-option :label="t('feedback.statuses.open')" value="open" disabled />
            <el-option :label="t('feedback.statuses.processing')" value="processing" :disabled="!allowedNext[active.status]?.includes('processing')" />
            <el-option :label="t('feedback.statuses.resolved')" value="resolved" :disabled="!allowedNext[active.status]?.includes('resolved')" />
            <el-option :label="t('feedback.statuses.closed')" value="closed" :disabled="!allowedNext[active.status]?.includes('closed')" />
          </el-select>
        </div>
        <div class="drawer-section">
          <p class="eyebrow">{{ t('admin.reply') }}</p>
          <el-input v-model="reply" type="textarea" :rows="5" maxlength="3000" :placeholder="t('admin.reply')" />
        </div>
        <button class="btn primary full-btn" :disabled="saving" @click="save">{{ saving ? t('common.saving') : t('common.save') }}</button>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.page-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
}
.page-title h1 {
  font-size: clamp(32px, 4vw, 48px);
  margin-top: 8px;
}
.page-title .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.summary-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 11px;
}
.summary-cell {
  border: 0;
  background: var(--surface);
  text-align: left;
  padding: 10px 12px;
  min-height: 68px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.summary-cell .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.summary-cell strong {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 540;
}
.summary-cell.active {
  background: var(--accent-soft);
  color: var(--accent);
}
.filter-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 11px;
}
.filter-bar .el-input {
  max-width: 240px;
}
.small {
  min-height: 34px;
  font-size: 9px;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.ticket-link {
  border: 0;
  background: transparent;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 8px;
  display: block;
  text-align: left;
}
.user-id {
  font-size: 6px;
  color: var(--muted-2);
}
.content-cell {
  font-size: 10px;
  color: var(--muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.date-cell {
  font-size: 7px;
  color: var(--muted-2);
}
.open-btn {
  border: 1px solid var(--line);
  background: transparent;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 6px;
  color: var(--muted);
  padding: 3px 4px;
}
.open-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.ticket-drawer {
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
.drawer-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.drawer-content {
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-wrap;
  background: var(--surface-2);
  padding: 12px;
  border-radius: 6px;
}
.drawer-images {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.drawer-images img {
  width: calc(50% - 3px);
  aspect-ratio: 16/10;
  object-fit: cover;
  border-radius: 5px;
  border: 1px solid var(--line);
}
.full-btn {
  width: 100%;
}
@media (max-width: 650px) {
  .summary-row {
    grid-template-columns: repeat(3, 1fr);
  }
  .page-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>
