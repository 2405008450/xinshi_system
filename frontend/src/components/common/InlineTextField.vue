<template>
  <div class="inline-text-field" :class="{ 'is-editing': editing }">
    <template v-if="editing">
      <el-input
        ref="inputRef"
        v-model="draft"
        :type="multiline ? 'textarea' : 'text'"
        :maxlength="maxlength || undefined"
        :show-word-limit="Boolean(maxlength)"
        :autosize="multiline ? { minRows: 2, maxRows: 8 } : undefined"
        :placeholder="placeholder"
        :disabled="saving"
        :aria-label="`编辑${label}`"
        @keydown="handleKeydown"
      />
      <div class="inline-text-field__actions">
        <el-button
          type="primary"
          link
          :loading="saving"
          :aria-label="`保存${label}`"
          @click="save"
        >
          <el-icon v-if="!saving"><Check /></el-icon>
        </el-button>
        <el-button
          link
          :disabled="saving"
          :aria-label="`取消修改${label}`"
          @click="cancel"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <span class="inline-text-field__hint">
        {{ multiline ? 'Ctrl+Enter 保存，Esc 取消' : 'Enter 保存，Esc 取消' }}
      </span>
    </template>
    <button
      v-else-if="editable"
      type="button"
      class="inline-text-field__trigger"
      :disabled="triggerDisabled"
      :aria-label="`编辑${label}`"
      @click="beginEdit"
    >
      <span class="inline-text-field__value">{{ displayText }}</span>
      <el-icon class="inline-text-field__edit-icon"><Edit /></el-icon>
    </button>
    <span v-else class="inline-text-field__value">{{ displayText }}</span>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Check, Close, Edit } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { activeInlineTextEditorId } from '@/composables/useInlineTextEditGroup'

const props = defineProps({
  modelValue: { type: [String, Number], default: null },
  displayValue: { type: [String, Number], default: null },
  editable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '字段' },
  multiline: { type: Boolean, default: false },
  maxlength: { type: Number, default: 0 },
  required: { type: Boolean, default: false },
  emptyAsNull: { type: Boolean, default: true },
  placeholder: { type: String, default: '' },
  saveField: { type: Function, default: null }
})

const emit = defineEmits(['editing-change', 'saved', 'conflict'])
const editorId = `inline-text-${Math.random().toString(36).slice(2)}`
const editing = ref(false)
const saving = ref(false)
const draft = ref('')
const inputRef = ref()

const displayText = computed(() => {
  const value = props.displayValue ?? props.modelValue
  return value === null || value === undefined || value === '' ? '-' : String(value)
})
const triggerDisabled = computed(() => (
  props.disabled
  || Boolean(activeInlineTextEditorId.value && activeInlineTextEditorId.value !== editorId)
))

const releaseEditor = () => {
  if (activeInlineTextEditorId.value === editorId) activeInlineTextEditorId.value = ''
}

const cancel = () => {
  if (!editing.value || saving.value) return
  draft.value = props.modelValue == null ? '' : String(props.modelValue)
  editing.value = false
  releaseEditor()
  emit('editing-change', false)
}

const closeOtherEditor = (event) => {
  if (event.detail === 'popover-hidden') cancel()
}

const beginEdit = async () => {
  if (!props.editable || triggerDisabled.value) return
  activeInlineTextEditorId.value = editorId
  draft.value = props.modelValue == null ? '' : String(props.modelValue)
  editing.value = true
  emit('editing-change', true)
  await nextTick()
  inputRef.value?.focus()
}

const errorMessage = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return error?.detail || error?.message || '保存失败，请稍后重试'
}

const save = async () => {
  if (saving.value || !props.saveField) return
  const normalized = draft.value.trim()
  if (props.required && !normalized) {
    ElMessage.warning(`${props.label}不能为空`)
    return
  }
  const original = props.modelValue == null ? '' : String(props.modelValue).trim()
  if (normalized === original) {
    cancel()
    return
  }
  saving.value = true
  try {
    const value = normalized || (props.emptyAsNull ? null : '')
    const updated = await props.saveField(value)
    editing.value = false
    releaseEditor()
    emit('editing-change', false)
    emit('saved', updated)
    ElMessage.success(`${props.label}已保存`)
  } catch (error) {
    if ((error?.response?.status || error?.status) === 409) {
      editing.value = false
      releaseEditor()
      emit('editing-change', false)
      emit('conflict', error)
      ElMessage.warning('记录已被其他人修改，已刷新详情，请重新编辑')
    } else {
      ElMessage.error(errorMessage(error))
    }
  } finally {
    saving.value = false
  }
}

const handleKeydown = (event) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation?.()
    cancel()
    return
  }
  if (event.key === 'Enter' && (!props.multiline || event.ctrlKey)) {
    event.preventDefault()
    save()
  }
}

watch(() => props.modelValue, (value) => {
  if (!editing.value) draft.value = value == null ? '' : String(value)
})

onMounted(() => window.addEventListener('business-inline-text-edit', closeOtherEditor))
onBeforeUnmount(() => {
  releaseEditor()
  window.removeEventListener('business-inline-text-edit', closeOtherEditor)
})
</script>

<style scoped>
.inline-text-field { min-width: 0; width: 100%; }
.inline-text-field__trigger {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: 1.6;
  text-align: left;
  cursor: pointer;
}
.inline-text-field__trigger:disabled { cursor: default; }
.inline-text-field__value { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.inline-text-field__edit-icon { flex: none; margin-top: 4px; color: var(--el-color-primary); opacity: .65; }
.inline-text-field__trigger:hover .inline-text-field__edit-icon,
.inline-text-field__trigger:focus-visible .inline-text-field__edit-icon { opacity: 1; }
.inline-text-field__actions { display: flex; justify-content: flex-end; gap: 2px; margin-top: 4px; }
.inline-text-field__actions .el-button + .el-button { margin-left: 0; }
.inline-text-field__hint { display: block; margin-top: 2px; color: var(--el-text-color-secondary); font-size: 12px; text-align: right; }
</style>
