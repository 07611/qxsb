<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { authApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import AuthShell from '@/components/auth/AuthShell.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const devResetUrl = ref('')
const emailForm = reactive({ email: '' })
const resetForm = reactive({ newPassword: '', confirmPassword: '' })
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const mode = computed(() => (token.value ? 'reset' : 'forgot'))

const emailRules = {
  email: [
    { required: true, message: t('auth.email'), trigger: 'blur' },
    { type: 'email', message: t('auth.emailPlaceholder'), trigger: 'blur' },
  ],
}
const resetRules = computed(() => ({
  newPassword: [
    { required: true, message: t('auth.newPassword'), trigger: 'blur' },
    { min: 8, max: 64, message: t('auth.passwordPlaceholder'), trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: t('auth.confirmNewPassword'), trigger: 'blur' },
    {
      validator: (_rule, value, callback) =>
        value === resetForm.newPassword ? callback() : callback(new Error(t('auth.passwordMismatch'))),
      trigger: 'blur',
    },
  ],
}))

async function requestReset() {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const response = await authApi.forgot(emailForm.email.trim())
    successMessage.value = response.data.message || t('auth.resetSent')
    devResetUrl.value = response.data.devResetUrl || ''
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    submitting.value = false
  }
}

async function resetPassword() {
  errorMessage.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await authApi.reset({ token: token.value, newPassword: resetForm.newPassword })
    ElMessage.success(t('auth.resetSuccess'))
    router.replace({ name: 'login' })
  } catch (error) {
    errorMessage.value = normalizeError(error).message || t('auth.resetInvalid')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell>
    <div class="form-head">
      <p class="eyebrow">RECOVER ACCESS</p>
      <h1>{{ mode === 'reset' ? t('auth.resetPassword') : t('auth.forgotTitle') }}</h1>
      <p class="form-sub">{{ t('auth.forgotSubtitle') }}</p>
    </div>

    <el-form
      v-if="mode === 'forgot'"
      ref="formRef"
      :model="emailForm"
      :rules="emailRules"
      label-position="top"
      @submit.prevent="requestReset"
    >
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="emailForm.email" :placeholder="t('auth.emailPlaceholder')" autocomplete="email" />
      </el-form-item>
      <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="mb">{{ errorMessage }}</el-alert>
      <el-alert v-if="successMessage" type="success" :closable="false" show-icon class="mb">{{ successMessage }}</el-alert>
      <a v-if="devResetUrl" :href="devResetUrl" class="dev-link">
        <span class="mono">{{ t('auth.devReset') }}</span>
        <span>{{ t('auth.resetPassword') }} →</span>
      </a>
      <button class="submit-btn" type="submit" :disabled="submitting">
        {{ submitting ? t('common.sending') : t('auth.sendReset') }}
        <el-icon><Right /></el-icon>
      </button>
    </el-form>

    <el-form
      v-else
      ref="formRef"
      :model="resetForm"
      :rules="resetRules"
      label-position="top"
      @submit.prevent="resetPassword"
    >
      <el-form-item :label="t('auth.newPassword')" prop="newPassword">
        <el-input v-model="resetForm.newPassword" type="password" :placeholder="t('auth.passwordPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('auth.confirmNewPassword')" prop="confirmPassword">
        <el-input v-model="resetForm.confirmPassword" type="password" :placeholder="t('auth.confirmNewPassword')" />
      </el-form-item>
      <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="mb">{{ errorMessage }}</el-alert>
      <button class="submit-btn" type="submit" :disabled="submitting">
        {{ submitting ? t('common.saving') : t('auth.resetPassword') }}
        <el-icon><Right /></el-icon>
      </button>
    </el-form>

    <p class="back-line">
      <router-link to="/login">← {{ t('auth.toLogin') }}</router-link>
    </p>
  </AuthShell>
</template>

<style scoped>
.form-head {
  margin-bottom: 30px;
}
.form-head h1 {
  margin: 12px 0 14px;
  font-size: clamp(36px, 4vw, 48px);
}
.form-sub {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}
.submit-btn {
  width: 100%;
  min-height: 50px;
  border: 0;
  border-radius: 9px;
  background: var(--ink);
  color: var(--bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-weight: 650;
  transition: background 160ms;
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent);
}
.submit-btn:disabled {
  opacity: 0.55;
}
.mb {
  margin-bottom: 14px;
}
.dev-link {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 13px;
  border: 1px dashed var(--accent);
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  margin-bottom: 14px;
}
.dev-link .mono {
  font-size: 8px;
  letter-spacing: 0.08em;
}
.back-line {
  margin-top: 26px;
  font-size: 12px;
  color: var(--muted);
  text-align: center;
}
.back-line a:hover {
  color: var(--accent);
}
</style>
