<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const refreshing = ref(false)

const email = computed(() => auth.user?.email || '')
const avatar = computed(() => auth.user?.avatarUrl)

async function refresh() {
  refreshing.value = true
  try {
    await auth.refreshProfile()
    if (auth.user?.status === 'active') router.replace('/')
  } finally {
    refreshing.value = false
  }
}

function logout() {
  auth.logout().finally(() => router.replace('/login'))
}

onMounted(() => {
  if (auth.user?.status === 'active') router.replace('/')
})
</script>

<template>
  <div class="pending-page">
    <div class="pending-orbit" aria-hidden="true">
      <span class="orbit o1"></span>
      <span class="orbit o2"></span>
      <span class="orbit o3"></span>
      <span class="core">
        <img v-if="avatar" :src="avatar" alt="" width="92" height="92" />
        <span v-else>{{ (auth.user?.nickname || 'M').slice(0, 1) }}</span>
      </span>
    </div>
    <p class="eyebrow">ACCOUNT REVIEW · PENDING</p>
    <h1>{{ t('auth.pendingTitle') }}</h1>
    <p class="muted">{{ t('auth.pendingBody') }}</p>
    <div class="account-line">
      <span class="mono">SIGNED IN AS</span>
      <strong>{{ auth.user?.nickname }}</strong>
      <span class="muted">{{ email }}</span>
    </div>
    <div class="actions">
      <button class="btn primary" :disabled="refreshing" @click="refresh">
        <el-icon><Refresh /></el-icon>
        {{ refreshing ? t('common.loading') : t('auth.refreshStatus') }}
      </button>
      <router-link to="/feedback" class="btn ghost">{{ t('nav.feedback') }}</router-link>
      <button class="btn quiet" @click="logout">{{ t('nav.logout') }}</button>
    </div>
  </div>
</template>

<style scoped>
.pending-page {
  min-height: calc(100vh - var(--header-h));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 60px 24px 100px;
  gap: 18px;
}
.pending-orbit {
  position: relative;
  width: 190px;
  height: 190px;
  margin-bottom: 18px;
}
.orbit {
  position: absolute;
  border-radius: 50%;
  border: 1px solid var(--line);
}
.o1 {
  inset: 0;
  border-style: dashed;
  animation: spin 30s linear infinite;
}
.o2 {
  inset: 20px;
  border-color: color-mix(in srgb, var(--accent) 25%, var(--line));
  animation: spin 24s linear infinite reverse;
}
.o3 {
  inset: 42px;
}
.core {
  position: absolute;
  inset: 57px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-family: var(--font-display);
  font-size: 34px;
  color: var(--accent);
}
.core img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
h1 {
  font-size: clamp(34px, 5vw, 56px);
  max-width: 760px;
}
.pending-page > .muted {
  max-width: 500px;
  font-size: 15px;
  line-height: 1.75;
}
.account-line {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 9px 16px;
  background: var(--surface);
  font-size: 12px;
}
.account-line .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}
</style>
