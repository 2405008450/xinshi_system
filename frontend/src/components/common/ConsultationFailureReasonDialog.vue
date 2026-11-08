<template>
  <DraggableFormDialog :model-value="modelValue" title="填写未成交原因" width="min(620px, calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close class="consultation-failure-dialog" @update:model-value="value => emit('update:modelValue', value)" @close="emit('cancel')">
    <AppForm ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="未成交原因" prop="reason">
        <el-select v-model="form.reason" filterable allow-create default-first-option placeholder="选择原因，或输入自定义原因" style="width:100%">
          <el-option v-for="item in options" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item :label="requiresDetails ? '具体原因/理由' : '补充说明'" prop="details">
        <el-input v-model="form.details" type="textarea" :rows="4" maxlength="5000" show-word-limit :placeholder="requiresDetails ? '请填写具体原因或理由（必填）' : '可补充未成交情况'" />
      </el-form-item>
    </AppForm>
    <template #footer><el-button @click="emit('update:modelValue', false)">取消</el-button><el-button type="primary" @click="confirm">确定</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
const props = defineProps({ modelValue: Boolean, initialValue: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])
const builtin = ['价格高', '反应慢', '处理速度不符合客户要求', '无法满足客户要求', '自动放弃', '已找其他公司', '对信实不满意', '一次跟进客户未回应', '多次跟进客户未回应', '自定义添加']
const required = new Set(['无法满足客户要求', '自动放弃', '对信实不满意', '自定义添加'])
const form = reactive({ reason: '', details: '' }), formRef = ref(), custom = ref([])
const storageKey = () => `consultation_failure_reasons:${localStorage.getItem('user_id') || 'anonymous'}`
const options = computed(() => [...new Set([...builtin, ...custom.value, ...(props.initialValue?.reason ? [props.initialValue.reason] : [])])])
const requiresDetails = computed(() => required.has(form.reason))
const rules = computed(() => ({
  reason: [{ required: true, whitespace: true, message: '请选择或填写未成交原因', trigger: 'change' }, { max: 100, message: '原因名称不能超过100字', trigger: 'change' }],
  details: [{ required: requiresDetails.value, whitespace: true, message: '请补充具体原因或理由', trigger: ['blur', 'change'] }],
}))
watch(() => props.modelValue, async value => {
  if (!value) return
  form.reason = props.initialValue?.reason || ''; form.details = props.initialValue?.details || ''
  try { const saved = JSON.parse(localStorage.getItem(storageKey()) || '[]'); custom.value = Array.isArray(saved) ? saved.filter(item => typeof item === 'string' && item.trim() && item.length <= 100).slice(0, 100) : [] } catch { custom.value = [] }
  await nextTick(); formRef.value?.clearValidate()
})
async function confirm() {
  if (!await formRef.value.validate().catch(() => false)) return
  const value = { reason: form.reason.trim(), details: form.details.trim() }
  if (!builtin.includes(value.reason)) { custom.value = [...new Set([...custom.value, value.reason])].slice(-100); try { localStorage.setItem(storageKey(), JSON.stringify(custom.value)) } catch { /* 禁用存储时仍可保存本条原因。 */ } }
  emit('confirm', value); emit('update:modelValue', false)
}
</script>
<style>
.consultation-failure-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.consultation-failure-dialog .el-dialog__header, .consultation-failure-dialog .el-dialog__footer { flex-shrink: 0; }
.consultation-failure-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.consultation-failure-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-extra-light); }
</style>
