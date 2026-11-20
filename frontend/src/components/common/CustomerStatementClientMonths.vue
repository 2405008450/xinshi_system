<template>
  <section class="client-months-group" :class="{'drop-active':dragOver}" @dragover="over" @dragleave="leave" @drop.prevent="drop">
    <header><strong>{{groupLabel}} · {{items.length}}</strong><div v-if="canExpand"><el-button link @click="expandAll">全部展开</el-button><el-button link @click="expanded=[];expandedMonths=[]">全部收起</el-button></div></header>
    <el-input v-model="keyword" :aria-label="`${groupLabel}搜索`" placeholder="搜索客户或子客户名称、简称或编号" clearable @input="queueSearch" @keyup.enter="search"><template #append><el-button @click="search">查询</el-button></template></el-input>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link :disabled="loading" @click="load">重试</el-button></el-alert>
    <div v-loading="loading" class="client-months-list">
      <p v-if="settlementScope!=='special'" class="drop-hint">{{dragOver?'松开鼠标调整此月份的分类':'可将另一栏的月份拖到这里调整对账单需求'}}</p>
      <el-empty v-if="!items.length&&!loading&&!error" description="所选月份没有匹配客户" :image-size="55" />
      <el-collapse v-model="expanded">
        <el-collapse-item v-for="client in pagedItems" :key="client.id" :name="client.id" :disabled="!canExpand">
          <template #title><div class="client-heading"><strong>{{client.shortName||client.name}}</strong><small>{{client.code}} · {{client.months.length}} 个月份 · {{client.projectCount}} 个项目 · 客户经理：{{client.clientManagers.join('、')||'未分配'}}</small></div></template>
          <el-collapse v-if="expanded.includes(client.id)" v-model="expandedMonths" class="client-months">
            <el-collapse-item v-for="entry in client.months" :key="entry.month" :name="monthKey(client,entry)">
              <template #title>
                <div class="month-heading" :draggable="canWrite&&!moving&&settlementScope!=='special'" @dragstart="startDrag($event,entry)" @dragend="dragOver=false">
                  <strong>{{entry.month}}</strong><small>{{entry.client.projectCount}} 个项目<span v-if="entry.client.pendingCount"> · 待入账 {{entry.client.pendingCount}} 项</span></small>
                  <el-select :model-value="entry.client.progress||'not_started'" :disabled="!canWrite||progressSaving.has(monthKey(client,entry))" size="small" :aria-label="`${entry.month} ${settlementScope==='special'?'特殊结算':'对账单'}进度`" style="width:115px" @click.stop @mousedown.stop @dragstart.prevent.stop @change="saveProgress(entry,$event)">
                    <el-option label="未开始" value="not_started" /><el-option label="部分完成" value="partial" /><el-option label="全部完成" value="completed" />
                  </el-select>
                </div>
              </template>
              <CustomerStatementClientWorkspace v-if="expandedMonths.includes(monthKey(client,entry))" :client="entry.client" :month="entry.month" :period-number="periodNumber" :settlement-scope="settlementScope" :required="required" :moving="moving" :manager-query="managerQuery" @move-client="emit('move-client',$event)" />
            </el-collapse-item>
          </el-collapse>
        </el-collapse-item>
      </el-collapse>
    </div>
    <el-pagination v-if="items.length>pageSize" v-model:current-page="page" :page-size="pageSize" :total="items.length" layout="slot,prev,pager,next"><span>共 {{items.length}} 个客户</span></el-pagination>
  </section>
</template>

