<script setup>
import { onErrorCaptured, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const error = ref(null)

onErrorCaptured((err, instance, info) => {
  error.value = err
  console.error('[Moodwave boundary]', err, info)
  return false
})

function reload() {
  window.location.reload()
}
</script>

<template>
  <slot v-if="!error" />
  <div v-else class="boundary">
    <div class="boundary-symbol">!</div>
    <p class="eyebrow">RENDER BOUNDARY</p>
    <h1>{{ t('errors.unexpected') }}</h1>
    <p class="muted">{{ error?.message }}</p>
    <div class="boundary-actions">
      <button class="btn primary" @click="reload">{{ t('common.retry') }}</button>
      <router-link to="/" class="btn ghost">{{ t('nav.home') }}</router-link>
    </div>
  </div>
</template>

<style scoped>
.boundary {
  min-height: 52vh;
  width: min(760px, calc(100% - 32px));
  margin: 40px auto;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  padding: clamp(24px, 5vw, 52px);
  display: flex;
  flex-direction: column;
  gap: 14px;
  justify-content: center;
}
.boundary-symbol {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--signal-soft);
  color: var(--signal);
  font-family: var(--font-display);
  font-size: 24px;
}
.boundary h1 {
  font-size: clamp(28px, 4vw, 42px);
}
.boundary-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>
