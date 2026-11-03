<script setup>
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const ui = useUiStore()
</script>

<template>
  <div class="auth-shell">
    <aside class="auth-visual">
      <div class="visual-grain"></div>
      <div class="visual-top">
        <router-link to="/" class="auth-brand">
          <span class="mark">
            <svg viewBox="0 0 40 40" width="38" height="38">
              <path d="M5 22c5 0 5-10 10-10s5 16 10 16 5-17 10-17" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
            </svg>
          </span>
          <span><strong>Moodwave</strong><small>{{ $t('extra.tagline') }}</small></span>
        </router-link>
        <button class="lang-switch" @click="ui.setLocale(ui.locale === 'zh-CN' ? 'en-US' : 'zh-CN')">
          {{ ui.locale === 'zh-CN' ? 'EN' : '中' }}
        </button>
      </div>

      <div class="visual-center">
        <p class="visual-eyebrow">EMOTION TO SOUNDSCAPE / 2026</p>
        <p class="visual-quote">
          {{ t('home.lead') }}
        </p>
        <div class="wave-visual" aria-hidden="true">
          <span v-for="n in 34" :key="n" :style="{ height: `${12 + Math.abs(Math.sin(n * 1.61)) * 58}px`, animationDelay: `${n * 0.06}s` }"></span>
        </div>
      </div>

      <div class="visual-bottom">
        <div class="stat">
          <strong>06</strong>
          <span>{{ t('home.statEmotions') }}</span>
        </div>
        <div class="stat">
          <strong>100%</strong>
          <span>{{ t('home.statLocal') }}</span>
        </div>
        <div class="stat">
          <strong>V1.0</strong>
          <span>{{ t('home.statExplain') }}</span>
        </div>
        <p class="visual-note">{{ t('home.privacy') }}</p>
      </div>
    </aside>

    <section class="auth-panel">
      <div class="panel-top">
        <router-link to="/" class="back-link">← {{ t('common.back') }}</router-link>
      </div>
      <div class="auth-form-wrap">
        <slot />
      </div>
      <div class="panel-footer">
        <span class="mono">MOODWAVE · LOCAL EMOTION LAB</span>
        <span class="mono">SECURE SESSION</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(380px, 0.88fr) minmax(480px, 1.12fr);
  background: var(--bg);
}
.auth-visual {
  position: relative;
  overflow: hidden;
  padding: 30px 34px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  color: #f4f0e8;
  background:
    radial-gradient(ellipse at 80% 10%, rgba(139, 139, 240, 0.32), transparent 45%),
    radial-gradient(ellipse at 5% 90%, rgba(232, 85, 47, 0.24), transparent 50%),
    linear-gradient(150deg, #16161c 0%, #20202c 55%, #272026 100%);
}
.visual-grain {
  position: absolute;
  inset: 0;
  opacity: 0.15;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 220 220' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.2'/%3E%3C/svg%3E");
}
.visual-top {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.auth-brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: #f4f0e8;
}
.auth-brand .mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  color: #b9b9ff;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.04);
}
.auth-brand span:last-child {
  display: flex;
  flex-direction: column;
  line-height: 1;
}
.auth-brand strong {
  font-family: var(--font-display);
  font-size: 19px;
  letter-spacing: -0.05em;
}
.auth-brand small {
  font-family: var(--font-mono);
  font-size: 7px;
  letter-spacing: 0.22em;
  opacity: 0.6;
  margin-top: 5px;
}
.lang-switch {
  min-width: 36px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.03);
  color: #ddd8cf;
  font-family: var(--font-mono);
  font-size: 10px;
}
.visual-center {
  position: relative;
  margin-block: auto;
  padding: 40px 0;
  max-width: 560px;
}
.visual-eyebrow {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.16em;
  color: rgba(244, 240, 232, 0.5);
  margin-bottom: 22px;
}
.visual-quote {
  font-family: var(--font-display);
  font-size: clamp(29px, 3.1vw, 46px);
  font-weight: 480;
  line-height: 1.18;
  letter-spacing: -0.04em;
  color: #f4f0e8;
  text-wrap: balance;
}
.wave-visual {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 84px;
  margin-top: 48px;
  opacity: 0.7;
}
.wave-visual span {
  width: 2px;
  border-radius: 2px;
  background: linear-gradient(180deg, #a4a4ff, #e98b70);
  animation: wave 2.8s ease-in-out infinite alternate;
}
@keyframes wave {
  to {
    transform: scaleY(0.4);
    opacity: 0.45;
  }
}
.visual-bottom {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 30px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 22px;
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.stat strong {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: -0.04em;
  color: #f4f0e8;
}
.stat span {
  font-size: 9px;
  color: rgba(244, 240, 232, 0.5);
  letter-spacing: 0.04em;
}
.visual-note {
  margin-left: auto;
  max-width: 200px;
  font-size: 9px;
  line-height: 1.6;
  color: rgba(244, 240, 232, 0.4);
  text-align: right;
}
.auth-panel {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 26px 42px;
  background:
    radial-gradient(ellipse at 85% 5%, rgba(232, 85, 47, 0.045), transparent 40%),
    var(--bg);
}
.panel-top {
  display: flex;
  justify-content: flex-end;
}
.back-link {
  font-size: 11.5px;
  color: var(--muted);
  padding: 8px;
}
.back-link:hover {
  color: var(--ink);
}
.auth-form-wrap {
  width: min(430px, 100%);
  margin: auto;
  padding: 28px 0 52px;
}
.panel-footer {
  display: flex;
  justify-content: space-between;
  color: var(--muted-2);
  font-size: 7px;
  letter-spacing: 0.1em;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }
  .auth-visual {
    min-height: auto;
    padding: 18px 20px;
    flex-direction: row;
    align-items: center;
  }
  .visual-center,
  .visual-bottom {
    display: none;
  }
  .visual-top {
    width: 100%;
  }
  .auth-panel {
    min-height: auto;
    padding: 16px 22px 36px;
  }
  .panel-top {
    display: none;
  }
  .auth-form-wrap {
    padding-top: 28px;
  }
  .panel-footer {
    display: none;
  }
}
@media (max-width: 480px) {
  .auth-panel {
    padding: 12px 18px 30px;
  }
}
</style>
