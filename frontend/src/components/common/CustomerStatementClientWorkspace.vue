<template>
  <div class="client-workspace">
    <el-select v-if="client.subClients?.length" v-model="selectedSubClient" aria-label="子客户" style="width:280px;max-width:100%;margin:8px 0">
      <el-option v-if="!client.filterSubClients" value="" label="全部项目" />
      <el-option v-for="child in client.subClients" :key="child.id" :value="child.id" :label="`${child.name} · ${child.code}`" />
    </el-select>
    <CustomerStatementWorkspace :key="selectedSubClient" :client-id="client.id" :sub-client-id="selectedSubClient||undefined"
      :settlement-scope="settlementScope" :manager-query="managerQuery" :period-number="periodNumber" :billing-month="month" :lock-month="!!periodNumber"
      :project-selection="options=>projectTable?.statementSelection(options)" :project-reload="()=>projectTable?.reloadProjects()">
      <template #customer-projects="{months,mode,reload,selectionChanged}">
        <StatementClientFinance ref="projectTable" :client-id="client.id" :sub-client-id="selectedSubClient||undefined"
          :settlement-scope="settlementScope" :period-number="periodNumber" client-scope statement-client-view :initial-month="month"
          :preview-months="months" :preview-mode="mode" :manager-query="managerQuery"
          @statement-selection-change="selectionChanged" @special-payment-saved="reload" />
      </template>
      <template #client-actions="{reload}">
        <CustomerStatementActions :client="client" :settlement-scope="settlementScope" @merged="reload">
          <el-button v-if="canWrite && settlementScope!=='special'" link :disabled="moving"
            @click="emit('move-client',{...client,statementRequired:required,statementBillingMonth:month})">移至{{required?'无需':'需'}}</el-button>
        </CustomerStatementActions>
      </template>
    </CustomerStatementWorkspace>
  </div>
</template>

<script setup>
import {computed,defineAsyncComponent,ref,watch} from 'vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
import CustomerStatementActions from './CustomerStatementActions.vue'
import {hasPermission} from '@/utils/permission'
const StatementClientFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const props=defineProps({client:{type:Object,required:true},month:String,periodNumber:Number,settlementScope:String,
  required:Boolean,moving:Boolean,managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['move-client'])
const canWrite=hasPermission('projects:write'),projectTable=ref(),selection=ref('')
const selectedSubClient=computed({
  get:()=>props.client.subClients?.some(child=>child.id===selection.value)?selection.value:
    props.client.filterSubClients?props.client.subClients?.[0]?.id||'':'',
  set:value=>{selection.value=value},
})
watch(()=>props.client.id,()=>{selection.value=''})
</script>

<style scoped>
.client-workspace{min-width:0;overflow-x:auto}
</style>
