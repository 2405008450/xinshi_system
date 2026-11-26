<template>
  <el-button @click="visible=true">名称修改/删除记录</el-button>
  <DraggableFormDialog v-model="visible" title="客户名称修改/删除记录" append-to-body
    width="min(1100px, calc(100vw - 32px))" top="5vh" class="client-name-history-dialog">
    <el-input v-model="keyword" placeholder="搜索客户编号、修改前后名称" clearable
      aria-label="搜索名称记录" @input="search" @keyup.enter="query" />
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-table v-loading="loading" :data="items" border>
      <el-table-column label="操作时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.occurred_at)}}</template></el-table-column>
      <el-table-column prop="actor_name" label="操作人" width="110" />
      <el-table-column prop="client_code" label="客户编号" width="170" />
      <el-table-column label="操作" width="110"><template #default="{row}">{{row.sub_client?'子客户':'客户'}}{{row.operation==='delete'?'删除':'改名'}}</template></el-table-column>
      <el-table-column label="名称变更" min-width="350"><template #default="{row}">
        <div v-for="(label,field) in fields" :key="field">
          <template v-if="row.operation==='delete' ? row.before[field] : row.before[field]!==row.after[field]">
            {{label}} {{row.before[field] || '空'}} → {{row.operation==='delete'?'已删除':row.after[field] || '空'}}
          </template>
        </div>
      </template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
      :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next"
      @current-change="load" @size-change="query" />
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import api from '@/api'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:String})
const visible=ref(false),keyword=ref(''),items=ref([]),total=ref(0),page=ref(1),pageSize=ref(10)
const loading=ref(false),error=ref('')
const fields={client_name:'客户全称',client_short_name:'客户简称',english_name:'英文全称',english_short_name:'英文简称'}
let request,timer
async function load(){
  request?.abort()
  const current=request=new AbortController()
  loading.value=true
  error.value=''
  try{
    const data=await api.get('/clients/name-history',{signal:current.signal,params:{
      client_id:props.clientId || undefined,keyword:keyword.value,page:page.value,page_size:pageSize.value,
    }})
    if(current.signal.aborted)return
    items.value=data.items
    total.value=data.total
  }catch(e){if(!current.signal.aborted)error.value=getLocalizedErrorMessage(e,'读取名称记录失败')}
  finally{if(!current.signal.aborted)loading.value=false}
}
function query(){clearTimeout(timer);page.value=1;void load()}
function search(value){clearTimeout(timer);if(!value)query();else timer=setTimeout(query,400)}
watch(visible,value=>{
  clearTimeout(timer)
  if(value){keyword.value='';query()}
  else request?.abort()
})
onBeforeUnmount(()=>{clearTimeout(timer);request?.abort()})
</script>
<style scoped>
.el-table,.el-pagination{margin-top:12px}
.el-pagination{flex-wrap:wrap}
.el-table :deep(.cell){overflow-wrap:anywhere}
</style>
<style>
.client-name-history-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.client-name-history-dialog .el-dialog__header,.client-name-history-dialog .el-dialog__footer{flex-shrink:0}
.client-name-history-dialog .el-dialog__body{min-height:0;overflow-y:auto}
</style>
