<template>
  <section class="sub-client-finance-preferences" v-loading="loading">
    <h4>子客户结算设置 <small v-if="settings">{{ settings.sub_client_name }} · {{ settings.sub_client_code }}</small></h4>
    <div v-if="settings" class="sub-client-finance-fields">
      <el-form-item v-for="field in documentFields" :key="field.key" :label="field.label">
        <el-select :model-value="settings[field.key] == null ? 'default' : settings[field.key]"
          :aria-label="field.label" :disabled="!canWrite || saving" style="width:156px" @change="save(field.key,$event)">
          <el-option :label="field.fallback" value="default" />
          <el-option label="需" :value="true" />
          <el-option label="无需" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="计费口径">
        <el-select :model-value="settings.tax_mode || 'default'" aria-label="子客户计费口径"
          :disabled="!canWrite || saving" style="width:156px" @change="save('tax_mode',$event)">
          <el-option label="按订单价格判断" value="default" />
          <el-option label="含税" value="incl_tax" />
          <el-option label="不含税" value="excl_tax" />
        </el-select>
      </el-form-item>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load">重试</el-button>
    </el-alert>
  </section>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { getSubClientFinancePreferences, saveSubClientFinancePreferences } from '@/api/translationCustomerFinance'
import { connectInvoiceParties, invoicePartiesEvent, notifyInvoiceParties } from '@/api/invoiceParties'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({ subClientId: String, canWrite: Boolean })
const documentFields = [
  { key: 'quotation_required', label: '是否需报价单', fallback: '按订单设置' },
  { key: 'statement_required', label: '是否需对账单', fallback: '按计费口径' },
]
const settings = ref(null), loading = ref(false), saving = ref(false), error = ref('')
let controller
async function load() {
  controller?.abort()
  if (!props.subClientId) return
  const request = new AbortController()
  controller = request
  loading.value = true
  error.value = ''
  try {
    const result = await getSubClientFinancePreferences(props.subClientId, {signal:request.signal})
    if (!request.signal.aborted) settings.value = result
  } catch (cause) {
    if (!request.signal.aborted) error.value = getLocalizedErrorMessage(cause,'读取子客户结算设置失败')
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

async function save(field, value) {
  if (!props.canWrite || saving.value || !settings.value) return
  saving.value = true
  error.value = ''
  const id = props.subClientId
  try {
    const result = await saveSubClientFinancePreferences(id, {
      revision:settings.value.revision, [field]:value === 'default' ? null : value,
    })
    if (id === props.subClientId) settings.value = result
    notifyInvoiceParties({kind:'sub-client-finance',subClientId:id,clientId:result.client_id})
  } catch (cause) {
    const message = getLocalizedErrorMessage(cause,'保存子客户结算设置失败')
    if (cause.response?.status === 409) await load()
    error.value = message
  } finally {
    saving.value = false
  }
}

function onSettingsChanged(event) {
  if (event.detail?.kind === 'sub-client-finance' && event.detail.subClientId === props.subClientId && !saving.value) void load()
}
watch(() => props.subClientId, () => { settings.value = null; void load() }, {immediate:true})
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,onSettingsChanged)
onBeforeUnmount(() => {
  controller?.abort()
  window.removeEventListener(invoicePartiesEvent,onSettingsChanged)
})
</script>

<style scoped>
.sub-client-finance-preferences { margin: 12px 0; padding: 12px; border: 1px solid var(--el-border-color-light); }
.sub-client-finance-fields { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.sub-client-finance-fields :deep(.el-form-item) { margin-bottom: 0; }
h4 { margin: 0 0 10px; }
small { margin-inline-start: 6px; color: var(--el-text-color-secondary); }
</style>
