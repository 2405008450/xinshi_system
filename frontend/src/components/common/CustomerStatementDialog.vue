<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-statement-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close
    :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="clientContext?.subClientId && settlementScope==='standard' ? `${title} · 子客户合并结算` : title" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template #actions>
      <span v-if="clientContext" class="statement-manager-label" @mousedown.stop>客户经理：{{clientContext.manager || '未分配'}}</span>
      <el-button v-else class="statement-manager-button" @mousedown.stop @click="openManagerPicker">
        客户经理：{{selectedManagerLabel}}
      </el-button>
    </template></DialogFieldSearchHeader></template>
    <div ref="body">
      <el-tabs v-if="settlementScope==='special'" v-model="activeTab" :before-leave="confirmClose">
        <el-tab-pane label="特殊结算" name="settlement" />
        <el-tab-pane label="特殊结算发票" name="invoice" />
      </el-tabs>
      <InvoiceWorkspace v-if="modelValue&&settlementScope==='special'&&activeTab==='invoice'" ref="invoiceWorkspace" model-value embedded
        :invoice-client-id="clientContext?.id" :invoice-client-name="clientContext?.name||clientName"
        :initial-month="clientContext?clientFilters.month:billingMonth" :period-number="clientContext?clientFilters.period:undefined"
        :manager-query="selectedManagerQuery" @invoice-saved="emit('invoice-saved',$event)" />
      <template v-else>
      <div class="statement-section-heading"><strong>{{title}}管理</strong><el-dropdown trigger="click" @command="refreshData"><el-button>更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="history">{{settlementScope==='special'?'刷新特殊结算记录':'刷新历史对账单'}}</el-dropdown-item><el-dropdown-item command="clients">刷新客户</el-dropdown-item><el-dropdown-item command="reload">重新加载</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
      <template v-if="modelValue&&clientContext?.id">
        <AppForm data-auto-draft="off" :model="clientFilters" inline @submit.prevent>
          <el-form-item label="账单月份">
            <el-date-picker :model-value="clientFilters.month" type="month" value-format="YYYY-MM" :clearable="false" style="width:160px" @update:model-value="changeClientMonth" />
          </el-form-item>
          <el-form-item v-if="settlementScope" label="账期"><StatementPeriodSelect v-model="clientFilters.period" :month="clientFilters.month" :client-id="clientContext.id" :settlement-scope="settlementScope" /></el-form-item>
        </AppForm>
        <h4 class="statement-client-context">{{[clientContext.name||clientName,clientContext.subClientName,clientFilters.month].filter(Boolean).join(' · ')}}</h4>
        <CustomerStatementWorkspace :key="`${clientContext.id}:${clientContext.subClientId||''}:${clientFilters.month}`" :client-id="clientContext.id" :sub-client-id="clientContext.subClientId" :period-number="clientFilters.period" :settlement-scope="settlementScope" :billing-month="clientFilters.month" :focus-board-id="focusedBoardId" :visible-board-ids="focusedBoardId?[focusedBoardId]:[]" lock-month :enforce-statement-requirement="settlementScope!=='special'" :project-selection="options=>contextProjects?.statementSelection(options)" :project-reload="()=>contextProjects?.reloadProjects()" @loaded="clientName=$event.client_name||clientName">
          <template #customer-projects="{months,mode,reload,selectionChanged}">
            <StatementClientFinance ref="contextProjects" :client-id="clientContext.id" :sub-client-id="clientContext.subClientId" :period-number="clientFilters.period" :settlement-scope="settlementScope" client-scope statement-client-view :require-statement-for-selection="settlementScope!=='special'" :initial-month="clientFilters.month" :preview-months="months" :preview-mode="mode" @statement-selection-change="selectionChanged" @special-payment-saved="reload" @saved="$event?.id && emit('saved',$event)" />
          </template>
          <template #client-actions="{reload}">
            <CustomerStatementActions :client="clientContext" :settlement-scope="settlementScope" @merged="reload" />
          </template>
        </CustomerStatementWorkspace>
      </template>
      <CustomerStatementClients ref="clientsRef" v-else-if="modelValue" :billing-month="billingMonth" :settlement-scope="settlementScope" :manager-query="selectedManagerQuery" @saved="emit('saved',$event)" />
      </template>
    </div>
    <template #footer><el-button @click="beforeClose(()=>emit('update:modelValue',false))">关闭</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" append-to-body
    class="statement-manager-dialog" width="min(560px, calc(100vw - 32px))" top="10vh" :close-on-click-modal="false">
    <el-radio-group v-model="managerDraftScope" data-auto-draft="off" class="statement-manager-choices">
      <el-radio value="self">本人（{{selfName}}）</el-radio>
      <el-radio value="all">不指定人（全部订单）</el-radio>
      <el-radio value="name">指定客户经理</el-radio>
    </el-radio-group>
    <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds"
      data-auto-draft="off" @options="cacheManagers" />
    <template #footer>
      <el-button @click="managerPickerVisible=false">取消</el-button>
      <el-button type="primary" @click="applyManager">确定</el-button>
    </template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,defineAsyncComponent,reactive,ref,watch} from 'vue'
