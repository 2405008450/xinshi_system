<template>
  <DraggableFormDialog :model-value="modelValue" title="合并客户项目" class="merged-statement-dialog" width="min(1500px, calc(100vw - 32px))" top="4vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="合并客户项目" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyElement">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="!processing">
      <p>选择本月需对账单的客户，集中筛选项目并合并出账；客户档案与原始项目不变。</p>
      <el-input v-model="keyword" placeholder="搜索客户名称、简称或编号" clearable class="merge-client-search" @input="queueSearch" @keyup.enter="search" />
      <span class="merge-selected-count">已选 {{selected.size}} 个客户 · 账单月份 {{month}}</span>
      <el-table v-loading="loading" :data="clients" row-key="id" border max-height="440"><el-table-column label="选择" width="70"><template #default="{row}"><el-checkbox :model-value="selected.has(row.id)" :disabled="!authorized.has(row.id)" :aria-label="`选择客户 ${row.shortName||row.name}`" @change="toggle(row,$event)" /></template></el-table-column><el-table-column prop="shortName" label="客户简称" min-width="200" /><el-table-column prop="code" label="客户编号" width="180" /><el-table-column prop="projectCount" label="项目数" width="90" /><el-table-column label="客户经理" min-width="130"><template #default="{row}">{{row.clientManagers?.join('、')||'未分配'}}</template></el-table-column><el-table-column label="跨客户授权" width="130"><template #default="{row}">{{authorized.has(row.id)?'已授权':'需先授权'}}</template></el-table-column></el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total,prev,pager,next" @current-change="load" />
    </template>
    <template v-else>
      <div class="merged-project-heading"><strong>{{[...selected.values()].map(client=>client.shortName||client.name).join(' + ')}}</strong><el-button link :disabled="saving" @click="processing=false">重新选择客户</el-button></div>
      <AppForm :model="form" inline class="merged-project-controls">
        <el-form-item label="筛选客户"><el-select v-model="filteredClients" multiple clearable collapse-tags collapse-tags-tooltip placeholder="全部合并客户" style="width:280px"><el-option v-for="client in selected.values()" :key="client.id" :value="client.id" :label="client.shortName||client.name" /></el-select></el-form-item>
        <el-form-item label="账单归属客户"><el-select v-model="form.target" filterable style="width:240px" @change="clearPreview"><el-option v-for="client in selected.values()" :key="client.id" :value="client.id" :label="client.shortName||client.name" /></el-select></el-form-item>
        <el-form-item label="对账单名称"><el-input v-model="form.name" maxlength="100" style="width:230px" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="saving" :disabled="!form.target||!form.name.trim()" @click="generate">生成合并对账单</el-button></el-form-item>
      </AppForm>
      <p class="merged-project-help">未勾选时使用当前客户、项目状态筛选结果；已入账任务不重复纳入，目标月份的待入账任务会自动接收。每项任务保留原客户来源。</p>
      <StatementClientFinance ref="projectTable" client-scope statement-client-view :client-ids="effectiveClients" :initial-month="month" :preview-months="[month]" preview-mode="children" :manager-query="managerQuery" :statement-preview="preview" />
      <section v-if="generated" class="merged-generated"><h3>已生成的合并对账单</h3><CustomerStatementWorkspace :key="generated.board" :client-id="generated.client" :focus-board-id="generated.board" :billing-month="month" /></section>
    </template>
    </div>
    <template #footer><el-button :disabled="saving" @click="emit('update:modelValue',false)">关闭</el-button><el-button v-if="!processing" type="primary" :disabled="selected.size<2||selected.size>30||loading" @click="start">合并客户（{{selected.size}}）</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,defineAsyncComponent,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
