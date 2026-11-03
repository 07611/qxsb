<script setup>
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const nav = [
  { to: '/admin', name: 'admin-dashboard', labelKey: 'admin.overview', icon: 'Odometer' },
  { to: '/admin/users', name: 'admin-users', labelKey: 'admin.users', icon: 'User' },
  { to: '/admin/feedback', name: 'admin-feedback', labelKey: 'admin.feedback', icon: 'ChatDotRound' },
  { to: '/admin/reports', name: 'admin-reports', labelKey: 'admin.reports', icon: 'TrendCharts' },
  { to: '/admin/analytics', name: 'admin-analytics', labelKey: 'admin.analytics', icon: 'DataAnalysis' },
]
</script>

<template>
  <div class="admin-shell">
    <div class="container admin-wrap">
      <aside class="admin-sidebar">
        <div class="admin-brand">
          <span class="admin-mark">M</span>
          <div>
            <strong>OPS CONSOLE</strong>
            <small>MOODWAVE / ADMIN</small>
          </div>
        </div>
        <nav class="admin-nav" :aria-label="$t('extra.adminNav')">
          <router-link
            v-for="item in nav"
            :key="item.name"
            :to="item.to"
            :class="{ active: route.name === item.name }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ t(item.labelKey) }}</span>
          </router-link>
        </nav>
        <div class="admin-sidebar-foot">
          <div class="admin-user">
            <span>{{ (auth.user?.nickname || 'A').slice(0, 1) }}</span>
            <div>
              <strong>{{ auth.user?.nickname }}</strong>
              <small>{{ t('admin.roles.admin') }}</small>
            </div>
          </div>
          <router-link to="/" class="back-site">← {{ t('admin.backToSite') }}</router-link>
        </div>
      </aside>
      <main class="admin-main">
        <div class="admin-topline">
          <span class="eyebrow">ADMINISTRATION / {{ String(route.name || '').replace('admin-', '').toUpperCase() }}</span>
          <span class="mono">LOCAL TIME · {{ new Date().toLocaleDateString() }}</span>
        </div>
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  min-height: calc(100vh - var(--header-h));
  padding: 24px 0 80px;
}
.admin-wrap {
  display: grid;
  grid-template-columns: 188px 1fr;
  gap: 32px;
  align-items: start;
}
.admin-sidebar {
  position: sticky;
  top: 90px;
  border-top: 1px solid var(--line);
}
.admin-brand {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 16px 4px;
  border-bottom: 1px solid var(--line);
}
.admin-mark {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--ink);
  color: var(--bg);
  font-family: var(--font-display);
  font-size: 15px;
}
.admin-brand div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.admin-brand strong {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.08em;
}
.admin-brand small {
  font-family: var(--font-mono);
  font-size: 6px;
  letter-spacing: 0.05em;
  color: var(--muted-2);
}
.admin-nav {
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.admin-nav a {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 38px;
  padding: 0 8px;
  border-radius: 5px;
  font-size: 11px;
  color: var(--muted);
}
.admin-nav a:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.admin-nav a.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 650;
}
.admin-sidebar-foot {
  padding: 16px 4px;
}
.admin-user {
  display: flex;
  gap: 8px;
  align-items: center;
}
.admin-user > span {
  width: 29px;
  height: 29px;
  border-radius: 50%;
  background: var(--surface-2);
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  font-size: 10px;
  color: var(--accent);
}
.admin-user div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.admin-user strong {
  font-size: 9px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.admin-user small {
  font-size: 7px;
  color: var(--muted-2);
}
.back-site {
  display: block;
  margin-top: 15px;
  font-size: 9px;
  color: var(--muted);
}
.back-site:hover {
  color: var(--accent);
}
.admin-main {
  min-width: 0;
}
.admin-topline {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 9px;
  margin-bottom: 22px;
}
.admin-topline .mono {
  font-size: 7px;
  color: var(--muted-2);
}
@media (max-width: 900px) {
  .admin-wrap {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  .admin-sidebar {
    position: static;
    border-top: 0;
  }
  .admin-brand {
    display: none;
  }
  .admin-nav {
    flex-direction: row;
    overflow-x: auto;
    border-bottom: 0;
    padding: 0;
    gap: 3px;
  }
  .admin-nav a {
    white-space: nowrap;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0 10px;
    min-height: 34px;
  }
  .admin-sidebar-foot {
    display: none;
  }
  .admin-topline {
    margin-top: 4px;
  }
}
</style>
