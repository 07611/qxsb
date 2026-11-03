<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const year = new Date().getFullYear()
</script>

<template>
  <footer class="site-footer">
    <div class="container footer-grid">
      <div class="footer-brand">
        <div class="wordmark">Moodwave<span>®</span></div>
        <p class="small muted">
          {{ t('meta.description') }}。
          <br />
          {{ t('algorithms.privacyBody') }}
        </p>
        <div class="footer-status">
          <span class="status-dot"></span>
          Local inference · v1.0
        </div>
      </div>
      <div class="footer-col">
        <p class="eyebrow">{{ t('nav.discover') }}</p>
        <router-link to="/discover">{{ t('discover.tracks') }}</router-link>
        <router-link to="/discover">{{ t('discover.categories') }}</router-link>
        <router-link to="/algorithms">{{ t('nav.algorithms') }}</router-link>
        <router-link to="/search">{{ t('common.search') }}</router-link>
      </div>
      <div class="footer-col">
        <p class="eyebrow">{{ t('nav.settings') }}</p>
        <router-link to="/me">{{ t('nav.me') }}</router-link>
        <router-link to="/settings/profile">{{ t('nav.profile') }}</router-link>
        <router-link to="/settings/notifications">{{ t('nav.push') }}</router-link>
        <router-link to="/feedback">{{ t('nav.feedback') }}</router-link>
      </div>
      <div class="footer-col footer-note">
        <p class="eyebrow">COLOPHON</p>
        <p class="small muted">
          Space Grotesk / Manrope / JetBrains Mono.<br />
          YuNet + FER+ · Krumhansl + Thayer.<br />
          No face images stored.
        </p>
      </div>
    </div>
    <div class="container footer-bottom">
      <span class="mono">© {{ year }} MOODWAVE</span>
      <span class="mono">MADE FOR QUIET MOMENTS</span>
    </div>
  </footer>
</template>

<style scoped>
.site-footer {
  margin-top: 40px;
  border-top: 1px solid var(--line);
  padding: 56px 0 26px;
  background:
    radial-gradient(ellipse at 12% 100%, rgba(91, 91, 214, 0.05), transparent 45%),
    color-mix(in srgb, var(--surface-2) 38%, transparent);
}
.footer-grid {
  display: grid;
  grid-template-columns: 1.8fr 1fr 1fr 1.2fr;
  gap: 38px;
}
.footer-brand {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 360px;
}
.wordmark {
  font-family: var(--font-display);
  font-size: 26px;
  letter-spacing: -0.05em;
  font-weight: 580;
}
.wordmark span {
  font-size: 10px;
  vertical-align: top;
  margin-left: 2px;
  color: var(--accent);
}
.footer-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.footer-col .eyebrow {
  margin-bottom: 4px;
}
.footer-col a {
  color: var(--muted);
  font-size: 13.5px;
}
.footer-col a:hover {
  color: var(--ink);
}
.footer-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--success);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
}
.footer-bottom {
  margin-top: 48px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  color: var(--muted-2);
  font-size: 9px;
  letter-spacing: 0.1em;
}
@media (max-width: 900px) {
  .footer-grid {
    grid-template-columns: 1fr 1fr;
    gap: 30px;
  }
  .footer-brand {
    grid-column: 1 / -1;
  }
}
@media (max-width: 560px) {
  .site-footer {
    padding-top: 36px;
    padding-bottom: 90px;
  }
  .footer-grid {
    grid-template-columns: 1fr;
  }
  .footer-note {
    display: none;
  }
  .footer-bottom {
    margin-top: 24px;
    font-size: 8px;
  }
}
</style>
