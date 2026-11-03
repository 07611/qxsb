<script setup>
defineProps({
  loading: Boolean,
  error: { type: Object, default: null },
  empty: Boolean,
  emptyText: { type: String, default: '' },
  skeletonRows: { type: Number, default: 3 },
})
defineEmits(['retry'])
</script>

<template>
  <div v-if="loading" class="async-state">
    <div v-for="index in skeletonRows" :key="index" class="skeleton state-skeleton" />
  </div>
  <div v-else-if="error" class="async-state error-state">
    <div class="state-icon">!</div>
    <div>
      <strong>{{ $t('common.loadFailed') }}</strong>
      <p class="small muted">{{ error.message || $t('common.error') }}</p>
      <p v-if="error.requestId" class="mono muted request-id">{{ $t('errors.requestId', { id: error.requestId }) }}</p>
    </div>
    <button class="btn ghost" @click="$emit('retry')">{{ $t('common.retry') }}</button>
  </div>
  <div v-else-if="empty" class="async-state empty-state">
    <slot name="empty">
      <div class="empty-symbol">◌</div>
      <p class="muted">{{ emptyText || $t('common.empty') }}</p>
    </slot>
  </div>
  <slot v-else />
</template>

<style scoped>
.async-state {
  display: grid;
  gap: 12px;
}
.state-skeleton {
  height: 84px;
}
.error-state {
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px;
  background: var(--surface);
}
.state-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--signal-soft);
  color: var(--signal);
  font-family: var(--font-display);
  font-weight: 700;
}
.request-id {
  margin-top: 4px;
  font-size: 10px;
}
.empty-state {
  place-items: center;
  text-align: center;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 42px 20px;
  background: color-mix(in srgb, var(--surface) 55%, transparent);
}
.empty-symbol {
  font-size: 34px;
  color: var(--muted-2);
  margin-bottom: 8px;
}
@media (max-width: 600px) {
  .error-state {
    grid-template-columns: auto 1fr;
  }
  .error-state .btn {
    grid-column: 1 / -1;
  }
}
</style>
