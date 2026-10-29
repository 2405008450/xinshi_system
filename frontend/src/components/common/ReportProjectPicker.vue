<template>
  <DraggableFormDialog v-model="visible" :title="`${projectType} · 搜索选择项目`" class="report-project-picker" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close>
    <div class="project-picker-search"><el-input v-model="keyword" clearable placeholder="搜索订单号或项目名称，可输入多个关键词" aria-label="搜索报告关联项目" @input="onInput" @clear="query" @keyup.enter="query" /><el-button :loading="loading" @click="query">查询</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border highlight-current-row row-key="id" @current-change="selected=$event" @row-dblclick="select($event)">
      <el-table-column prop="order_no" label="订单号" width="180" /><el-table-column prop="project_name" label="项目名称" min-width="250" show-overflow-tooltip />
      <el-table-column label="操作" width="85"><template #default="{row}"><el-button type="primary" link @click="select(row)">选定</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :disabled="!selected||loading" @click="select(selected)">确认选择</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {searchReportProjects} from '@/api/projectArrangements'
const props=defineProps({modelValue:Boolean,projectType:{type:String,default:''}})
const emit=defineEmits(['update:modelValue','selected'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const keyword=ref(''),rows=ref([]),selected=ref(null),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
let controller,sequence=0,timer
async function load(){const id=++sequence;controller?.abort();controller=new AbortController();selected.value=null;loading.value=true;error.value='';try{const data=await searchReportProjects({project_type:props.projectType,keyword:keyword.value.trim(),page:page.value},{signal:controller.signal});if(id!==sequence)return;rows.value=data.items;total.value=data.total}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'搜索项目失败'}finally{if(id===sequence)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
function onInput(value){clearTimeout(timer);if(!value.trim())query();else timer=setTimeout(query,400)}
function select(row){if(!row||loading.value)return;emit('selected',row);visible.value=false}
watch(()=>props.modelValue,open=>{clearTimeout(timer);if(open){keyword.value='';rows.value=[];page.value=1;load()}else{sequence++;controller?.abort();selected.value=null}})
onBeforeUnmount(()=>{clearTimeout(timer);sequence++;controller?.abort()})
</script>
<style scoped>.project-picker-search{display:flex;gap:12px;margin-bottom:14px}.el-pagination{margin-top:14px;justify-content:flex-end;overflow-x:auto}</style>
