<template>
  <section class="statement-requirements">
    <AppForm :model="filters" inline @submit.prevent="search">
      <el-form-item label="月份"><el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" :clearable="false" style="width:160px" @change="search" /></el-form-item>
      <el-form-item><el-button @click="selectMonth(currentStatementMonth())">本月</el-button><el-button @click="selectMonth(previousStatementMonth())">上个月</el-button></el-form-item>
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="订单号、项目名称、客户名称" clearable @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="客户"><el-input v-model="filters.client" placeholder="客户全称或简称" clearable @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced" @reset="clearAdvanced"><el-form-item label="是否需对账单"><el-select v-model="filters.required" clearable placeholder="全部" @change="search"><el-option label="需对账单" value="yes" /><el-option label="不需对账单" value="no" /></el-select></el-form-item><el-form-item label="项目状态"><el-select v-model="filters.status" clearable placeholder="全部状态" @change="search"><el-option v-for="item in statuses" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></AdvancedFilterPopover></el-form-item>
    </AppForm>
    <p class="statement-requirements-hint">按订单号所属月份显示笔译母订单；“是否需对账单”修改后立即保存，与项目主表单同步。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table ref="tableRef" @sort-change="changeSort" v-loading="loading" :data="rows" row-key="id" border empty-text="所选月份暂无笔译项目">
      <el-table-column type="index" label="序号" width="65" :index="index=>(page-1)*10+index+1" />
      <el-table-column prop="orderNo" label="订单号" width="160" />
      <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="clientShortName" sortable="custom" :sort-orders="['ascending','descending',null]" label="客户简称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="clientManager" label="客户经理" width="120" />
      <el-table-column label="项目状态" width="120"><template #default="{row}">{{getProjectStatusLabel('translation',row.projectStatus)}}</template></el-table-column>
      <el-table-column label="是否需对账单" width="155" fixed="right"><template #default="{row}"><el-checkbox :key="`${row.id}-${savingIds.has(row.id)}`" :model-value="row.statementRequired" :disabled="!canWrite||savingIds.size>0" :aria-label="`${row.orderNo} 是否需对账单`" @update:model-value="saveRequired(row,$event)">{{row.statementRequired?'需':'不需'}}</el-checkbox><span v-if="savingIds.has(row.id)" class="statement-requirements-saving">保存中</span></template></el-table-column>
      <el-table-column label="对账单" width="125" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="!row.clientId" :title="row.clientId?'查看该客户的对账单':'请先为项目关联客户'" @click="emit('view',row,filters.month)">查看对账单</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next, jumper" @current-change="load" />
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import AdvancedFilterPopover from './AdvancedFilterPopover.vue'
import {getCustomerFinancePage,setProjectStatementRequired} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {getProjectStatusLabel,getProjectStatusOptions} from '@/utils/projectStatus'
import {currentStatementMonth,previousStatementMonth} from '@/utils/statementRequirementMonth'
const props=defineProps({query:{type:Object,default:()=>({})}})
const emit=defineEmits(['view','saved'])
const canWrite=hasPermission('projects:write')
const filters=reactive({month:currentStatementMonth(),keyword:'',client:'',required:'',status:''}),rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),error=ref(''),savingIds=reactive(new Set())
const tableRef=ref(),sortOrder=ref(''),advancedVisible=ref(false),statuses=getProjectStatusOptions('translation')
const advancedCount=computed(()=>Number(!!filters.required)+Number(!!filters.status))
function clearAdvanced(){filters.required='';filters.status='';search()}
function changeSort({order}){sortOrder.value=order==='ascending'?'client_short_name_asc':order==='descending'?'client_short_name_desc':'';search()}
let controller,sequence=0,timer,disposed=false
function params(){return {...props.query,billing_month:filters.month,keyword:filters.keyword.trim()||undefined,client:filters.client.trim()||undefined,project_status:filters.status||undefined,statement_required:filters.required==='yes'?true:filters.required==='no'?false:undefined,sort:sortOrder.value||undefined,skip:(page.value-1)*10,limit:10}}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getCustomerFinancePage(params(),{signal:controller.signal});if(seq===sequence&&!disposed){rows.value=data.items||[];total.value=data.total||0}}catch(e){if(seq===sequence&&!disposed&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'笔译项目加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function selectMonth(month){filters.month=month;search()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function reset(){Object.assign(filters,{month:currentStatementMonth(),keyword:'',client:'',required:'',status:''});sortOrder.value='';tableRef.value?.clearSort();search()}
async function saveRequired(row,value){
  if(!canWrite||savingIds.size||value===row.statementRequired)return
  let copy=false
  savingIds.add(row.id);error.value=''
  try{
    if(value&&row.clientId){
      try{await ElMessageBox.confirm(`是否将“需对账单”复制至“${row.clientShortName}”在 ${filters.month} 的其他母订单？`, '复制对账单选择', {confirmButtonText:'同步同月其他项目',cancelButtonText:'仅修改当前项目',distinguishCancelAndClose:true,type:'warning'});copy=true}
      catch(action){if(action!=='cancel')return}
    }
    if(disposed)return
    const data=await setProjectStatementRequired(row.id,{statement_required:value,expected_statement_required:row.statementRequired,expected_updated_at:row.updatedAt||null,copy_to_same_month:copy,billing_month:filters.month})
    if(!disposed){row.statementRequired=data.statementRequired;row.updatedAt=data.updatedAt;emit('saved',data);ElMessage.success(copy?`已同步，修改 ${data.affectedCount} 个项目`:'是否需对账单已保存');await load()}
  }catch(e){if(!disposed){error.value=getLocalizedErrorMessage(e,'保存失败');if(e.response?.status===409)void load()}}finally{savingIds.delete(row.id)}
}
watch(()=>JSON.stringify(props.query),search,{immediate:true})
onBeforeUnmount(()=>{disposed=true;sequence++;clearTimeout(timer);controller?.abort()})
</script>
<style scoped>
.statement-requirements{min-width:0}.statement-requirements :deep(.el-input){width:220px;max-width:100%}.statement-requirements :deep(.el-form--inline .el-form-item){margin-right:16px}.statement-requirements-hint{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 12px}.statement-requirements-saving{font-size:12px;color:var(--el-text-color-secondary);margin-left:6px}.el-pagination{margin-top:16px;justify-content:flex-end;flex-wrap:wrap}
</style>
