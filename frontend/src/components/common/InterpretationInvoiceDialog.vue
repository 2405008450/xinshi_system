<template>
  <DraggableFormDialog :model-value="modelValue" class="interpretation-invoice-dialog"
    width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close
    :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="title" copyable-title
        :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
    </template>
    <div ref="body" v-loading="loading">
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <div v-if="scope">
        <el-button :disabled="!current||dirty||busy" @click="requestVisible=true">发送开票需求／查看回执</el-button>
        <el-descriptions v-if="subject" :column="1" border size="small"><el-descriptions-item label="开票主体">{{subject.name}}</el-descriptions-item><el-descriptions-item label="税号">{{subject.party?.tax_number||'未填写'}}</el-descriptions-item></el-descriptions>
        <p>{{[scope.client_name,scope.month,settlementModeLabels[scope.mode]].filter(Boolean).join(' · ')}}</p>
        <div v-if="scope.mode==='special'" class="invoice-actions">
          <el-button :disabled="!scope.month||busy" @click="navigate('statement')">特殊结算对账单</el-button>
          <el-button :disabled="busy" @click="navigate('price')">价格与收费</el-button>
        </div>
        <template v-if="grouped">
          <p>本期需开票项目的含税合计：{{formatFinanceAmounts(scope.totals)}}</p>
          <AppForm :model="selection" label-position="top" data-auto-draft="off">
            <el-form-item label="本次结算项目">
              <el-select :model-value="selection.id" :disabled="busy" @change="choose">
                <el-option v-for="item in scope.items" :key="item.id" :value="item.id" :label="`${item.order_no} · ${item.project_name||'-'}`" />
              </el-select>
            </el-form-item>
          </AppForm>
        </template>
        <CustomerInvoiceProfile v-if="current?.client_id&&canReadClients" :key="current.id"
          :client-id="current.client_id" :sub-client-id="current.sub_client_id" :can-write="canWriteClients" collapsible default-collapsed />
        <AppForm v-if="current" :model="draft" label-position="top" :disabled="!canWrite||saving" data-auto-draft="off">
          <div class="invoice-fields">
            <el-form-item label="订单号"><ReadonlyField :model-value="current.order_no" source="auto" /></el-form-item>
            <el-form-item label="是否需发票"><ReadonlyField :model-value="current.required?'需发票':'未勾选需发票'" source="auto" /></el-form-item>
            <el-form-item label="项目含税金额"><ReadonlyField :model-value="formatFinanceAmounts(current.totals)" source="auto" /></el-form-item>
            <el-form-item label="开票主体"><el-select v-model="draft.subject_key" clearable><el-option v-for="row in subjects" :key="row.key" :value="row.key" :label="row.name" /></el-select></el-form-item>
            <el-form-item label="发票状态"><el-select v-model="draft.invoice_status">
              <el-option v-for="option in invoiceStatusOptions" :key="option.value" v-bind="option" />
            </el-select></el-form-item>
          </div>
          <el-form-item label="发票附件及备注">
            <ScreenshotInput :key="current.id" v-model="draft.proofs" type="textarea" allow-invoice-files
              :invoice-order-no="current.order_no" :rows="3" :maxlength="20000"
              :disabled="!canWrite||saving" placeholder="拖入 PDF、OFD 发票或截图，也可填写开票备注"
              @uploading-change="uploading=$event" />
          </el-form-item>
        </AppForm>
      </div>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="requestClose">关闭</el-button>
      <el-button v-if="canWrite" type="primary" :loading="saving" :disabled="!current||loading||uploading||!dirty" @click="save">保存发票</el-button>
    </template>
  </DraggableFormDialog>
  <BusinessInvoiceRequestDialog v-if="requestVisible" v-model="requestVisible" :project-id="selection.id" :module="module" @saved="emit('saved')" />
</template>

<script setup>
import api from '@/api'
import BusinessInvoiceRequestDialog from './BusinessInvoiceRequestDialog.vue'
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getInterpretationInvoice,saveInterpretationInvoice} from '@/api/interpretationCustomerFinance'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {settlementModeLabels} from '@/utils/settlementModes'
import {invoiceStatusOptions} from '@/utils/documentRequirements'
import {formatFinanceAmounts} from '@/utils/interpretationCustomerFinance'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import ReadonlyField from './ReadonlyField.vue'
import ScreenshotInput from './ScreenshotInput.vue'

