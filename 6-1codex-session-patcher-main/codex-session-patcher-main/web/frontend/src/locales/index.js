import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

// 支持的语言
export const SUPPORTED_LOCALES = [
  { code: 'zh-CN', name: '中文', naiveLocale: 'zhCN', naiveDateLocale: 'dateZhCN' },
  { code: 'en-US', name: 'English', naiveLocale: 'enUS', naiveDateLocale: 'dateEnUS' },
]

// 获取存储的语言偏好
function getStoredLocale() {
  return localStorage.getItem('locale')
}

// 保存语言偏好
export function setStoredLocale(locale) {
  localStorage.setItem('locale', locale)
}

// 检测浏览器语言
function detectBrowserLocale() {
  const browserLang = navigator.language || navigator.userLanguage

  // 精确匹配
  if (SUPPORTED_LOCALES.some(l => l.code === browserLang)) {
    return browserLang
  }

  // 语言前缀匹配（如 zh -> zh-CN）
  const prefix = browserLang.split('-')[0]
  const match = SUPPORTED_LOCALES.find(l => l.code.startsWith(prefix))
  if (match) {
    return match.code
  }

  // 默认中文
  return 'zh-CN'
}

// 获取初始语言
function getInitialLocale() {
  // 优先级：存储偏好 > 浏览器检测 > 默认中文
  const stored = getStoredLocale()
  if (stored && SUPPORTED_LOCALES.some(l => l.code === stored)) {
    return stored
  }
  return detectBrowserLocale()
}

// 创建 i18n 实例
const i18n = createI18n({
  legacy: false, // 使用 Composition API
  globalInjection: true, // 全局注入 $t
  locale: getInitialLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export default i18n
