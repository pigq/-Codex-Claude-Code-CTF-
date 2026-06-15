<template>
  <div class="cooperation-panel">
    <n-space vertical size="large">
      <n-card :title="$t('cooperation.adsTitle')" size="small">
        <n-space vertical size="small">
          <n-text>{{ $t('cooperation.adsDesc') }}</n-text>
          <n-space>
            <n-tag v-for="item in $tm('cooperation.adsTags')" :key="item" type="info" :bordered="false">
              {{ item }}
            </n-tag>
          </n-space>
        </n-space>
      </n-card>

      <n-card :title="$t('cooperation.devTitle')" size="small">
        <n-space vertical size="small">
          <n-text>{{ $t('cooperation.devDesc') }}</n-text>
          <n-ul>
            <n-li v-for="item in $tm('cooperation.devItems')" :key="item">{{ item }}</n-li>
          </n-ul>
        </n-space>
      </n-card>

      <n-card :title="$t('cooperation.tokenTitle')" size="small">
        <n-text>{{ $t('cooperation.tokenDesc') }}</n-text>
      </n-card>

      <n-card :title="$t('cooperation.intentTitle')" size="small">
        <n-form class="intent-form" label-placement="top">
          <n-form-item :label="$t('cooperation.intentType')">
            <n-select v-model:value="intentForm.intent_type" :options="intentTypeOptions" />
          </n-form-item>
          <n-form-item :label="$t('cooperation.name')">
            <n-input v-model:value="intentForm.name" :maxlength="80" show-count :placeholder="$t('cooperation.namePlaceholder')" />
          </n-form-item>
          <n-form-item :label="$t('cooperation.contact')">
            <n-input v-model:value="intentForm.contact" :maxlength="120" show-count :placeholder="$t('cooperation.contactPlaceholder')" />
          </n-form-item>
          <n-form-item :label="$t('cooperation.message')">
            <n-input v-model:value="intentForm.message" type="textarea" :rows="4" :maxlength="1000" show-count :placeholder="$t('cooperation.messagePlaceholder')" />
          </n-form-item>
          <n-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitIntent">
            {{ $t('cooperation.submit') }}
          </n-button>
          <p v-if="noticeText" class="submit-notice">
            {{ noticeText }}
          </p>
        </n-form>
      </n-card>

      <n-card :title="$t('cooperation.contactTitle')" size="small">
        <div class="contact-icons">
          <a class="contact-icon" href="mqqwpa://im/chat?chat_type=wpa&uin=89045349&version=1&src_type=web&web_src=codex-session-patcher" aria-label="QQ">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21.395 15.035a40 40 0 0 0-.803-2.264l-1.079-2.695c.001-.032.014-.562.014-.836C19.526 4.632 17.351 0 12 0S4.474 4.632 4.474 9.241c0 .274.013.804.014.836l-1.08 2.695a39 39 0 0 0-.802 2.264c-1.021 3.283-.69 4.643-.438 4.673.54.065 2.103-2.472 2.103-2.472 0 1.469.756 3.387 2.394 4.771-.612.188-1.363.479-1.845.835-.434.32-.379.646-.301.778.343.578 5.883.369 7.482.189 1.6.18 7.14.389 7.483-.189.078-.132.132-.458-.301-.778-.483-.356-1.233-.646-1.846-.836 1.637-1.384 2.393-3.302 2.393-4.771 0 0 1.563 2.537 2.103 2.472.251-.03.581-1.39-.438-4.673" />
            </svg>
          </a>
          <button class="contact-icon" type="button" aria-label="WeChat" @click="copyWechat">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8.69 3.2C4.3 3.2.8 6.2.8 9.88c0 2 1.04 3.78 2.68 5.02l-.42 1.5c-.08.28.2.52.46.37l1.86-1.08c.94.31 1.97.48 3.05.48h.4a6.3 6.3 0 0 1-.08-1.02c0-3.45 3.2-6.24 7.15-6.24.25 0 .5.01.74.04-.5-3.24-3.85-5.75-7.95-5.75Zm-2.5 3.35c.6 0 1.08.48 1.08 1.08S6.8 8.7 6.2 8.7s-1.08-.48-1.08-1.08.48-1.08 1.08-1.08Zm5 0c.6 0 1.08.48 1.08 1.08s-.48 1.08-1.08 1.08-1.08-.48-1.08-1.08.48-1.08 1.08-1.08Zm4.74 3.42c-3.32 0-6.02 2.25-6.02 5.03s2.7 5.03 6.02 5.03c.79 0 1.55-.13 2.25-.36l1.42.82c.22.13.45-.08.39-.31l-.32-1.15c1.37-1.02 2.23-2.45 2.23-4.03 0-2.78-2.69-5.03-5.97-5.03Zm-2.02 2.52c.5 0 .9.4.9.9s-.4.89-.9.89-.9-.4-.9-.9.4-.9.9-.9Zm4.05 0c.5 0 .9.4.9.9s-.4.89-.9.89-.9-.4-.9-.9.4-.9.9-.9Z" />
            </svg>
          </button>
          <a class="contact-icon" href="https://t.me/+mchui8mtzoM0MDlh" target="_blank" rel="noreferrer" aria-label="Telegram">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21.6 4.28c.28-1.18-.86-1.56-1.67-1.22L2.92 10.18c-1.16.48-1.14 1.14-.2 1.43l4.36 1.36 10.1-6.37c.48-.29.92-.13.56.2l-8.18 7.38-.31 4.65c.46 0 .66-.21.92-.46l2.2-2.14 4.58 3.39c.85.47 1.46.23 1.67-.78L21.6 4.28Z" />
            </svg>
          </a>
        </div>
        <p v-if="contactStatus" class="contact-status">{{ contactStatus }}</p>
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../services/api'

