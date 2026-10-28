<template>
  <AppForm ref="formRef" :model="form" :rules="rules" class="chat-inline-name-editor" @submit.prevent="submit">
    <el-form-item prop="name" :error="error">
      <el-input ref="inputRef" v-model="form.name" :aria-label="label" :placeholder="label" :disabled="saving" @keydown="keydown" @compositionstart="composing = true" @compositionend="composing = false">
        <template #suffix>
          <el-button native-type="button" class="chat-inline-name-editor__close" link :disabled="saving" aria-label="取消名称编辑" title="取消编辑（Esc）" @mousedown.prevent @click.stop="cancel"><el-icon><Close /></el-icon></el-button>
        </template>
      </el-input>
    </el-form-item>
    <div class="chat-inline-name-editor__actions">
      <small>Enter 保存 · Esc 取消</small>
      <el-button native-type="button" size="small" :disabled="saving" @click="cancel">取消</el-button>
      <el-button native-type="button" size="small" type="primary" :loading="saving" @click="submit">保存</el-button>
    </div>
  </AppForm>
</template>
<script setup>
import { getCurrentInstance, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Close } from '@element-plus/icons-vue'
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
function focus() { nextTick(() => { inputRef.value?.focus({ preventScroll: true }); inputRef.value?.select() }) }
function cancel() {
  if (props.saving) return
  cancelled = true
  emit('cancel')
}
async function submit() {
  if (cancelled || composing || props.saving || validating) return
  validating = true
  try { const valid = await formRef.value.validate().catch(() => false); if (valid && !cancelled && !props.saving) emit('save', form.name.trim()) }
  finally { validating = false }
}
function keydown(event) {
  if (composing || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); submit() }
  if (event.key === 'Escape' && !props.saving) { event.preventDefault(); event.stopPropagation(); cancel() }
}
watch(() => [props.error, props.saving], ([error, saving]) => { if (error && !saving) focus() })
onMounted(() => { activeChatNameEditor.value = owner; focus() })
onBeforeUnmount(() => { cancelled = true; if (activeChatNameEditor.value === owner) activeChatNameEditor.value = null })
</script>
<style scoped>
.chat-inline-name-editor{flex:1;min-width:0;width:100%}.chat-inline-name-editor :deep(.el-form-item){margin-bottom:20px}.chat-inline-name-editor__actions{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:6px;margin-bottom:8px}.chat-inline-name-editor small{flex:1;color:#64748b;font-size:11px;white-space:nowrap}.chat-inline-name-editor__actions .el-button{margin:0}.chat-inline-name-editor :deep(.el-input__wrapper){background:#fff}
</style>
