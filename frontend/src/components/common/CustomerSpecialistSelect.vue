<template>
  <el-select
    ref="selectRef"
    v-model="draft"
    class="customer-specialist-select"
    filterable
    clearable
    :size="size"
    :loading="loading || saving"
    :disabled="disabled || saving"
    aria-label="现客户经理"
    placeholder="请选择客户专员"
    @change="handleChange"
  >
    <el-option v-if="modelValue && !options.some(item => userName(item) === modelValue)" :label="modelValue" :value="modelValue" disabled />
    <el-option v-for="user in options" :key="user.id" :label="userName(user)" :value="userName(user)" />
    <template v-if="saveField" #footer>
      <div class="customer-specialist-actions">
        <el-button type="primary" size="small" :loading="saving" :disabled="!dirty || disabled" @click="save">确认调整</el-button>
        <el-button size="small" :disabled="saving" @click="cancel">取消</el-button>
      </div>
    </template>
  </el-select>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  loading: Boolean,
  disabled: Boolean,
  size: { type: String, default: 'default' },
  saveField: { type: Function, default: null },
})
const emit = defineEmits(['update:modelValue', 'conflict'])
const selectRef = ref()
const draft = ref(props.modelValue || '')
const saving = ref(false)
const dirty = computed(() => (draft.value || '') !== (props.modelValue || ''))
const userName = user => user.full_name || user.fullName || user.username
watch(() => props.modelValue, value => { draft.value = value || '' })
const cancel = () => { draft.value = props.modelValue || ''; selectRef.value?.blur() }
const handleChange = async () => {
  if (!props.saveField) { emit('update:modelValue', draft.value || ''); return }
  // 单选后继续展示确认按钮，避免误选立即写入。
  await nextTick()
  selectRef.value?.toggleMenu()
}
const save = async () => {
  if (!dirty.value || saving.value || props.disabled) return
  saving.value = true
  try {
    await props.saveField(draft.value || null)
    selectRef.value?.blur()
    ElMessage.success('现客户经理已更新')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '现客户经理更新失败'))
    if (error?.status === 409 || error?.response?.status === 409) emit('conflict')
  } finally { saving.value = false }
}
</script>

<style scoped>
.customer-specialist-select { width: 100%; min-width: 0; }
.customer-specialist-actions { display: flex; justify-content: flex-end; gap: 8px; }
.customer-specialist-actions .el-button + .el-button { margin-left: 0; }
</style>
