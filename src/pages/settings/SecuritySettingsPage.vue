<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { authApi, userApi, socialApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatDateTime, relativeTime } from '@/utils/format'
import SettingsLayout from '@/components/settings/SettingsLayout.vue'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const auth = useAuthStore()
const sessions = ref([])
const loadingSessions = ref(true)
const sessionError = ref(null)
const revoking = reactive({})
const changingPassword = ref(false)
const passwordForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const passwordError = ref('')
const codeState = reactive({ channel: 'email', sending: false, verifying: false, devCode: '', code: '', sent: false, verified: false })
const providerMeta = ref([])
const codeTarget = computed(() => (codeState.channel === 'email' ? auth.user?.email || '' : auth.user?.phoneRaw || ''))

function setCodeChannel(channel) {
  codeState.channel = channel
  codeState.sent = false
  codeState.verified = false
  codeState.devCode = ''
  codeState.code = ''
}

async function loadSessions() {
  loadingSessions.value = true
  sessionError.value = null
  try {
    const response = await authApi.sessions()
    sessions.value = response.data.items || []
  } catch (error) {
    sessionError.value = normalizeError(error)
  } finally {
    loadingSessions.value = false
  }
}

async function revoke(session) {
  try {
    await ElMessageBox.confirm(
      `${session.device} · ${session.ip}`,
      t('settings.revoke'),
      { confirmButtonText: t('settings.revoke'), cancelButtonText: t('common.cancel'), type: 'warning' },
    )
  } catch {
    return
  }
  revoking[session.id] = true
  try {
    await authApi.revokeSession(session.id)
    sessions.value = sessions.value.filter((item) => item.id !== session.id)
    ElMessage.success(t('settings.revoked'))
  } catch (error) {
    ElMessage.error(normalizeError(error).message)
  } finally {
    revoking[session.id] = false
  }
}

async function changePassword() {
  passwordError.value = ''
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    passwordError.value = t('auth.passwordMismatch')
    return
  }
  if (passwordForm.newPassword.length < 8) {
    passwordError.value = t('auth.passwordPlaceholder')
    return
  }
  changingPassword.value = true
  try {
    await userApi.changePassword({
      currentPassword: passwordForm.currentPassword,
      newPassword: passwordForm.newPassword,
    })
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    ElMessage.success(t('settings.passwordChanged'))
    loadSessions()
  } catch (error) {
    passwordError.value = normalizeError(error).message
  } finally {
    changingPassword.value = false
  }
}

async function sendEmailCode() {
  if (!codeTarget.value) {
    ElMessage.warning(t('extra.bindPhoneHint'))
    return
  }
  codeState.sending = true
  try {
    const response = await authApi.sendCode({
      target: codeTarget.value,
      scene: 'verify_email',
      channel: codeState.channel,
    })
    codeState.sent = true
    codeState.devCode = response.data.devCode || ''
    ElMessage.success(t('auth.codeSent'))
  } catch (error) {
    ElMessage.error(normalizeError(error).message)
  } finally {
    codeState.sending = false
  }
}

async function verifyEmailCode() {
  codeState.verifying = true
  try {
    await authApi.verifyCode({ target: codeTarget.value, scene: 'verify_email', code: codeState.code })
    codeState.verified = true
    codeState.code = ''
    ElMessage.success(t('settings.verified'))
  } catch (error) {
    ElMessage.error(normalizeError(error).message)
  } finally {
    codeState.verifying = false
  }
}

async function loadProviders() {
  try {
    const response = await socialApi.meta()
    providerMeta.value = (response.data.oauthProviders || []).filter((item) => item.enabled)
  } catch {
    providerMeta.value = []
  }
}

onMounted(() => {
  loadSessions()
  loadProviders()
})
</script>

