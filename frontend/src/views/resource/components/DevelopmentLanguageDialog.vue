<template>
  <DraggableFormDialog v-model="visible" title="增加语言/方言" width="min(600px, calc(100vw - 32px))" class="development-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose">
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="save">
      <el-form-item label="名称" prop="label"><el-input v-model="form.label" maxlength="100" :disabled="saving" placeholder="请输入语言或方言名称" /></el-form-item>
      <el-form-item label="类型" prop="language_type"><el-select v-model="form.language_type" :disabled="saving"><el-option label="语种" value="language" /><el-option label="方言" value="dialect" /></el-select></el-form-item>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'

const emit = defineEmits(['created'])
const visible = ref(false), saving = ref(false), formRef = ref(null)
const form = reactive({ label: '', language_type: 'language' })
const rules = {
  label: [{ required: true, whitespace: true, message: '请填写名称', trigger: 'blur' }],
  language_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}
async function open() {
  if (saving.value) return
  Object.assign(form, { label: '', language_type: 'language' })
  visible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}
function beforeClose(done) { if (!saving.value) done() }
async function save() {
  if (saving.value) return
  saving.value = true
  try {
    if (!await formRef.value.validate().catch(() => false)) return
    const language = await api.addLanguage({ label: form.label.trim(), language_type: form.language_type })
    visible.value = false
    emit('created', language)
    ElMessage.success('语言/方言已保存')
  } catch (error) {
    await formRef.value?.applyServerErrors(error)
    ElMessage.error(error.message || '新增语言/方言失败')
  } finally { saving.value = false }
}
defineExpose({ open })
</script>
