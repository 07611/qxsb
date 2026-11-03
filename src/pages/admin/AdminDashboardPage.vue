<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { formatDate, parseUserIds, toDateString } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'
import ImageUploader from '@/components/content/ImageUploader.vue'

const { t, locale } = useI18n()
const auth = useAuthStore()
const stats = ref(null)
const loading = ref(true)
const error = ref(null)
const emailTo = ref('')
const emailSending = ref(false)
const emailLogs = ref([])
const pushForm = reactive({
  templateCode: 'system_notice',
  content: '',
  userIds: '',
  channels: ['inapp'],
  marketing: false,
})
const pushSending = ref(false)
const banners = ref([])
const bannerLoading = ref(false)
const bannerForm = reactive({
  position: 'home',
  title: '',
  subtitle: '',
  image: null,
  linkUrl: '',
  sort: 0,
  status: 'active',
  aspectRatio: '16/5',
})
const bannerSaving = ref(false)

const maxSignups = computed(() => Math.max(...(stats.value?.signupSeries || []).map((item) => item.users), 1))
const statCards = computed(() => [
  { label: t('admin.statsUsers'), value: stats.value?.users.total || 0, sub: `${stats.value?.users.active || 0} active`, icon: 'User', tone: 'accent' },
  { label: t('admin.statsPending'), value: stats.value?.users.pending || 0, sub: 'awaiting review', icon: 'Clock', tone: 'warning' },
  { label: t('admin.statsItems'), value: stats.value?.content.items || 0, sub: `${stats.value?.content.published || 0} published`, icon: 'Collection', tone: 'neutral' },
  { label: t('admin.statsFeedback'), value: stats.value?.feedback.open || 0, sub: 'open tickets', icon: 'ChatDotRound', tone: 'signal' },
  { label: t('admin.statsTracks'), value: stats.value?.content.tracks || 0, sub: 'local + metadata', icon: 'Headset', tone: 'neutral' },
])

