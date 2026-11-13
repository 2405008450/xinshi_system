<template>
  <DraggableFormDialog :model-value="modelValue" class="project-invoice-dialog" width="min(800px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`发票 · ${display.orderNo||''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <CustomerInvoiceProfile v-if="info.clientId && !requestId" :client-id="info.clientId" :can-write="canWriteClient" />
      <AppForm ref="formRef" :model="form" label-position="top" :disabled="loading||saving||!canWrite">
        <el-form-item label="订单号"><ReadonlyField :model-value="display.orderNo||'保存项目后自动生成'" source="auto" /></el-form-item>
        <el-form-item label="客户"><ReadonlyField :model-value="display.clientName||'-'" source="auto" /></el-form-item>
        <el-form-item label="是否需发票"><ReadonlyField :model-value="display.required===null?'按计费口径自动判断':display.required?'需（含税）':'无需（不含税）'" source="auto" /><small>由价格与付款中的计费口径决定，此处不可修改。</small></el-form-item>
        <el-form-item label="项目计费金额"><ReadonlyField :model-value="formatTotals(display.totals)" source="auto" /></el-form-item>
        <el-form-item label="发票说明"><ReadonlyField :model-value="display.note||'-'" source="auto" /><small>说明在价格与付款中填写。</small></el-form-item>
        <el-form-item label="发票状态" prop="invoiceStatus" :rules="[{required:true,message:'请选择发票状态',trigger:'change'}]"><el-select v-model="form.invoiceStatus" style="width:100%"><el-option v-for="option in invoiceStatusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        <el-form-item label="发票截图及备注">
          <ScreenshotInput v-model="form.proofs" type="textarea" allow-invoice-files :invoice-request-id="requestId" :invoice-order-no="display.orderNo" :rows="3" :maxlength="20000"
            :disabled="loading || saving || !canWrite || !context.projectId" placeholder="拖入 PDF、OFD 发票或截图，也可填写开票备注"
            @uploading-change="onUploadingChange" @attachment-added="attachmentAdded = true" />
        </el-form-item>
        <p v-if="!context.projectId">保存项目后可保存发票信息。</p>
        <p>发票状态和附件按母订单保存，三个入口共用同一份记录。</p>
      </AppForm>
      <CustomerInvoiceRecords v-if="info.clientId && !requestId" :client-id="info.clientId" :allow-open="false" />
    </div>
    <template #footer>
      <el-button :disabled="saving || uploading" @click="close">关闭</el-button>
      <el-button v-if="canWrite" :type="canNotify ? 'default' : 'primary'" :loading="saving" :disabled="loading || uploading || !version || !context.projectId" @click="save()">保存发票</el-button>
      <el-button v-if="canNotify && canWrite" type="primary" :loading="saving" :disabled="loading || uploading || !version || !screenshotIds(form.proofs).length || form.invoiceStatus !== 'issued'" @click="save(true)">通知开票完成</el-button>
    </template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {invoiceStatusOptions} from '@/utils/documentRequirements'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
import ScreenshotInput from './ScreenshotInput.vue'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import CustomerInvoiceRecords from './CustomerInvoiceRecords.vue'
import {notifyInvoiceParties} from '@/api/invoiceParties'
import {screenshotIds} from '@/utils/screenshotReferences'
const props=defineProps({modelValue:Boolean,context:{type:Object,default:()=>({})},requestId:String,canDeliver:Boolean})
const emit=defineEmits(['update:modelValue','saved'])
const canWrite=computed(()=>props.requestId ? props.canDeliver : hasPermission('projects:write')||hasPermission('finance:write'))
const invoiceUrl=computed(()=>props.requestId
  ? `/invoice-workflow/requests/${props.requestId}/projects/${props.context.projectId}/invoice`
  : `/translation-customer-finance/project/${props.context.projectId}/invoice`)
