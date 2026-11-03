<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useNotificationStore } from '@/stores/notifications'

const auth = useAuthStore()
const ui = useUiStore()
const notifications = useNotificationStore()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const mobileOpen = ref(false)
const scrolled = ref(false)
const searchFocused = ref(false)
const searchTerm = ref('')

const navItems = computed(() => {
  const items = [
    { label: t('nav.home'), to: '/' },
    { label: t('nav.discover'), to: '/discover' },
    { label: t('nav.algorithms'), to: '/algorithms' },
  ]
  if (auth.user?.status === 'pending') items.push({ label: t('auth.pending'), to: '/pending' })
  return items
})

const avatarFallback = computed(() => (auth.user?.nickname || 'M').slice(0, 1))

function isActive(to) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}

function onScroll() {
  scrolled.value = window.scrollY > 8
}

function goScan() {
  mobileOpen.value = false
  if (route.path === '/') {
    document.querySelector('#scanner')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } else {
    router.push({ path: '/', hash: '#scanner' })
  }
}

function onUserCommand(command) {
  if (command === 'logout') {
    auth.logout().finally(() => {
      notifications.clear()
      router.push('/')
    })
    return
  }
  router.push(command)
}

async function onLocale(lang) {
  await ui.setLocale(lang)
}

function submitSearch() {
  const value = searchTerm.value.trim()
  if (value) router.push({ path: '/search', query: { q: value } })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  if (auth.isAuthenticated) notifications.fetchUnread()
})
onUnmounted(() => window.removeEventListener('scroll', onScroll))

watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false
  },
)
</script>

