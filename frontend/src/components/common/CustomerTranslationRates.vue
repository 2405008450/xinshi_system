<template>
  <div class="customer-reference-rates">
    <el-button :disabled="!clientId" @click="open">{{buttonLabel}}</el-button><small v-if="!clientId">请先保存客户，再维护参考价</small>
    <DraggableFormDialog v-model="visible" append-to-body class="customer-reference-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="subClientId ? '子客户语种参考价' : '客户语种参考价'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body" v-loading="loading||saving"><p class="rate-sync-help">参考价保存后自动更新匹配的订单。操作时间、来源和变更前后的单价可在下方查看。</p>
        <el-alert v-if="loadError" :title="loadError" type="error" :closable="false">
          <el-button link type="primary" :disabled="loading" @click="loadRates">重新加载</el-button>
        </el-alert>
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        <AppForm v-if="ready" ref="form" :model="draft" :disabled="!canWrite||saving||loading" label-position="top">
          <CustomerTranslationPriceEditor v-model="draft.prices" reference-mode :readonly="!canWrite" :disabled="saving" />
        </AppForm>
        <el-collapse v-model="expandedSections">
          <el-collapse-item :title="historyTotal === null ? '参考价修改记录' : `参考价修改记录（${historyTotal}）`" name="history">
            <div v-loading="historyLoading" class="reference-rate-history">
              <el-alert v-if="historyError" :title="historyError" type="error" :closable="false">
                <el-button link type="primary" @click="loadHistory">重新加载记录</el-button>
              </el-alert>
              <p v-else-if="historyTotal === 0">暂无修改记录</p>
              <el-collapse v-if="history.length">
                <el-collapse-item v-for="event in history" :key="event.id" :title="historyTitle(event)">
                  <div v-for="[label,items] in [['变更前',event.before],['变更后',event.after]]" :key="label">
                    <strong>{{ label }}</strong>
                    <p v-if="!items?.length">暂无单价</p>
                    <p v-for="(item,index) in items" :key="item.id||index">{{item.languagePair}} · {{historyPrice(item)}} · {{basisLabel(item.metric)}}</p>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-pagination v-if="historyTotal > 0" v-model:current-page="historyPage" :page-size="10"
                :total="historyTotal" layout="total, prev, pager, next" @current-change="loadHistory" />
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite" type="primary" :disabled="!ready||loading" :loading="saving" @click="save">保存参考价</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {taxPriceForm,taxPriceSummary} from '@/utils/taxPrices'
import {ref,watch,onBeforeUnmount,onMounted} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import CustomerTranslationPriceEditor from './CustomerTranslationPriceEditor.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getCustomerTranslationRates,saveCustomerTranslationRates,getCustomerTranslationRateHistory} from '@/api/translationCustomerFinance'
import {ratePayload,newCustomerRate} from '@/utils/customerTranslationRates'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const emit=defineEmits(['saved'])
const props=defineProps({subClientId:String,clientId:{type:[String,Number],default:''},canWrite:Boolean,openOnMount:Boolean,buttonLabel:{type:String,default:'客户语种单价'}})
const visible=ref(false),loading=ref(false),saving=ref(false),ready=ref(false),draft=ref({prices:[]}),history=ref([]),form=ref(),body=ref()
const loadError=ref(''),saveError=ref(''),historyError=ref(''),historyLoading=ref(false)
const historyTotal=ref(null),historyPage=ref(1),expandedSections=ref([])
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let version='',original='[]',client='',sequence=0
let rateRequest, historyRequest
const signature=()=>JSON.stringify(draft.value.prices.map(ratePayload))
function apply(data){version=data.version;ready.value=data.ready;draft.value.prices=data.items.map(row=>({...newCustomerRate(row.languagePair),...row,taxPrices:taxPriceForm(row.taxPrices),amount:Number(row.amount),unitSize:Number(row.unitSize)}));original=signature()}
function applyHistory(data){history.value=data.items||[];historyTotal.value=data.total??history.value.length}
const historyActions = {
  manual_entry: '人工登记',
  manual_project_sync: '从项目人工同步参考价',
  automatic_order_sync: '自动同步至项目',
  manual_order_sync: '人工同步至项目',
}
function historyTitle(event) {
  const action = historyActions[event.action] ?? (event.origin?.startsWith('sub:')
    ? '历史记录（同步方式未记录）'
    : {project:'项目同步',order_rates:'订单单价变更'}[event.origin] ?? '客户资料')
  return [formatTime(event.createdAt), action, event.orderNo, event.actorName,
    event.revision && `第${event.revision}版`].filter(Boolean).join(' · ')
}
function historyPrice(item) {
  const size = Number(item.unitSize)
  return taxPriceSummary(item.taxPrices, item.currency, String(size), false)
    || `${item.currency} ${item.amount ?? '—'} / ${size}`
}
async function loadHistory() {
  if (!visible.value || !expandedSections.value.includes('history')) return
  historyRequest?.abort()
  const request = historyRequest = new AbortController()
  historyLoading.value = true
  historyError.value = ''
  try {
    const data = await getCustomerTranslationRateHistory(client, { page: historyPage.value }, { signal: request.signal, params: { sub_client_id: props.subClientId || undefined } })
    if (!request.signal.aborted) applyHistory(data)
  } catch (error) {
    if (!request.signal.aborted) historyError.value = getLocalizedErrorMessage(error, '修改记录加载失败')
  } finally {
    if (!request.signal.aborted) historyLoading.value = false
  }
}

