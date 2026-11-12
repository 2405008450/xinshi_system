<template>
  <div class="finance-document-requirements">
    <el-form-item label="是否需报价单" prop="quotationRequired" data-field-key="quotationRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.quotationRequired" @update:model-value="update('quotationRequired',$event)">需</el-checkbox><el-button v-if="modelValue.quotationRequired" link type="primary" @click="$emit('quotation')">打开报价单</el-button></div><el-input :model-value="notes.quotation" size="small" placeholder="说明" aria-label="报价单说明" data-dialog-field-search-label="报价单说明" :maxlength="2000" clearable @update:model-value="updateNote('quotation',$event)" /></el-form-item>
    <el-form-item label="是否需对账单" prop="statementRequired" data-field-key="statementRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.statementRequired" :disabled="confirmingStatement" @update:model-value="update('statementRequired',$event)">需</el-checkbox><el-tag v-if="unknownDefault" type="warning" size="small" effect="plain">客户默认未知</el-tag><el-button v-if="modelValue.statementRequired" link type="primary" @click="$emit('statement')">打开对账单</el-button></div><el-input :model-value="notes.statement" size="small" placeholder="说明" aria-label="对账单说明" data-dialog-field-search-label="对账单说明" :maxlength="2000" clearable @update:model-value="updateNote('statement',$event)" /></el-form-item>
    <el-form-item label="是否需发票" data-field-key="invoiceRequired"><div class="finance-document-choice"><ReadonlyField :model-value="invoiceNeeded===null?'按计费口径自动判断':invoiceNeeded?'需':'无需'" source="auto" aria-label="是否需发票" /><el-button v-if="invoiceNeeded" link type="primary" @click="$emit('invoice')">发票</el-button></div><el-input :model-value="notes.invoice" size="small" placeholder="说明" aria-label="发票说明" data-dialog-field-search-label="发票说明" :maxlength="2000" clearable @update:model-value="updateNote('invoice',$event)" /></el-form-item>
  </div>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {confirmStatementRequirement} from '@/utils/confirmStatementRequirement'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {getStatementRequirementContext} from '@/api/translationCustomerFinance'
import ReadonlyField from './ReadonlyField.vue'
import {documentNotesForm,invoiceRequirement} from '@/utils/documentRequirements'
const props=defineProps({modelValue:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','quotation','statement','invoice'])
const notes=computed(()=>documentNotesForm(props.modelValue.documentNotes))
const invoiceNeeded=computed(()=>invoiceRequirement(props.modelValue))
const confirmingStatement=ref(false)
const unknownDefault=ref(false)
watch(()=>[props.modelValue.rootId,props.modelValue.clientId],async ([projectId,clientId],_,onCleanup)=>{
  let current=true
  onCleanup(()=>{current=false})
  unknownDefault.value=false
  if(!projectId&&!clientId)return
  try{
    const context=await getStatementRequirementContext({project_id:projectId||undefined,client_id:clientId||undefined})
    if(current)unknownDefault.value=!!context.clientId&&context.statementDefault==='unknown'
  }catch{/* 确认调整时重新读取客户设置。 */}
},{immediate:true})
async function update(field,value){
  if(field!=='statementRequired'){
    emit('update:modelValue',{...props.modelValue,[field]:value})
    return
  }
  if(confirmingStatement.value)return
  const order=props.modelValue
  confirmingStatement.value=true
  try{
    const result=await confirmStatementRequirement({projectId:order.rootId,clientId:order.clientId,billingMonth:order.billingMonth,value})
    if(result && props.modelValue.rootId===order.rootId && props.modelValue.clientId===order.clientId){
      emit('update:modelValue',{...props.modelValue,statementRequired:value,statementRequiredDirty:true,statementSync:result.scope,statementCustomerSync:result.customerScope})
    }
  }catch(error){ElMessage.error(getLocalizedErrorMessage(error,'读取客户对账单设置失败'))}
  finally{confirmingStatement.value=false}
}
function updateNote(field,value){emit('update:modelValue',{...props.modelValue,documentNotes:{...notes.value,[field]:value},documentNotesDirty:true})}
</script>
<style scoped>
.finance-document-requirements{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px 20px;margin-bottom:16px}.finance-document-requirements :deep(.el-form-item){min-width:0;margin-bottom:0}.finance-document-choice{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-height:32px;width:100%;margin-bottom:6px}.finance-document-choice>.el-input{width:120px;max-width:100%}
</style>