const { t } = useI18n()

const intentForm = ref({
  intent_type: 'ads',
  name: '',
  contact: '',
  message: '',
})
const submitting = ref(false)
const noticeText = ref('')
const contactStatus = ref('')

const intentTypeOptions = computed(() => [
  { label: t('cooperation.intentTypeAds'), value: 'ads' },
  { label: t('cooperation.intentTypeDevelopment'), value: 'development' },
  { label: t('cooperation.intentTypeToken'), value: 'token_supply' },
  { label: t('cooperation.intentTypeOther'), value: 'other' },
])

const canSubmit = computed(() => {
  return intentForm.value.name.trim()
    && intentForm.value.contact.trim()
    && intentForm.value.message.trim().length >= 5
})

async function copyWechat() {
  try {
    await navigator.clipboard.writeText('zyf_code')
    contactStatus.value = t('cooperation.wechatCopied')
    window.setTimeout(() => {
      contactStatus.value = ''
    }, 1600)
  } catch {
    contactStatus.value = ''
  }
}

async function submitIntent() {
  if (!canSubmit.value || submitting.value) return

  submitting.value = true
  noticeText.value = ''
  try {
    const response = await api.post('/cooperation/intent', {
      ...intentForm.value,
      source: 'web',
    })
    noticeText.value = response.message || t('cooperation.submitDone')
    intentForm.value = { intent_type: 'ads', name: '', contact: '', message: '' }
  } catch (caught) {
    noticeText.value = caught.message || t('cooperation.submitFallback')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.cooperation-panel {
  max-width: 800px;
  margin: 0 auto;
}

.n-card {
  background: var(--color-bg-1);
}

.contact-icons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.contact-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-2);
  color: var(--color-text-1);
  cursor: pointer;
  padding: 0;
  text-decoration: none;
  transition: border-color var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.contact-icon:hover {
  color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  background: var(--color-primary-soft);
}

.contact-icon svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.submit-notice {
  margin-top: 12px;
}

.contact-status,
.submit-notice {
  color: var(--color-text-3);
  font-size: 13px;
}

.intent-form :deep(.n-form-item:last-of-type) {
  margin-bottom: 8px;
}

:deep(.n-ul) {
  margin: 8px 0 0;
  padding-left: 20px;
}

@media (max-width: 768px) {
  .contact-icons {
    justify-content: center;
  }
}
</style>
