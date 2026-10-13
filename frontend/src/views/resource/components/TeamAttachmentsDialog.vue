<template>
  <DraggableFormDialog ref="dialogRef" v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="team-form-dialog team-attachments-dialog" append-to-body destroy-on-close :before-close="beforeClose">
    <template #header><span class="el-dialog__title"><span class="team-attachment-title-name" @mousedown.stop>{{ team.short_name }}</span> · 资料附件</span></template>
    <el-alert title="附件上传、删除立即生效，与团队表单保存独立。" type="info" :closable="false" show-icon />
    <DocumentSectionAttachments v-if="visible && team.id" :key="team.id" ref="filesRef" :section-id="team.id" :can-edit="canEdit" :adapter="teamAttachmentAdapter" title="团队资料附件" entity-label="团队" @changed="items => emit('changed', team.id, items.length)" />
    <template #footer><el-button @click="dialogRef.handleClose()">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DocumentSectionAttachments from '@/components/common/DocumentSectionAttachments.vue'
import { teamAttachmentAdapter } from '@/api/teams'
defineProps({ canEdit: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const visible = ref(false), team = ref({}), dialogRef = ref(null), filesRef = ref(null)
function open(row) { team.value = { id: row.id, short_name: row.short_name || '团队' }; visible.value = true }
async function beforeClose(done) {
  if (filesRef.value?.isBusy) { ElMessage.warning('附件正在上传或删除，请完成后关闭'); return }
  if (filesRef.value?.hasPendingFiles) {
    try { await ElMessageBox.confirm('仍有未成功上传的文件，关闭后将清除这些待上传文件，已上传附件会保留。确定关闭吗？', '关闭资料附件', { type: 'warning' }) } catch { return }
  }
  done()
}
defineExpose({ open })
</script>

<style>
.team-attachment-title-name { user-select:text; cursor:text; }
.team-attachments-dialog .document-section-attachments { margin-top:16px; }
</style>
