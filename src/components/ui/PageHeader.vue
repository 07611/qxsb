<script setup>
defineProps({
  eyebrow: String,
  title: String,
  lead: String,
  align: { type: String, default: 'left' },
})
</script>

<template>
  <header class="page-header" :class="align">
    <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
    <h1 class="title">{{ title }}</h1>
    <p v-if="lead" class="lead">{{ lead }}</p>
    <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 40px;
  max-width: 900px;
}
.page-header.center {
  text-align: center;
  align-items: center;
  margin-inline: auto;
}
.title {
  font-size: clamp(38px, 5vw, 68px);
  white-space: pre-line;
}
.lead {
  color: var(--muted);
  font-size: clamp(16px, 1.8vw, 19px);
  max-width: 680px;
  line-height: 1.65;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
}
@media (max-width: 640px) {
  .page-header {
    margin-bottom: 28px;
    gap: 14px;
  }
}
</style>