import {getStatementCustomerGroups} from '@/api/translationCustomerFinance'
import {getCrossStatementClients,previewMergedProjects,generateMergedProjects} from '@/api/statementAccess'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const StatementClientFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const props=defineProps({modelValue:Boolean,month:String,managerQuery:{type:Object,default:()=>({})}}),emit=defineEmits(['update:modelValue','saved'])
const clients=ref([]),authorized=ref(new Set()),selected=reactive(new Map()),filteredClients=ref([]),keyword=ref(''),page=ref(1),total=ref(0),loading=ref(false),saving=ref(false),processing=ref(false),error=ref(''),projectTable=ref(),generated=ref(null)
const form=reactive({target:'',name:''}),effectiveClients=computed(()=>filteredClients.value.length?filteredClients.value:[...selected.keys()])
const bodyElement=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(bodyElement)
let timer,controller,sequence=0
function clearPreview(){generated.value=null}
function toggle(client,checked){if(checked)selected.set(client.id,client);else selected.delete(client.id)}
function search(){page.value=1;void load()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!value.trim())search();else timer=setTimeout(search,400)}
async function load(){controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value='';try{const data=await getStatementCustomerGroups({...props.managerQuery,billing_month:props.month,statement_required:true,keyword:keyword.value.trim()||undefined,skip:(page.value-1)*20,limit:20},{signal:controller.signal});if(seq===sequence){clients.value=data.items||[];total.value=data.total||0}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户加载失败')}finally{if(seq===sequence)loading.value=false}}
function start(){processing.value=true;form.target=[...selected.keys()][0];form.name=`${props.month} 合并对账单`;filteredClients.value=[];generated.value=null}
function body(order_ids){return {client_ids:[...selected.keys()],source_client_ids:effectiveClients.value,target_client_id:form.target,month:props.month,order_ids,...props.managerQuery}}
async function preview(order_ids){error.value='';const data=await previewMergedProjects(body(order_ids));if(data.existing_count)ElMessage.info(`${data.existing_count} 项已入账任务已排除`);return data.statement}
async function generate(){
  if(saving.value)return
  saving.value=true;error.value=''
  try{const order_ids=await projectTable.value.statementSelection();const data=body(order_ids);const scope=await previewMergedProjects(data);if(!scope.statement.rows.length)throw new Error('当前筛选项目均已入账或没有可生成内容')
    try{await ElMessageBox.confirm(`将当前选定／筛选项目生成“${form.name}”，归属“${selected.get(form.target)?.shortName||selected.get(form.target)?.name}”。保留原客户来源及操作记录，已入账任务不重复纳入。`,'确认合并出账',{type:'warning',confirmButtonText:'确认并生成',cancelButtonText:'取消'})}catch{return}
    const result=await generateMergedProjects({...data,versions:scope.versions,name:form.name.trim(),confirmed:true});generated.value={client:form.target,board:result.target_board_id};ElMessage.success(`已生成，纳入 ${result.imported} 项，排除已入账 ${result.existing} 项`);emit('saved');window.dispatchEvent(new CustomEvent('translation-statements-changed'))
  }catch(e){error.value=getLocalizedErrorMessage(e,'合并出账失败')}finally{saving.value=false}
}
watch(()=>props.modelValue,async visible=>{if(!visible){controller?.abort();return}selected.clear();keyword.value='';processing.value=false;generated.value=null;page.value=1;error.value='';try{const data=await getCrossStatementClients();authorized.value=new Set(data.items.map(client=>client.id));await load()}catch(e){error.value=getLocalizedErrorMessage(e,'授权客户加载失败')}})
watch(()=>props.month,()=>{if(props.modelValue){selected.clear();processing.value=false;search()}})
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
</script>
<style scoped>
.merge-client-search{width:320px;max-width:100%;margin:10px 12px 12px 0}.merge-selected-count,.merged-project-help{font-size:12px;color:var(--el-text-color-secondary)}.merged-project-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.merged-project-controls :deep(.el-form-item){margin-right:14px;margin-bottom:10px}.merged-generated{margin-top:18px;border-top:1px solid var(--el-border-color);padding-top:12px}.el-pagination{margin-top:12px}
:global(.merged-statement-dialog){display:flex;flex-direction:column;max-height:92vh;overflow:hidden}:global(.merged-statement-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.merged-statement-dialog .el-dialog__header),:global(.merged-statement-dialog .el-dialog__footer){flex:none}
</style>
