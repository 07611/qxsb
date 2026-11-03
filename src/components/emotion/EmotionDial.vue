<script setup>
defineProps({
  emotion: { type: String, default: 'neutral' },
  score: { type: Number, default: 0 },
  color: { type: String, default: 'var(--accent)' },
  size: { type: Number, default: 132 },
})
</script>

<template>
  <div
    class="emotion-dial"
    :style="{
      '--dial-color': color,
      '--dial-score': `${Math.round(Math.max(0, Math.min(1, score)) * 360)}deg`,
      width: `${size}px`,
      height: `${size}px`,
    }"
    role="img"
    :aria-label="`${emotion} ${Math.round(score * 100)}%`"
  >
    <div class="dial-track"></div>
    <div class="dial-inner">
      <span class="dial-value">{{ Math.round(score * 100) }}<small>%</small></span>
      <span class="dial-label">{{ $t(`emotions.${emotion}`) }}</span>
    </div>
    <span class="dial-tick tick-1"></span>
    <span class="dial-tick tick-2"></span>
    <span class="dial-tick tick-3"></span>
  </div>
</template>

<style scoped>
.emotion-dial {
  position: relative;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(var(--dial-color) var(--dial-score), var(--line) 0);
  padding: 5px;
}
.emotion-dial::before {
  content: '';
  position: absolute;
  inset: -10px;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--dial-color) 18%, transparent);
  pointer-events: none;
}
.dial-track {
  position: absolute;
  inset: 5px;
  background: var(--surface);
  border-radius: 50%;
}
.dial-inner {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.dial-value {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 560;
  letter-spacing: -0.06em;
  line-height: 1;
}
.dial-value small {
  font-size: 12px;
  color: var(--muted);
  margin-left: 2px;
}
.dial-label {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.06em;
  color: var(--dial-color);
}
.dial-tick {
  position: absolute;
  background: var(--dial-color);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  opacity: 0.5;
}
.tick-1 {
  top: 11px;
  left: 50%;
}
.tick-2 {
  bottom: 26px;
  right: 17px;
}
.tick-3 {
  bottom: 26px;
  left: 17px;
}
</style>
