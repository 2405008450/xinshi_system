<template>
  <DraggableFormDialog v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="channel-dialog" append-to-body destroy-on-close>
    <template #header><span class="channel-dialog-title" @mousedown.stop>{{ record?.name }} · 平台情况说明</span></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="资料已被其他人修改。当前草稿已保留，请重新读取最新内容后再保存。" type="warning" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" label-position="top">
        <el-form-item label="平台情况说明" prop="description">
          <el-input v-if="canWrite" v-model="form.description" type="textarea" :rows="14" maxlength="5000" show-word-limit />
          <div v-else class="channel-long-text">{{ form.description || '-' }}</div>
        </el-form-item>
      </AppForm>
    </div>
    <template #footer>
      <el-button v-if="conflict || failed" :loading="loading" @click="readLatest">重新读取最新内容</el-button>
      <el-button v-if="!conflict && draft !== null" @click="restoreDraft">恢复保留的草稿</el-button>
      <el-button @click="visible = false">{{ canWrite ? '取消' : '关闭' }}</el-button>
      <el-button v-if="canWrite" type="primary" :loading="saving" :disabled="loading || conflict || failed || !form.revision" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'

defineProps({ canWrite: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])
const visible = ref(false), loading = ref(false), saving = ref(false), conflict = ref(false), failed = ref(false), draft = ref(null), record = ref(null), formRef = ref(null), bodyRef = ref(null)
const form = reactive({ description: '', revision: 0 })
let request, sequence = 0
async function readLatest() {
  request?.abort(); request = new AbortController(); const seq = ++sequence
  loading.value = true; failed.value = false
  try {
    const data = await api.channel(record.value.id, request.signal)
    if (seq !== sequence) return
    record.value = data; Object.assign(form, { description: data.description, revision: data.revision }); conflict.value = false
  } catch (error) { if (seq === sequence && error.code !== 'ERR_CANCELED') { failed.value = true; ElMessage.error(error.message) } }
  finally { if (seq === sequence) loading.value = false }
}
async function open(row) {
  record.value = row; draft.value = null; conflict.value = false; visible.value = true
  Object.assign(form, { description: '', revision: 0 })
  await readLatest()
}
function restoreDraft() { if (draft.value !== null) { form.description = draft.value; draft.value = null } }
async function save() {
  if (saving.value || loading.value || conflict.value || failed.value || !form.revision) return
  saving.value = true
  try {
    const saved = await api.saveChannelDescription(record.value.id, { ...form })
    visible.value = false; emit('saved', saved); ElMessage.success('平台情况说明已保存')
  } catch (error) {
    if (error.response?.status === 409) { conflict.value = true; draft.value = form.description }
    await formRef.value?.applyServerErrors(error); ElMessage.error(error.message)
  } finally { saving.value = false }
}
onBeforeUnmount(() => { request?.abort(); sequence++ })
defineExpose({ open })
</script>

<style>
.channel-dialog { display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
.channel-dialog>.el-dialog__header,.channel-dialog>.el-dialog__footer { flex-shrink:0; }
.channel-dialog>.el-dialog__body { flex:1; min-height:0; overflow-y:auto; }
.channel-dialog>.el-dialog__footer { background:#f8fafc; border-top:1px solid var(--el-border-color-light); }
.channel-dialog .el-alert { margin-bottom:16px; }
.channel-dialog-title { user-select:text; cursor:text; overflow-wrap:anywhere; }
.channel-long-text { white-space:pre-wrap; overflow-wrap:anywhere; width:100%; }
</style>