<template>
  <SettingsLayout
    :eyebrow="t('settings.eyebrow') + ' / SECURITY'"
    :title="t('settings.securityTitle')"
    :lead="t('settings.contactLead')"
  >
    <div class="settings-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">ACTIVE SESSIONS</p>
          <h3>{{ t('settings.sessions') }}</h3>
        </div>
        <span class="mono">{{ sessions.length }} ACTIVE</span>
      </div>
      <AsyncState :loading="loadingSessions" :error="sessionError" :empty="!loadingSessions && !sessions.length" :empty-text="t('settings.noSessions')" @retry="loadSessions">
        <div class="session-list">
          <div v-for="session in sessions" :key="session.id" class="session-row">
            <span class="device-icon"><el-icon><Monitor /></el-icon></span>
            <div class="session-info">
              <div class="session-title">
                <strong>{{ session.device }}</strong>
                <span v-if="session.current" class="current-badge">{{ t('settings.current') }}</span>
              </div>
              <span class="session-meta">{{ session.platform }} · {{ session.ip }} · {{ t('settings.lastActive') }} {{ relativeTime(session.lastActiveAt, locale) }}</span>
            </div>
            <button v-if="!session.current" class="btn quiet danger-text" :disabled="revoking[session.id]" @click="revoke(session)">
              {{ t('settings.revoke') }}
            </button>
            <span v-else class="mono current-mark">THIS DEVICE</span>
          </div>
        </div>
      </AsyncState>
    </div>

    <div class="settings-panel two-panel">
      <div class="security-section">
        <p class="eyebrow">PASSWORD</p>
        <h3>{{ t('settings.passwordTitle') }}</h3>
        <el-form label-position="top" class="security-form" @submit.prevent="changePassword">
          <el-form-item :label="t('settings.currentPassword')">
            <el-input v-model="passwordForm.currentPassword" type="password" autocomplete="current-password" />
          </el-form-item>
          <el-form-item :label="t('settings.newPassword')">
            <el-input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" />
          </el-form-item>
          <el-form-item :label="t('auth.confirmNewPassword')">
            <el-input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" />
          </el-form-item>
          <p v-if="passwordError" class="error-text">{{ passwordError }}</p>
          <button class="btn primary full-btn" type="submit" :disabled="changingPassword">
            {{ changingPassword ? t('common.saving') : t('settings.changePassword') }}
          </button>
        </el-form>
      </div>

      <div class="security-section code-section">
        <p class="eyebrow">CONTACT VERIFICATION</p>
        <h3>{{ t('extra.verifyChannelTitle') }}</h3>
        <p class="small muted">{{ t('settings.emailVerifyLead') }}</p>
        <div class="channel-switch">
          <button type="button" :class="{ active: codeState.channel === 'email' }" @click="setCodeChannel('email')">
            {{ t('auth.email') }}
          </button>
          <button type="button" :class="{ active: codeState.channel === 'sms' }" :disabled="!auth.user?.phoneRaw" @click="setCodeChannel('sms')">
            {{ t('extra.phone') }}
          </button>
        </div>
        <div class="email-line">
          <span>{{ codeTarget || t('extra.bindPhoneHint') }}</span>
          <span v-if="codeState.verified" class="verified"><el-icon><CircleCheckFilled /></el-icon> {{ t('settings.verified') }}</span>
        </div>
        <button class="btn ghost" type="button" :disabled="codeState.sending || !codeTarget" @click="sendEmailCode">
          {{ codeState.sending ? t('common.sending') : t('settings.sendCode') }}
        </button>
        <template v-if="codeState.sent">
          <div v-if="codeState.devCode" class="dev-code">
            <span class="mono">DEV</span> {{ t('auth.devCode') }}: <strong>{{ codeState.devCode }}</strong>
          </div>
          <div class="code-row">
            <el-input v-model="codeState.code" maxlength="6" :placeholder="t('auth.code')" />
            <button class="btn primary" type="button" :disabled="codeState.verifying" @click="verifyEmailCode">{{ t('settings.verify') }}</button>
          </div>
        </template>
      </div>
    </div>

    <div class="settings-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">OAUTH</p>
          <h3>{{ t('settings.oauthTitle') }}</h3>
          <p class="small muted">{{ t('settings.oauthLead') }}</p>
        </div>
      </div>
      <div v-if="providerMeta.length" class="provider-row">
        <a v-for="provider in providerMeta" :key="provider.code" :href="`/api/v1/auth/oauth/${provider.code}`" class="provider-btn">
          <span>{{ provider.name.slice(0, 1) }}</span>
          {{ provider.name }}
        </a>
      </div>
      <p v-else class="small muted">{{ t('auth.oauthUnavailable') }}</p>
    </div>
  </SettingsLayout>
</template>

<style scoped>
.settings-panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 24px;
  margin-bottom: 18px;
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
  letter-spacing: 0.04em;
}
.session-list {
  display: flex;
  flex-direction: column;
}
.session-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 13px 0;
  border-top: 1px solid var(--line);
}
.session-row:first-child {
  border-top: 0;
}
.device-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  color: var(--muted);
  flex-shrink: 0;
}
.session-info {
  flex: 1;
  min-width: 0;
}
.session-title {
  display: flex;
  align-items: center;
  gap: 7px;
}
.session-title strong {
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.current-badge {
  font-size: 8px;
  color: var(--success);
  border: 1px solid color-mix(in srgb, var(--success) 30%, var(--line));
  border-radius: 3px;
  padding: 2px 4px;
}
.session-meta {
  font-size: 9px;
  color: var(--muted-2);
}
.danger-text {
  color: var(--danger);
  font-size: 10px;
}
.current-mark {
  font-size: 7px;
  color: var(--muted-2);
}
.two-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  padding: 0;
}
.security-section {
  padding: 24px;
}
.security-section + .security-section {
  border-left: 1px solid var(--line);
}
.security-section h3 {
  margin: 7px 0 15px;
  font-size: 21px;
}
.security-form {
  margin-top: 13px;
}
.full-btn {
  width: 100%;
}
.code-section .small {
  line-height: 1.65;
  margin-bottom: 13px;
}
.channel-switch {
  display: flex;
  gap: 4px;
  margin-bottom: 9px;
}
.channel-switch button {
  flex: 1;
  min-height: 32px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
}
.channel-switch button.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}
.channel-switch button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.email-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 10px;
  font-family: var(--font-mono);
  font-size: 10px;
  margin-bottom: 8px;
}
.verified {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--success);
  font-family: var(--font-body);
  font-size: 9px;
}
.dev-code {
  margin-top: 8px;
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 8px 10px;
  border-radius: 5px;
}
.dev-code .mono {
  font-size: 7px;
  margin-right: 5px;
}
.code-row {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.code-row .btn {
  min-height: 40px;
  flex-shrink: 0;
  font-size: 11px;
}
.provider-row {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.provider-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 9px 13px;
  font-size: 11px;
  color: var(--muted);
}
.provider-btn span {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  font-size: 9px;
  color: var(--ink);
}
.provider-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
@media (max-width: 800px) {
  .two-panel {
    grid-template-columns: 1fr;
  }
  .security-section + .security-section {
    border-left: 0;
    border-top: 1px solid var(--line);
  }
}
@media (max-width: 600px) {
  .settings-panel {
    padding: 18px;
  }
  .session-row {
    flex-wrap: wrap;
  }
  .session-info {
    flex-basis: calc(100% - 52px);
  }
  .session-row .btn {
    margin-left: 49px;
  }
  .current-mark {
    display: none;
  }
}
</style>
