<template>
  <section class="customer-invoice-profile" v-loading="loading">
    <div class="invoice-profile-heading"><strong>客户开（专）票信息</strong><el-button v-if="clientId&&canWrite" link type="primary" :disabled="loading||!!error" @click="edit">编辑客户开票信息</el-button><el-button v-if="clientId" link @click="load">刷新</el-button></div>
    <p v-if="!clientId">保存客户后可维护开票资料。</p>
    <template v-else>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-else-if="data"><p>发票类型：{{kindLabel[data.invoice_kind]||'待选择'}}；开票主体：{{data.subject?.name||'待选择'}}</p><InvoicePartyDetails :party="data.party" /><template v-if="data.subject"><strong>开票主体资料 · {{data.subject.name}}</strong><InvoicePartyDetails :party="data.subject.party" /><small>主体信息在组织架构对应办公室维护，此处同步显示。</small></template></template>
    </template>
    <DraggableFormDialog v-model="visible" class="invoice-party-editor" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="客户开票信息" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body"><AppForm ref="formRef" :model="form" label-position="top" :disabled="saving"><el-form-item label="发票类型"><el-select v-model="form.invoice_kind" clearable placeholder="待选择"><el-option label="增值税普通发票" value="normal" /><el-option label="增值税专用发票" value="special" /></el-select></el-form-item><el-form-item label="开票主体"><el-select v-model="form.subject_key" clearable placeholder="请选择开票主体" style="width:100%"><el-option v-for="item in subjects" :key="item.key" :label="item.name" :value="item.key" /></el-select></el-form-item><InvoicePartyFields v-model="form.party" /></AppForm><el-alert v-if="saveError" :title="saveError" type="error" :closable="false" /></div>
      <template #footer><el-button :disabled="saving" @click="close">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存客户开票信息</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {ref,reactive,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getClientInvoiceProfile,saveClientInvoiceProfile,getInvoiceSubjects,emptyInvoiceParty,connectInvoiceParties,notifyInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import InvoicePartyFields from './InvoicePartyFields.vue'
import InvoicePartyDetails from './InvoicePartyDetails.vue'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const data=ref(null),subjects=ref([]),loading=ref(false),error=ref(''),visible=ref(false),saving=ref(false),saveError=ref(''),formRef=ref(),body=ref()
const kindLabel={normal:'增值税普通发票',special:'增值税专用发票'}
const form=reactive({party:emptyInvoiceParty(),subject_key:null,invoice_kind:null})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const source=`client-invoice-${Math.random().toString(36).slice(2)}`
let seq=0,alive=true,revision=0,original=''
const signature=()=>JSON.stringify(form)
async function load(){const current=++seq;if(!props.clientId){data.value=null;return}loading.value=true;error.value='';try{const value=await getClientInvoiceProfile(props.clientId);if(alive&&current===seq)data.value=value}catch(e){if(alive&&current===seq)error.value=getLocalizedErrorMessage(e,'客户开票信息加载失败')}finally{if(current===seq)loading.value=false}}
async function edit(){saveError.value='';try{subjects.value=(await getInvoiceSubjects()).items||[];const fresh=await getClientInvoiceProfile(props.clientId);data.value=fresh;revision=fresh.revision;Object.assign(form,{party:{...emptyInvoiceParty(),...fresh.party},subject_key:fresh.subject_key,invoice_kind:fresh.invoice_kind});original=signature();clearFieldSearch();visible.value=true}catch(e){ElMessage.error(getLocalizedErrorMessage(e,'开票信息加载失败'))}}
async function save(){if(saving.value||!await formRef.value?.validate().catch(()=>false))return;saving.value=true;try{data.value=await saveClientInvoiceProfile(props.clientId,{revision,party:form.party,subject_key:form.subject_key||null,invoice_kind:form.invoice_kind||null});visible.value=false;original=signature();notifyInvoiceParties({kind:'client',clientId:String(props.clientId),source});ElMessage.success('客户开票信息已保存，与发票窗口同步')}catch(e){saveError.value=getLocalizedErrorMessage(e,'开票信息保存失败')}finally{saving.value=false}}
async function beforeClose(done){if(saving.value)return;if(signature()!==original){try{await ElMessageBox.confirm('开票资料有未保存修改，是否放弃？','关闭客户开票信息',{type:'warning'})}catch{return}}done()}
function close(){void beforeClose(()=>visible.value=false)}
function changed(event){if(event.detail?.source===source)return;if(event.detail?.kind==='subject'||String(event.detail?.clientId)===String(props.clientId))void load()}
watch(()=>props.clientId,()=>{visible.value=false;void load()},{immediate:true})
onMounted(()=>{connectInvoiceParties();window.addEventListener(invoicePartiesEvent,changed)})
onBeforeUnmount(()=>{alive=false;seq++;window.removeEventListener(invoicePartiesEvent,changed)})
</script>
<style scoped>
.invoice-profile-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.customer-invoice-profile p,.customer-invoice-profile small{font-size:12px;color:var(--el-text-color-secondary)}.customer-invoice-profile{margin:12px 0}.customer-invoice-profile p{overflow-wrap:anywhere}:global(.invoice-party-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.invoice-party-editor>.el-dialog__header),:global(.invoice-party-editor>.el-dialog__footer){flex:none}:global(.invoice-party-editor>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
</style>
