<script setup lang="ts">
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ProductStatusBanner from '@/components/product/ProductStatusBanner.vue'
import type { UiSelectOption } from '@/components/ui/selectTypes'

// 移動章節／合併書籍時選擇目的地。chapter 模式可以選「新書」。
const NEW_BOOK = '__new__'

const props = defineProps<{
  mode: 'chapter' | 'book'
  books: Array<{ id: string; title: string; chapterCount?: number }>
  targetBookId: string
  newBookTitle: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:targetBookId', value: string): void
  (event: 'update:newBookTitle', value: string): void
}>()

const options = computed<UiSelectOption[]>(() => [
  ...(props.mode === 'chapter' ? [{ label: '＋ 移出成為新書', value: NEW_BOOK }] : []),
  ...props.books.map(book => ({
    label: book.chapterCount !== undefined ? `${book.title}（${book.chapterCount} 章）` : book.title,
    value: book.id,
  })),
])

const creatingBook = computed(() => props.targetBookId === NEW_BOOK)
</script>

<template>
  <div class="move-target">
    <UiField
      :label="mode === 'chapter' ? '移到哪一本书' : '并入哪一本书'"
      control-id="moveTargetSelect"
      variant="dialog"
      required
    >
      <UiSelect
        id="moveTargetSelect"
        :model-value="targetBookId"
        :options="options"
        :disabled="loading"
        :placeholder="loading ? '载入书籍中…' : '请选择书籍'"
        @update:model-value="emit('update:targetBookId', String($event))"
      />
    </UiField>
    <UiField
      v-if="creatingBook"
      label="新书名称"
      control-id="moveNewBookTitle"
      variant="dialog"
    >
      <UiInput
        id="moveNewBookTitle"
        :model-value="newBookTitle"
        type="text"
        autocomplete="off"
        placeholder="留空则使用章节名称"
        @update:model-value="emit('update:newBookTitle', String($event))"
      />
    </UiField>
    <ProductStatusBanner tone="neutral" role="note">
      <template v-if="mode === 'chapter' && creatingBook">
        章节连同所有页面、译文与封面会移到新书，新书沿用这本书的术语表与标签。
      </template>
      <template v-else-if="mode === 'chapter'">
        章节连同所有页面、译文与封面会移到所选书籍的最后。
      </template>
      <template v-else>
        这本书的所有章节会按顺序加到所选书籍的最后，术语表与标签会合并（所选书籍原有的译法优先），
        书籍封面会变成第一个章节的封面。之后这本书会被删除，它的笔记、角色工作室与分析资料不会保留。
      </template>
    </ProductStatusBanner>
  </div>
</template>

<style scoped>
.move-target {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 8px;
}
</style>
