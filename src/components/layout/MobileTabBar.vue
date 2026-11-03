<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const { t } = useI18n()

function scan() {
  if (route.path === '/') document.querySelector('#scanner')?.scrollIntoView({ behavior: 'smooth' })
  else router.push('/#scanner')
}
</script>

<template>
  <nav class="mobile-tabbar" :aria-label="$t('extra.mobileNav')">
    <router-link to="/" :class="{ active: route.path === '/' }">
      <el-icon><HomeFilled /></el-icon><span>{{ t('nav.home') }}</span>
    </router-link>
    <router-link to="/discover" :class="{ active: route.path.startsWith('/discover') }">
      <el-icon><Compass /></el-icon><span>{{ t('nav.discover') }}</span>
    </router-link>
    <button class="scan-tab" @click="scan" :aria-label="$t('home.scanCta')">
      <span class="scan-shape"><el-icon><Aim /></el-icon></span>
      <span>{{ t('home.scanCta') }}</span>
    </button>
    <router-link to="/notifications" :class="{ active: route.path.startsWith('/notifications') }">
      <el-icon><Bell /></el-icon><span>{{ t('nav.notifications') }}</span>
    </router-link>
    <router-link :to="auth.isAuthenticated ? '/me' : '/login'" :class="{ active: ['/me', '/login'].includes(route.path) }">
      <el-icon><User /></el-icon><span>{{ auth.isAuthenticated ? t('nav.me') : t('nav.login') }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.mobile-tabbar {
  display: none;
}
@media (max-width: 760px) {
  .mobile-tabbar {
    position: fixed;
    left: 10px;
    right: 10px;
    bottom: 10px;
    z-index: 95;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    align-items: center;
    height: 62px;
    padding: 5px 6px;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: color-mix(in srgb, var(--surface) 91%, transparent);
    backdrop-filter: blur(20px) saturate(140%);
    box-shadow: 0 12px 34px rgba(26, 26, 28, 0.09);
  }
  .mobile-tabbar a {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-width: 44px;
    min-height: 48px;
    font-size: 9px;
    color: var(--muted);
    font-weight: 600;
  }
  .mobile-tabbar a.active {
    color: var(--accent);
  }
  .mobile-tabbar .el-icon {
    font-size: 19px;
  }
  .scan-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: 8.5px;
    color: var(--signal);
    border: 0;
    background: transparent;
    padding: 0;
    min-width: 44px;
    min-height: 48px;
  }
  .scan-shape {
    width: 40px;
    height: 40px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: var(--signal);
    color: #fff;
    margin-top: -22px;
    border: 3px solid var(--surface);
    box-shadow: 0 6px 18px rgba(232, 85, 47, 0.25);
  }
  .scan-shape .el-icon {
    font-size: 19px;
  }
}
</style>
