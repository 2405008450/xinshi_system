<template>
  <AppForm :model="draft" inline @submit.prevent="save">
    <el-form-item label="订单开票主体">
      <el-select v-model="draft.subject" style="width:150px">
        <el-option value="" label="沿用默认主体" />
        <el-option v-for="(label,key) in invoiceSubjectLabels" :key="key" :value="key" :label="label" />
      </el-select>
    </el-form-item>
    <el-form-item label="订单发票类型">
      <el-select v-model="draft.type" style="width:150px">
        <el-option value="" label="沿用客户默认" />
        <el-option v-for="(label,key) in invoiceTypeLabels" :key="key" :value="key" :label="label" />
      </el-select>
    </el-form-item>
    <el-form-item><el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">保存选择</el-button></el-form-item>
  </AppForm>
  <el-alert v-if="error" :title="error" type="error" :closable="false" />
</template>

<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import AppForm from './AppForm.vue'
import {invoiceSubjectLabels,invoiceTypeLabels,notifyInvoiceParties,saveOrderInvoiceSelections} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'

const props=defineProps({row:{type:Object,required:true},clientId:[String,Number]})
const draft=reactive({subject:'',type:''}),saving=ref(false),error=ref('')
const saved=computed(()=>props.row.invoice_selection)
const dirty=computed(()=>draft.subject!==(saved.value.order_subject_key||'')||draft.type!==(saved.value.order_invoice_type||''))
watch(saved,value=>{draft.subject=value.order_subject_key||'';draft.type=value.order_invoice_type||''},{immediate:true})
async function save(){
  if(!dirty.value||saving.value)return
  saving.value=true
  error.value=''
  try{
    await saveOrderInvoiceSelections([{project_id:props.row.root_id||props.row.id,revision:saved.value.revision,
      subject_key:draft.subject||null,invoice_type:draft.type||null}])
    notifyInvoiceParties({kind:'records',clientId:String(props.clientId)})
    ElMessage.success('订单开票选择已保存')
  }catch(e){error.value=getLocalizedErrorMessage(e,'保存订单开票选择失败')}
  finally{saving.value=false}
}
</script>
