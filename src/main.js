import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import '@fontsource-variable/manrope'
import '@fontsource-variable/space-grotesk'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './styles/tokens.css'
import './styles/base.css'
import './styles/element.css'
import { installErrorReporting } from './utils/errorReporter'
import { useAuthStore } from './stores/auth'
import { trackPageview } from './utils/track'

const app = createApp(App)
const pinia = createPinia()

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(i18n)
app.use(ElementPlus, {
  locale: localStorage.getItem('mw.locale') === 'en-US' ? en : zhCn,
  size: 'large',
})

installErrorReporting(app)

router.afterEach((to) => {
  trackPageview(to.fullPath)
  const auth = useAuthStore()
  if (auth.initialized) {
    // 页面标题跟随路由
    const base = i18n.global.t('meta.title')
    document.title = to.meta.titleKey ? `${i18n.global.t(to.meta.titleKey)} · Moodwave` : base
  }
})

app.mount('#app')