<template>
  <header class="site-header" :class="{ scrolled }">
    <div class="container header-inner">
      <router-link to="/" class="brand" :aria-label="$t('nav.home')">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 40 40" width="35" height="35">
            <path
              d="M5 22c5 0 5-10 10-10s5 16 10 16 5-17 10-17"
              fill="none"
              stroke="currentColor"
              stroke-width="2.4"
              stroke-linecap="round"
            />
          </svg>
        </span>
        <span class="brand-words">
          <strong>Moodwave</strong>
          <small>{{ $t('extra.tagline') }}</small>
        </span>
      </router-link>

      <nav class="desktop-nav" :aria-label="$t('extra.mainNav')">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: isActive(item.to) }"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="header-actions">
        <form class="search-pill" role="search" @submit.prevent="submitSearch">
          <el-icon><Search /></el-icon>
          <input
            id="global-search"
            v-model="searchTerm"
            type="search"
            :placeholder="t('common.searchPlaceholder')"
            :aria-label="t('common.search')"
            @focus="searchFocused = true"
            @blur="searchFocused = false"
          />
          <kbd>/</kbd>
        </form>

        <button class="icon-btn theme-btn" :aria-label="$t('extra.theme')" @click="ui.toggleTheme">
          <el-icon :size="18"><Moon v-if="!ui.isDark" /><Sunny v-else /></el-icon>
        </button>

        <el-dropdown trigger="click" @command="onLocale">
          <button class="icon-btn lang-btn" :aria-label="$t('extra.language')">
            <span>{{ locale === 'zh-CN' ? '中' : 'EN' }}</span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh-CN" :disabled="locale === 'zh-CN'">{{ $t('extra.languageZh') }}</el-dropdown-item>
              <el-dropdown-item command="en-US" :disabled="locale === 'en-US'">{{ $t('extra.languageEn') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <router-link to="/notifications" class="icon-btn notification-btn" :aria-label="t('nav.notifications')">
          <el-badge :value="notifications.unread" :hidden="!notifications.unread" :max="99">
            <el-icon :size="18"><Bell /></el-icon>
          </el-badge>
        </router-link>

        <button class="btn primary scan-cta" @click="goScan">
          <el-icon><Aim /></el-icon>
          <span>{{ t('home.scanCta') }}</span>
        </button>

        <template v-if="auth.isAuthenticated">
          <el-dropdown trigger="click" @command="onUserCommand">
            <button class="avatar-trigger" :aria-label="t('nav.me')">
              <img v-if="auth.user?.avatarUrl" :src="auth.user.avatarUrl" alt="" width="36" height="36" />
              <span v-else>{{ avatarFallback }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="/me">{{ t('nav.me') }}</el-dropdown-item>
                <el-dropdown-item command="/items/new">{{ t('nav.create') }}</el-dropdown-item>
                <el-dropdown-item command="/settings/profile">{{ t('nav.profile') }}</el-dropdown-item>
                <el-dropdown-item command="/settings/security">{{ t('nav.security') }}</el-dropdown-item>
                <el-dropdown-item command="/settings/notifications">{{ t('nav.push') }}</el-dropdown-item>
                <el-dropdown-item command="/feedback">{{ t('nav.feedback') }}</el-dropdown-item>
                <el-dropdown-item v-if="auth.isAdmin" command="/admin" divided>{{ t('nav.admin') }}</el-dropdown-item>
                <el-dropdown-item command="logout" divided>{{ t('nav.logout') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <router-link to="/login" class="login-link">{{ t('nav.login') }}</router-link>
          <router-link to="/register" class="btn ghost register-link">{{ t('nav.register') }}</router-link>
        </template>

        <button class="icon-btn menu-toggle" :aria-expanded="mobileOpen" @click="mobileOpen = true">
          <el-icon :size="20"><Menu /></el-icon>
        </button>
      </div>
    </div>

    <el-drawer v-model="mobileOpen" direction="rtl" size="82%" :with-header="false">
      <div class="mobile-drawer">
        <div class="spread">
          <router-link to="/" class="brand" @click="mobileOpen = false">
            <span class="brand-mark">
              <svg viewBox="0 0 40 40" width="35" height="35">
                <path d="M5 22c5 0 5-10 10-10s5 16 10 16 5-17 10-17" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" />
              </svg>
            </span>
            <span class="brand-words"><strong>Moodwave</strong><small>{{ $t('extra.tagline') }}</small></span>
          </router-link>
          <button class="icon-btn" @click="mobileOpen = false"><el-icon><Close /></el-icon></button>
        </div>
        <nav class="mobile-nav">
          <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="mobile-nav-link">
            {{ item.label }}
            <el-icon><ArrowRight /></el-icon>
          </router-link>
          <router-link v-if="auth.isAuthenticated" to="/items/new" class="mobile-nav-link">{{ t('nav.create') }}<el-icon><ArrowRight /></el-icon></router-link>
          <router-link v-if="auth.isAuthenticated" to="/feedback" class="mobile-nav-link">{{ t('nav.feedback') }}<el-icon><ArrowRight /></el-icon></router-link>
          <router-link v-if="auth.isAdmin" to="/admin" class="mobile-nav-link">{{ t('nav.admin') }}<el-icon><ArrowRight /></el-icon></router-link>
        </nav>
        <div class="mobile-preferences">
          <button class="chip" :class="{ active: locale === 'zh-CN' }" @click="onLocale('zh-CN')">{{ t('extra.languageZh') }}</button>
          <button class="chip" :class="{ active: locale === 'en-US' }" @click="onLocale('en-US')">{{ t('extra.languageEn') }}</button>
          <button class="chip mobile-theme" @click="ui.toggleTheme">
            <el-icon><Moon v-if="!ui.isDark" /><Sunny v-else /></el-icon>
            {{ t('extra.theme') }}
          </button>
        </div>
        <div class="mobile-cta">
          <button class="btn primary" @click="goScan">{{ t('home.scanCta') }}</button>
          <router-link v-if="!auth.isAuthenticated" to="/register" class="btn ghost">{{ t('nav.register') }}</router-link>
          <button v-else class="btn ghost" @click="onUserCommand('logout')">{{ t('nav.logout') }}</button>
        </div>
        <p class="small muted privacy">{{ t('home.privacy') }}</p>
      </div>
    </el-drawer>
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid transparent;
  transition:
    background 200ms var(--ease),
    border-color 200ms var(--ease),
    backdrop-filter 200ms;
}
.site-header.scrolled {
  background: color-mix(in srgb, var(--bg) 80%, transparent);
  border-color: var(--line);
  backdrop-filter: blur(18px) saturate(130%);
}
.header-inner {
  min-height: var(--header-h);
  display: flex;
  align-items: center;
  gap: 28px;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex-shrink: 0;
}
.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  color: var(--accent);
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--surface) 80%, transparent);
  transition: all 180ms var(--ease);
}
.brand:hover .brand-mark {
  border-color: var(--accent);
  transform: rotate(-4deg);
}
.brand-words {
  display: flex;
  flex-direction: column;
  line-height: 1;
}
.brand-words strong {
  font-family: var(--font-display);
  font-size: 19px;
  letter-spacing: -0.045em;
  font-weight: 580;
}
.brand-words small {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.24em;
  color: var(--muted);
  margin-top: 5px;
}
.desktop-nav {
  display: flex;
  gap: 4px;
}
.nav-link {
  position: relative;
  padding: 10px 12px;
  font-size: 14px;
  font-weight: 560;
  color: var(--muted);
  border-radius: 7px;
  transition: all 160ms;
}
.nav-link:hover {
  color: var(--ink);
  background: var(--surface-2);
}
.nav-link.active {
  color: var(--ink);
}
.nav-link.active::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 3px;
  height: 2px;
  background: var(--accent);
  border-radius: 2px;
}
.header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 5px;
}
.search-pill {
  display: flex;
  align-items: center;
  width: 192px;
  height: 38px;
  padding: 0 10px;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  color: var(--muted);
  transition: all 180ms var(--ease);
}
.search-pill:focus-within {
  width: 240px;
  border-color: var(--accent);
  background: var(--surface);
}
.search-pill input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 12.5px;
}
.search-pill kbd {
  border: 1px solid var(--line);
  border-bottom-width: 2px;
  border-radius: 4px;
  padding: 0 4px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--muted-2);
}
.theme-btn,
.notification-btn {
  display: grid;
  place-items: center;
  color: var(--muted);
}
.notification-btn :deep(.el-badge__content) {
  font-size: 9px;
  height: 15px;
  min-width: 15px;
  padding: 0 4px;
  border: 2px solid var(--bg);
  background: var(--signal);
}
.lang-btn span {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 650;
}
.scan-cta {
  min-height: 38px;
  padding-inline: 14px;
  font-size: 13px;
  margin-left: 4px;
}
.avatar-trigger {
  width: 38px;
  height: 38px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-2);
  display: grid;
  place-items: center;
  color: var(--ink);
  font-family: var(--font-display);
  font-weight: 650;
  margin-left: 2px;
}
.avatar-trigger img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.login-link {
  font-size: 13.5px;
  font-weight: 600;
  padding: 10px 9px;
  color: var(--muted);
}
.login-link:hover {
  color: var(--ink);
}
.register-link {
  min-height: 38px;
  padding-inline: 12px;
  font-size: 13px;
}
.menu-toggle {
  display: none;
}
.mobile-drawer {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 8px 4px;
}
.mobile-nav {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--line);
}
.mobile-nav-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 56px;
  border-bottom: 1px solid var(--line);
  font-family: var(--font-display);
  font-size: 20px;
  letter-spacing: -0.02em;
}
.mobile-nav-link:hover {
  color: var(--accent);
}
.mobile-cta {
  display: grid;
  gap: 10px;
}
.mobile-preferences {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.mobile-theme {
  margin-left: auto;
}
.privacy {
  margin-top: auto;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}
@media (max-width: 1100px) {
  .desktop-nav {
    display: none;
  }
  .search-pill {
    width: 160px;
  }
  .scan-cta span {
    display: none;
  }
  .scan-cta {
    width: 38px;
    padding: 0;
  }
}
@media (max-width: 900px) {
  .search-pill,
  .register-link,
  .login-link,
  .theme-btn,
  .lang-btn {
    display: none;
  }
  .menu-toggle {
    display: grid;
  }
  .header-inner {
    gap: 12px;
  }
  .site-header {
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    border-color: var(--line);
    backdrop-filter: blur(18px);
  }
}
@media (max-width: 480px) {
  .scan-cta,
  .notification-btn {
    display: none;
  }
  .brand-words small {
    display: none;
  }
}
</style>
