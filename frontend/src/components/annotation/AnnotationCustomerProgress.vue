<template>
  <section ref="entryRef" class="progress-entry-panel customer-progress-entry" v-loading="loading">
    <div class="progress-entry-panel__header">
      <b>{{ editingId ? '编辑客户进度' : '录入客户进度' }}</b>
      <el-button v-if="editingId" link :disabled="busy" @click="$emit('cancel-edit')">取消编辑</el-button>
    </div>
    <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon>
      <el-button link type="primary" :disabled="busy || loading" @click="$emit('retry')">重试加载</el-button>
    </el-alert>
    <AppForm ref="formRef" :model="form" :rules="rules" label-width="76px" size="small" class="progress-entry-form" :disabled="saving">
      <el-row :gutter="14" class="progress-entry-metadata">
        <el-col :xs="24" :sm="12"><el-form-item label="当前状态"><ReadonlyField :model-value="projectStatusLabel" source="auto" /></el-form-item></el-col>
        <el-col :xs="24" :sm="12">
      <el-form-item label="节点时间" prop="effectiveOn">
        <el-date-picker v-model="form.effectiveOn" :disabled="loading || Boolean(loadError)" :validate-event="!busy && active" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
      </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="具体进度" prop="changeNote" label-width="124px" class="annotation-progress-note-item">
        <template #label><slot name="note-label">具体进度</slot></template>
        <el-input ref="noteRef" v-model="form.changeNote" :disabled="loading || Boolean(loadError)" :validate-event="!busy && active" type="textarea" aria-label="客户具体进度" :rows="3" maxlength="10000" show-word-limit placeholder="例如：报价已发，等待客户确认；客户预计周五反馈试标结果" />
      </el-form-item>
    </AppForm>
    <div v-if="draftSource" class="progress-chat-source">
      已从项目沟通带入客户进度：{{ draftSource.messageCount }} 条消息 · {{ draftSource.senderSummary }}，保存前可编辑
      <el-button link type="primary" :disabled="busy" @click="$emit('transfer')">转到项目进度</el-button>
    </div>
    <div class="progress-entry-actions" />
  </section>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { focusFormTarget, scrollFormTarget } from '@/utils/formNavigation'

defineProps({ form: { type: Object, required: true }, projectStatusLabel: String, active: { type: Boolean, default: true }, editingId: String, draftSource: Object, loading: Boolean, loadError: String, busy: Boolean, saving: Boolean, submitLoading: Boolean, submitDisabled: Boolean, submitLabel: { type: String, default: '添加客户进度' } })
defineEmits(['cancel-edit', 'retry', 'transfer', 'submit'])
const formRef = ref(), entryRef = ref(), noteRef = ref()
const rules = {
  effectiveOn: [{ required: true, message: '请选择节点时间', trigger: 'change' }],
  changeNote: [{ validator: (_rule, value, callback) => {
    const note = String(value || '').trim()
    callback(!note ? new Error('请填写客户具体进度') : note.length > 10000 ? new Error('具体进度不能超过 10000 字') : undefined)
  }, trigger: ['blur', 'change'] }],
}
const focusEntry = async () => {
  await nextTick(); formRef.value?.clearValidate()
  const target = noteRef.value?.$el
  scrollFormTarget(target); focusFormTarget(target)
}
defineExpose({ focusEntry, validate: () => formRef.value?.validate(), clearValidate: () => formRef.value?.clearValidate(), applyServerErrors: (error) => formRef.value?.applyServerErrors(error) })
</script>

<style scoped>
.progress-entry-panel{padding:12px 14px 4px;border:1px solid var(--el-color-primary-light-7);border-radius:8px;background:var(--el-color-primary-light-9)}
.progress-entry-panel__header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.progress-entry-form :deep(.el-form-item){margin-bottom:10px}
.progress-chat-source{margin-bottom:10px;font-size:12px;color:var(--el-color-primary)}
.progress-entry-actions{display:flex;justify-content:flex-end;gap:12px;padding:2px 0 10px}
@media(max-width:768px){.progress-entry-actions{flex-wrap:wrap}}
</style>
