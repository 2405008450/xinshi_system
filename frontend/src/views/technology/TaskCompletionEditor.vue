<template>
  <DraggableFormDialog v-model="visible" :title="mode === 'date' ? '调整完成日期' : amountTitle" width="min(650px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="close" @closed="$emit('close')">
    <div v-loading="loading"><el-alert v-if="error" :title="error" type="error" :closable="false" /><template v-if="task">
      <p>{{ task.task_no }} · {{ task.task_name }}</p><p>预定完成日期：{{ task.due_on || '-' }}；完成日期：{{ task.completed_on || '待完成' }}</p>
      <AppForm v-if="mode === 'date'" ref="dateForm" :model="date" :rules="dateRules" label-position="top"><el-form-item label="完成日期" prop="completed_on"><el-date-picker v-model="date.completed_on" type="date" value-format="YYYY-MM-DD" :automatic-dropdown="false" clearable /></el-form-item><el-form-item label="调整原因" prop="reason"><PlainInput v-model="date.reason" type="textarea" :rows="3" maxlength="3000" :placeholder="task.completed_on ? '请说明调整原因' : '可填写完成说明'" /></el-form-item></AppForm>
      <template v-else><el-alert :title="task.on_time ? '按时完成：给予奖励' : '未按时完成：抵消奖金'" :type="task.on_time ? 'success' : 'warning'" :closable="false" /><AppForm ref="amountForm" :model="amount" :rules="amountRules" label-position="top"><el-form-item label="金额" prop="value"><PlainInput v-model="amount.value" inputmode="decimal" placeholder="填写金额，最多两位小数" /></el-form-item><el-form-item label="金额说明／调整原因" prop="reason"><PlainInput v-model="amount.reason" type="textarea" :rows="3" maxlength="3000" :placeholder="task.incentive ? '调整金额必须填写原因' : '可填写说明'" /></el-form-item></AppForm><p class="completion-note">归属任务执行人；当前有效金额计入人事管理 → KPI管理 → 开发部门奖励。关闭窗口暂不登记金额。</p></template>
    </template></div>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :disabled="loading || !task" :loading="saving" @click="save">{{ mode === 'date' ? '保存完成日期' : '确认金额' }}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElInput as PlainInput, ElMessage } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getTaskCompletion, saveTaskCompletion, saveTaskIncentive } from '@/api/technicalIncentives'
const props = defineProps({ taskId: { type: String, required: true }, initialMode: { type: String, default: 'date' }, initialDate: { type: String, default: undefined } }), emit = defineEmits(['close', 'changed'])
const visible = ref(true), mode = ref(props.initialMode), task = ref(null), loading = ref(false), saving = ref(false), error = ref(''), dateForm = ref(null), amountForm = ref(null)
const date = reactive({ completed_on: null, reason: '' }), amount = reactive({ value: '', reason: '' })
let dateRequest = crypto.randomUUID(), amountRequest = crypto.randomUUID()
const amountTitle = computed(() => task.value?.on_time ? '给予奖励' : '抵消奖金')
const dateRules = computed(() => ({ reason: [{ validator: (_, value, done) => done(task.value?.completed_on && date.completed_on !== task.value.completed_on && !value.trim() ? new Error('调整完成日期必须填写原因') : undefined), trigger: 'blur' }] }))
const amountRules = computed(() => ({ value: [{ validator: (_, value, done) => done(!/^\d{1,12}(\.\d{1,2})?$/.test(value) ? new Error('请填写非负金额，最多两位小数') : undefined), trigger: 'blur' }], reason: [{ validator: (_, value, done) => done(task.value?.incentive && Number(amount.value) !== Number(task.value.incentive.amount) && !value.trim() ? new Error('调整金额必须填写原因') : undefined), trigger: 'blur' }] }))
function initialize(value) { task.value = value; date.completed_on = value.completed_on; date.reason = ''; amount.value = value.incentive?.amount || ''; amount.reason = '' }
function close(done) { if (!saving.value) done() }
async function load() { loading.value = true; try { initialize(await getTaskCompletion(props.taskId)); if (props.initialDate !== undefined) date.completed_on = props.initialDate; if (mode.value === 'amount' && task.value.on_time == null) mode.value = 'date' } catch (e) { error.value = typeof e.detail === 'string' ? e.detail : '加载失败' } finally { loading.value = false } }
async function save() {
  const form = mode.value === 'date' ? dateForm : amountForm
  if (saving.value || !await form.value.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  try {
    if (mode.value === 'date') {
      const previous = task.value.completion_revision
      const value = await saveTaskCompletion(props.taskId, { request_id: dateRequest, task_revision: task.value.task_revision, completion_revision: previous, completed_on: date.completed_on || null, reason: date.reason })
      initialize(value); dateRequest = crypto.randomUUID(); emit('changed', value)
      if (value.on_time != null && value.completion_revision !== previous) { mode.value = 'amount'; amountRequest = crypto.randomUUID(); ElMessage.success('完成日期已保存，请填写金额') }
      else visible.value = false
    } else {
      initialize(await saveTaskIncentive(props.taskId, { request_id: amountRequest, completion_revision: task.value.completion_revision, expected_latest_id: task.value.incentive?.id || null, amount: amount.value, reason: amount.reason }))
      emit('changed', task.value); ElMessage.success('金额已登记'); visible.value = false
    }
  } catch (e) { error.value = typeof e.detail === 'string' ? e.detail : '保存失败，请重试' }
  finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>.completion-note{color:var(--el-text-color-secondary);font-size:12px;line-height:1.7}</style>
