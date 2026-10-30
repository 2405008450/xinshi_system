<template>
  <div class="feedback-cell">
    <template v-if="editable">
      <el-select v-if="type === 'select'" v-model="draft" :aria-label="label" :clearable="clearable" filterable @change="save"><el-option v-for="option in availableOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select>
      <el-date-picker v-else-if="type === 'date'" v-model="draft" type="date" value-format="YYYY-MM-DD" :aria-label="label" clearable @change="save" />
      <ScreenshotInput v-else-if="type === 'attachments'" v-model="draft" type="textarea" :rows="2" :maxlength="30000" :aria-label="label" @blur="save" @change="save" @uploading-change="uploadState" />
      <PlainInput v-else v-model="draft" :type="type === 'text' ? 'text' : 'textarea'" :autosize="{ minRows: 2, maxRows: 6 }" :maxlength="type === 'text' ? 300 : 30000" :aria-label="label" @blur="save" @keyup.ctrl.enter="save" @keyup.esc="reset" />
    </template>
    <ScreenshotText v-else-if="type === 'attachments'" :text="modelValue || '-'" />
    <div v-else class="feedback-cell-readonly">{{ displayValue || '-' }}</div>
    <a v-for="url in links" :key="url" :href="url" target="_blank" rel="noopener noreferrer" class="attachment-link">{{ url }}</a>
    <small v-if="saving">保存中…</small>
    <span v-if="error" class="feedback-cell-error" role="alert">{{ error }} <el-button link type="primary" @click="save">重试</el-button></span>
  </div>
</template>
<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElInput as PlainInput } from 'element-plus'
import ScreenshotInput from '@/components/common/ScreenshotInput.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
const props = defineProps({ modelValue: [String, Number], label: String, type: { type: String, default: 'textarea' }, editable: Boolean, clearable: Boolean, options: { type: Array, default: () => [] }, currentLabel: String, saveValue: { type: Function, required: true } })
const draft = ref(props.modelValue ?? ''), base = ref(props.modelValue ?? ''), saving = ref(false), uploading = ref(false), error = ref('')
const equal = (a, b) => (a ?? '') === (b ?? '')
watch(() => props.modelValue, value => { if (equal(draft.value, base.value) || equal(draft.value, value)) draft.value = value ?? ''; base.value = value ?? '' })
const availableOptions = computed(() => props.modelValue && !props.options.some(option => option.value === props.modelValue) ? [...props.options, { value: props.modelValue, label: props.currentLabel || String(props.modelValue) }] : props.options)
const displayValue = computed(() => props.options.find(option => option.value === props.modelValue)?.label || props.currentLabel || props.modelValue)
const links = computed(() => props.type === 'attachments' ? [...new Set(String(props.modelValue || '').match(/https?:\/\/[^\s<>]+/g) || [])] : [])
function reset() { draft.value = props.modelValue ?? ''; error.value = '' }
function uploadState(value) { uploading.value = value; if (!value) nextTick(save) }
async function save() {
  if (!props.editable || saving.value || uploading.value || equal(draft.value, props.modelValue)) return
  saving.value = true; error.value = ''
  try {
    while (!equal(draft.value, props.modelValue)) {
      const snapshot = draft.value
      await props.saveValue(snapshot)
      await nextTick()
      if (equal(draft.value, snapshot)) draft.value = props.modelValue ?? ''
    }
  } catch (e) { error.value = typeof e.detail === 'string' ? e.detail : e.message || '保存失败，请重试' }
  finally { saving.value = false }
}
</script>
<style scoped>
.feedback-cell{min-width:0}.feedback-cell :deep(.el-select),.feedback-cell :deep(.el-date-editor){width:100%}.feedback-cell-readonly{white-space:pre-wrap;overflow-wrap:anywhere;border-radius:4px;background:#F1F5F9;color:var(--el-text-color-regular);padding:6px 8px;min-height:32px}.feedback-cell-error{display:block;color:var(--el-color-danger);font-size:12px;white-space:normal}.feedback-cell small{color:var(--el-text-color-secondary)}.attachment-link{display:block;overflow-wrap:anywhere}
</style>
