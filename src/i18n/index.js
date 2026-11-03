import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

const stored = localStorage.getItem('mw.locale')
const browser = navigator.language?.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'

const i18n = createI18n({
  legacy: false,
  locale: stored || browser,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
  missingWarn: false,
  fallbackWarn: false,
})

export default i18n
