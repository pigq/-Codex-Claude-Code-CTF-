<template>
  <n-dropdown
    :options="localeOptions"
    @select="handleSelect"
  >
    <n-button quaternary size="small">
      <template #icon>
        <n-icon><LanguageOutline /></n-icon>
      </template>
      {{ localeStore.localeInfo.name }}
    </n-button>
  </n-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { NDropdown, NButton, NIcon } from 'naive-ui'
import { LanguageOutline } from '@vicons/ionicons5'
import { useLocaleStore } from '../stores/localeStore'

const localeStore = useLocaleStore()

const localeOptions = computed(() => {
  return localeStore.supportedLocales.map(locale => ({
    label: locale.name,
    key: locale.code,
  }))
})

function handleSelect(key) {
  localeStore.setLocale(key)
}
</script>
