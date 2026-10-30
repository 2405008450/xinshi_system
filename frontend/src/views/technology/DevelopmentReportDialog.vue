<template>
  <DraggableFormDialog v-model="visible" title="加至工作报告" class="development-report-dialog" width="min(840px, calc(100vw - 32px))" top="5vh" append-to-body :before-close="close" :close-on-click-modal="false" @closed="$emit('close')">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="加至工作报告" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading" data-screenshot-editor="own" @paste.capture="blockReportImages" @drop.capture="blockReportImages">
      <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error && !context" @click="load">重新加载</el-button>
      <template v-if="context">
        <p class="report-note">添加到 {{ context.report_date }} 的工作报告草稿。香港时间每天 07:00 换日，请完整填写本次工作记录。</p>
        <el-descriptions :column="1" border size="small"><el-descriptions-item label="报告日期">{{ context.report_date }}</el-descriptions-item><el-descriptions-item label="添加时间">确认添加时由系统记录（香港时间 UTC+8）</el-descriptions-item></el-descriptions>
        <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
          <el-form-item label="任务/项目类型" prop="report_types"><el-select v-model="form.report_types" multiple filterable><el-option v-for="type in types" :key="type" :label="type" :value="type" /></el-select></el-form-item>
          <el-form-item label="订单号" prop="order_no"><el-input v-model="form.order_no" maxlength="100" /><TechnicalTaskReference :task-id="taskId" :label="context.order_no" /></el-form-item>
          <el-form-item label="项目名称" prop="task_name"><el-input v-model="form.task_name" maxlength="255" /><TechnicalTaskReference :task-id="taskId" :label="context.task_name + ' · 查看各天具体进度'" kind="progress" /></el-form-item>
          <el-form-item label="具体任务" prop="progress_content"><el-input v-model="form.progress_content" type="textarea" :rows="5" maxlength="10000" /></el-form-item>
          <el-row :gutter="16">
            <el-col :xs="24" :sm="8"><el-form-item label="工作量" prop="quantity"><el-input v-model="form.quantity" inputmode="decimal" placeholder="请填写非负数字" /></el-form-item></el-col>
            <el-col :xs="24" :sm="8"><el-form-item label="单位" prop="quantity_unit"><el-select v-model="form.quantity_unit" filterable allow-create default-first-option clearable><el-option v-for="unit in ['个','份','页','字','次','项','人','小时','其他']" :key="unit" :label="unit" :value="unit" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :sm="8"><el-form-item label="耗时" prop="duration_minutes"><el-select v-model="form.duration_minutes" filterable placeholder="请选择"><el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" /></el-select></el-form-item></el-col>
          </el-row>
          <el-form-item v-if="form.quantity_unit === '其他'" label="具体单位" prop="quantity_unit_other"><el-input v-model="form.quantity_unit_other" maxlength="80" /></el-form-item>
        </AppForm>
      </template>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :disabled="loading || !context" :loading="saving" @click="submit">确认添加</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TechnicalTaskReference from '@/components/common/TechnicalTaskReference.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { blockReportImages, projectTypes, defaultWorkCategories, durationOptions, durationLabel, validQuantity } from '@/utils/workReportForm'
import { getDevelopmentReportContext, addDevelopmentReport } from '@/api/technicalDevelopment'
const props = defineProps({ taskId: { type: String, required: true } }), emit = defineEmits(['close', 'saved'])
const visible = ref(true), body = ref(null), formRef = ref(null), loading = ref(false), saving = ref(false), error = ref(''), context = ref(null)
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(body)
const form = reactive({ report_types: ['开发任务'], order_no: '', task_name: '', progress_content: '', quantity: '', quantity_unit: '', quantity_unit_other: '', duration_minutes: null })
const types = [...new Set([...projectTypes.filter(type => type !== '其他项目'), ...Object.keys(defaultWorkCategories)])]
const required = [{ required: true, whitespace: true, message: '请填写此字段', trigger: ['blur', 'change'] }]
const rules = {
  order_no: required, task_name: required, progress_content: required, quantity_unit: required,
  report_types: [{ type: 'array', required: true, min: 1, message: '请选择任务/项目类型', trigger: 'change' }],
  quantity: [{ required: true, validator: (_r, value, done) => done(value !== '' && value != null && validQuantity(value) ? undefined : new Error('请填写非负数字工作量')), trigger: ['blur', 'change'] }],
  duration_minutes: [{ required: true, type: 'number', min: 1, max: 1440, message: '请选择耗时', trigger: 'change' }],
  quantity_unit_other: required,
}
const requestId = crypto.randomUUID()
let active = true
async function load() {
  loading.value = true; error.value = ''
  try { const value = await getDevelopmentReportContext(props.taskId); if (active) { context.value = value; for (const key of Object.keys(form)) if (value[key] !== undefined) form[key] = value[key] } }
  catch (e) { if (active) error.value = typeof e.detail === 'string' ? e.detail : '工作报告表单加载失败' }
  finally { if (active) loading.value = false }
}
function close(done) { if (!saving.value) done() }
async function submit() {
  if (saving.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  try { const result = await addDevelopmentReport(props.taskId, { ...form, quantity_unit_other: form.quantity_unit === '其他' ? form.quantity_unit_other : '', report_type: form.report_types[0], request_id: requestId }); ElMessage.success(`已加入 ${result.report_date} 的工作报告`); emit('saved', result); visible.value = false }
  catch (e) { error.value = typeof e.detail === 'string' ? e.detail : '添加失败，请重试' }
  finally { saving.value = false }
}
onMounted(load); onBeforeUnmount(() => { active = false })
</script>
<style>
.development-report-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.development-report-dialog>.el-dialog__header,.development-report-dialog>.el-dialog__footer{flex-shrink:0}.development-report-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.development-report-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}.development-report-dialog .el-select{width:100%}.development-report-dialog .report-note{color:var(--el-text-color-secondary);font-size:13px;line-height:1.6}
</style>
