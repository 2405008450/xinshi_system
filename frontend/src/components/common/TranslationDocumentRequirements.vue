<template>
  <div class="finance-document-requirements">
    <el-form-item label="是否需报价单" prop="quotationRequired" data-field-key="quotationRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.quotationRequired" @update:model-value="update('quotationRequired',$event)">需</el-checkbox><el-button v-if="modelValue.quotationRequired" link type="primary" @click="$emit('quotation')">打开报价单</el-button></div><el-input :model-value="notes.quotation" size="small" placeholder="说明" aria-label="报价单说明" data-dialog-field-search-label="报价单说明" :maxlength="2000" clearable @update:model-value="updateNote('quotation',$event)" /></el-form-item>
    <el-form-item label="是否需对账单" prop="statementRequired" data-field-key="statementRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.statementRequired" @update:model-value="update('statementRequired',$event)">需</el-checkbox><el-button v-if="modelValue.statementRequired" link type="primary" @click="$emit('statement')">打开对账单</el-button></div><el-input :model-value="notes.statement" size="small" placeholder="说明" aria-label="对账单说明" data-dialog-field-search-label="对账单说明" :maxlength="2000" clearable @update:model-value="updateNote('statement',$event)" /></el-form-item>
    <el-form-item label="是否需发票" data-field-key="invoiceRequired"><div class="finance-document-choice"><ReadonlyField :model-value="invoiceNeeded===null?'按计费口径自动判断':invoiceNeeded?'需':'无需'" source="auto" aria-label="是否需发票" /><el-button v-if="invoiceNeeded" link type="primary" @click="$emit('invoice')">发票</el-button></div><el-input :model-value="notes.invoice" size="small" placeholder="说明" aria-label="发票说明" data-dialog-field-search-label="发票说明" :maxlength="2000" clearable @update:model-value="updateNote('invoice',$event)" /></el-form-item>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import {documentNotesForm,invoiceRequirement} from '@/utils/documentRequirements'
const props=defineProps({modelValue:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','quotation','statement','invoice'])
const notes=computed(()=>documentNotesForm(props.modelValue.documentNotes))
const invoiceNeeded=computed(()=>invoiceRequirement(props.modelValue))
function update(field,value){emit('update:modelValue',{...props.modelValue,[field]:value,...(field==='statementRequired'?{statementRequiredDirty:true}:{})})}
function updateNote(field,value){emit('update:modelValue',{...props.modelValue,documentNotes:{...notes.value,[field]:value},documentNotesDirty:true})}
</script>
<style scoped>
.finance-document-requirements{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px 20px;margin-bottom:16px}.finance-document-requirements :deep(.el-form-item){min-width:0;margin-bottom:0}.finance-document-choice{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-height:32px;width:100%;margin-bottom:6px}.finance-document-choice>.el-input{width:120px;max-width:100%}
</style>
