<template>
  <DraggableFormDialog :model-value="modelValue" title="复用项目信息" width="min(1150px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="$emit('update:modelValue',$event)">
    <el-alert title="目前只支持复用母订单（无论是否包含子订单）的信息。" type="info" :closable="false" />
    <div class="reuse-search"><el-input v-model="keyword" clearable placeholder="订单号、客户名称、项目名称、翻译方向、客户经理、客户类型；支持多个关键词" @keyup.enter="search" /><el-button type="primary" @click="search">查询</el-button><el-button @click="keyword='';search()">重置</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border highlight-current-row max-height="420" @current-change="selected=$event">
      <el-table-column label="选择" width="65"><template #default="{row}"><el-radio :model-value="selected?.id" :value="row.id" :aria-label="`选择${row.orderNo}`" @change="selected=row"><span /></el-radio></template></el-table-column>
      <el-table-column prop="orderNo" label="订单号" min-width="175" />
      <el-table-column prop="clientShortName" label="客户名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="customerType" label="客户类型" min-width="125" />
      <el-table-column prop="projectName" label="项目名称" min-width="230" show-overflow-tooltip />
      <el-table-column prop="languagePair" label="翻译方向" min-width="170" show-overflow-tooltip />
      <el-table-column prop="clientManager" label="客户经理" min-width="110" />
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
    <p v-if="selected">已选：{{ selected.orderNo }} · {{ selected.clientShortName }} · {{ selected.projectName }}</p>
    <template #footer><el-button @click="$emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="!selected || loading" :loading="applying" @click="$emit('reuse',selected)">复用信息</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getProjectPage} from '@/api/projects'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean,applying:Boolean})
defineEmits(['update:modelValue','reuse'])
const keyword=ref(''),page=ref(1),total=ref(0),rows=ref([]),selected=ref(null),loading=ref(false),error=ref('')
let timer,request=0,controller
function stop(){clearTimeout(timer);request++;controller?.abort();loading.value=false}
async function load(){
  clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++request
  loading.value=true;error.value='';selected.value=null
  try{const result=await getProjectPage({keyword:keyword.value.trim()||undefined,skip:(page.value-1)*20,limit:20,sort:'order_no_desc'},{signal:controller.signal});if(current!==request)return;rows.value=result.items||[];total.value=result.total||0}
  catch(e){if(current===request&&e.code!=='ERR_CANCELED'){rows.value=[];total.value=0;error.value=getLocalizedErrorMessage(e,'加载历史母订单失败')}}
  finally{if(current===request)loading.value=false}
}
function search(){page.value=1;load()}
watch(keyword,value=>{stop();if(!props.modelValue)return;if(!value.trim())search();else timer=setTimeout(search,400)})
watch(()=>props.modelValue,visible=>{stop();if(visible){keyword.value='';page.value=1;rows.value=[];selected.value=null;load()}})
onBeforeUnmount(stop)
</script>
<style scoped>
.reuse-search{display:flex;gap:12px;margin:16px 0}.el-pagination{margin-top:14px}p{font-size:13px;color:#475569}
</style>