const props=defineProps({modelValue:Boolean,projectId:String,canWrite:Boolean,module:{type:String,default:'interpretation'}})
const emit=defineEmits(['update:modelValue','saved','statement','price'])
const requestVisible=ref(false),subjects=ref([])
const subject=computed(()=>subjects.value.find(row=>row.key===draft.subject_key))
const canWriteClients=hasPermission('clients:write')
const canReadClients=canWriteClients||hasPermission('clients:read')
const scope=ref(null),error=ref(''),loading=ref(false),saving=ref(false),uploading=ref(false),body=ref()
const selection=reactive({id:''}),draft=reactive({invoice_status:'unissued',proofs:'',subject_key:null,invoice_type:'electronic_normal',buyer_index:0})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const current=computed(()=>scope.value?.items.find(item=>item.id===selection.id))
const grouped=computed(()=>['monthly','sub_client'].includes(scope.value?.mode))
const title=computed(()=>{
  const heading={special:'特殊结算',monthly:'合并结算发票',sub_client:'子客户结算发票'}[scope.value?.mode]||'发票'
  return current.value ? `${heading} · ${current.value.order_no}` : heading
})
const dirty=computed(()=>!!current.value&&(draft.invoice_status!==current.value.invoice_status||draft.proofs!==current.value.proofs||draft.subject_key!==(current.value.subject_key||null)))
const busy=computed(()=>saving.value||uploading.value)
let controller
function assign(id){
  selection.id=id
  Object.assign(draft,{invoice_status:current.value?.invoice_status||'unissued',proofs:current.value?.proofs||'',subject_key:current.value?.subject_key||null,invoice_type:current.value?.invoice_type||'electronic_normal',buyer_index:current.value?.buyer_index||0})
}
async function canLeave(){
  if(busy.value)return false
  if(!dirty.value)return true
  try{await ElMessageBox.confirm('发票修改尚未保存，是否放弃？','确认关闭');return true}catch{return false}
}
async function choose(id){if(await canLeave())assign(id)}
async function beforeClose(done){if(await canLeave())done()}
async function requestClose(){if(await canLeave())emit('update:modelValue',false)}
async function navigate(action){
  if(!await canLeave())return
  emit('update:modelValue',false)
  emit(action)
}
async function save(){
  if(!current.value||busy.value||!props.canWrite)return
  const {id,revision}=current.value
  saving.value=true;error.value=''
  try{
    const item=await (props.module==='interpretation'?saveInterpretationInvoice(id,{...draft,revision}):api.put(`/business-finance/${props.module}/project/${id}/invoice`,{...draft,revision}))
    scope.value.items=scope.value.items.map(row=>row.id===id?item:row)
    assign(id)
    emit('saved')
    ElMessage.success('发票已保存')
  }catch(e){error.value=getLocalizedErrorMessage(e,'口译发票保存失败')}
  finally{saving.value=false}
}
watch(()=>[props.modelValue,props.projectId],async ([opened,id])=>{
  controller?.abort()
  if(!opened||!id)return
  const request=controller=new AbortController()
  clearFieldSearch()
  api.get('/invoice-parties/subjects').then(data=>subjects.value=data.items).catch(()=>{})
  scope.value=null;error.value='';loading.value=true
  try{
    const data=await (props.module==='interpretation'?getInterpretationInvoice(id,{signal:request.signal}):api.get(`/business-finance/${props.module}/project/${id}/invoice`,{signal:request.signal}))
    if(!request.signal.aborted){scope.value=data;assign(id)}
  }catch(e){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'口译发票加载失败')}
  finally{if(!request.signal.aborted)loading.value=false}
},{immediate:true})
onBeforeUnmount(()=>controller?.abort())
</script>

<style scoped>
:global(.interpretation-invoice-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.interpretation-invoice-dialog>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.interpretation-invoice-dialog>.el-dialog__header),:global(.interpretation-invoice-dialog>.el-dialog__footer){flex:none}
:global(.interpretation-invoice-dialog>.el-dialog__footer){border-top:1px solid var(--el-border-color-light)}
.invoice-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:0 12px}
.invoice-actions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
.invoice-actions>.el-button{margin:0}
</style>
