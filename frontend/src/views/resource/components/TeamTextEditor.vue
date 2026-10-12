<template>
  <DraggableFormDialog ref="dialogRef" v-model="visible" :title="title" width="min(800px, calc(100vw - 32px))" top="5vh" class="team-form-dialog" append-to-body destroy-on-close :before-close="beforeClose">
    <AppForm ref="formRef" :model="form" label-position="top">
      <el-form-item :label="title" prop="text"><el-input v-model="form.text" type="textarea" :rows="14" maxlength="5000" show-word-limit /></el-form-item>
    </AppForm>
    <template #footer><el-button @click="dialogRef.handleClose()">取消</el-button><el-button type="primary" @click="confirm">确定</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
const emit = defineEmits(['confirmed'])
const visible = ref(false), title = ref(''), field = ref(''), dialogRef = ref(null), formRef = ref(null)
const form = reactive({ text: '' })
let original = ''
function open(key, label, value) { field.value = key; title.value = label; original = value || ''; form.text = original; visible.value = true }
async function beforeClose(done) {
  if (form.text !== original) {
    try { await ElMessageBox.confirm('文本修改尚未回填，确定放弃吗？', '放弃修改', { type: 'warning' }) } catch { return }
  }
  done()
}
function confirm() { emit('confirmed', field.value, form.text); visible.value = false }
defineExpose({ open })
</script>
