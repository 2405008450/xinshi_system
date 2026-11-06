<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-statement-history-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${mergeMonths?'合并月份':'客户管理 · 对账单'} · ${client?.shortName||client?.name||''}`" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body"><CustomerStatementHistory v-if="modelValue&&client?.id" :client-id="client.id" :merge-months="mergeMonths" /></div>
    <template #footer><el-button @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementHistory from './CustomerStatementHistory.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,client:Object,mergeMonths:Boolean})
const emit=defineEmits(['update:modelValue'])
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
watch(()=>props.modelValue,clearFieldSearch)
</script>
<style>
.customer-statement-history-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.customer-statement-history-dialog .el-dialog__header,.customer-statement-history-dialog .el-dialog__footer{flex:none}.customer-statement-history-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.customer-statement-history-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
</style>
