<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-statement-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="对账单" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template #actions><span class="statement-manager-label" @mousedown.stop>客户经理：{{clientContext ? (clientContext.manager || '未分配') : '全部'}}</span></template></DialogFieldSearchHeader></template>
    <div ref="body">
      <div class="statement-section-heading"><strong>对账单管理</strong><el-dropdown trigger="click" @command="refreshData"><el-button>更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="history">刷新历史对账单</el-dropdown-item><el-dropdown-item command="clients">刷新客户</el-dropdown-item><el-dropdown-item command="reload">重新加载</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
      <template v-if="modelValue&&clientContext?.id"><h4 class="statement-client-context">{{clientContext.name}} · {{clientContext.month}}</h4><CustomerStatementWorkspace :key="`${clientContext.id}:${clientContext.month}`" :client-id="clientContext.id" :billing-month="clientContext.month" lock-month enforce-statement-requirement :project-selection="()=>contextProjects?.statementSelection()" :project-reload="()=>contextProjects?.reloadProjects()"><template #customer-projects="{months,mode}"><StatementClientFinance ref="contextProjects" :client-id="clientContext.id" client-scope statement-client-view require-statement-for-selection :initial-month="clientContext.month" :preview-months="months" :preview-mode="mode" @saved="$event?.id && emit('saved',$event)" /></template></CustomerStatementWorkspace></template>
      <CustomerStatementClients ref="clientsRef" v-else-if="modelValue" :billing-month="billingMonth" @saved="emit('saved',$event)" />
    </div>
    <template #footer><el-button @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {defineAsyncComponent,ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementClients from './CustomerStatementClients.vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
const StatementClientFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,billingMonth:String,clientContext:Object})
const clientsRef=ref(),contextProjects=ref()
function refreshData(command){if(command==='clients'){if(props.clientContext)void contextProjects.value?.reloadProjects();else clientsRef.value?.refresh()}else if(command==='reload')window.dispatchEvent(new CustomEvent('customer-statement-workspace-reload'));else refreshHistory()}
function refreshHistory(){window.dispatchEvent(new CustomEvent('customer-statement-history-refresh'));window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
const emit=defineEmits(['update:modelValue','saved'])
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
watch(()=>props.modelValue,clearFieldSearch)
</script>
<style scoped>
.statement-client-context{margin:6px 0;font-size:14px}.statement-section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;border-bottom:1px solid var(--el-border-color-lighter)}.statement-section-heading>strong{font-size:16px;font-weight:500;padding:6px 0;border-bottom:2px solid var(--el-color-primary)}.statement-section-heading .el-dropdown{margin-bottom:4px}.statement-manager-label{display:inline-block;max-width:min(460px,42vw);font-size:14px;font-weight:400;line-height:1.5;color:var(--el-text-color-secondary);white-space:normal;overflow-wrap:anywhere;user-select:text;cursor:text}
:global(.customer-statement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.customer-statement-dialog .el-dialog__header),:global(.customer-statement-dialog .el-dialog__footer){flex:none}
:global(.customer-statement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.customer-statement-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
:global(.customer-statement-dialog .el-dialog__footer){padding:8px 16px}:global(.customer-statement-dialog .el-dialog__footer .el-button){height:28px;padding:6px 14px;font-size:13px}
</style>
