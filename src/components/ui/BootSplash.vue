<template>
  <div class="boot-splash" aria-live="polite" :aria-label="$t('extra.booting')">
    <div class="boot-mark">
      <svg viewBox="0 0 64 64" width="42" height="42" aria-hidden="true">
        <path
          d="M8 36c8 0 8-16 16-16s8 26 16 26 8-27 16-27"
          fill="none"
          stroke="currentColor"
          stroke-width="4"
          stroke-linecap="round"
        />
      </svg>
    </div>
    <div class="boot-word">Moodwave</div>
    <div class="boot-line"><span></span></div>
  </div>
</template>

<style scoped>
.boot-splash {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 14px;
  background:
    radial-gradient(circle at 50% 40%, rgba(91, 91, 214, 0.1), transparent 36%),
    var(--bg);
}
.boot-mark {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 18px;
  color: var(--accent);
  background: var(--surface);
}
.boot-word {
  font-family: var(--font-display);
  font-size: 20px;
  letter-spacing: -0.03em;
}
.boot-line {
  width: 120px;
  height: 2px;
  overflow: hidden;
  background: var(--line);
}
.boot-line span {
  display: block;
  width: 40%;
  height: 100%;
  background: var(--accent);
  animation: boot 1.2s var(--ease) infinite;
}
@keyframes boot {
  0% {
    transform: translateX(-110%);
  }
  100% {
    transform: translateX(360%);
  }
}
</style>
