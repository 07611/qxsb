<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDate, statusType } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const users = ref([])
const pagination = ref(null)
const loading = ref(true)
const error = ref(null)
const query = ref('')
const status = ref('')
const role = ref('')
const page = ref(1)
const invites = ref([])
const inviteForm = reactive({ count: 1, expiresInDays: 7 })
const creatingInvite = ref(false)
const changing = reactive({})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [userResponse, inviteResponse] = await Promise.all([
      adminApi.users({
        q: query.value || undefined,
        status: status.value || undefined,
        role: role.value || undefined,
        page: page.value,
        pageSize: 15,
      }),
      adminApi.inviteCodes(),
    ])
    users.value = userResponse.data.items || []
    pagination.value = userResponse.data.pagination
    invites.value = inviteResponse.data.items || []
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  query.value = ''
  status.value = ''
  role.value = ''
  page.value = 1
  load()
}

async function changeRole(user, nextRole) {
  if (nextRole === user.role) return
  try {
    await ElMessageBox.confirm(`${user.nickname}: ${user.role} → ${nextRole}`, t('admin.changeRole'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  changing[user.id] = true
  try {
    const response = await adminApi.changeRole(user.id, nextRole)
    const index = users.value.findIndex((item) => item.id === user.id)
    if (index >= 0) users.value[index] = response.data.user
    ElMessage.success(t('admin.roleDone'))
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
    await load()
  } finally {
    changing[user.id] = false
  }
}

async function approve(user, approved) {
  try {
    await ElMessageBox.confirm(
      approved ? `${user.nickname} / ${user.email}` : t('admin.reject'),
      approved ? t('admin.approve') : t('admin.reject'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: approved ? 'info' : 'warning' },
    )
  } catch {
    return
  }
  changing[user.id] = true
  try {
    const response = await adminApi.approve(user.id, approved, approved ? '' : '管理员拒绝了注册申请')
    const index = users.value.findIndex((item) => item.id === user.id)
    if (index >= 0) users.value[index] = response.data.user
    ElMessage.success(t('admin.approveDone'))
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    changing[user.id] = false
  }
}

async function createInvite() {
  creatingInvite.value = true
  try {
    const response = await adminApi.createInvite({ count: inviteForm.count, expiresInDays: inviteForm.expiresInDays })
    ElMessage.success(`${t('admin.inviteCreated')}: ${response.data.codes.join(', ')}`)
    const inviteResponse = await adminApi.inviteCodes()
    invites.value = inviteResponse.data.items || []
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    creatingInvite.value = false
  }
}

function changePage(next) {
  page.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="admin-users">
    <div class="page-title">
      <div>
        <p class="eyebrow">ACCESS CONTROL</p>
        <h1>{{ t('admin.usersTitle') }}</h1>
      </div>
      <span class="mono">{{ pagination?.total || 0 }} USERS</span>
    </div>

    <div class="filter-bar">
      <el-input v-model="query" :placeholder="t('admin.userSearch')" clearable @keyup.enter="search" />
      <el-select v-model="status" clearable :placeholder="t('admin.status')">
        <el-option :label="t('admin.statuses.active')" value="active" />
        <el-option :label="t('admin.statuses.pending')" value="pending" />
        <el-option :label="t('admin.statuses.disabled')" value="disabled" />
      </el-select>
      <el-select v-model="role" clearable :placeholder="t('admin.role')">
        <el-option :label="t('admin.roles.admin')" value="admin" />
        <el-option :label="t('admin.roles.editor')" value="editor" />
        <el-option :label="t('admin.roles.user')" value="user" />
      </el-select>
      <button class="btn primary small" @click="search"><el-icon><Search /></el-icon>{{ t('common.search') }}</button>
      <button class="btn quiet small" @click="reset">{{ t('common.reset') }}</button>
    </div>

    <AsyncState :loading="loading" :error="error" :empty="!loading && !users.length" @retry="load">
      <div class="table-wrap">
        <el-table :data="users" stripe>
          <el-table-column label="USER" min-width="220">
            <template #default="{ row }">
              <div class="user-cell">
                <span class="mini-avatar"><img v-if="row.avatarUrl" :src="row.avatarUrl" alt="" width="30" height="30" /><template v-else>{{ row.nickname.slice(0, 1) }}</template></span>
                <div>
                  <strong>{{ row.nickname }}</strong>
                  <span>{{ row.email }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('admin.role')" width="155">
            <template #default="{ row }">
              <el-select :model-value="row.role" size="small" :disabled="changing[row.id]" @change="(value) => changeRole(row, value)">
                <el-option :label="t('admin.roles.admin')" value="admin" />
                <el-option :label="t('admin.roles.editor')" value="editor" />
                <el-option :label="t('admin.roles.user')" value="user" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="t('admin.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ t(`admin.statuses.${row.status}`) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="JOINED" width="125">
            <template #default="{ row }">
              <span class="mono date-cell">{{ formatDate(row.createdAt, locale) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="ACTION" width="140" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <button class="table-action approve" :disabled="changing[row.id]" @click="approve(row, true)">{{ t('admin.approve') }}</button>
                <button class="table-action reject" :disabled="changing[row.id]" @click="approve(row, false)">{{ t('admin.reject') }}</button>
              </template>
              <span v-else class="mono muted-action">—</span>
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

    <section class="invite-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">INVITE ONLY</p>
          <h3>{{ t('admin.invitations') }}</h3>
        </div>
        <span class="mono">{{ invites.length }} / 100</span>
      </div>
      <div class="invite-form">
        <el-input-number v-model="inviteForm.count" :min="1" :max="20" size="small" />
        <el-select v-model="inviteForm.expiresInDays" size="small">
          <el-option label="7 days" :value="7" />
          <el-option label="30 days" :value="30" />
          <el-option label="90 days" :value="90" />
        </el-select>
        <button class="btn ghost small" :disabled="creatingInvite" @click="createInvite">{{ t('admin.createInvite') }}</button>
      </div>
      <div class="invite-list">
        <div v-for="invite in invites.slice(0, 8)" :key="invite.id" class="invite-row">
          <code>{{ invite.code }}</code>
          <span :class="{ used: invite.consumed }">{{ invite.consumed ? 'CONSUMED' : 'AVAILABLE' }}</span>
          <span class="mono">{{ formatDate(invite.expiresAt, locale) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-title {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 20px;
}
.page-title h1 {
  font-size: clamp(32px, 4vw, 48px);
  margin-top: 8px;
}
.page-title .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.filter-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.filter-bar .el-input {
  width: 220px;
}
.filter-bar .el-select {
  width: 135px;
}
.small {
  min-height: 36px;
  font-size: 10px;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 9px;
}
.mini-avatar {
  width: 29px;
  height: 29px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--accent);
  font-size: 10px;
  flex-shrink: 0;
}
.mini-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.user-cell div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.user-cell strong {
  font-size: 11px;
}
.user-cell span {
  font-size: 9px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.date-cell {
  font-size: 7px;
  color: var(--muted-2);
}
.table-action {
  border: 0;
  background: transparent;
  font-size: 8px;
  padding: 4px 4px;
  font-weight: 650;
}
.table-action.approve {
  color: var(--success);
}
.table-action.reject {
  color: var(--danger);
}
.muted-action {
  color: var(--muted-2);
  font-size: 7px;
}
.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.invite-panel {
  margin-top: 22px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  padding: 16px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 10px;
}
.panel-head h3 {
  margin-top: 4px;
  font-size: 20px;
}
.panel-head .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.invite-form {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.invite-form .el-input-number {
  width: 100px;
}
.invite-form .el-select {
  width: 110px;
}
.invite-list {
  display: flex;
  flex-direction: column;
  margin-top: 10px;
}
.invite-row {
  display: grid;
  grid-template-columns: 1fr 80px 100px;
  gap: 8px;
  align-items: center;
  border-top: 1px solid var(--line);
  padding: 7px 0;
  font-size: 8px;
}
.invite-row code {
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--ink-2);
}
.invite-row span:not(.used) {
  color: var(--success);
  font-size: 7px;
}
.invite-row .used {
  color: var(--muted-2);
  font-size: 7px;
}
.invite-row .mono {
  color: var(--muted-2);
  font-size: 7px;
}
@media (max-width: 650px) {
  .page-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }
  .filter-bar .el-input,
  .filter-bar .el-select {
    width: 100%;
  }
  .invite-row {
    grid-template-columns: 1fr 70px;
  }
  .invite-row .mono {
    display: none;
  }
}
</style>
