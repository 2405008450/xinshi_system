<template>
  <section class="sub-client-finance-preferences" v-loading="loading">
    <div class="sub-client-settlement-heading">
      <h4>子客户结算设置 <small v-if="settings">{{ settings.sub_client_name }} · {{ settings.sub_client_code }}</small></h4>
      <div v-if="month" class="sub-client-settlement-party" data-dialog-field-search-label="账期结算对象">
        <small>{{ month }} · {{ period ? `第${period}期` : '整月（不分期）' }}</small>
        <el-radio-group :model-value="party" aria-label="账期结算对象" :disabled="!canWrite || !party || switching" @update:model-value="changeParty">
          <el-radio-button value="client">客户结算</el-radio-button>
          <el-radio-button value="sub_client">子客户结算</el-radio-button>
        </el-radio-group>
      </div>
    </div>
    <p v-if="party === 'client'">本账期采用客户的报价单、对账单和含税设置，新生成的对账单及发票使用客户资料。</p>
    <template v-if="settings">
      <div class="sub-client-finance-fields">
        <el-form-item label="对账单主体">
          <el-select :model-value="settings.statement_subject_key || 'default'" aria-label="子客户对账单主体" :disabled="!canWrite || saving" @change="save('statement_subject_key',$event)">
            <el-option label="系统默认" value="default" /><el-option label="广州总公司" value="guangzhou" /><el-option label="深圳分公司" value="shenzhen" /><el-option label="上海分公司" value="shanghai" />
          </el-select>
        </el-form-item>
        <el-form-item v-for="field in documentFields" :key="field.key" :label="field.label">
          <div class="sub-client-document-choice">
            <el-select :model-value="settings[field.key] ?? 'default'"
              :aria-label="`子客户${field.label}`" :disabled="!canWrite || saving" @change="save(field.key,$event)">
              <el-option :label="field.fallback" value="default" />
              <el-option label="需" :value="true" />
              <el-option label="无需" :value="false" />
            </el-select>
            <slot name="document-action" :kind="field.kind" />
          </div>
          <el-input :model-value="settings.document_notes?.[field.kind] || ''" size="small" placeholder="说明"
            :aria-label="`子客户${field.noteLabel}说明`" :disabled="!canWrite || saving" :maxlength="2000" clearable
            @change="saveNote(field.kind,$event)" />
        </el-form-item>
        <slot name="settings-link" />
      </div>
      <el-form-item v-if="!hideTax" data-dialog-field-search-label="单价含税">
        <el-checkbox :model-value="settings.tax_mode === 'incl_tax'" :disabled="!canWrite || saving"
          @change="save('tax_mode',$event ? 'incl_tax' : 'excl_tax')">单价含税</el-checkbox>
        <el-button v-if="settings.tax_mode" link :disabled="!canWrite || saving" @click="save('tax_mode','default')">按订单价格判断</el-button>
        <small v-else>按订单价格判断</small>
      </el-form-item>
    </template>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load();loadParty()">重试</el-button>
    </el-alert>
  </section>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { getSubClientFinancePreferences, saveSubClientFinancePreferences, getSubClientSettlementParty, saveSubClientSettlementParty } from '@/api/translationCustomerFinance'
import { connectInvoiceParties, invoicePartiesEvent, notifyInvoiceParties } from '@/api/invoiceParties'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({ subClientId: String, canWrite: Boolean, month: String, period: Number, hideTax: Boolean })
const documentFields = [
  {key:'quotation_required',kind:'quotation',noteLabel:'报价单',label:'是否需报价单',fallback:'按订单设置'},
  {key:'statement_required',kind:'statement',noteLabel:'对账单',label:'是否需对账单',fallback:'按计费口径'},
  {key:'invoice_required',kind:'invoice',noteLabel:'发票',label:'是否需发票',fallback:'按计费口径'},
]
const settings = ref(null), loading = ref(false), saving = ref(false), error = ref('')
let controller
let partyController
const party = ref(null), switching = ref(false)
async function loadParty() {
  partyController?.abort()
  party.value = null
  if (!props.subClientId || !props.month) return
  const request = new AbortController()
  partyController = request
  try {
    const result = await getSubClientSettlementParty(props.subClientId, {month:props.month,period:props.period}, request.signal)
    if (!request.signal.aborted) party.value = result.party
  } catch (cause) {
    if (!request.signal.aborted) error.value = getLocalizedErrorMessage(cause,'读取账期结算对象失败')
  }
}

async function changeParty(value) {
  const {subClientId, month, period} = props
  const previous = party.value
  if (!props.canWrite || switching.value || !previous || previous === value) return
  switching.value = true
  error.value = ''
  try {
    const name = value === 'client' ? '客户' : '子客户'
    const confirmed = await ElMessageBox.confirm(
      `${month} ${period ? `第${period}期` : '整月（不分期）'}内该子客户的项目将采用${name}的报价单、对账单和含税设置。新生成的对账单、发票将使用${name}的名称和资料。`,
      `切换为${name}结算`, {type:'warning',confirmButtonText:'确认切换',cancelButtonText:'取消'},
    ).catch(() => false)
    if (!confirmed || subClientId !== props.subClientId || month !== props.month || period !== props.period) return
    const result = await saveSubClientSettlementParty(subClientId, {month,period,party:value,expected_party:previous})
    if (subClientId === props.subClientId && month === props.month && period === props.period) party.value = result.party
    notifyInvoiceParties({kind:'sub-client-finance',subClientId,clientId:result.client_id})
  } catch (cause) {
    if (cause.response?.status === 409) await loadParty()
    error.value = getLocalizedErrorMessage(cause,'保存账期结算对象失败')
  } finally {
    switching.value = false
  }
}
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
function saveNote(kind,value){
  if(value===(settings.value?.document_notes?.[kind]||''))return
  return save('document_notes',{...settings.value?.document_notes,[kind]:value})
}

function onSettingsChanged(event) {
  if (!['sub-client-finance','statement-subject'].includes(event.detail?.kind) || event.detail.subClientId !== props.subClientId) return
  if (!saving.value) void load()
  if (!switching.value) void loadParty()
}
watch(() => props.subClientId, () => { settings.value = null; void load() }, {immediate:true})
watch(() => [props.subClientId,props.month,props.period], loadParty, {immediate:true})
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,onSettingsChanged)
onBeforeUnmount(() => {
  controller?.abort()
  partyController?.abort()
  window.removeEventListener(invoicePartiesEvent,onSettingsChanged)
})
</script>

<style scoped>
.sub-client-finance-preferences { margin: 12px 0; padding: 12px; border: 1px solid var(--el-border-color-light); }
.sub-client-settlement-heading,.sub-client-settlement-party { display:flex; align-items:center; flex-wrap:wrap; gap:8px 12px; }
.sub-client-settlement-heading { justify-content:space-between; margin-bottom:10px; }
.sub-client-finance-fields { display:grid;grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr));gap:8px 16px; }
.sub-client-document-choice { display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;width:100%;margin-bottom:4px; }
.sub-client-document-choice .el-select { flex:1 1 110px; }
.sub-client-finance-fields :deep(.el-form-item) { margin-bottom: 0; }
h4 { margin: 0; }
small { margin-inline-start: 6px; color: var(--el-text-color-secondary); }
</style>
