<template>
  <DraggableFormDialog v-model="visible" :title="`${projectType} · 搜索选择项目`" class="report-project-picker" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close>
    <el-alert :title="rangeHint" type="info" :closable="false" class="project-picker-hint" />
    <div class="project-picker-search"><el-input v-model="keyword" clearable placeholder="订单号、项目名称、客户名称、翻译方向，可输入多个关键词" aria-label="搜索报告关联项目" @input="onInput" @clear="query" @keyup.enter="query" /><el-button :loading="loading" @click="query">查询</el-button><el-button @click="reset">重置</el-button></div>
    <div class="project-picker-fields"><el-input v-model="clientKeyword" clearable placeholder="搜索客户全称或简称" aria-label="搜索客户名称" @input="onInput" @clear="query" @keyup.enter="query" /><el-input v-model="directionKeyword" clearable placeholder="搜索翻译方向，如：日文 中文" aria-label="搜索翻译方向" @input="onInput" @clear="query" @keyup.enter="query" /></div>
    <details class="project-picker-ranges"><summary>订单时间范围 · {{periodLabel}}</summary><div><el-button v-for="option in periods" :key="option.value" :type="period===option.value?'primary':'default'" @click="changePeriod(option.value)">{{option.label}}</el-button></div></details>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border highlight-current-row row-key="id" @current-change="selected=$event" @row-dblclick="select($event)">
      <el-table-column prop="order_no" label="订单号" width="180" /><el-table-column prop="project_name" label="项目名称" min-width="250" show-overflow-tooltip />
      <el-table-column label="客户名称" min-width="160" show-overflow-tooltip><template #default="{row}">{{row.client_name||row.client_short_name||'-'}}</template></el-table-column>
      <el-table-column prop="translation_direction" label="翻译方向" min-width="140" show-overflow-tooltip><template #default="{row}">{{row.translation_direction||'-'}}</template></el-table-column>
      <el-table-column label="操作" width="85" fixed="right"><template #default="{row}"><el-button type="primary" link @click="select(row)">选定</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :disabled="!selected||loading" @click="select(selected)">确认选择</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {searchReportProjects} from '@/api/projectArrangements'
const props=defineProps({modelValue:Boolean,projectType:{type:String,default:''},taskScope:Boolean})
const emit=defineEmits(['update:modelValue','selected'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const keyword=ref(''),rows=ref([]),selected=ref(null),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
const clientKeyword=ref(''),directionKeyword=ref(''),period=ref('week'),dateFrom=ref(''),dateTo=ref('')
const periods=[{value:'week',label:'最近一周订单'},{value:'month',label:'一个月订单'},{value:'quarter',label:'三个月订单'},{value:'year',label:'一年订单'},{value:'all',label:'全部订单'}]
const periodLabel=computed(()=>periods.find(option=>option.value===period.value)?.label)
const rangeHint=computed(()=>`${props.taskScope?'仅显示工作台“我的任务”中的未取消、未结款口译项目。':''}当前${period.value==='all'?'加载':'仅加载'}${periodLabel.value}${dateFrom.value&&dateTo.value?`（${dateFrom.value} 至 ${dateTo.value}）`:''}，按订单创建日期筛选（UTC+8）。可展开“订单时间范围”切换。`)
let controller,sequence=0,timer
async function load(){const id=++sequence;controller?.abort();controller=new AbortController();selected.value=null;loading.value=true;error.value='';try{const data=await searchReportProjects({project_type:props.projectType,task_scope:props.taskScope||undefined,keyword:keyword.value.trim(),client_keyword:clientKeyword.value.trim(),direction_keyword:directionKeyword.value.trim(),period:period.value,page:page.value},{signal:controller.signal});if(id!==sequence)return;rows.value=data.items;total.value=data.total;dateFrom.value=data.date_from||'';dateTo.value=data.date_to||''}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'搜索项目失败'}finally{if(id===sequence)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
function onInput(value){clearTimeout(timer);sequence++;controller?.abort();selected.value=null;if(!value.trim())query();else timer=setTimeout(query,400)}
function changePeriod(value){period.value=value;dateFrom.value='';dateTo.value='';query()}
function reset(){keyword.value='';clientKeyword.value='';directionKeyword.value='';changePeriod(props.taskScope?'all':'week')}
function select(row){if(!row||loading.value)return;emit('selected',row);visible.value=false}
watch(()=>props.modelValue,open=>{clearTimeout(timer);if(open){rows.value=[];reset()}else{sequence++;controller?.abort();selected.value=null}},{immediate:true})
onBeforeUnmount(()=>{clearTimeout(timer);sequence++;controller?.abort()})
</script>
<style scoped>.project-picker-search{display:flex;gap:12px;margin-bottom:14px}.el-pagination{margin-top:14px;justify-content:flex-end;overflow-x:auto}</style>
<style scoped>.project-picker-hint{margin-bottom:14px}.project-picker-fields{display:flex;gap:12px;margin-bottom:12px}.project-picker-ranges{margin-bottom:14px}.project-picker-ranges summary{cursor:pointer;color:#475569}.project-picker-ranges>div{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.project-picker-ranges .el-button{margin-left:0}@media(max-width:640px){.project-picker-fields{flex-direction:column}.project-picker-search{flex-wrap:wrap}.project-picker-search>.el-input{width:100%}}</style>