async function load() {
  loading.value = true
  error.value = null
  try {
    const [statsResponse, emailResponse, bannerResponse] = await Promise.all([
      adminApi.stats(),
      adminApi.emailLogs({ pageSize: 5 }),
      adminApi.banners(),
    ])
    stats.value = statsResponse.data
    emailLogs.value = emailResponse.data.items || []
    banners.value = bannerResponse.data.items || []
    emailTo.value = auth.user?.email || ''
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

async function sendTestEmail() {
  if (!emailTo.value.trim()) return
  emailSending.value = true
  try {
    const response = await adminApi.emailTest(emailTo.value.trim())
    ElMessage.success(t('admin.emailQueued'))
    const logs = await adminApi.emailLogs({ pageSize: 5 })
    emailLogs.value = logs.data.items || []
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    emailSending.value = false
  }
}

function toggleChannel(channel) {
  pushForm.channels = pushForm.channels.includes(channel)
    ? pushForm.channels.filter((item) => item !== channel)
    : [...pushForm.channels, channel]
}

async function sendPush() {
  if (!pushForm.content.trim()) return
  pushSending.value = true
  try {
    const response = await adminApi.push({
      templateCode: pushForm.templateCode,
      content: pushForm.content.trim(),
      userIds: parseUserIds(pushForm.userIds),
      channels: pushForm.channels,
      marketing: pushForm.marketing,
    })
    ElMessage.success(t('admin.pushDone', { created: response.data.tasksCreated, skipped: response.data.skipped }))
    pushForm.content = ''
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    pushSending.value = false
  }
}

async function saveBanner() {
  if (!bannerForm.title.trim() || !bannerForm.image?.url) {
    ElMessage.warning(t('extra.bannerValidation'))
    return
  }
  bannerSaving.value = true
  try {
    await adminApi.createBanner({
      position: bannerForm.position,
      title: bannerForm.title.trim(),
      subtitle: bannerForm.subtitle.trim(),
      imageUrl: bannerForm.image.url,
      linkUrl: bannerForm.linkUrl.trim() || null,
      sort: Number(bannerForm.sort) || 0,
      status: bannerForm.status,
      aspectRatio: '16/5',
    })
    ElMessage.success(t('admin.bannerSaved'))
    bannerForm.title = ''
    bannerForm.subtitle = ''
    bannerForm.image = null
    bannerForm.linkUrl = ''
    const response = await adminApi.banners()
    banners.value = response.data.items || []
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    bannerSaving.value = false
  }
}

async function removeBanner(banner) {
  try {
    await ElMessageBox.confirm(banner.title, t('common.delete'), { type: 'warning' })
    await adminApi.deleteBanner(banner.id)
    banners.value = banners.value.filter((item) => item.id !== banner.id)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(normalizeError(err).message)
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-dashboard">
    <AsyncState :loading="loading" :error="error" @retry="load">
      <div class="admin-heading">
        <div>
          <p class="eyebrow">{{ t('admin.eyebrow') }}</p>
          <h1>{{ t('admin.title') }}</h1>
        </div>
        <div class="heading-meta">
          <span class="mono">{{ stats?.generatedAt ? new Date(stats.generatedAt).toLocaleString() : '' }}</span>
          <button class="btn ghost small" @click="load"><el-icon><Refresh /></el-icon>{{ t('common.retry') }}</button>
        </div>
      </div>

      <div class="stat-grid">
        <div v-for="card in statCards" :key="card.label" class="stat-box" :class="card.tone">
          <div class="stat-icon"><el-icon><component :is="card.icon" /></el-icon></div>
          <div class="stat-value">{{ String(card.value).padStart(2, '0') }}</div>
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-sub mono">{{ card.sub }}</div>
        </div>
      </div>

      <div class="dashboard-grid">
        <section class="panel panel-wide">
          <div class="panel-head">
            <div>
              <p class="eyebrow">GROWTH</p>
              <h3>{{ t('admin.signupTrend') }}</h3>
            </div>
            <span class="mono">7D</span>
          </div>
          <div class="signup-chart">
            <div v-for="entry in stats.signupSeries" :key="entry.date" class="signup-bar-wrap">
              <span class="signup-count mono">{{ entry.users }}</span>
              <div class="signup-bar" :style="{ height: `${Math.max(4, (entry.users / maxSignups) * 100)}%` }"></div>
              <span class="signup-label mono">{{ entry.date.slice(5) }}</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">MONITORING</p>
              <h3>{{ t('admin.recentErrors') }}</h3>
            </div>
            <span class="mono">{{ stats.recentErrors.length }}</span>
          </div>
          <div v-if="stats.recentErrors.length" class="error-list">
            <div v-for="entry in stats.recentErrors" :key="entry.id" class="error-item">
              <span class="error-mark">!</span>
              <div>
                <strong>{{ entry.message }}</strong>
                <p class="mono">{{ entry.route }}</p>
              </div>
              <span class="mono">{{ formatDate(entry.createdAt, locale, { hour: '2-digit', minute: '2-digit' }) }}</span>
            </div>
          </div>
          <p v-else class="empty-line">{{ t('admin.noData') }}</p>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">TOOLKIT</p>
              <h3>{{ t('admin.emailTest') }}</h3>
            </div>
            <span class="mono">SMTP</span>
          </div>
          <p class="panel-note">{{ t('admin.emailTestHint') }}</p>
          <div class="inline-form">
            <el-input v-model="emailTo" placeholder="you@example.com" />
            <button class="btn ghost" :disabled="emailSending" @click="sendTestEmail">{{ emailSending ? t('common.sending') : t('admin.sendTest') }}</button>
          </div>
          <div class="email-mini-list">
            <div v-for="log in emailLogs.slice(0, 4)" :key="log.id" class="email-mini">
              <span :class="{ ok: log.status === 'sent', fail: log.status === 'failed' }">{{ log.status }}</span>
              <span>{{ log.subject }}</span>
              <span class="mono">{{ log.retryCount }}r</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">TARGETED</p>
              <h3>{{ t('admin.pushSend') }}</h3>
            </div>
            <span class="mono">MAX 5 / DAY</span>
          </div>
          <div class="push-form">
            <el-select v-model="pushForm.templateCode" size="small">
              <el-option :label="t('extra.pushTemplateSystem')" value="system_notice" />
              <el-option :label="t('extra.pushTemplateFeature')" value="feature_update" />
              <el-option :label="t('extra.pushTemplateWeekly')" value="weekly_pick" />
            </el-select>
            <el-input v-model="pushForm.content" type="textarea" :rows="2" maxlength="500" :placeholder="t('admin.pushContent')" />
            <el-input v-model="pushForm.userIds" size="small" :placeholder="t('admin.pushUsers')" />
            <div class="push-bottom">
              <div class="channel-pills">
                <button v-for="channel in ['inapp', 'email', 'sms', 'push']" :key="channel" :class="{ active: pushForm.channels.includes(channel) }" @click="toggleChannel(channel)">
                  {{ channel }}
                </button>
              </div>
              <label class="marketing-toggle">
                <el-switch v-model="pushForm.marketing" size="small" /> {{ t('admin.pushMarketing') }}
              </label>
            </div>
            <button class="btn signal small" :disabled="pushSending" @click="sendPush">{{ pushSending ? t('common.sending') : t('admin.pushSendBtn') }}</button>
          </div>
        </section>

        <section class="panel panel-wide">
          <div class="panel-head">
            <div>
              <p class="eyebrow">OPERATIONS</p>
              <h3>{{ t('admin.banners') }}</h3>
            </div>
            <span class="mono">{{ banners.length }} ACTIVE</span>
          </div>
          <div class="banner-manager">
            <div class="banner-form">
              <div class="banner-fields">
                <el-select v-model="bannerForm.position" size="small">
                  <el-option label="HOME" value="home" />
                  <el-option label="DISCOVER" value="discover" />
                  <el-option label="SETTINGS" value="settings" />
                </el-select>
                <el-input v-model="bannerForm.title" size="small" :placeholder="t('admin.bannerTitle')" />
                <el-input v-model="bannerForm.linkUrl" size="small" :placeholder="t('admin.bannerLink')" />
              </div>
              <el-input v-model="bannerForm.subtitle" size="small" :placeholder="t('admin.bannerSubtitle')" />
              <ImageUploader v-model="bannerForm.image" biz-type="banner" aspect="16 / 5" hint="1600×500 SVG/PNG/JPG" />
              <div class="banner-submit">
                <el-switch v-model="bannerForm.status" active-value="active" inactive-value="inactive" size="small" />
                <button class="btn primary small" :disabled="bannerSaving" @click="saveBanner">{{ t('admin.bannerAdd') }}</button>
              </div>
            </div>
            <div class="banner-list">
              <div v-for="banner in banners" :key="banner.id" class="banner-row">
                <img :src="banner.imageUrl" :alt="banner.title" width="160" height="50" />
                <div>
                  <strong>{{ banner.title }}</strong>
                  <span class="mono">{{ banner.position.toUpperCase() }} · SORT {{ banner.sort }}</span>
                </div>
                <button class="delete-mini" @click="removeBanner(banner)"><el-icon><Delete /></el-icon></button>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">LATEST</p>
              <h3>{{ t('admin.recentFeedback') }}</h3>
            </div>
            <router-link to="/admin/feedback" class="mono">ALL →</router-link>
          </div>
          <div class="feedback-list">
            <div v-for="entry in stats.recentFeedback" :key="entry.id" class="feedback-mini">
              <div class="feedback-mini-top">
                <span class="mono">{{ entry.ticketNo }}</span>
                <span class="status-tag">{{ entry.status }}</span>
              </div>
              <p>{{ entry.content }}</p>
            </div>
          </div>
        </section>
      </div>
    </AsyncState>
  </div>
</template>

<style scoped>
.admin-heading {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-end;
  margin-bottom: 22px;
}
.admin-heading h1 {
  font-size: clamp(34px, 4vw, 52px);
  margin-top: 8px;
}
.heading-meta {
  display: flex;
  align-items: center;
  gap: 9px;
}
.heading-meta .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.small {
  min-height: 32px;
  font-size: 9px;
  padding: 0 9px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 9px;
  overflow: hidden;
  margin-bottom: 16px;
}
.stat-box {
  background: var(--surface);
  padding: 14px;
  min-height: 118px;
  display: flex;
  flex-direction: column;
  position: relative;
}
.stat-icon {
  position: absolute;
  right: 12px;
  top: 12px;
  color: var(--muted-2);
  font-size: 15px;
}
.stat-value {
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 540;
  letter-spacing: -0.05em;
  margin-top: auto;
}
.stat-label {
  font-size: 9px;
  color: var(--ink-2);
}
.stat-sub {
  font-size: 7px;
  color: var(--muted-2);
  margin-top: 3px;
}
.stat-box.accent .stat-value {
  color: var(--accent);
}
.stat-box.warning .stat-value {
  color: var(--warning);
}
.stat-box.signal .stat-value {
  color: var(--signal);
}
.dashboard-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 13px;
}
.panel {
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  padding: 15px;
  min-width: 0;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 11px;
}
.panel-head h3 {
  font-size: 18px;
  margin-top: 4px;
}
.panel-head .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.panel-note {
  font-size: 9px;
  color: var(--muted);
  line-height: 1.55;
  margin-bottom: 8px;
}
.signup-chart {
  height: 155px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 8px 5px 0;
}
.signup-bar-wrap {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.signup-count {
  font-size: 7px;
  color: var(--muted);
}
.signup-bar {
  width: 100%;
  max-width: 33px;
  background: linear-gradient(180deg, var(--accent), color-mix(in srgb, var(--accent) 30%, var(--surface-2)));
  border-radius: 2px 2px 0 0;
  min-height: 4px;
  transition: height 500ms var(--ease);
}
.signup-label {
  font-size: 6.5px;
  color: var(--muted-2);
  white-space: nowrap;
}
.error-list,
.feedback-list {
  display: flex;
  flex-direction: column;
}
.error-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
}
.error-mark {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--danger) 12%, var(--surface));
  color: var(--danger);
  display: grid;
  place-items: center;
  font-size: 9px;
  flex-shrink: 0;
}
.error-item div {
  flex: 1;
  min-width: 0;
}
.error-item strong {
  font-size: 9.5px;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.error-item p {
  font-size: 7px;
  color: var(--muted-2);
  margin-top: 2px;
}
.error-item > .mono {
  font-size: 6.5px;
  color: var(--muted-2);
  white-space: nowrap;
}
.empty-line {
  color: var(--muted-2);
  font-size: 10px;
  padding: 16px 0;
}
.inline-form {
  display: flex;
  gap: 6px;
}
.inline-form .btn {
  min-height: 34px;
  font-size: 9px;
  flex-shrink: 0;
}
.email-mini-list {
  margin-top: 8px;
}
.email-mini {
  display: grid;
  grid-template-columns: 34px 1fr 18px;
  gap: 5px;
  padding: 5px 0;
  border-top: 1px solid var(--line);
  font-size: 8px;
  color: var(--muted);
}
.email-mini > span:first-child {
  color: var(--warning);
}
.email-mini > span:first-child.ok {
  color: var(--success);
}
.email-mini > span:first-child.fail {
  color: var(--danger);
}
.email-mini .mono {
  font-size: 6px;
  color: var(--muted-2);
}
.push-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.push-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.channel-pills {
  display: flex;
  gap: 3px;
}
.channel-pills button {
  font-family: var(--font-mono);
  font-size: 7px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: transparent;
  padding: 3px 4px;
  color: var(--muted-2);
}
.channel-pills button.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}
.marketing-toggle {
  font-size: 8px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 5px;
}
.push-form > .btn {
  min-height: 34px;
  width: 100%;
  font-size: 9px;
}
.banner-manager {
  display: grid;
  grid-template-columns: 1fr 0.8fr;
  gap: 16px;
}
.banner-form {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.banner-fields {
  display: grid;
  grid-template-columns: 100px 1fr 1fr;
  gap: 5px;
}
.banner-submit {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.banner-submit .btn {
  min-height: 31px;
  font-size: 8px;
}
.banner-list {
  display: flex;
  flex-direction: column;
}
.banner-row {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding: 6px 0;
}
.banner-row img {
  width: 110px;
  height: 35px;
  object-fit: cover;
  border-radius: 3px;
  border: 1px solid var(--line);
}
.banner-row div {
  flex: 1;
  min-width: 0;
}
.banner-row strong {
  font-size: 8.5px;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.banner-row .mono {
  font-size: 6px;
  color: var(--muted-2);
}
.delete-mini {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--muted-2);
}
.delete-mini:hover {
  color: var(--danger);
  background: var(--signal-soft);
}
.feedback-mini {
  padding: 7px 0;
  border-top: 1px solid var(--line);
}
.feedback-mini-top {
  display: flex;
  justify-content: space-between;
}
.feedback-mini-top .mono {
  font-size: 6.5px;
  color: var(--muted-2);
}
.status-tag {
  font-size: 6.5px;
  color: var(--warning);
  text-transform: uppercase;
}
.feedback-mini p {
  font-size: 8.5px;
  line-height: 1.5;
  color: var(--muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  .banner-manager {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .stat-grid {
    grid-template-columns: 1fr 1fr;
  }
  .stat-box {
    min-height: 98px;
  }
  .admin-heading {
    flex-direction: column;
    align-items: flex-start;
  }
  .heading-meta {
    width: 100%;
    justify-content: space-between;
  }
  .banner-fields {
    grid-template-columns: 1fr;
  }
}
</style>