<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import CustomerStatementClientWorkspace from './CustomerStatementClientWorkspace.vue'
import {getStatementCustomerGroups,setStatementProgress} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {groupStatementClientsByMonth} from '@/utils/statementClientMonths'
const props=defineProps({months:{type:Array,default:()=>[]},keywordValue:{type:String,default:''},periodNumber:Number,
  settlementScope:String,required:Boolean,progressFilter:String,moving:Boolean,managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['drop-client','move-client','managers','keyword-change'])
const groupLabel=computed(()=>props.settlementScope==='special'?(props.required?'特殊结算客户':'非特殊结算客户'):(props.required?'需对账单客户':'无需对账单客户'))
const canExpand=computed(()=>props.settlementScope!=='special'||props.required)
const canWrite=hasPermission('projects:write'),pageSize=20
const items=ref([]),page=ref(1),keyword=ref(props.keywordValue),expanded=ref([]),expandedMonths=ref([]),progressSaving=ref(new Set())
const loading=ref(false),error=ref(''),dragOver=ref(false)
const pagedItems=computed(()=>items.value.slice((page.value-1)*pageSize,page.value*pageSize))
const monthKey=(client,entry)=>`${client.id}:${entry.month}`
let controller,sequence=0,timer
async function load(){
  clearTimeout(timer);controller?.abort();const request=controller=new AbortController(),seq=++sequence
  loading.value=true;error.value=''
  const months=[...new Set(props.months)].sort(),sources=[]
  try{
    // 按月读取完整客户清单后去重，再按客户分页；限制并发避免占满业务连接池。
    async function worker(){
      while(months.length&&!request.signal.aborted){
        const month=months.shift(),rows=[];let skip=0,total=0
        do{
          const data=await getStatementCustomerGroups({...props.managerQuery,billing_month:month,period_number:props.periodNumber,
            settlement_scope:props.settlementScope,statement_required:props.required,progress:props.progressFilter||undefined,
            keyword:keyword.value.trim()||undefined,skip,limit:100},{signal:request.signal})
          if(seq!==sequence||request.signal.aborted)return
          rows.push(...(data.items||[]));total=data.total||0;skip+=100
          if(!data.items?.length)break
        }while(skip<total)
        sources.push({month,items:rows})
      }
    }
    await Promise.all(Array.from({length:Math.min(2,months.length)},worker))
    if(seq!==sequence||request.signal.aborted)return
    items.value=groupStatementClientsByMonth(sources)
    page.value=Math.min(page.value,Math.max(1,Math.ceil(items.value.length/pageSize)))
    expanded.value=expanded.value.filter(id=>items.value.some(client=>client.id===id))
    const keys=new Set(items.value.flatMap(client=>client.months.map(entry=>monthKey(client,entry))))
    expandedMonths.value=expandedMonths.value.filter(key=>keys.has(key))
  }catch(cause){
    if(seq===sequence&&cause.code!=='ERR_CANCELED'){request.abort();items.value=[];error.value=getLocalizedErrorMessage(cause,'客户加载失败')}
  }finally{if(seq===sequence)loading.value=false}
}
function search(){page.value=1;void load()}
function queueSearch(value){emit('keyword-change',value);clearTimeout(timer);controller?.abort();sequence++;if(!value.trim())search();else timer=setTimeout(search,400)}
function expandAll(){expanded.value=pagedItems.value.map(client=>client.id);expandedMonths.value=pagedItems.value.flatMap(client=>client.months.map(entry=>monthKey(client,entry)))}
async function saveProgress(entry,progress){
  const key=monthKey(entry.client,entry);progressSaving.value.add(key)
  try{const result=await setStatementProgress(entry.client.id,{billing_month:entry.month,progress,revision:entry.client.progressRevision||0,...props.managerQuery});Object.assign(entry.client,result);if(props.progressFilter&&props.progressFilter!==progress)await load()}
  catch(cause){error.value=getLocalizedErrorMessage(cause,'对账单进度保存失败');if(cause.response?.status===409)await load()}
  finally{progressSaving.value.delete(key)}
}
function startDrag(event,entry){if(!canWrite||props.moving||props.settlementScope==='special'){event.preventDefault();return}event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-statement-client',JSON.stringify({...entry.client,statementRequired:props.required,statementBillingMonth:entry.month}))}
function over(event){if(!canWrite||props.moving||props.settlementScope==='special'||!Array.from(event.dataTransfer?.types||[]).includes('application/x-statement-client'))return;event.preventDefault();event.dataTransfer.dropEffect='move';dragOver.value=true}
function drop(event){dragOver.value=false;if(!canWrite||props.moving||props.settlementScope==='special')return;try{emit('drop-client',JSON.parse(event.dataTransfer.getData('application/x-statement-client')))}catch{}}
function leave(event){if(!event.currentTarget.contains(event.relatedTarget))dragOver.value=false}
watch([items,expanded],()=>{const shown=expanded.value.length?items.value.filter(client=>expanded.value.includes(client.id)):items.value;emit('managers',[...new Set(shown.flatMap(client=>client.clientManagers))])},{deep:true})
watch(()=>[JSON.stringify(props.months),props.periodNumber,props.progressFilter,JSON.stringify(props.managerQuery)],()=>{expanded.value=[];expandedMonths.value=[];search()},{immediate:true})
watch(()=>props.keywordValue,value=>{if(value!==keyword.value){keyword.value=value;queueSearch(value)}})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
defineExpose({refresh:search})
</script>

<style scoped>
.client-months-group{min-width:0;border:1px solid var(--el-border-color);border-radius:8px;padding:12px;background:#fff}.drop-active{outline:2px solid var(--el-color-primary)}header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}.client-months-list{min-height:150px}.client-heading{display:grid;gap:3px;line-height:1.5;padding:10px 0;min-width:0}.client-heading small,.month-heading small,.drop-hint{font-size:11px;color:var(--el-text-color-secondary)}.month-heading{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:8px 0;min-width:0}.month-heading[draggable=true]{cursor:grab}.client-months{margin-left:12px}.client-months-group :deep(.el-collapse-item__header){height:auto;min-height:48px;gap:8px}.client-months-group :deep(.el-collapse-item__content){padding-bottom:12px}.el-pagination{margin-top:12px;max-width:100%;overflow-x:auto}
</style>
