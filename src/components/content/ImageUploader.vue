<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { uploadImage, validateImage } from '@/utils/image'
import { uploadApi } from '@/services/api'
import { normalizeError } from '@/services/http'

const props = defineProps({
  modelValue: { type: [Object, Array], default: null },
  multiple: Boolean,
  max: { type: Number, default: 3 },
  bizType: { type: String, default: 'screenshot' },
  aspect: { type: String, default: '16 / 10' },
  hint: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const input = ref(null)
const uploading = ref(false)
const error = ref('')
const drag = ref(false)

const items = computed(() => {
  if (!props.modelValue) return []
  return Array.isArray(props.modelValue) ? props.modelValue : [props.modelValue]
})

const previews = computed(() =>
  items.value.map((item) => ({
    ...item,
    preview: item.thumbUrl || item.detailUrl || item.url,
  })),
)

function choose() {
  if (uploading.value) return
  input.value?.click()
}

async function handleFiles(files) {
  const list = Array.from(files || [])
  if (!list.length) return
  const remaining = props.multiple ? props.max - items.value.length : 1
  if (remaining <= 0) {
    error.value = t('extra.maxImages', { max: props.max })
    return
  }
  error.value = ''
  uploading.value = true
  const uploaded = []
  try {
    for (const file of list.slice(0, remaining)) {
      const message = validateImage(file)
      if (message) {
        error.value = message
        continue
      }
      const attachment = await uploadImage(file, props.bizType)
      uploaded.push(attachment)
    }
    if (uploaded.length) {
      if (props.multiple) {
        emit('update:modelValue', [...items.value, ...uploaded])
      } else {
        emit('update:modelValue', uploaded[0])
      }
    }
  } catch (err) {
    error.value = normalizeError(err).message
    ElMessage.error(error.value)
  } finally {
    uploading.value = false
  }
}

function onChange(event) {
  handleFiles(event.target.files)
  event.target.value = ''
}

function onDrop(event) {
  drag.value = false
  handleFiles(event.dataTransfer?.files)
}

async function remove(index) {
  const target = items.value[index]
  try {
    if (target?.id) await uploadApi.remove(target.id)
  } catch {
    // 删除远端失败时不影响前端移除选择，管理员可后续清理孤儿附件
  }
  const next = items.value.filter((_, i) => i !== index)
  emit('update:modelValue', props.multiple ? next : null)
}

function move(index, direction) {
  const next = [...items.value]
  const to = index + direction
  if (to < 0 || to >= next.length) return
  ;[next[index], next[to]] = [next[to], next[index]]
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="image-uploader" :class="{ drag }">
    <div v-if="previews.length" class="preview-grid" :class="{ multiple }">
      <div v-for="(item, index) in previews" :key="item.id || item.url" class="preview-card">
        <img :src="item.preview" :alt="t('extra.uploadedImage', { index: index + 1 })" width="800" height="500" />
        <div class="preview-actions">
          <button v-if="multiple && index > 0" type="button" :aria-label="t('extra.prev')" @click="move(index, -1)"><el-icon><Back /></el-icon></button>
          <button v-if="multiple && index < previews.length - 1" type="button" :aria-label="t('extra.next')" @click="move(index, 1)"><el-icon><Right /></el-icon></button>
          <button type="button" class="danger" :aria-label="t('extra.remove')" @click="remove(index)"><el-icon><Delete /></el-icon></button>
        </div>
        <span class="preview-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
      </div>
      <button
        v-if="multiple ? previews.length < max : !previews.length"
        class="add-card"
        type="button"
        :disabled="uploading"
        @click="choose"
      >
        <el-icon :size="22"><Plus /></el-icon>
        <span>{{ uploading ? t('common.processing') : t('extra.add') }}</span>
      </button>
    </div>
    <button
      v-else
      type="button"
      class="drop-zone"
      :style="{ aspectRatio: aspect }"
      :disabled="uploading"
      @click="choose"
      @dragover.prevent="drag = true"
      @dragleave.prevent="drag = false"
      @drop.prevent="onDrop"
    >
      <span class="drop-icon"><el-icon :size="24"><PictureFilled /></el-icon></span>
      <strong>{{ uploading ? t('common.processing') : t('common.preview') }}</strong>
      <span class="small muted">{{ hint || 'JPG / PNG / WebP · 5MB' }}</span>
    </button>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" :multiple="multiple" hidden @change="onChange" />
    <p v-if="error" class="error-text">{{ error }}</p>
  </div>
</template>

<style scoped>
.image-uploader {
  width: 100%;
}
.drop-zone {
  width: 100%;
  min-height: 170px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--ink-2);
  transition: all 170ms var(--ease);
  padding: 20px;
}
.drop-zone:hover,
.image-uploader.drag .drop-zone {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.drop-icon {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--accent);
  margin-bottom: 3px;
}
.drop-zone strong {
  font-size: 13px;
}
.preview-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: minmax(0, 1fr);
}
.preview-grid.multiple {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.preview-card {
  position: relative;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 1px solid var(--line);
  aspect-ratio: 16 / 10;
  background: var(--surface-2);
}
.preview-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.preview-actions {
  position: absolute;
  top: 5px;
  right: 5px;
  display: flex;
  gap: 3px;
  opacity: 0;
  transition: opacity 150ms;
}
.preview-card:hover .preview-actions {
  opacity: 1;
}
.preview-actions button {
  width: 27px;
  height: 27px;
  border: 0;
  border-radius: 4px;
  background: rgba(20, 20, 26, 0.62);
  color: #fff;
  display: grid;
  place-items: center;
  backdrop-filter: blur(6px);
}
.preview-actions button.danger {
  background: rgba(200, 70, 49, 0.8);
}
.preview-index {
  position: absolute;
  left: 6px;
  bottom: 5px;
  font-size: 7px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(20, 20, 26, 0.5);
  padding: 2px 4px;
  border-radius: 3px;
}
.add-card {
  aspect-ratio: 16 / 10;
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--muted);
  font-size: 10px;
}
.add-card:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.error-text {
  margin-top: 6px;
  color: var(--danger);
  font-size: 12px;
}
@media (max-width: 560px) {
  .preview-grid.multiple {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
