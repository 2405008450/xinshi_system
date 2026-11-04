<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-statement-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="对账单" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="是否需对账单" name="requirements">
          <CustomerStatementRequirements v-if="modelValue&&activeTab==='requirements'" :query="query" @view="viewCustomer" @saved="emit('saved',$event)" />
        </el-tab-pane>
        <el-tab-pane label="对账单查看" name="view" lazy>
          <CustomerStatementClients v-if="modelValue" :initial-client="initialClient" :billing-month="billingMonth" />
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer><el-button @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementRequirements from './CustomerStatementRequirements.vue'
import CustomerStatementClients from './CustomerStatementClients.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})},billingMonth:String})
const emit=defineEmits(['update:modelValue','saved'])
const body=ref(),activeTab=ref('requirements'),initialClient=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
function viewCustomer(project,month){if(!project.clientId)return;initialClient.value={id:project.clientId,name:project.clientShortName,shortName:project.clientShortName,month};activeTab.value='view'}
watch(()=>props.modelValue,visible=>{
  clearFieldSearch()
  if(!visible)return
  activeTab.value='requirements'
  const client=props.projects.find(project=>project.clientId)
  initialClient.value=client?{id:client.clientId,name:client.clientShortName,shortName:client.clientShortName}:null
})
</script>
<style scoped>
:global(.customer-statement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.customer-statement-dialog .el-dialog__header),:global(.customer-statement-dialog .el-dialog__footer){flex:none}
:global(.customer-statement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.customer-statement-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
</style>
