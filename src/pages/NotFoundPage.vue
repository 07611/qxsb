<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <div class="not-found">
    <div class="big-number">4<span>0</span>4</div>
    <p class="eyebrow">SIGNAL LOST · PAGE NOT FOUND</p>
    <h1>{{ t('errors.notFound') }}</h1>
    <p class="muted">{{ $t('errors.notFoundBody') }}</p>
    <div class="actions">
      <router-link to="/" class="btn primary">{{ t('nav.home') }}</router-link>
      <router-link to="/search" class="btn ghost">{{ t('common.search') }}</router-link>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  min-height: calc(100vh - var(--header-h) - 100px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 16px;
  padding: 60px 20px;
}
.big-number {
  font-family: var(--font-display);
  font-size: clamp(120px, 24vw, 280px);
  line-height: 0.78;
  letter-spacing: -0.1em;
  font-weight: 500;
  color: var(--ink);
  opacity: 0.1;
}
.big-number span {
  color: var(--signal);
  opacity: 0.8;
  -webkit-text-stroke: 1px var(--signal);
}
h1 {
  font-size: clamp(28px, 4vw, 46px);
}
.actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
