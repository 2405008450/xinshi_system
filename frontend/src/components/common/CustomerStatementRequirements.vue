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
      <el-table-column prop="orderNo" label="订单号" width="120" show-overflow-tooltip />
      <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="clientShortName" sortable="custom" :sort-orders="['ascending','descending',null]" label="客户简称" width="120" show-overflow-tooltip />
      <el-table-column label="对账单状态" width="115"><template #default="{row}"><ProjectStatementStatus :value="row.statementStatus||[]" /></template></el-table-column>
      <el-table-column prop="clientManager" label="客户经理" width="95" show-overflow-tooltip />
      <el-table-column label="项目状态" width="100"><template #default="{row}">{{getProjectStatusLabel('translation',row.projectStatus)}}</template></el-table-column>
      <el-table-column label="是否需对账单" width="115" fixed="right"><template #default="{row}"><CustomerStatementRequiredToggle :row="row" :month="filters.month" @saved="emit('saved',$event)" /></template></el-table-column>
      <el-table-column label="对账单" width="80" fixed="right"><template #default="{row}"><RouterLink v-if="hasMonthlyStatement(row)" class="statement-view-link" :to="{name:'CustomerStatementPage',params:{clientId:row.clientId},query:{month:filters.month}}" :title="`查看 ${row.clientShortName} ${filters.month} 的已生成对账单`" @click="emit('navigate')">查看</RouterLink><span v-else>无</span></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="slot, prev, pager, next, jumper" @current-change="load"><span>共 {{total}} 条</span></el-pagination>
  </section>
</template>
<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {RouterLink} from 'vue-router'
import CustomerStatementRequiredToggle from './CustomerStatementRequiredToggle.vue'
import AppForm from './AppForm.vue'
import ProjectStatementStatus from './ProjectStatementStatus.vue'
import AdvancedFilterPopover from './AdvancedFilterPopover.vue'
import {getCustomerFinancePage,setProjectStatementRequired} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {getProjectStatusLabel,getProjectStatusOptions} from '@/utils/projectStatus'
import {currentStatementMonth,previousStatementMonth} from '@/utils/statementRequirementMonth'
const props=defineProps({query:{type:Object,default:()=>({})}})
const emit=defineEmits(['view','saved','navigate','managers'])
const hasMonthlyStatement=row=>!!row.clientId&&(row.customerStatements||[]).some(board=>(board.months||[]).includes(filters.month))
const canWrite=hasPermission('projects:write')
const filters=reactive({month:currentStatementMonth(),keyword:'',client:'',required:'',status:''}),rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),error=ref(''),savingIds=reactive(new Set())
const tableRef=ref(),sortOrder=ref(''),advancedVisible=ref(false),statuses=getProjectStatusOptions('translation')
const advancedCount=computed(()=>Number(!!filters.required)+Number(!!filters.status))
function clearAdvanced(){filters.required='';filters.status='';search()}
function changeSort({order}){sortOrder.value=order==='ascending'?'client_short_name_asc':order==='descending'?'client_short_name_desc':'';search()}
let controller,sequence=0,timer,disposed=false
function params(){return {...props.query,group_clients:false,billing_month:filters.month,keyword:filters.keyword.trim()||undefined,client:filters.client.trim()||undefined,project_status:filters.status||undefined,statement_required:filters.required==='yes'?true:filters.required==='no'?false:undefined,sort:sortOrder.value||undefined,skip:(page.value-1)*10,limit:10}}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getCustomerFinancePage(params(),{signal:controller.signal});if(seq===sequence&&!disposed){rows.value=data.items||[];total.value=data.total||0;emit('managers',[...new Set(rows.value.map(row=>row.clientManager||'未分配'))])}}catch(e){if(seq===sequence&&!disposed&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'笔译项目加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function selectMonth(month){filters.month=month;search()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function reset(){Object.assign(filters,{month:currentStatementMonth(),keyword:'',client:'',required:'',status:''});sortOrder.value='';tableRef.value?.clearSort();search()}
function onStatementChanged(){void load()}
window.addEventListener('translation-statements-changed',onStatementChanged)
watch(()=>JSON.stringify(props.query),search,{immediate:true})
onBeforeUnmount(()=>{window.removeEventListener('translation-statements-changed',onStatementChanged);disposed=true;sequence++;clearTimeout(timer);controller?.abort()})
useProjectStatusSync('translation',rows,{onChanged:()=>{if(!loading.value)void load()}})
</script>
<style scoped>
.statement-view-link{color:var(--el-color-primary);text-decoration:none}.statement-view-link:hover{text-decoration:underline}
.statement-requirements{min-width:0}.statement-requirements :deep(.el-input){width:220px;max-width:100%}.statement-requirements :deep(.el-form--inline .el-form-item){margin-right:16px}.statement-requirements-hint{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 12px}.statement-requirements-saving{font-size:12px;color:var(--el-text-color-secondary);margin-left:6px}.el-pagination{margin-top:16px;justify-content:flex-end;flex-wrap:wrap}
</style>
