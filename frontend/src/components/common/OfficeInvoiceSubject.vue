<template>
  <section v-if="subject" class="office-invoice-subject">
    <div><strong>{{subject.name}}</strong><el-tag size="small" :type="subject.complete?'success':'info'">{{subject.complete?'资料已填写':'开票信息待填写'}}</el-tag></div>
    <el-button link type="primary" @click="edit">{{canWrite?'填写 / 编辑开票信息':'查看开票信息'}}</el-button>
    <DraggableFormDialog v-model="visible" class="invoice-party-editor" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${subject.name} · 开票信息`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body"><AppForm v-if="canWrite" ref="formRef" :model="form" label-position="top" :disabled="saving"><InvoicePartyFields v-model="form.party" title-readonly /></AppForm><InvoicePartyDetails v-else :party="subject.party" /><el-alert v-if="error" :title="error" type="error" :closable="false" /></div>
      <template #footer><el-button :disabled="saving" @click="close">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" @click="save">保存主体开票信息</el-button></template>
    </DraggableFormDialog>
  </section>
  <el-alert v-else-if="error" :title="error" type="error" :closable="false" />
</template>
<script setup>
import {ref,reactive,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getInvoiceSubjects,saveInvoiceSubject,emptyInvoiceParty,notifyInvoiceParties,connectInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import InvoicePartyFields from './InvoicePartyFields.vue'
import InvoicePartyDetails from './InvoicePartyDetails.vue'
const props=defineProps({city:String,officeId:String,canWrite:Boolean})
const subject=ref(null),visible=ref(false),saving=ref(false),error=ref(''),body=ref(),formRef=ref(),form=reactive({party:emptyInvoiceParty()})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let alive=true,revision=0,original=''
const source=`office-invoice-${Math.random().toString(36).slice(2)}`
const signature=()=>JSON.stringify(form.party)
async function load(){try{const values=(await getInvoiceSubjects()).items||[];if(alive){subject.value=values.find(item=>item.office_id===props.officeId||props.city?.startsWith(item.city))||null;error.value=''}}catch(e){if(alive)error.value=getLocalizedErrorMessage(e,'主体开票信息加载失败')}}
async function edit(){await load();if(!subject.value)return;Object.assign(form,{party:{...emptyInvoiceParty(),...subject.value.party}});revision=subject.value.revision;original=signature();clearFieldSearch();visible.value=true}
async function save(){if(saving.value||!await formRef.value?.validate().catch(()=>false))return;saving.value=true;try{subject.value=await saveInvoiceSubject(subject.value.key,{revision,party:form.party});visible.value=false;notifyInvoiceParties({kind:'subject',source});ElMessage.success('主体开票信息已保存，客户及发票窗口同步更新')}catch(e){error.value=getLocalizedErrorMessage(e,'主体开票信息保存失败')}finally{saving.value=false}}
async function beforeClose(done){if(saving.value)return;if(props.canWrite&&signature()!==original){try{await ElMessageBox.confirm('主体资料有未保存修改，是否放弃？','关闭主体开票信息',{type:'warning'})}catch{return}}done()}
function close(){void beforeClose(()=>visible.value=false)}
function changed(event){if(event.detail?.kind==='subject'&&event.detail.source!==source)void load()}
watch(()=>props.city,load,{immediate:true})
onMounted(()=>{connectInvoiceParties();window.addEventListener(invoicePartiesEvent,changed)})
onBeforeUnmount(()=>{alive=false;window.removeEventListener(invoicePartiesEvent,changed)})
</script>
<style scoped>.office-invoice-subject{border-top:1px solid var(--el-border-color-lighter);margin-top:12px;padding-top:12px}.office-invoice-subject>div{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.office-invoice-subject strong{font-size:13px;overflow-wrap:anywhere}</style>
