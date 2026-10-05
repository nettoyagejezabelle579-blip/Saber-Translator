<script setup lang="ts">
import { ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFileInput from '@/components/ui/UiFileInput.vue'
import type { ChapterData } from '@/types/api'

// 章節以「單行本」封面卡片呈現：自訂封面，沒有就顯示第一頁。
defineProps<{
  chapters: ChapterData[]
  translationAllowed?: boolean
  busyChapterId?: string | null
}>()

const emit = defineEmits<{
  (event: 'read', chapterId: string): void
  (event: 'translate', chapterId: string): void
  (event: 'setCover', chapterId: string, file: File): void
  (event: 'clearCover', chapterId: string): void
  (event: 'move', chapterId: string): void
}>()

const fileInput = ref<InstanceType<typeof UiFileInput> | null>(null)
const pickingFor = ref<string | null>(null)
const failedCovers = ref(new Set<string>())

function pickCover(chapterId: string): void {
  pickingFor.value = chapterId
  fileInput.value?.click()
}

function onFileChosen(files: File[]): void {
  const file = files[0]
  const chapterId = pickingFor.value
  fileInput.value?.clear()
  pickingFor.value = null
  if (file && chapterId) {
    failedCovers.value.delete(chapterId)
    emit('setCover', chapterId, file)
  }
}

function onCoverError(chapterId: string): void {
  failedCovers.value = new Set([...failedCovers.value, chapterId])
}
</script>

<template>
  <div class="chapter-cover-grid" role="list" aria-label="章节封面">
    <UiFileInput
      ref="fileInput"
      hidden
      accept="image/*"
      @files-change="onFileChosen"
    />
    <article
      v-for="chapter in chapters"
      :key="chapter.id"
      class="chapter-cover"
      role="listitem"
      :data-chapter-id="chapter.id"
    >
      <UiButton
        variant="card-action"
        class="chapter-cover__image"
        :title="`阅读：${chapter.title}`"
        :disabled="!(chapter.imageCount ?? 0)"
        @click="emit('read', chapter.id)"
      >
        <img
          v-if="chapter.coverUrl && !failedCovers.has(chapter.id)"
          :src="chapter.coverUrl"
          :alt="chapter.title"
          loading="lazy"
          @error="onCoverError(chapter.id)"
        >
        <span v-else class="chapter-cover__placeholder" data-no-convert>{{ chapter.title.slice(0, 6) }}</span>
      </UiButton>
      <strong class="chapter-cover__title" :title="chapter.title" data-no-convert>{{ chapter.title }}</strong>
      <small class="chapter-cover__meta">{{ chapter.imageCount ?? 0 }} 页</small>
      <div class="chapter-cover__actions">
        <UiButton
          size="xs"
          variant="ghost"
          :loading="busyChapterId === chapter.id"
          @click="pickCover(chapter.id)"
        >
          换封面
        </UiButton>
        <UiButton
          v-if="chapter.hasCustomCover"
          size="xs"
          variant="ghost"
          :disabled="busyChapterId === chapter.id"
          @click="emit('clearCover', chapter.id)"
        >
          用第一页
        </UiButton>
        <UiButton
          v-if="translationAllowed"
          size="xs"
          variant="ghost"
          @click="emit('translate', chapter.id)"
        >
          翻译
        </UiButton>
        <UiButton size="xs" variant="ghost" @click="emit('move', chapter.id)">
          移动
        </UiButton>
      </div>
    </article>
  </div>
</template>

<style scoped>
.chapter-cover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 14px;
  max-block-size: 420px;
  padding: 4px 4px 4px 0;
  overflow-y: auto;
}

.chapter-cover {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.chapter-cover__image {
  --ui-button-padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 2 / 3;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-default);
  border-radius: 6px;
}

.chapter-cover__image:disabled {
  cursor: default;
}

.chapter-cover__image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chapter-cover__placeholder {
  padding: 8px;
  color: var(--color-text-muted);
  font-size: 13px;
  text-align: center;
}

.chapter-cover__title {
  overflow: hidden;
  color: var(--color-text-default);
  font-size: 13px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.chapter-cover__meta {
  color: var(--color-text-muted);
  font-size: 12px;
}

.chapter-cover__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
</style>
