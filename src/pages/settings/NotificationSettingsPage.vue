<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { userApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import SettingsLayout from '@/components/settings/SettingsLayout.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t } = useI18n()
const settings = ref([])
const loading = ref(true)
const error = ref(null)
const saving = ref(false)

const description = (code) => ({
  inapp: t('extra.channelInapp'),
  email: t('extra.channelEmail'),
  sms: t('extra.channelSms'),
  push: t('extra.channelPush'),
}[code] || code)

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await userApi.pushSettings()
    settings.value = (response.data.items || []).map((item) => ({ ...item }))
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const response = await userApi.updatePushSettings(
      settings.value.map((item) => ({
        channelCode: item.channelCode,
        enabled: item.enabled,
        quietHours: item.quietHours,
      })),
    )
    settings.value = response.data.items || settings.value
    ElMessage.success(t('settings.settingsSaved'))
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <SettingsLayout
    :eyebrow="t('settings.eyebrow') + ' / NOTIFICATIONS'"
    :title="t('settings.notificationsTitle')"
    :lead="t('settings.notificationsLead')"
  >
    <div class="settings-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">CHANNELS</p>
          <h3>{{ t('settings.channel') }}</h3>
        </div>
        <span class="mono">{{ settings.filter((item) => item.enabled).length }} / {{ settings.length }} ENABLED</span>
      </div>

      <AsyncState :loading="loading" :error="error" :empty="!loading && !settings.length" @retry="load">
        <div class="channel-list">
          <div v-for="item in settings" :key="item.channelCode" class="channel-row">
            <span class="channel-icon">
              <el-icon v-if="item.channelCode === 'email'"><Message /></el-icon>
              <el-icon v-else-if="item.channelCode === 'sms'"><Iphone /></el-icon>
              <el-icon v-else-if="item.channelCode === 'push'"><Notification /></el-icon>
              <el-icon v-else><Bell /></el-icon>
            </span>
            <div class="channel-info">
              <strong>{{ item.name }}</strong>
              <p>{{ description(item.channelCode) }}</p>
            </div>
            <div class="channel-controls">
              <div class="control">
                <span>{{ t('settings.enabled') }}</span>
                <el-switch v-model="item.enabled" />
              </div>
              <div class="control">
                <span>{{ t('settings.quietHours') }}</span>
                <el-switch v-model="item.quietHours" :disabled="!item.enabled" />
              </div>
            </div>
          </div>
        </div>
      </AsyncState>

      <div class="notice">
        <el-icon><Moon /></el-icon>
        <span>{{ t('extra.marketingNotice') }}</span>
      </div>

      <div class="form-actions">
        <button class="btn primary" :disabled="saving" @click="save">{{ saving ? t('common.saving') : t('settings.saveSettings') }}</button>
      </div>
    </div>
  </SettingsLayout>
</template>

<style scoped>
.settings-panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 24px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}
.panel-head h3 {
  margin-top: 6px;
  font-size: 23px;
}
.panel-head .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.channel-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px 0;
  border-top: 1px solid var(--line);
}
.channel-row:first-child {
  border-top: 0;
}
.channel-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  color: var(--accent);
  flex-shrink: 0;
  background: var(--surface-2);
}
.channel-info {
  flex: 1;
  min-width: 0;
}
.channel-info strong {
  font-size: 13px;
}
.channel-info p {
  font-size: 10px;
  color: var(--muted);
  margin-top: 3px;
  line-height: 1.5;
}
.channel-controls {
  display: flex;
  gap: 22px;
}
.control {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.control span {
  font-size: 8px;
  color: var(--muted-2);
  white-space: nowrap;
}
.notice {
  display: flex;
  gap: 9px;
  margin-top: 15px;
  padding: 12px;
  background: var(--surface-2);
  border: 1px dashed var(--line);
  border-radius: 6px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.6;
}
.notice .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--accent);
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
@media (max-width: 640px) {
  .settings-panel {
    padding: 18px;
  }
  .channel-row {
    flex-wrap: wrap;
    align-items: flex-start;
  }
  .channel-info {
    flex-basis: calc(100% - 55px);
  }
  .channel-controls {
    width: 100%;
    justify-content: flex-end;
    gap: 30px;
    margin-top: 6px;
  }
  .form-actions .btn {
    width: 100%;
  }
}
</style>
