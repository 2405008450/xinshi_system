<template>
  <AppForm ref="formRef" :model="form" :rules="rules" class="chat-inline-name-editor" @submit.prevent="submit">
    <el-form-item prop="name" :error="error">
      <el-input ref="inputRef" v-model="form.name" :aria-label="label" :placeholder="label" :disabled="saving" @blur="submit" @keydown="keydown" @compositionstart="composing = true" @compositionend="composing = false" />
    </el-form-item>
    <small>Enter 保存 · Esc 取消</small>
  </AppForm>
</template>
<script setup>
import { getCurrentInstance, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { activeChatNameEditor } from '@/composables/useChatNameEditing'
const props = defineProps({ initialName: { type: String, default: '' }, label: { type: String, default: '名称' }, saving: Boolean, error: { type: String, default: '' } })
const emit = defineEmits(['save', 'cancel'])
const owner = getCurrentInstance().uid
const form = reactive({ name: props.initialName }), formRef = ref(), inputRef = ref()
const rules = { name: [{ validator: (_rule, value, done) => {
  const name = value.trim()
  done(!name ? new Error('请填写名称') : name.length > 80 ? new Error('名称不能超过80个字符') : undefined)
}, trigger: 'submit' }] }
let composing = false, validating = false, cancelled = false
function focus() { nextTick(() => { inputRef.value?.focus(); inputRef.value?.select() }) }
async function submit() {
  if (cancelled || composing || props.saving || validating) return
  validating = true
  try { const valid = await formRef.value.validate().catch(() => false); if (valid && !cancelled && !props.saving) emit('save', form.name.trim()) }
  finally { validating = false }
}
function keydown(event) {
  if (composing || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); submit() }
  if (event.key === 'Escape' && !props.saving) { event.preventDefault(); event.stopPropagation(); cancelled = true; emit('cancel') }
}
watch(() => [props.error, props.saving], ([error, saving]) => { if (error && !saving) focus() })
onMounted(() => { activeChatNameEditor.value = owner; focus() })
onBeforeUnmount(() => { cancelled = true; if (activeChatNameEditor.value === owner) activeChatNameEditor.value = null })
</script>
<style scoped>
.chat-inline-name-editor{flex:1;min-width:0;width:100%}.chat-inline-name-editor :deep(.el-form-item){margin-bottom:20px}.chat-inline-name-editor small{display:block;color:#64748b;font-size:11px;margin-top:-14px;margin-bottom:8px}.chat-inline-name-editor :deep(.el-input__wrapper){background:#fff}
</style>
