<template>
  <div class="customer-progress" v-loading="loading">
    <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon>
      <el-button link type="primary" @click="reload">重试加载</el-button>
    </el-alert>
    <section v-if="canWrite && !loadError" ref="entryRef" class="progress-entry-panel">
      <div class="progress-entry-panel__header">
        <b>{{ editingId ? '编辑客户进度' : '录入客户进度' }}</b>
        <el-button v-if="editingId" link :disabled="submitting || busy" @click="clearDraft">取消编辑</el-button>
      </div>
      <div v-if="draftSource" class="progress-chat-source">
        已从项目沟通带入客户进度：{{ draftSource.messageCount }} 条消息 · {{ draftSource.senderSummary }}，保存前可编辑
        <el-button link type="primary" :disabled="submitting || busy" @click="$emit('transfer', getDraft())">转到项目进度</el-button>
      </div>
      <AppForm ref="formRef" :model="form" :rules="rules" label-width="76px" size="small" class="progress-entry-form" :disabled="submitting || busy">
        <el-form-item label="节点时间" prop="effectiveOn">
          <el-date-picker v-model="form.effectiveOn" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" />
        </el-form-item>
        <el-form-item label="具体进度" prop="changeNote">
          <div class="progress-note-control">
            <el-input ref="noteRef" v-model="form.changeNote" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="10000" show-word-limit placeholder="例如：报价已发，等待客户确认；客户预计周五反馈试标结果" />
            <el-button type="primary" :loading="submitting" :disabled="loading || busy" @click="save">{{ editingId ? '保存客户进度' : '添加客户进度' }}</el-button>
          </div>
        </el-form-item>
      </AppForm>
    </section>
    <el-divider content-position="left">客户进度记录</el-divider>
    <el-timeline class="customer-progress-timeline">
      <el-timeline-item v-for="row in rows" :key="`customer:${row.id}`" :data-progress-record-id="row.id" data-progress-track="customer" :class="{ 'is-progress-search-target': String(row.id) === String(targetRecordId) }">
        <div class="progress-child-note">{{ row.changeNote }}</div>
        <div class="progress-child-meta">
          <span>{{ formatBusinessDateTimeMinute(row.effectiveOn) }}</span>
          <span>填写人：{{ row.changedByName || '系统' }}</span>
          <el-tag size="small" effect="plain">客户进度</el-tag>
          <template v-if="canWrite">
            <el-button link type="primary" size="small" :disabled="submitting || busy" @click="edit(row)">编辑</el-button>
            <el-button link type="danger" size="small" :disabled="submitting || busy" @click="$emit('delete', row)">删除</el-button>
          </template>
        </div>
        <div v-if="row.updatedAt !== row.changedAt" class="progress-child-meta">修改人：{{ row.updatedByName || '系统' }} · {{ formatBusinessDateTimeMinute(row.updatedAt) }}</div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-if="!loading && !loadError && !rows.length" description="暂无客户进度，可记录客户确认、反馈及后续安排" :image-size="80" />
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/annotationOps'
import { businessDateTimeInputValue, formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { appendProgressDraft } from '@/utils/annotationCustomerProgress'

const props = defineProps({ projectId: String, active: Boolean, canWrite: Boolean, busy: Boolean, targetRecordId: String })
const emit = defineEmits(['busy', 'changed', 'delete', 'transfer'])
const loading = ref(false), submitting = ref(false), loadError = ref(''), rows = ref([])
const formRef = ref(), entryRef = ref(), noteRef = ref(), editingId = ref(''), expectedUpdatedAt = ref(''), draftSource = ref(null)
const form = reactive({ effectiveOn: businessDateTimeInputValue(), changeNote: '' })
let baseline = '', loadedProject = '', requestId = 0, controller
const rules = {
  effectiveOn: [{ required: true, message: '请选择节点时间', trigger: 'change' }],
  changeNote: [{ validator: (_rule, value, callback) => String(value || '').trim() ? callback() : callback(new Error('请填写客户具体进度')), trigger: ['blur', 'change'] }],
}
const hasDraft = () => editingId.value ? JSON.stringify(form) !== baseline : Boolean(form.changeNote.trim())
const getDraft = () => ({ ...form, source: draftSource.value, editingId: editingId.value })
const clearDraft = () => {
  editingId.value = ''; expectedUpdatedAt.value = ''; draftSource.value = null
  Object.assign(form, { effectiveOn: businessDateTimeInputValue(), changeNote: '' })
  baseline = JSON.stringify(form); formRef.value?.clearValidate()
}
const reload = async () => {
  const projectId = props.projectId
  if (!projectId) return
  controller?.abort(); controller = new AbortController()
  const current = ++requestId; loading.value = true; loadError.value = ''
  try {
    const result = await api.getCustomerProgress(projectId, { signal: controller.signal })
    if (current !== requestId || projectId !== props.projectId) return
    rows.value = result; loadedProject = projectId
    if (editingId.value && !rows.value.some((row) => row.id === editingId.value)) clearDraft()
    await nextTick()
    if (props.targetRecordId) document.querySelector(`[data-progress-track="customer"][data-progress-record-id="${props.targetRecordId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  } catch (error) {
    if (current === requestId && error?.code !== 'ERR_CANCELED') loadError.value = error?.detail || '客户进度加载失败，请重试'
  } finally { if (current === requestId) loading.value = false }
}
const focusEntry = async () => {
  await nextTick(); formRef.value?.clearValidate()
  entryRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); noteRef.value?.focus?.()
}
const edit = async (row) => {
  if (hasDraft()) {
    try { await ElMessageBox.confirm('录入区有未保存内容，是否放弃并编辑这条客户进度？', '编辑客户进度', { confirmButtonText: '放弃并编辑', cancelButtonText: '保留草稿', type: 'warning' }) } catch { return }
  }
  editingId.value = row.id; expectedUpdatedAt.value = row.updatedAt; draftSource.value = null
  Object.assign(form, { effectiveOn: businessDateTimeInputValue(row.effectiveOn), changeNote: row.changeNote })
  baseline = JSON.stringify(form); await focusEntry()
}
const acceptDraft = async (draft) => {
  if (loadedProject !== props.projectId) await reload()
  if (loadError.value) throw new Error(loadError.value)
  if (editingId.value) throw new Error('请先保存或取消当前客户进度编辑，再带入沟通消息')
  const note = appendProgressDraft(form.changeNote, draft.changeNote)
  if (!form.changeNote.trim()) form.effectiveOn = draft.effectiveOn
  form.changeNote = note
  draftSource.value = draftSource.value && draft.source
    ? { messageCount: draftSource.value.messageCount + draft.source.messageCount, senderSummary: [...new Set([...draftSource.value.senderSummary.split('、'), ...draft.source.senderSummary.split('、')])].join('、') }
    : draft.source || draftSource.value
  await focusEntry()
}
const save = async () => {
  if (submitting.value || props.busy) return
  if (!await formRef.value?.validate().catch(() => false)) return
  submitting.value = true; emit('busy', true)
  try {
    const payload = { ...form, effectiveOn: form.effectiveOn.replace(' ', 'T') + '+08:00', changeNote: form.changeNote.trim() }
    const saved = editingId.value ? await api.updateCustomerProgress(editingId.value, { ...payload, expectedUpdatedAt: expectedUpdatedAt.value }) : await api.createCustomerProgress(props.projectId, payload)
    clearDraft(); ElMessage.success('客户进度已保存'); emit('changed', saved)
    await reload()
  } catch (error) {
    await formRef.value?.applyServerErrors(error)
    ElMessage.error(error?.detail || '客户进度保存失败，请重试')
  } finally { submitting.value = false; emit('busy', false) }
}
watch(() => props.projectId, () => { controller?.abort(); requestId++; loading.value = false; rows.value = []; loadedProject = ''; loadError.value = ''; clearDraft() })
watch(() => [props.active, props.projectId], ([active, projectId]) => { if (active && projectId && loadedProject !== projectId) void reload() }, { immediate: true })
onBeforeUnmount(() => { controller?.abort(); requestId++ })
defineExpose({ reload, hasDraft, getDraft, clearDraft, acceptDraft })
</script>

<style scoped>
.progress-entry-panel{padding:12px 14px 4px;border:1px solid var(--el-color-primary-light-7);border-radius:8px;background:var(--el-color-primary-light-9)}
.progress-entry-panel__header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.progress-entry-form :deep(.el-form-item){margin-bottom:10px}
.progress-note-control{display:flex;width:100%;align-items:flex-end;gap:10px}.progress-note-control .el-textarea{flex:1;min-width:0}
.progress-chat-source{margin-bottom:10px;font-size:12px;color:var(--el-color-primary)}
.progress-child-note{white-space:pre-wrap;word-break:break-word;line-height:1.6}
.progress-child-meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px;font-size:12px;color:var(--el-text-color-secondary)}
.customer-progress-timeline{padding-left:8px;margin-top:10px}.is-progress-search-target{border-radius:6px;background:var(--el-color-warning-light-9);box-shadow:inset 3px 0 0 var(--el-color-warning)}
@media(max-width:768px){.progress-note-control{flex-direction:column;align-items:stretch}.progress-note-control .el-button{align-self:flex-end}}
</style>
