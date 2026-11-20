<template>
  <div class="finance-document-layout">
    <div class="finance-document-requirements" :class="{'has-customer-settings':modelValue.clientId}">
      <el-form-item label="是否需报价单" prop="quotationRequired" data-field-key="quotationRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.quotationRequired" @update:model-value="update('quotationRequired',$event)">需</el-checkbox><el-button v-if="modelValue.quotationRequired" link type="primary" @click="$emit('quotation')">打开报价单</el-button></div><el-input :model-value="notes.quotation" size="small" placeholder="说明" aria-label="报价单说明" data-dialog-field-search-label="报价单说明" :maxlength="2000" clearable @update:model-value="updateNote('quotation',$event)" /></el-form-item>
      <el-form-item label="是否需对账单" prop="statementRequired" data-field-key="statementRequired"><div class="finance-document-choice"><el-checkbox v-model="statementChecked" :disabled="confirmingStatement" @change="update('statementRequired',$event)">需</el-checkbox><el-tag v-if="modelValue.paymentMethod==='special' && unknownDefault" type="warning" size="small" effect="plain">客户默认未知</el-tag><el-button v-if="modelValue.statementRequired" link type="primary" @click="$emit('statement')">打开对账单</el-button></div><el-input :model-value="notes.statement" size="small" placeholder="说明" aria-label="对账单说明" data-dialog-field-search-label="对账单说明" :maxlength="2000" clearable @update:model-value="updateNote('statement',$event)" /></el-form-item>
      <el-form-item label="是否需发票" data-field-key="invoiceRequired"><div class="finance-document-choice"><el-select v-if="editableInvoice" :model-value="modelValue.invoiceRequirementOverride ?? 'auto'" aria-label="是否需发票" @change="update('invoiceRequirementOverride',$event)"><el-option label="需" :value="true" /><el-option label="无需" :value="false" /><el-option v-if="modelValue.invoiceRequirementOverride==null" :label="invoiceNeeded===null?'按计费口径自动判断':invoiceNeeded?'需（计费口径）':'无需（计费口径）'" value="auto" /></el-select><ReadonlyField v-else :model-value="invoiceNeeded===null?'按计费口径自动判断':invoiceNeeded?'需':'无需'" source="auto" aria-label="是否需发票" /><el-button v-if="invoiceNeeded" link type="primary" @click="$emit('invoice')">发票</el-button></div><el-input :model-value="notes.invoice" size="small" placeholder="说明" aria-label="发票说明" data-dialog-field-search-label="发票说明" :maxlength="2000" clearable @update:model-value="updateNote('invoice',$event)" /></el-form-item>
      <div v-if="modelValue.clientId" class="document-customer-settings" data-dialog-field-search-label="客户单据设置同步">
        <el-button link type="primary" @click="emit('customer-settings')">{{usesSubClient ? '客户管理 → 财务信息 → 笔译 → 子客户结算设置' : '客户管理 → 财务信息 → 笔译 → 对账单设置'}}</el-button>
        <div v-for="[field,label] in documentFields" :key="field" class="document-sync-row">
          <span>{{label}}</span>
          <el-tag v-if="modelValue.customerDocumentSources?.[field]" size="small" type="info">来自客户管理</el-tag>
          <small v-else>保存后自动双向同步客户或子客户设置</small>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {confirmStatementRequirement} from '@/utils/confirmStatementRequirement'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {getStatementRequirementContext} from '@/api/translationCustomerFinance'
import ReadonlyField from './ReadonlyField.vue'
import {documentNotesForm,invoiceRequirement,usesSubClientDocumentSettings} from '@/utils/documentRequirements'
const props=defineProps({modelValue:{type:Object,required:true},persistStatement:Function,editableInvoice:Boolean})
const emit=defineEmits(['update:modelValue','quotation','statement','invoice','customer-settings'])
const documentFields=[['quotationRequired','报价单'],['statementRequired','对账单'],['invoiceRequired','发票']]
const notes=computed(()=>documentNotesForm(props.modelValue.documentNotes))
const invoiceNeeded=computed(()=>invoiceRequirement(props.modelValue))
const confirmingStatement=ref(false)
const usesParentSettings=computed(()=>!!props.modelValue.subClientId && props.modelValue.settlementParty==='client')
const usesSubClient=computed(()=>usesSubClientDocumentSettings(props.modelValue) && !!props.persistStatement)
const statementChecked=ref(props.modelValue.statementRequired)
watch(()=>props.modelValue.statementRequired,value=>{statementChecked.value=value})
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
    if(field==='invoiceRequirementOverride'&&typeof value!=='boolean')return
    const updates=field==='invoiceRequirementOverride'&&usesSubClient.value?{subClientInvoiceRequired:value}:{}
    emit('update:modelValue',{...props.modelValue,...updates,[field]:value})
    return
  }
  if(confirmingStatement.value)return
  const order=props.modelValue
  if(usesSubClient.value){
    confirmingStatement.value=true
    try{await props.persistStatement(value,{})}
    finally{statementChecked.value=props.modelValue.statementRequired;confirmingStatement.value=false}
    return
  }
  if(order.paymentMethod==='special' && order.id!==order.rootId){
    emit('update:modelValue',{...order,statementRequired:value,statementRequiredDirty:true})
    return
  }
  confirmingStatement.value=true
  try{
    const result=await confirmStatementRequirement({projectId:order.rootId,clientId:order.clientId,billingMonth:order.billingMonth,value,syncCustomerDefault:false})
    if(result && props.modelValue.rootId===order.rootId && props.modelValue.clientId===order.clientId){
      if(props.persistStatement){
        await props.persistStatement(value,result)
        return
      }
      emit('update:modelValue',{...props.modelValue,statementRequired:value,statementRequiredDirty:true,statementSync:result.scope,statementCustomerSync:result.customerScope})
    }
  }catch(error){ElMessage.error(getLocalizedErrorMessage(error,'读取客户对账单设置失败'))}
  finally{statementChecked.value=props.modelValue.statementRequired;confirmingStatement.value=false}
}
function updateNote(field,value){emit('update:modelValue',{...props.modelValue,documentNotes:{...notes.value,[field]:value},documentNotesDirty:true})}
</script>
<style scoped>
.finance-document-layout { container: document-layout / inline-size; }
.finance-document-requirements {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
  gap: 12px 20px;
  margin-bottom: 16px;
}
.finance-document-requirements :deep(.el-form-item){min-width:0;margin-bottom:0}.finance-document-choice{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-height:32px;width:100%;margin-bottom:6px}.finance-document-choice>.el-input{width:120px;max-width:100%}
.document-customer-settings{grid-column:1/-1;min-width:0}.document-customer-settings>.el-button{height:auto;white-space:normal;text-align:left;line-height:1.5;margin-bottom:4px}.document-sync-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px}.document-sync-row small{color:var(--el-text-color-secondary)}
@container document-layout (min-width: 760px) {
  .finance-document-requirements.has-customer-settings {
    grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(250px, 1.5fr);
  }
  .document-customer-settings {
    grid-column: 4;
    padding-inline-start: 12px;
    border-inline-start: 1px solid var(--el-border-color-lighter);
  }
}
</style>
