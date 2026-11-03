<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { socialApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { useNotificationStore } from '@/stores/notifications'
import { formatDateTime, relativeTime } from '@/utils/format'
import PageHeader from '@/components/ui/PageHeader.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const router = useRouter()
const store = useNotificationStore()
const items = ref([])
const pagination = ref(null)
const unreadByType = ref([])
const loading = ref(true)
const error = ref(null)
const activeType = ref('')
const unreadOnly = ref(false)
const page = ref(1)
const typeOptions = ['system', 'security', 'approval', 'feedback', 'comment', 'push']
const unreadMap = computed(() => Object.fromEntries(unreadByType.value.map((item) => [item.value, item.count])))

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await socialApi.notifications({
      type: activeType.value || undefined,
      unreadOnly: unreadOnly.value || undefined,
      page: page.value,
      pageSize: 15,
    })
    items.value = response.data.items || []
    pagination.value = response.data.pagination
    unreadByType.value = response.data.unreadByType || []
    await store.fetchUnread()
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function setType(type) {
  activeType.value = type
  page.value = 1
  load()
}

function toggleUnread() {
  unreadOnly.value = !unreadOnly.value
  page.value = 1
  load()
}

async function markAll() {
  try {
    const response = await socialApi.markAllRead()
    ElMessage.success(t('notifications.markAllDone'))
    store.clear()
    await load()
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  }
}

async function markRead(item) {
  if (item.read) return
  try {
    await socialApi.markRead(item.id)
    item.read = true
    item.readAt = new Date().toISOString()
    store.decrement()
    await store.fetchUnread()
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  }
}

function target(item) {
  if (item.targetType === 'item') return `/items/${item.targetId}`
  if (item.targetType === 'feedback') return '/feedback'
  if (item.targetType === 'security') return '/settings/security'
  if (item.targetType === 'approval' || item.targetType === 'role') return '/pending'
  if (item.targetType === 'push') return '/settings/notifications'
  return null
}

async function openItem(item) {
  await markRead(item)
  const link = target(item)
  if (link) router.push(link)
}

function changePage(next) {
  page.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="page notifications-page">
    <div class="container narrow">
      <PageHeader eyebrow="NOTIFICATIONS" :title="t('notifications.title')" :lead="t('notifications.lead')">
        <template #actions>
          <button class="btn ghost" :disabled="!store.unread" @click="markAll">{{ t('notifications.markAll') }}</button>
        </template>
      </PageHeader>

      <div class="notification-toolbar">
        <div class="type-filters">
          <button :class="{ active: !activeType }" @click="setType('')">{{ t('notifications.all') }}</button>
          <button v-for="type in typeOptions" :key="type" :class="{ active: activeType === type }" @click="setType(type)">
            {{ t(`notifications.types.${type}`) }}
            <span v-if="unreadMap[type]" class="unread-chip">{{ unreadMap[type] }}</span>
          </button>
        </div>
        <button class="unread-toggle" :class="{ active: unreadOnly }" @click="toggleUnread">
          <span></span>{{ t('notifications.unread') }}
        </button>
      </div>

      <AsyncState :loading="loading" :error="error" :empty="!loading && !items.length" :empty-text="t('notifications.empty')" @retry="load">
        <div class="notification-list">
          <button
            v-for="item in items"
            :key="item.id"
            class="notification-item"
            :class="{ unread: !item.read }"
            @click="openItem(item)"
          >
            <span class="notification-icon" :class="item.type">
              <el-icon v-if="item.type === 'security'"><Lock /></el-icon>
              <el-icon v-else-if="item.type === 'approval'"><CircleCheck /></el-icon>
              <el-icon v-else-if="item.type === 'feedback'"><ChatDotRound /></el-icon>
              <el-icon v-else-if="item.type === 'comment'"><ChatLineRound /></el-icon>
              <el-icon v-else-if="item.type === 'push'"><Promotion /></el-icon>
              <el-icon v-else><Bell /></el-icon>
            </span>
            <span class="notification-content">
              <span class="notification-head">
                <strong>{{ item.title }}</strong>
                <span class="type-label mono">{{ t(`notifications.types.${item.type}`) }}</span>
              </span>
              <span class="notification-message">{{ item.message }}</span>
              <span class="notification-time">{{ relativeTime(item.createdAt, locale) }}</span>
            </span>
            <span v-if="!item.read" class="unread-dot"></span>
          </button>
        </div>
      </AsyncState>

      <div v-if="pagination && pagination.pages > 1" class="pagination-row">
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @current-change="changePage"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.notification-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 6px;
}
.type-filters {
  display: flex;
  gap: 2px;
  overflow-x: auto;
}
.type-filters button {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  padding: 7px 9px;
  border-radius: 5px;
  white-space: nowrap;
}
.type-filters button.active {
  background: var(--surface-2);
  color: var(--ink);
  font-weight: 650;
}
.unread-chip {
  min-width: 14px;
  height: 14px;
  display: inline-grid;
  place-items: center;
  background: var(--signal);
  color: #fff;
  font-size: 7px;
  border-radius: 999px;
  margin-left: 3px;
  padding: 0 3px;
}
.unread-toggle {
  display: flex;
  gap: 6px;
  align-items: center;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  white-space: nowrap;
  min-height: 34px;
}
.unread-toggle span {
  width: 26px;
  height: 15px;
  border-radius: 999px;
  background: var(--line-strong);
  position: relative;
  transition: background 150ms;
}
.unread-toggle span::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--surface);
  transition: transform 150ms;
}
.unread-toggle.active span {
  background: var(--accent);
}
.unread-toggle.active span::after {
  transform: translateX(11px);
}
.notification-list {
  display: flex;
  flex-direction: column;
}
.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  padding: 16px 7px;
  text-align: left;
  color: inherit;
  transition: background 150ms;
  position: relative;
}
.notification-item:hover {
  background: var(--surface-2);
}
.notification-item.unread {
  background: color-mix(in srgb, var(--accent-soft) 32%, transparent);
}
.notification-icon {
  width: 35px;
  height: 35px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid var(--line);
  color: var(--muted);
  background: var(--surface);
}
.notification-icon.security {
  color: var(--signal);
}
.notification-icon.approval {
  color: var(--success);
}
.notification-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}
.notification-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notification-head strong {
  font-size: 12.5px;
}
.type-label {
  font-size: 7px;
  color: var(--muted-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 2px 4px;
}
.notification-message {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.6;
}
.notification-time {
  color: var(--muted-2);
  font-size: 9px;
  margin-top: 2px;
}
.unread-dot {
  width: 5px;
  height: 5px;
  background: var(--accent);
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}
.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
@media (max-width: 640px) {
  .notification-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .type-filters {
    padding-bottom: 2px;
  }
}
</style>
