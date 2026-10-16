<template>
  <DraggableFormDialog v-model="visible" title="负责人调整原因" width="min(600px, calc(100vw - 32px))"
    append-to-body destroy-on-close class="annotation-manager-reason-dialog" @closed="cancel">
    <div class="manager-change-summary">
      <p>订单号：{{ orderNo }}</p>
      <p v-for="change in changes" :key="change.role">{{ change.label }}：{{ names(change.previous) }} → {{ names(change.next) }}</p>
    </div>
    <AppForm ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="调整原因" prop="reason">
        <el-input v-model="form.reason" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="请填写本次负责人调整原因" />
      </el-form-item>
    </AppForm>
    <template #footer><el-button @click="cancel">取消</el-button><el-button type="primary" @click="confirm">确认调整</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
const props = defineProps({ users: { type: Array, default: () => [] } })
const visible = ref(false), formRef = ref(), orderNo = ref(''), changes = ref([])
const form = reactive({ reason: '' })
const rules = { reason: [{ validator: (_rule, value, callback) => String(value || '').trim() ? callback() : callback(new Error('请填写调整原因')), trigger: 'blur' }] }
let resolveRequest
const names = ids => ids.map(id => {
  const user = props.users.find(item => item.id === id)
  return user?.full_name || user?.fullName || user?.username || id
}).join('、') || '未分配'
function finish(value) {
  const resolve = resolveRequest
  resolveRequest = undefined
  visible.value = false
  resolve?.(value)
}
const cancel = () => finish(null)
const confirm = async () => { if (await formRef.value?.validate().catch(() => false)) finish(form.reason.trim()) }
function request(options) {
  cancel()
  orderNo.value = options.orderNo
  changes.value = options.changes
  form.reason = ''
  visible.value = true
  return new Promise(resolve => { resolveRequest = resolve })
}
onBeforeUnmount(cancel)
defineExpose({ request })
</script>

<style scoped>
.manager-change-summary{overflow-wrap:anywhere;max-height:240px;overflow-y:auto;margin-bottom:16px}
</style>