async function loadRates() {
  rateRequest?.abort()
  const request = rateRequest = new AbortController()
  const target = client
  const config = { signal: request.signal, timeout: 15000, params: { sub_client_id: props.subClientId || undefined } }
  loading.value = true
  loadError.value = ''
  try {
    let data
    try {
      data = await getCustomerTranslationRates(target, config)
    } catch (error) {
      // 排队超时返回 Retry-After；只重试读取，不自动重发保存。
      if (error.response?.status !== 503 || error.response?.headers?.['retry-after'] !== '1') throw error
      await new Promise(resolve => setTimeout(resolve, 1000))
      if (request.signal.aborted) return
      data = await getCustomerTranslationRates(target, config)
    }
    if (request.signal.aborted) return
    apply(data)
    if (!data.ready) loadError.value = '客户语种单价存储尚未初始化'
  } catch (error) {
    if (!request.signal.aborted) loadError.value = getLocalizedErrorMessage(error, '参考价加载失败')
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

function open() {
  if (!props.clientId || visible.value) return
  client = props.clientId
  visible.value = true
  void loadRates()
}
async function close(done){if(saving.value)return;if(signature()!==original&&props.canWrite){try{await ElMessageBox.confirm('参考价有未保存修改，确定放弃？','关闭参考价',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}if(typeof done==='function')done();else visible.value=false}
async function save(){if(!props.canWrite||!ready.value||saving.value||!await form.value?.validate().catch(()=>false))return;const target=client,current=sequence;saving.value=true;saveError.value='';try{const data=await saveCustomerTranslationRates(target,{version,items:draft.value.prices.map(ratePayload)},{params:{sub_client_id:props.subClientId||undefined}});if(current!==sequence)return;apply(data);historyPage.value=1;historyTotal.value=null;window.dispatchEvent(new CustomEvent('translation-finance-changed',{detail:{clientId:String(target),fromCustomer:true}}));emit('saved');ElMessage.success('已保存客户参考价，并同步至匹配的订单');void loadHistory()}catch(e){if(current===sequence)saveError.value=getLocalizedErrorMessage(e,'保存参考价失败')}finally{saving.value=false}}
function resetDialog() {
  sequence++
  rateRequest?.abort()
  historyRequest?.abort()
  loading.value = false
  historyLoading.value = false
  ready.value = false
  draft.value.prices = []
  original = '[]'
  version = ''
  loadError.value = saveError.value = historyError.value = ''
  history.value = []
  historyTotal.value = null
  historyPage.value = 1
  expandedSections.value = []
}
watch(visible, value => { if (!value) resetDialog() }, { flush: 'sync' })
watch(()=>[props.clientId,props.subClientId],()=>{visible.value=false})
watch(expandedSections, sections => {
  if (sections.includes('history')) void loadHistory()
})
function refreshOrderHistory(event){
  if(visible.value&&event.detail?.clientId===String(client)){historyTotal.value=null;void loadHistory()}
}
onBeforeUnmount(()=>{resetDialog();window.removeEventListener('customer-order-finance-saved',refreshOrderHistory)})
onMounted(()=>{
  window.addEventListener('customer-order-finance-saved',refreshOrderHistory)
  if(props.openOnMount)void open()
})
</script>
<style scoped>
.reference-rate-history { min-height: 36px; }
.customer-reference-rates>small,.rate-sync-help{color:#64748b;font-size:12px}.customer-reference-rates>small{margin-left:8px}:global(.customer-reference-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-reference-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.customer-reference-dialog .el-dialog__header),:global(.customer-reference-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-reference-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
</style>
