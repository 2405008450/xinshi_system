<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-statement-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="title" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template #actions><span class="statement-manager-label" @mousedown.stop>客户经理：{{clientContext ? (clientContext.manager || '未分配') : managerLabel}}</span></template></DialogFieldSearchHeader></template>
    <div ref="body">
      <el-tabs v-if="settlementScope==='special'" v-model="activeTab">
        <el-tab-pane label="特殊结算" name="settlement" />
        <el-tab-pane label="特殊结算发票" name="invoice" />
      </el-tabs>
      <SpecialSettlementInvoices v-if="modelValue&&settlementScope==='special'&&activeTab==='invoice'"
        :client-id="clientContext?.id" :month="clientContext?clientFilters.month:billingMonth" :period-number="clientContext?clientFilters.period:undefined" :manager-query="managerQuery" />
      <template v-else>
      <div class="statement-section-heading"><strong>{{title}}管理</strong><el-dropdown trigger="click" @command="refreshData"><el-button>更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="history">{{settlementScope==='special'?'刷新特殊结算记录':'刷新历史对账单'}}</el-dropdown-item><el-dropdown-item command="clients">刷新客户</el-dropdown-item><el-dropdown-item command="reload">重新加载</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
      <template v-if="modelValue&&clientContext?.id">
        <AppForm :model="clientFilters" inline @submit.prevent>
          <el-form-item label="账单月份">
            <el-date-picker :model-value="clientFilters.month" type="month" value-format="YYYY-MM" :clearable="false" style="width:160px" @update:model-value="changeClientMonth" />
          </el-form-item>
          <el-form-item v-if="settlementScope" label="账期"><StatementPeriodSelect v-model="clientFilters.period" :month="clientFilters.month" :client-id="clientContext.id" :settlement-scope="settlementScope" /></el-form-item>
        </AppForm>
        <h4 class="statement-client-context">{{clientContext.name||clientName}} · {{clientFilters.month}}</h4>
        <CustomerStatementWorkspace :key="`${clientContext.id}:${clientFilters.month}`" :client-id="clientContext.id" :period-number="clientFilters.period" :settlement-scope="settlementScope" :billing-month="clientFilters.month" lock-month :enforce-statement-requirement="settlementScope!=='special'" :project-selection="()=>contextProjects?.statementSelection()" :project-reload="()=>contextProjects?.reloadProjects()" @loaded="clientName=$event.client_name||clientName">
          <template #customer-projects="{months,mode,reload}">
            <StatementClientFinance ref="contextProjects" :client-id="clientContext.id" :period-number="clientFilters.period" :settlement-scope="settlementScope" client-scope statement-client-view :require-statement-for-selection="settlementScope!=='special'" :initial-month="clientFilters.month" :preview-months="months" :preview-mode="mode" @special-payment-saved="reload" @saved="$event?.id && emit('saved',$event)" />
          </template>
          <template #client-actions="{reload}">
            <CustomerStatementActions v-if="!settlementScope" :client="clientContext" @merged="reload" />
          </template>
        </CustomerStatementWorkspace>
      </template>
      <CustomerStatementClients ref="clientsRef" v-else-if="modelValue" :billing-month="billingMonth" :settlement-scope="settlementScope" :manager-query="managerQuery" @saved="emit('saved',$event)" />
      </template>
    </div>
    <template #footer><el-button @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {defineAsyncComponent,reactive,ref,watch} from 'vue'
import AppForm from '../AppForm.vue'
import StatementPeriodSelect from './BackupStatementPeriodSelect.vue'
import DraggableFormDialog from '../DraggableFormDialog.vue'
import DialogFieldSearchHeader from '../DialogFieldSearchHeader.vue'
import CustomerStatementClients from './BackupCustomerStatementClients.vue'
import CustomerStatementWorkspace from './BackupCustomerStatementWorkspace.vue'
import CustomerStatementActions from './BackupCustomerStatementActions.vue'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'
const StatementClientFinance=defineAsyncComponent(()=>import('./BackupCustomerFinance.vue'))
const SpecialSettlementInvoices=defineAsyncComponent(()=>import('./BackupSpecialSettlementInvoices.vue'))
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,billingMonth:String,clientContext:Object,
  settlementScope:String,title:{type:String,default:'对账单'},
  managerLabel:{type:String,default:'全部'},managerQuery:{type:Object,default:()=>({})}})
const clientsRef=ref(),contextProjects=ref(),clientName=ref('')
const activeTab=ref('settlement')
const clientFilters=reactive({month:'',period:undefined})
watch(()=>[props.modelValue,props.clientContext?.id,props.clientContext?.month,props.clientContext?.period],([visible,,month,period])=>{
  if(visible){clientFilters.month=month||props.billingMonth||currentStatementMonth();clientFilters.period=period}
},{immediate:true})
async function changeClientMonth(month){
  if(!month||month===clientFilters.month)return
  const projects=contextProjects.value
  if(projects&&!await projects.flushTableEdits())return
  if(props.modelValue&&projects===contextProjects.value){clientFilters.period=undefined;clientFilters.month=month}
}
function refreshData(command){if(command==='clients'){if(props.clientContext)void contextProjects.value?.reloadProjects();else clientsRef.value?.refresh()}else if(command==='reload')window.dispatchEvent(new CustomEvent('customer-statement-workspace-reload'));else refreshHistory()}
function refreshHistory(){window.dispatchEvent(new CustomEvent('customer-statement-history-refresh'));window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
const emit=defineEmits(['update:modelValue','saved'])
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
watch(()=>props.modelValue,visible=>{clearFieldSearch();if(visible)activeTab.value='settlement'})
</script>
<style scoped>
.statement-client-context{margin:6px 0;font-size:14px}.statement-section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;border-bottom:1px solid var(--el-border-color-lighter)}.statement-section-heading>strong{font-size:16px;font-weight:500;padding:6px 0;border-bottom:2px solid var(--el-color-primary)}.statement-section-heading .el-dropdown{margin-bottom:4px}.statement-manager-label{display:inline-block;max-width:min(460px,42vw);font-size:14px;font-weight:400;line-height:1.5;color:var(--el-text-color-secondary);white-space:normal;overflow-wrap:anywhere;user-select:text;cursor:text}
:global(.customer-statement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.customer-statement-dialog .el-dialog__header),:global(.customer-statement-dialog .el-dialog__footer){flex:none}
:global(.customer-statement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.customer-statement-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
:global(.customer-statement-dialog .el-dialog__footer){padding:8px 16px}:global(.customer-statement-dialog .el-dialog__footer .el-button){height:28px;padding:6px 14px;font-size:13px}
</style>
