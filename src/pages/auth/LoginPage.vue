<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { socialApi, authApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import AuthShell from '@/components/auth/AuthShell.vue'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const meta = ref({ oauthProviders: [] })
const submitting = ref(false)
const errorMessage = ref('')
const oauthError = ref(String(route.query.oauth_error || ''))
const showPassword = ref(false)
const form = reactive({ email: '', password: '' })

const rules = computed(() => ({
  email: [
    { required: true, message: t('auth.email'), trigger: 'blur' },
    { type: 'email', message: t('auth.emailPlaceholder'), trigger: 'blur' },
  ],
  password: [{ required: true, message: t('auth.password'), trigger: 'blur' }],
}))

const enabledProviders = computed(() => (meta.value.oauthProviders || []).filter((item) => item.enabled))

async function loadMeta() {
  try {
    const response = await socialApi.meta()
    meta.value = response.data
  } catch {
    meta.value = { oauthProviders: [] }
  }
}

async function submit() {
  errorMessage.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const session = await auth.login({ email: form.email.trim(), password: form.password })
    ElMessage.success(t('common.success'))
    if (session.requiresApproval || auth.isPending) {
      router.replace({ name: 'pending' })
      return
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (error) {
    const normalized = normalizeError(error)
    errorMessage.value = normalized.message
    if (normalized.status === 429) {
      errorMessage.value = normalized.message || t('auth.locked')
    }
  } finally {
    submitting.value = false
  }
}

async function useOAuth(provider) {
  try {
    const response = await authApi.oauthUrl(provider)
    window.location.href = response
  } catch (error) {
    ElMessage.error(normalizeError(error).message)
  }
}

onMounted(loadMeta)
</script>

<template>
  <AuthShell>
    <div class="form-head">
      <p class="eyebrow">{{ t('auth.loginEyebrow') }}</p>
      <h1>{{ t('auth.loginTitle') }}</h1>
      <p class="form-sub">{{ t('auth.loginSubtitle') }}</p>
    </div>

    <div v-if="oauthError" class="oauth-error">
      <el-icon><WarningFilled /></el-icon>
      {{ oauthError }}
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" :placeholder="t('auth.emailPlaceholder')" autocomplete="email" size="large" />
      </el-form-item>
      <el-form-item :label="t('auth.password')" prop="password">
        <el-input
          v-model="form.password"
          :type="showPassword ? 'text' : 'password'"
          :placeholder="t('auth.passwordPlaceholder')"
          autocomplete="current-password"
          size="large"
          @keyup.enter="submit"
        >
          <template #suffix>
            <button type="button" class="eye-btn" :aria-label="showPassword ? 'Hide password' : 'Show password'" @click="showPassword = !showPassword">
              <el-icon><View v-if="!showPassword" /><Hide v-else /></el-icon>
            </button>
          </template>
        </el-input>
      </el-form-item>

      <div class="form-row-between">
        <router-link to="/forgot-password" class="forgot">{{ t('auth.forgot') }}</router-link>
      </div>

      <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="form-error">
        {{ errorMessage }}
      </el-alert>

      <button class="submit-btn" type="submit" :disabled="submitting">
        <span>{{ submitting ? t('auth.loggingIn') : t('auth.login') }}</span>
        <span class="submit-arrow"><el-icon><Right /></el-icon></span>
      </button>
    </el-form>

    <template v-if="enabledProviders.length">
      <div class="divider-row">
        <span></span><em>{{ t('auth.oauthDivider') }}</em><span></span>
      </div>
      <div class="oauth-row">
        <button v-for="provider in enabledProviders" :key="provider.code" class="oauth-btn" @click="useOAuth(provider.code)">
          <span>{{ provider.name.slice(0, 1) }}</span>
          {{ provider.name }}
        </button>
      </div>
    </template>

    <p class="switch-line">
      {{ t('auth.noAccount') }}
      <router-link to="/register">{{ t('auth.toRegister') }}</router-link>
    </p>
  </AuthShell>
</template>

<style scoped>
.form-head {
  margin-bottom: 32px;
}
.form-head h1 {
  margin: 12px 0 16px;
  font-size: clamp(38px, 4vw, 52px);
  white-space: pre-line;
  line-height: 1.02;
}
.form-sub {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.65;
  max-width: 380px;
}
.form-row-between {
  display: flex;
  justify-content: flex-end;
  margin: -4px 0 16px;
}
.forgot {
  color: var(--muted);
  font-size: 12px;
  border-bottom: 1px solid transparent;
}
.forgot:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.submit-btn {
  width: 100%;
  min-height: 52px;
  border: 0;
  border-radius: 9px;
  padding: 0 8px 0 20px;
  background: var(--ink);
  color: var(--bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 650;
  font-size: 14px;
  transition: all 180ms var(--ease);
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent);
  color: #fff;
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}
.submit-arrow {
  width: 38px;
  height: 38px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.1);
}
.eye-btn {
  border: 0;
  background: transparent;
  color: var(--muted);
  display: grid;
  place-items: center;
  padding: 4px;
}
.form-error {
  margin-bottom: 14px;
}
.oauth-error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 6%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--danger) 20%, var(--line));
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 18px;
}
.divider-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  margin: 24px 0 16px;
}
.divider-row span {
  height: 1px;
  background: var(--line);
}
.divider-row em {
  font-style: normal;
  font-size: 10px;
  color: var(--muted-2);
}
.oauth-row {
  display: flex;
  gap: 8px;
}
.oauth-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 43px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 600;
  transition: all 160ms;
}
.oauth-btn span {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  border-radius: 50%;
  font-size: 10px;
}
.oauth-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.switch-line {
  margin-top: 26px;
  font-size: 12.5px;
  color: var(--muted);
  text-align: center;
}
.switch-line a {
  color: var(--ink);
  font-weight: 650;
  margin-left: 4px;
  border-bottom: 1px solid var(--ink);
}
</style>
