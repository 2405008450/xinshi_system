<template>
  <section class="client-group" :class="{'drop-active':dragOver}" @dragover.prevent="dragOver=true" @dragleave="leave" @drop.prevent="drop">
    <header><strong>{{required?'需对账单客户':'无需对账单客户'}} · {{total}}</strong><div><el-button link @click="expanded=items.map(client=>client.id)">全部展开</el-button><el-button link @click="expanded=[]">全部收起</el-button></div></header>
    <el-input v-model="keyword" :aria-label="`${required?'需':'无需'}对账单客户搜索`" placeholder="搜索客户名称、简称或编号" clearable @input="queueSearch" @keyup.enter="search"><template #append><el-button @click="search">查询</el-button></template></el-input>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="client-group-list">
      <p class="drop-hint">{{dragOver?'松开鼠标移入此栏':'可将另一栏的客户拖到这里'}}</p>
      <el-empty v-if="!items.length&&!loading" description="当前月份没有匹配客户" :image-size="55" />
      <el-collapse v-model="expanded">
        <el-collapse-item v-for="client in items" :key="client.id" :name="client.id">
          <template #title><div class="client-title" :draggable="canWrite&&!moving" @dragstart="startDrag($event,client)" @dragend="dragOver=false"><div class="client-name-line"><strong>{{client.shortName||client.name}}</strong><el-select :model-value="client.progress||'not_started'" :disabled="!canWrite||progressSaving.has(client.id)" size="small" aria-label="对账单进度" style="width:115px" @click.stop @mousedown.stop @dragstart.prevent.stop @change="saveProgress(client,$event)"><el-option label="未开始" value="not_started" /><el-option label="部分完成" value="partial" /><el-option label="全部完成" value="completed" /></el-select></div><small>{{client.code}} · {{client.projectCount}} 个项目<span v-if="client.pendingCount"> · 待入账 {{client.pendingCount}} 项</span> · 客户经理：{{client.clientManagers?.join('、')||'未分配'}}</small></div></template>
          <div class="client-workspace"><CustomerStatementWorkspace v-if="expanded.includes(client.id)" :client-id="client.id" :billing-month="month" :project-selection="()=>projectTables.get(client.id)?.statementSelection()" :project-reload="()=>projectTables.get(client.id)?.reloadProjects()"><template #customer-projects="{months,mode}"><StatementClientFinance :ref="el=>el?projectTables.set(client.id,el):projectTables.delete(client.id)" :client-id="client.id" client-scope statement-client-view :initial-month="month" :preview-months="months" :preview-mode="mode" :manager-query="managerQuery" /></template><template #client-actions><div class="client-statement-actions"><el-button link type="primary" @click.stop="historyClient=client;mergeMonthsMode=false;historyVisible=true">查看历史对账单</el-button><el-button v-if="canWrite" link @click.stop="historyClient=client;mergeMonthsMode=true;historyVisible=true">合并月份</el-button><el-button v-if="canWrite" link :disabled="moving" @click.stop="emit('move-client',{...client,statementRequired:required})">移至{{required?'无需':'需'}}</el-button></div></template></CustomerStatementWorkspace></div>
        </el-collapse-item>
      </el-collapse>
    </div>
    <CustomerStatementHistoryDialog v-model="historyVisible" :client="historyClient" :merge-months="mergeMonthsMode" />
    <el-pagination v-if="total>pageSize" v-model:current-page="page" :page-size="pageSize" :total="total" layout="slot,prev,pager,next" @current-change="load"><span class="statement-pagination-total">共 {{total}} 个客户</span></el-pagination>
  </section>
</template>
<script setup>
import {defineAsyncComponent,onBeforeUnmount,ref,watch} from 'vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
const StatementClientFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
import CustomerStatementHistoryDialog from './CustomerStatementHistoryDialog.vue'
import {getStatementCustomerGroups,setStatementProgress} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
const props=defineProps({required:Boolean,month:String,progressFilter:String,moving:Boolean,managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['drop-client','move-client','managers'])
const canWrite=hasPermission('projects:write'),pageSize=20
const projectTables=new Map(),progressSaving=ref(new Set())
const historyVisible=ref(false),historyClient=ref(null),mergeMonthsMode=ref(false)
const items=ref([]),total=ref(0),page=ref(1),keyword=ref(''),expanded=ref([]),loading=ref(false),error=ref(''),dragOver=ref(false)
let controller,sequence=0,timer
async function load(){
  if(!props.month)return
  clearTimeout(timer);controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value=''
  try{const data=await getStatementCustomerGroups({...props.managerQuery,billing_month:props.month,statement_required:props.required,progress:props.progressFilter||undefined,keyword:keyword.value.trim()||undefined,skip:(page.value-1)*pageSize,limit:pageSize},{signal:controller.signal});if(seq!==sequence)return;items.value=data.items||[];total.value=data.total||0;expanded.value=expanded.value.filter(id=>items.value.some(client=>client.id===id))}
  catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED'){error.value=getLocalizedErrorMessage(e,'客户加载失败');items.value=[];emit('managers',[])}}
  finally{if(seq===sequence)loading.value=false}
}
async function saveProgress(client,progress){progressSaving.value.add(client.id);try{const result=await setStatementProgress(client.id,{billing_month:props.month,progress,revision:client.progressRevision||0,...props.managerQuery});Object.assign(client,result);if(props.progressFilter&&props.progressFilter!==progress)await load()}catch(e){error.value=getLocalizedErrorMessage(e,'对账单进度保存失败');if(e.response?.status===409)await load()}finally{progressSaving.value.delete(client.id)}}
function search(){page.value=1;void load()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!value.trim())search();else timer=setTimeout(search,400)}
function startDrag(event,client){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-statement-client',JSON.stringify({...client,statementRequired:props.required}))}
function drop(event){dragOver.value=false;if(!canWrite||props.moving)return;try{const value=JSON.parse(event.dataTransfer.getData('application/x-statement-client'));emit('drop-client',value)}catch{}}
function leave(event){if(!event.currentTarget.contains(event.relatedTarget))dragOver.value=false}
watch([items,expanded],()=>{const shown=expanded.value.length?items.value.filter(client=>expanded.value.includes(client.id)):items.value;emit('managers',[...new Set(shown.flatMap(client=>client.clientManagers||[]))])},{deep:true})
watch(()=>[props.month,props.progressFilter,JSON.stringify(props.managerQuery)],()=>{expanded.value=[];search()},{immediate:true})
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
defineExpose({refresh:search})
</script>
<style scoped>
.client-name-line{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.client-group{min-width:0;border:1px solid var(--el-border-color);border-radius:8px;padding:12px;background:#fff}.client-group.drop-active{outline:2px solid var(--el-color-primary)}header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}.client-group-list{min-height:150px}.drop-hint{font-size:11px;color:var(--el-text-color-secondary);margin:8px 0}.client-title{display:grid;gap:3px;flex:1;min-width:0;line-height:1.5;padding:10px 0}.client-title[draggable=true]{cursor:grab}.client-title small{color:var(--el-text-color-secondary);font-size:11px;overflow-wrap:anywhere}.client-statement-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:4px 0 6px}.client-workspace{min-width:0;overflow-x:auto}.client-group :deep(.el-collapse-item__header){height:auto;min-height:52px;gap:8px}.client-group :deep(.el-collapse-item__content){padding-bottom:12px}.el-pagination{margin-top:12px;max-width:100%;overflow-x:auto}
</style>
