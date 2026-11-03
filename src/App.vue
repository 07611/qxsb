<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useNotificationStore } from '@/stores/notifications'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import MobileTabBar from '@/components/layout/MobileTabBar.vue'
import PlayerBar from '@/components/player/PlayerBar.vue'
import BootSplash from '@/components/ui/BootSplash.vue'
import AppErrorBoundary from '@/components/ui/AppErrorBoundary.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const notifications = useNotificationStore()

const isAuthLayout = computed(() => route.meta.layout === 'auth')
const showChrome = computed(() => !isAuthLayout.value)

ui.init()

onMounted(async () => {
  await auth.ensureSession()
  if (auth.isAuthenticated) notifications.fetchUnread()
  if (auth.isPending && route.meta.requiresActive) router.replace({ name: 'pending' })
})

watch(
  () => auth.user?.id,
  (id) => {
    if (id) notifications.fetchUnread()
    else notifications.clear()
  },
)
</script>

<template>
  <a class="skip-link" href="#main">{{ $t('extra.skip') }}</a>
  <BootSplash v-if="!auth.initialized" />
  <div v-else class="app-root" :class="{ 'auth-mode': isAuthLayout }">
    <AppHeader v-if="showChrome" />
    <main id="main" :class="{ 'with-player': $route.name }">
      <router-view v-slot="{ Component }">
        <AppErrorBoundary>
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </AppErrorBoundary>
      </router-view>
    </main>
    <AppFooter v-if="showChrome" />
    <MobileTabBar v-if="showChrome" />
    <PlayerBar />
  </div>
</template>

<style>
.skip-link {
  position: fixed;
  top: -100px;
  left: 16px;
  z-index: 3000;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--ink);
  color: var(--bg);
  font-size: 14px;
}
.skip-link:focus {
  top: 12px;
}
.app-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-root main {
  flex: 1;
}
.page-enter-active,
.page-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (max-width: 760px) {
  .app-root {
    padding-bottom: 68px;
  }
  .app-root:has(.player-shell) {
    padding-bottom: 144px;
  }
}
</style>
