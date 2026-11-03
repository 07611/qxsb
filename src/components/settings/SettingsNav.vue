<script setup>
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { t } = useI18n()
const items = [
  { to: '/settings/profile', key: 'profile', icon: 'User' },
  { to: '/settings/security', key: 'security', icon: 'Lock' },
  { to: '/settings/notifications', key: 'push', icon: 'Bell' },
  { to: '/me', key: 'me', icon: 'Collection' },
  { to: '/feedback', key: 'feedback', icon: 'ChatDotRound' },
]
</script>

<template>
  <nav class="settings-nav" :aria-label="$t('extra.settingsNav')">
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="settings-link"
      :class="{ active: route.path === item.to }"
    >
      <el-icon><component :is="item.icon" /></el-icon>
      <span>{{ t(`nav.${item.key}`) }}</span>
      <el-icon class="arrow"><Right /></el-icon>
    </router-link>
  </nav>
</template>

<style scoped>
.settings-nav {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--line);
}
.settings-link {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 45px;
  padding: 0 9px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 12.5px;
  transition: all 150ms;
}
.settings-link:hover {
  color: var(--ink);
  padding-left: 13px;
}
.settings-link.active {
  color: var(--accent);
}
.settings-link .arrow {
  margin-left: auto;
  font-size: 11px;
  opacity: 0;
  transition: opacity 150ms;
}
.settings-link:hover .arrow,
.settings-link.active .arrow {
  opacity: 1;
}
@media (max-width: 900px) {
  .settings-nav {
    flex-direction: row;
    overflow-x: auto;
    gap: 4px;
    border-top: 0;
    padding-bottom: 2px;
  }
  .settings-link {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0 12px;
    white-space: nowrap;
    font-size: 11px;
  }
  .settings-link .arrow {
    display: none;
  }
}
</style>
