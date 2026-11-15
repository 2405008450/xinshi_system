<template>
  <section class="invoice-subject">
    <div><strong>{{subject.name}}</strong><el-tag size="small" :type="subject.complete?'success':'info'">{{subject.complete?'资料已填写':'开票信息待填写'}}</el-tag></div>
    <el-button link type="primary" @click="edit">{{canWrite?'填写 / 编辑开票信息':'查看开票信息'}}</el-button>
    <DraggableFormDialog v-model="visible" class="invoice-party-editor" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${subject.name} · 开票信息`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body"><AppForm v-if="canWrite" ref="formRef" :model="form" label-position="top" :disabled="saving"><InvoicePartyFields v-model="form.party" title-readonly /></AppForm><InvoicePartyDetails v-else :party="subject.party" /><el-alert v-if="error" :title="error" type="error" :closable="false" /></div>
      <template #footer><el-button :disabled="saving" @click="close">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" @click="save">保存主体开票信息</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {ref,reactive} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {saveInvoiceSubject,emptyInvoiceParty,notifyInvoiceParties} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import InvoicePartyFields from './InvoicePartyFields.vue'
import InvoicePartyDetails from './InvoicePartyDetails.vue'
const props=defineProps({subject:{type:Object,required:true},canWrite:Boolean})
const visible=ref(false),saving=ref(false),error=ref(''),body=ref(),formRef=ref(),form=reactive({party:emptyInvoiceParty()})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let revision=0,original=''
const signature=()=>JSON.stringify(form.party)
function edit(){
  form.party={...emptyInvoiceParty(),...props.subject.party}
  revision=props.subject.revision
  original=signature()
  error.value=''
  clearFieldSearch()
  visible.value=true
}
async function save(){
  if(saving.value||!await formRef.value?.validate().catch(()=>false))return
  saving.value=true
  error.value=''
  try{
    await saveInvoiceSubject(props.subject.key,{revision,party:form.party})
    visible.value=false
    notifyInvoiceParties({kind:'subject'})
    ElMessage.success('主体开票信息已保存，客户及发票窗口同步更新')
  }catch(e){
    error.value=getLocalizedErrorMessage(e,'主体开票信息保存失败')
    if(e.response?.status===409)notifyInvoiceParties({kind:'subject'})
  }finally{
    saving.value=false
  }
}
async function beforeClose(done){if(saving.value)return;if(props.canWrite&&signature()!==original){try{await ElMessageBox.confirm('主体资料有未保存修改，是否放弃？','关闭主体开票信息',{type:'warning'})}catch{return}}done()}
function close(){void beforeClose(()=>visible.value=false)}
</script>
<style scoped>
.invoice-subject{padding:12px;border:1px solid var(--el-border-color-lighter);border-radius:var(--el-border-radius-base)}
.invoice-subject>div{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.invoice-subject strong{overflow-wrap:anywhere}
</style>
