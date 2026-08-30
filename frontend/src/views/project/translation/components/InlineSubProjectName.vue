<template>
  <div class="inline-sub-project-name">
    <template v-if="editing">
      <el-input
        ref="inputRef"
        v-model="draft"
        size="small"
        maxlength="255"
        show-word-limit
        :disabled="saving"
        @click.stop
        @keyup.enter.stop="save()"
        @keyup.esc.stop="cancel"
      />
      <el-button type="primary" link :icon="Check" :loading="saving" aria-label="保存子项目名称" @click.stop="save()" />
      <el-button link :icon="Close" :disabled="saving" aria-label="取消修改子项目名称" @click.stop="cancel" />
    </template>
    <button
      v-else-if="editable"
      type="button"
      class="inline-sub-project-name__trigger"
      :title="`${displayName}（点击修改）`"
      @click.stop="beginEdit"
    >
      <span>{{ displayName }}</span>
      <el-icon><EditPen /></el-icon>
    </button>
    <span v-else class="inline-sub-project-name__readonly" :title="displayName">{{ displayName }}</span>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Check, Close, EditPen } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { updateSubOrder } from '@/api/subOrders'

const props = defineProps({
  subOrderId: { type: String, required: true },
  modelValue: { type: String, default: '' },
  editable: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'pending-change'])
const editing = ref(false)
const saving = ref(false)
const draft = ref(props.modelValue || '')
const inputRef = ref(null)
const displayName = computed(() => props.modelValue || '-')

watch(() => props.modelValue, (value) => {
  if (editing.value && String(value || '').trim() === draft.value.trim()) editing.value = false
  if (!editing.value) draft.value = value || ''
})

watch([draft, editing], () => {
  const name = draft.value.trim()
  emit('pending-change', {
    id: props.subOrderId,
    name,
    pending: editing.value && name !== String(props.modelValue || '').trim(),
    valid: Boolean(name) && name.length <= 255,
  })
})

const beginEdit = async () => {
  draft.value = props.modelValue || ''
  editing.value = true
  await nextTick()
  inputRef.value?.focus?.()
  inputRef.value?.select?.()
}

const cancel = () => {
  draft.value = props.modelValue || ''
  editing.value = false
}

const save = async () => {
  const name = draft.value.trim()
  if (!name) return ElMessage.warning('子项目名称不能为空')
  if (name.length > 255) return ElMessage.warning('子项目名称不能超过 255 个字符')
  if (name === (props.modelValue || '').trim()) return cancel()
  saving.value = true
  try {
    const updated = await updateSubOrder(props.subOrderId, { subProjectName: name })
    emit('saved', updated)
    editing.value = false
    ElMessage.success('子项目名称已更新')
  } catch (error) {
    ElMessage.error(error.detail || error.message || '子项目名称更新失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.inline-sub-project-name { display: flex; align-items: center; gap: 4px; min-width: 0; }
.inline-sub-project-name :deep(.el-input) { min-width: 180px; }
.inline-sub-project-name__trigger {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-width: 0;
  gap: 5px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.inline-sub-project-name__trigger span,
.inline-sub-project-name__readonly { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.inline-sub-project-name__trigger .el-icon { flex: none; opacity: 0; transition: opacity 0.15s ease; }
.inline-sub-project-name__trigger:hover .el-icon,
.inline-sub-project-name__trigger:focus-visible .el-icon { opacity: 1; }
</style>
