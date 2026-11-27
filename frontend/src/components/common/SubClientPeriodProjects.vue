<template>
  <el-popover v-model:visible="visible" title="同期子客户项目" trigger="click" placement="bottom-start"
    width="min(460px, calc(100vw - 32px))" @mousedown.stop>
    <template #reference>
      <el-button size="small" :aria-expanded="visible" @mousedown.stop>同期子客户项目</el-button>
    </template>
    <div v-loading="loading" class="period-projects">
      <el-alert v-if="error" :title="error" type="error" :closable="false">
        <el-button link @click="load">重新加载</el-button>
      </el-alert>
      <template v-else-if="result">
        <div v-if="result.month">{{ result.month }} · {{result.period ? `第${result.period}期` : '未分账期'}}</div>
        <ul v-if="result.items.length">
          <li v-for="project in result.items" :key="project.id">
            <strong>{{ project.orderNo }}</strong> {{ project.projectName }}
          </li>
        </ul>
        <p v-else>暂无同期子客户项目</p>
      </template>
    </div>
  </el-popover>
</template>

<script setup>
import {onBeforeUnmount, ref, watch} from 'vue'
import {getSubClientPeriodProjects} from '@/api/translationCustomerFinance'
import {readOralPeriodProjects} from '@/api/interpretationSettlementSettings'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'

const props=defineProps({projectId:{type:String,required:true},periodKey:String,module:{type:String,default:'translation'}})
const visible=ref(false), loading=ref(false), error=ref(''), result=ref(null)
let request
async function load(){
  request?.abort()
  const current=new AbortController()
  request=current
  loading.value=true
  error.value=''
  result.value=null
  try{
    const data=await (props.module==='interpretation'?readOralPeriodProjects(props.projectId,current.signal):getSubClientPeriodProjects(props.projectId,current.signal))
    if(!current.signal.aborted)result.value=data
  }catch(cause){
    if(!current.signal.aborted)error.value=getLocalizedErrorMessage(cause,'同期项目加载失败')
  }finally{
    if(!current.signal.aborted)loading.value=false
  }
}
watch(()=>[visible.value,props.projectId,props.periodKey],([open])=>{
  if(open)void load()
  else request?.abort()
})
onBeforeUnmount(()=>request?.abort())
</script>

<style scoped>
.period-projects{min-height:48px;max-height:min(360px,60vh);overflow:auto;overflow-wrap:anywhere}
ul{padding-inline-start:18px;margin:8px 0 0}
li+li{margin-top:6px}
</style>
