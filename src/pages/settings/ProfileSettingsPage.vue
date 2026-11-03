<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { compressImage, validateImage } from '@/utils/image'
import SettingsLayout from '@/components/settings/SettingsLayout.vue'

const { t, locale } = useI18n()
const auth = useAuthStore()
const formRef = ref(null)
const avatarInput = ref(null)
const avatarUploading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const loading = ref(true)
const contact = reactive({ type: 'email', value: '', code: '', sending: false, confirming: false, devCode: '' })
const form = reactive({
  nickname: '',
  bio: '',
  gender: 'secret',
  birthday: '',
  location: '',
  locale: 'zh-CN',
})

const avatar = computed(() => auth.user?.avatarUrl)
const currentContact = computed(() => (contact.type === 'email' ? auth.user?.email : auth.user?.phone || '—'))

const rules = {
  nickname: [
    { required: true, message: t('settings.nickname'), trigger: 'blur' },
    { min: 2, max: 20, message: t('auth.nicknamePlaceholder'), trigger: 'blur' },
  ],
}

function fillForm(user) {
  form.nickname = user?.nickname || ''
  form.bio = user?.bio || ''
  form.gender = user?.gender || 'secret'
  form.birthday = user?.birthday || ''
  form.location = user?.location || ''
  form.locale = user?.locale || 'zh-CN'
}

async function load() {
  loading.value = true
  try {
    const response = await userApi.me()
    auth.setUser(response.data.user)
    fillForm(response.data.user)
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    loading.value = false
  }
}

async function save() {
  errorMessage.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = {
      nickname: form.nickname.trim(),
      bio: form.bio.trim(),
      gender: form.gender,
      birthday: form.birthday || null,
      location: form.location.trim(),
      locale: form.locale,
    }
    const response = await userApi.update(payload)
    auth.setUser(response.data.user)
    ElMessage.success(t('settings.saved'))
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    saving.value = false
  }
}

function pickAvatar() {
  avatarInput.value?.click()
}

async function onAvatar(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const error = validateImage(file)
  if (error) {
    ElMessage.error(error)
    return
  }
  avatarUploading.value = true
  try {
    const compressed = await compressImage(file, { maxSide: 512, quality: 0.9, square: true })
    const response = await userApi.uploadAvatar(compressed)
    auth.setUser({ ...auth.user, avatarUrl: response.data.avatarUrl })
    ElMessage.success(t('common.saved'))
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    avatarUploading.value = false
  }
}

async function sendCode() {
  errorMessage.value = ''
  contact.devCode = ''
  if (!contact.value.trim()) {
    errorMessage.value = t('settings.contactValue')
    return
  }
  contact.sending = true
  try {
    const response = await userApi.requestContact({ type: contact.type, value: contact.value.trim() })
    contact.devCode = response.data.devCode || ''
    ElMessage.success(t('auth.codeSent'))
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    contact.sending = false
  }
}

async function confirmContact() {
  errorMessage.value = ''
  contact.confirming = true
  try {
    const response = await userApi.confirmContact({
      type: contact.type,
      value: contact.value.trim(),
      code: contact.code.trim(),
    })
    if (response.data.revokedSessions) {
      ElMessage.warning(t('settings.contactLead'))
    }
    await auth.refreshProfile()
    contact.value = ''
    contact.code = ''
    ElMessage.success(t('settings.contactUpdated'))
  } catch (error) {
    errorMessage.value = normalizeError(error).message
  } finally {
    contact.confirming = false
  }
}

onMounted(load)
</script>

