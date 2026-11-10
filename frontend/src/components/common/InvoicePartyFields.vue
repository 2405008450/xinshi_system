<template><div class="invoice-party-fields"><el-form-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label" :prop="`party.${field.key}`"><ReadonlyField v-if="field.key==='title'&&titleReadonly" :model-value="modelValue.title" source="auto" /><el-input v-else :model-value="modelValue[field.key]" :type="field.key==='remarks'?'textarea':'text'" :rows="2" :maxlength="field.max" placeholder="待填写" @update:model-value="$emit('update:modelValue',{...modelValue,[field.key]:$event})" /></el-form-item></div></template>
<script setup>
import ReadonlyField from './ReadonlyField.vue'
import {invoicePartyFields} from '@/api/invoiceParties'
defineProps({modelValue:{type:Object,required:true},titleReadonly:Boolean})
defineEmits(['update:modelValue'])
</script>
<style scoped>.invoice-party-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 18px}@media(max-width:640px){.invoice-party-fields{grid-template-columns:1fr}}:global(.invoice-party-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.invoice-party-editor>.el-dialog__header),:global(.invoice-party-editor>.el-dialog__footer){flex:none}:global(.invoice-party-editor>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}</style>