import AppForm from './AppForm.vue'
import StatementPeriodSelect from './StatementPeriodSelect.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementClients from './CustomerStatementClients.vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
import CustomerStatementActions from './CustomerStatementActions.vue'
import CustomerDepartmentManagerSelect from './CustomerDepartmentManagerSelect.vue'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'
const StatementClientFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const InvoiceWorkspace=defineAsyncComponent(()=>import('./ProjectPaymentDialog.vue'))
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,billingMonth:String,clientContext:Object,
  settlementScope:String,title:{type:String,default:'对账单'},
  managerLabel:{type:String,default:'全部'},managerQuery:{type:Object,default:()=>({})}})
const clientsRef=ref(),contextProjects=ref(),clientName=ref('')
const activeTab=ref('settlement')
const invoiceWorkspace=ref()
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerPickerVisible=ref(false)
const managerDraftScope=ref('all')
const managerDraftIds=ref([])
const managerNames=ref({})
const managerOverride=ref(null)
const selectedManagerQuery=computed(()=>managerOverride.value?.query ?? props.managerQuery)
const selectedManagerLabel=computed(()=>managerOverride.value?.label ?? props.managerLabel)
function cacheManagers(people) {
  managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[
    person.id,`${person.name}${person.username&&person.username!==person.name?`（${person.username}）`:''}`,
  ]))}
}
function openManagerPicker() {
  const query=selectedManagerQuery.value
  managerDraftIds.value=[...(query.manager_ids||[])]
  managerDraftScope.value=query.only_mine?'self':managerDraftIds.value.length?'name':'all'
  managerPickerVisible.value=true
}
async function applyManager() {
  if (!await confirmClose()) return
  const scope=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value
  const ids=scope==='name'?[...managerDraftIds.value]:[]
  const label=scope==='self'?`本人（${selfName}）`:scope==='all'?'不指定人（全部订单）':
    `指定（${ids.length}人）：${ids.map(id=>managerNames.value[id]||'已选人员').join('、')}`
  managerOverride.value={query:{manager_ids:scope==='name'?ids:undefined,only_mine:scope==='self'},label}
  managerPickerVisible.value=false
}
watch(()=>props.modelValue,()=>{managerOverride.value=null;managerPickerVisible.value=false})
watch(()=>props.managerQuery,()=>{managerOverride.value=null},{deep:true})
function confirmClose(){return invoiceWorkspace.value?.confirmClose() ?? true}
async function beforeClose(done){if(await confirmClose())done()}
const clientFilters=reactive({month:'',period:undefined})
const focusedBoardId=computed(()=>clientFilters.month===props.clientContext?.month&&clientFilters.period===props.clientContext?.period
  ? props.clientContext?.boardId : undefined)
watch(()=>[props.modelValue,props.clientContext?.id,props.clientContext?.month,props.clientContext?.period,props.clientContext?.boardId],([visible,,month,period])=>{
  clientFilters.month=month||props.billingMonth||currentStatementMonth()
  clientFilters.period=visible?period:undefined
},{immediate:true})
async function changeClientMonth(month){
  if(!month||month===clientFilters.month)return
  const projects=contextProjects.value
  if(projects&&!await projects.flushTableEdits())return
  if(props.modelValue&&projects===contextProjects.value){clientFilters.period=undefined;clientFilters.month=month}
}
function refreshData(command){if(command==='clients'){if(props.clientContext)void contextProjects.value?.reloadProjects();else clientsRef.value?.refresh()}else if(command==='reload')window.dispatchEvent(new CustomEvent('customer-statement-workspace-reload'));else refreshHistory()}
function refreshHistory(){window.dispatchEvent(new CustomEvent('customer-statement-history-refresh'));window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
const emit=defineEmits(['update:modelValue','saved','invoice-saved'])
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
watch(()=>props.modelValue,visible=>{clearFieldSearch();if(visible)activeTab.value='settlement'})
</script>
<style scoped>
.statement-manager-button{max-width:min(460px,42vw);height:auto;white-space:normal;overflow-wrap:anywhere;text-align:left}
.statement-manager-choices{display:flex;flex-direction:column;align-items:flex-start;margin-bottom:12px}
.statement-client-context{margin:6px 0;font-size:14px}.statement-section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;border-bottom:1px solid var(--el-border-color-lighter)}.statement-section-heading>strong{font-size:16px;font-weight:500;padding:6px 0;border-bottom:2px solid var(--el-color-primary)}.statement-section-heading .el-dropdown{margin-bottom:4px}.statement-manager-label{display:inline-block;max-width:min(460px,42vw);font-size:14px;font-weight:400;line-height:1.5;color:var(--el-text-color-secondary);white-space:normal;overflow-wrap:anywhere;user-select:text;cursor:text}
:global(.customer-statement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.customer-statement-dialog .el-dialog__header),:global(.customer-statement-dialog .el-dialog__footer){flex:none}
:global(.customer-statement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.customer-statement-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
:global(.customer-statement-dialog .el-dialog__footer){padding:8px 16px}:global(.customer-statement-dialog .el-dialog__footer .el-button){height:28px;padding:6px 14px;font-size:13px}
</style>