<template>
  <SettingsLayout
    :eyebrow="t('settings.eyebrow') + ' / PROFILE'"
    :title="t('settings.profileTitle')"
    :lead="t('settings.profileLead')"
  >
    <div class="settings-panel">
      <div class="avatar-section">
        <div class="avatar-preview">
          <img v-if="avatar" :src="avatar" alt="" width="112" height="112" />
          <span v-else>{{ (form.nickname || 'M').slice(0, 1) }}</span>
        </div>
        <div>
          <p class="eyebrow">{{ t('settings.avatar') }}</p>
          <p class="small muted">{{ t('settings.avatarHint') }}</p>
          <button class="btn ghost small-btn" :disabled="avatarUploading" @click="pickAvatar">
            {{ avatarUploading ? t('common.processing') : t('common.edit') }}
          </button>
          <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onAvatar" />
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="profile-form" @submit.prevent="save">
        <div class="form-grid">
          <el-form-item :label="t('settings.nickname')" prop="nickname">
            <el-input v-model="form.nickname" maxlength="20" show-word-limit />
          </el-form-item>
          <el-form-item :label="t('settings.gender')">
            <el-select v-model="form.gender">
              <el-option :label="t('settings.genders.secret')" value="secret" />
              <el-option :label="t('settings.genders.female')" value="female" />
              <el-option :label="t('settings.genders.male')" value="male" />
              <el-option :label="t('settings.genders.nonbinary')" value="nonbinary" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('settings.birthday')">
            <el-date-picker v-model="form.birthday" type="date" value-format="YYYY-MM-DD" :placeholder="t('common.select')" />
          </el-form-item>
          <el-form-item :label="t('settings.location')">
            <el-input v-model="form.location" maxlength="80" />
          </el-form-item>
          <el-form-item :label="t('settings.locale')">
            <el-select v-model="form.locale">
              <el-option :label="t('extra.localeZh')" value="zh-CN" />
              <el-option :label="t('extra.localeEn')" value="en-US" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('auth.email')">
            <el-input :model-value="auth.user?.email" disabled />
          </el-form-item>
          <el-form-item :label="t('settings.bio')" class="full">
            <el-input v-model="form.bio" type="textarea" :rows="4" maxlength="300" show-word-limit :placeholder="t('settings.bioPlaceholder')" />
          </el-form-item>
        </div>
        <el-alert v-if="errorMessage" type="error" :closable="false" show-icon class="mb">{{ errorMessage }}</el-alert>
        <div class="form-actions">
          <button class="btn primary" type="submit" :disabled="saving">{{ saving ? t('common.saving') : t('settings.saveProfile') }}</button>
        </div>
      </el-form>
    </div>

    <div class="settings-panel contact-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">RE-VERIFY CONTACT</p>
          <h3>{{ t('settings.contactTitle') }}</h3>
          <p class="small muted">{{ t('settings.contactLead') }}</p>
        </div>
        <span class="current-contact">{{ currentContact }}</span>
      </div>
      <div class="contact-grid">
        <el-select v-model="contact.type" class="type-select">
          <el-option :label="t('auth.email')" value="email" />
          <el-option :label="t('extra.phone')" value="phone" />
        </el-select>
        <el-input v-model="contact.value" :placeholder="t('settings.contactValue')" />
        <button class="btn ghost" :disabled="contact.sending" @click="sendCode">{{ contact.sending ? t('common.sending') : t('settings.sendCode') }}</button>
      </div>
      <div v-if="contact.devCode" class="dev-code">
        <span class="mono">DEV</span>
        {{ t('auth.devCode') }}: <strong>{{ contact.devCode }}</strong>
      </div>
      <div class="contact-grid code-row">
        <el-input v-model="contact.code" maxlength="6" :placeholder="t('auth.code')" />
        <button class="btn primary" :disabled="contact.confirming" @click="confirmContact">{{ t('settings.confirmContact') }}</button>
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
  margin-bottom: 18px;
}
.avatar-section {
  display: flex;
  gap: 20px;
  align-items: center;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 22px;
}
.avatar-preview {
  width: 98px;
  height: 98px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-2);
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 36px;
  color: var(--accent);
  flex-shrink: 0;
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-section .small {
  margin: 4px 0 9px;
}
.small-btn {
  min-height: 34px;
  font-size: 11px;
  padding: 0 10px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
}
.mb {
  margin-bottom: 16px;
}
.contact-panel {
  background: var(--surface);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}
.panel-head h3 {
  margin: 7px 0;
  font-size: 22px;
}
.panel-head .small {
  max-width: 450px;
  line-height: 1.6;
}
.current-contact {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 4px 8px;
  white-space: nowrap;
}
.contact-grid {
  display: flex;
  gap: 8px;
}
.type-select {
  width: 110px;
  flex-shrink: 0;
}
.contact-grid .btn {
  min-height: 40px;
  flex-shrink: 0;
  font-size: 11px;
}
.code-row {
  margin-top: 8px;
}
.code-row .btn {
  min-width: 120px;
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
  margin-right: 6px;
}
@media (max-width: 640px) {
  .settings-panel {
    padding: 18px;
  }
  .avatar-section {
    align-items: flex-start;
  }
  .contact-grid {
    flex-wrap: wrap;
  }
  .contact-grid .el-input {
    flex: 1;
    min-width: 120px;
  }
  .panel-head {
    flex-direction: column;
  }
}
</style>
