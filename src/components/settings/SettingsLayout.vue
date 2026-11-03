<script setup>
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/ui/PageHeader.vue'
import SettingsNav from './SettingsNav.vue'

defineProps({
  eyebrow: String,
  title: String,
  lead: String,
})
const { t } = useI18n()
</script>

<template>
  <div class="page settings-page">
    <div class="container">
      <PageHeader :eyebrow="eyebrow" :title="title" :lead="lead">
        <template #actions>
          <router-link to="/me" class="btn quiet">← {{ t('nav.me') }}</router-link>
        </template>
      </PageHeader>
      <div class="settings-layout">
        <aside class="settings-aside">
          <p class="aside-label eyebrow">{{ t('settings.title') }}</p>
          <SettingsNav />
          <div class="aside-note">
            <span class="mono">LOCAL FIRST</span>
            <p>{{ t('home.privacy') }}</p>
          </div>
        </aside>
        <div class="settings-content"><slot /></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-layout {
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 44px;
  align-items: start;
}
.settings-aside {
  position: sticky;
  top: 94px;
}
.aside-label {
  font-size: 8px;
  margin-bottom: 11px;
}
.aside-note {
  margin-top: 24px;
  border: 1px dashed var(--line);
  border-radius: 6px;
  padding: 11px;
}
.aside-note .mono {
  font-size: 7px;
  color: var(--accent);
  letter-spacing: 0.08em;
}
.aside-note p {
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--muted);
  margin-top: 5px;
}
.settings-content {
  min-width: 0;
}
@media (max-width: 900px) {
  .settings-layout {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .settings-aside {
    position: static;
  }
  .aside-note {
    display: none;
  }
  .aside-label {
    display: none;
  }
}
</style>
