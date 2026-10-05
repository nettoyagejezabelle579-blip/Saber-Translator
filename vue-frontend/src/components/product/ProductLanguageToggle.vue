<script setup lang="ts">
import { computed } from 'vue'
import ProductHeaderAction from './ProductHeaderAction.vue'
import { currentUiLanguage, setUiLanguage } from '@/i18n/uiLanguage'

// 介面語言切換：顯示「要切換成」的語言名稱；這個按鈕本身不轉換文字
const language = currentUiLanguage()
const next = computed(() => (language === 'zh-TW' ? 'zh-CN' : 'zh-TW'))
const label = computed(() => (next.value === 'zh-CN' ? '简体' : '繁體'))
const title = computed(() => (
  next.value === 'zh-CN' ? '介面語言：繁體中文（點擊切換為简体中文）' : '界面语言：简体中文（点击切换为繁體中文）'
))
</script>

<template>
  <ProductHeaderAction
    type="button"
    class="product-language-toggle"
    data-no-convert
    :label="label"
    :title="title"
    :aria-label="title"
    @click="setUiLanguage(next)"
  />
</template>

<style scoped>
.product-language-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}
</style>
