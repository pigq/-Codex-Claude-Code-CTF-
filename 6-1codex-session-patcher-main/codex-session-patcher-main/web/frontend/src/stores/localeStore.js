import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setStoredLocale, SUPPORTED_LOCALES } from '../locales'

export const useLocaleStore = defineStore('locale', () => {
  const i18n = useI18n()

  const currentLocale = ref(i18n.locale.value)

  const localeInfo = computed(() => {
    return SUPPORTED_LOCALES.find(l => l.code === currentLocale.value) || SUPPORTED_LOCALES[0]
  })

  function setLocale(locale) {
    if (SUPPORTED_LOCALES.some(l => l.code === locale)) {
      currentLocale.value = locale
      i18n.locale.value = locale
      setStoredLocale(locale)
    }
  }

  return {
    currentLocale,
    localeInfo,
    setLocale,
    supportedLocales: SUPPORTED_LOCALES,
  }
})
