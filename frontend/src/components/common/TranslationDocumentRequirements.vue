<template>
  <div class="finance-document-requirements">
    <el-form-item label="是否需报价单" prop="quotationRequired" data-field-key="quotationRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.quotationRequired" @update:model-value="update('quotationRequired',$event)">需</el-checkbox><el-button v-if="modelValue.quotationRequired" link type="primary" @click="$emit('quotation')">打开报价单</el-button></div></el-form-item>
    <el-form-item label="是否需对账单" prop="statementRequired" data-field-key="statementRequired"><div class="finance-document-choice"><el-checkbox :model-value="modelValue.statementRequired" @update:model-value="update('statementRequired',$event)">需</el-checkbox><el-button link type="primary" @click="$emit('statement')">打开对账单</el-button></div></el-form-item>
  </div>
</template>
<script setup>
const props=defineProps({modelValue:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','quotation','statement'])
function update(field,value){emit('update:modelValue',{...props.modelValue,[field]:value,...(field==='statementRequired'?{statementRequiredDirty:true}:{})})}
</script>
<style scoped>
.finance-document-requirements{display:flex;gap:12px 24px;align-items:flex-start;flex-wrap:wrap;margin-bottom:16px}.finance-document-requirements :deep(.el-form-item){flex:1;min-width:180px;margin-bottom:0}.finance-document-choice{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
</style>