const canWriteClient=hasPermission('clients:write')
const body=ref(),formRef=ref(),loading=ref(false),saving=ref(false),error=ref(''),info=ref({}),form=reactive({invoiceStatus:'unissued',proofs:''})
const uploading = ref(false)
const attachmentAdded = ref(false)
const canNotify = computed(() => Boolean(props.requestId ? props.canDeliver : info.value.canNotifyRequester))
let confirmingCompletion = false
async function onUploadingChange(value) {
  uploading.value = value
  if (value || !attachmentAdded.value || !props.modelValue || confirmingCompletion) return
  attachmentAdded.value = false
  confirmingCompletion = true
  const notify = canNotify.value
  try {
    await ElMessageBox.confirm(notify ? '是否确认已开票，并通知需求人？' : '是否确认已开票？',
      '确认开票完成', {confirmButtonText:notify ? '确认并通知' : '确认已开票', cancelButtonText:'继续编辑'})
    if (!props.modelValue) return
    form.invoiceStatus = 'issued'
    await save(notify)
  } catch {
    // 继续编辑时保留已上传的附件。
  } finally {
    confirmingCompletion = false
  }
}
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const camel=data=>Object.fromEntries(Object.entries(data).map(([key,value])=>[key.replace(/_([a-z])/g,(_,letter)=>letter.toUpperCase()),value]))
const display=computed(()=>({...info.value,...props.context.preview}))
const formatTotals=totals=>Object.entries(totals||{}).map(([currency,amount])=>`${currency} ${Number(amount).toFixed(2)}`).join('；')||'-'
let original='',version='',sequence=0,controller
const signature=()=>JSON.stringify(form)
async function load(){const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';version='';clearFieldSearch();Object.assign(form,{invoiceStatus:'unissued',proofs:''});info.value={};try{if(!props.context.projectId)return;const data=camel(await api.get(invoiceUrl.value,{params:{order_id:props.context.orderId||undefined},signal:controller.signal}));if(current!==sequence)return;info.value=data;version=data.version;Object.assign(form,{invoiceStatus:data.invoiceStatus,proofs:data.proofs||''})}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'发票信息加载失败')}finally{if(current===sequence){original=signature();loading.value=false}}}
async function save(deliver = false) {
  if (!canWrite.value || loading.value || saving.value || uploading.value || !version) return
  if (!await formRef.value?.validate().catch(()=>false) || saving.value || uploading.value) return
  saving.value = true
  error.value = ''
  let savedProjectId
  try {
    const projectId = props.context.projectId
    const data = camel(await api.put(invoiceUrl.value, {
      version, invoice_status:form.invoiceStatus, proofs:form.proofs,
    }, {params:{order_id:props.context.orderId || undefined}}))
    version = data.version
    original = signature()
    savedProjectId = projectId
    if (deliver) {
      const notifyUrl = props.requestId
        ? `/invoice-workflow/requests/${props.requestId}/projects/${projectId}/deliver`
        : `/invoice-workflow/projects/${projectId}/notify-issued`
      await api.post(notifyUrl, {version})
    }
    emit('saved', data)
    ElMessage.success(deliver ? '开票完成通知已发送' : '发票信息已保存')
    emit('update:modelValue', false)
  } catch (e) {
    error.value = getLocalizedErrorMessage(e, deliver ? '发票发送失败' : '发票保存失败')
  } finally {
    if (savedProjectId) {
      notifyInvoiceParties({kind:'records', clientId:String(info.value.clientId || ''), projectId:savedProjectId})
      window.dispatchEvent(new CustomEvent('translation-invoice-changed', {detail:{projectId:savedProjectId}}))
    }
    saving.value = false
  }
}
async function beforeClose(done){if(saving.value||uploading.value)return;if(signature()!==original){try{await ElMessageBox.confirm('发票信息有未保存修改，是否放弃？','关闭发票',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}done()}
function close(){void beforeClose(()=>emit('update:modelValue',false))}
watch(()=>[props.modelValue,props.context.projectId,props.context.orderId],()=>{if(props.modelValue)void load();else{sequence++;controller?.abort()}},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
:global(.project-invoice-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-invoice-dialog>.el-dialog__header),:global(.project-invoice-dialog>.el-dialog__footer){flex:none}:global(.project-invoice-dialog>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}.project-invoice-dialog small{width:100%;color:var(--el-text-color-secondary)}
</style>
