<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { socialApi, authApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import AuthShell from '@/components/auth/AuthShell.vue'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const formRef = ref(null)
const meta = ref({ registrationRequireInvite: false, oauthProviders: [] })
const submitting = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)
const form = reactive({ nickname: '', email: '', password: '', confirmPassword: '', inviteCode: '' })

const rules = computed(() => ({
  nickname: [
    { required: true, message: t('auth.nickname'), trigger: 'blur' },
    { min: 2, max: 20, message: t('auth.nicknamePlaceholder'), trigger: 'blur' },
  ],
  email: [
    { required: true, message: t('auth.email'), trigger: 'blur' },
    { type: 'email', message: t('auth.emailPlaceholder'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('auth.password'), trigger: 'blur' },
    { min: 8, max: 64, message: t('auth.passwordPlaceholder'), trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: t('auth.confirmPassword'), trigger: 'blur' },
    {
      validator: (_rule, value, callback) => (value === form.password ? callback() : callback(new Error(t('auth.passwordMismatch')))),
      trigger: 'blur',
    },
  ],
  inviteCode: [
    {
      validator: (_rule, value, callback) => {
        if (meta.value.registrationRequireInvite && !value) callback(new Error(t('auth.inviteOptional')))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}))

const enabledProviders = computed(() => (meta.value.oauthProviders || []).filter((item) => item.enabled))

async function loadMeta() {
  try {
    const response = await socialApi.meta()
    meta.value = response.data
  } catch {
    meta.value = {}
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
    const session = await auth.register({
      nickname: form.nickname.trim(),
      email: form.email.trim(),
      password: form.password,
      inviteCode: form.inviteCode || undefined,
    })
    ElMessage.success(t('common.success'))
    if (session.requiresApproval || auth.isPending) router.replace({ name: 'pending' })
    else router.replace('/')
  } catch (error) {
    const normalized = normalizeError(error)
    errorMessage.value = normalized.message
    // 保留已填写内容，只高亮服务端返回的字段
    if (Object.keys(normalized.fieldErrors || {}).length && formRef.value) {
      formRef.value.validate().catch(() => {})
    }
  } finally {
    submitting.value = false
  }
}

async function useOAuth(provider) {
  window.location.href = authApi.oauthUrl(provider)
}

onMounted(loadMeta)
</script>

<template>
  <AuthShell>
    <div class="form-head">
      <p class="eyebrow">{{ t('auth.registerEyebrow') }}</p>
      <h1>{{ t('auth.registerTitle') }}</h1>
      <p class="form-sub">{{ t('auth.registerSubtitle') }}</p>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
      <el-form-item :label="t('auth.nickname')" prop="nickname">
        <el-input v-model="form.nickname" :placeholder="t('auth.nicknamePlaceholder')" maxlength="20" show-word-limit />
      </el-form-item>
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" :placeholder="t('auth.emailPlaceholder')" autocomplete="email" />
      </el-form-item>
      <div class="password-grid">
        <el-form-item :label="t('auth.password')" prop="password">
          <el-input v-model="form.password" :type="showPassword ? 'text' : 'password'" :placeholder="t('auth.passwordPlaceholder')" autocomplete="new-password">
            <template #suffix>
              <button type="button" class="eye-btn" @click="showPassword = !showPassword">
                <el-icon><View v-if="!showPassword" /><Hide v-else /></el-icon>
              </button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item :label="t('auth.confirmPassword')" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" :placeholder="t('auth.confirmPassword')" autocomplete="new-password" />
        </el-form-item>
      </div>
      <el-form-item v-if="meta.registrationRequireInvite" :label="t('auth.inviteCode')" prop="inviteCode">
        <el-input v-model="form.inviteCode" :placeholder="t('auth.inviteOptional')" />
      </el-form-item>

      <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="form-error">{{ errorMessage }}</el-alert>

      <p class="terms">{{ t('auth.terms') }}</p>
      <button class="submit-btn" type="submit" :disabled="submitting">
        <span>{{ submitting ? t('auth.registering') : t('auth.register') }}</span>
        <span class="submit-arrow"><el-icon><Right /></el-icon></span>
      </button>
    </el-form>

    <template v-if="enabledProviders.length">
      <div class="divider-row"><span></span><em>{{ t('auth.oauthDivider') }}</em><span></span></div>
      <div class="oauth-row">
        <button v-for="provider in enabledProviders" :key="provider.code" class="oauth-btn" @click="useOAuth(provider.code)">
          {{ provider.name }}
        </button>
      </div>
    </template>

    <p class="switch-line">
      {{ t('auth.hasAccount') }}
      <router-link to="/login">{{ t('auth.toLogin') }}</router-link>
    </p>
  </AuthShell>
</template>

<style scoped>
.form-head {
  margin-bottom: 24px;
}
.form-head h1 {
  margin: 12px 0 14px;
  font-size: clamp(36px, 3.8vw, 50px);
  white-space: pre-line;
  line-height: 1.02;
}
.form-sub {
  color: var(--muted);
  font-size: 13.5px;
  line-height: 1.65;
  max-width: 390px;
}
.password-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.terms {
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.6;
  margin: 2px 0 14px;
  padding-left: 10px;
  border-left: 2px solid var(--line);
}
.submit-btn {
  width: 100%;
  min-height: 50px;
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
  height: 36px;
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
.divider-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  margin: 20px 0 12px;
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
  min-height: 42px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--surface);
  font-size: 12px;
  font-weight: 600;
}
.oauth-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.switch-line {
  margin-top: 22px;
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
@media (max-width: 480px) {
  .password-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
