<template>
  <DraggableFormDialog :model-value="modelValue" title="同客户历史项目 · 同步翻译方向" width="min(1120px, calc(100vw - 32px))" top="5vh" class="customer-direction-history-dialog" append-to-body destroy-on-close @update:model-value="$emit('update:modelValue',$event)">
    <p class="customer-history-note">客户：{{ clientName || '当前客户' }}。按客户档案精确匹配，包含该客户下的子客户项目；按创建日期筛选，不包含当前编辑的项目。首次打开从最近一周开始，没有项目则依次扩大到一个月、一年、全部。</p>
    <div class="customer-history-query"><el-select v-model="period" aria-label="历史项目时间范围" style="width:170px" @change="search(false)"><el-option v-for="item in periods" :key="item.value" :value="item.value" :label="item.label" /></el-select><el-input v-model="keyword" clearable placeholder="搜索订单号、项目名称、翻译方向" @input="onInput" @keyup.enter="search(false)" /><el-button type="primary" @click="search(false)">查询</el-button><el-button @click="reset">重置</el-button></div>
    <p v-if="expanded" class="customer-history-note">较近范围没有项目，已自动扩大至{{ periods.find(item=>item.value===period)?.label }}。</p>
    <el-alert v-if="failure" :title="failure" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border highlight-current-row max-height="330" empty-text="该时间范围暂无同客户项目" @current-change="select">
      <el-table-column label="选择" width="65"><template #default="{row}"><el-radio :model-value="selected?.id" :value="row.id" :aria-label="'选择'+row.order_no" @change="select(row)"><span /></el-radio></template></el-table-column>
      <el-table-column prop="order_no" label="订单号" min-width="170" /><el-table-column prop="project_name" label="项目名称" min-width="240" show-overflow-tooltip /><el-table-column prop="language_pair" label="当时的翻译方向" min-width="220" show-overflow-tooltip /><el-table-column label="创建时间" min-width="180"><template #default="{row}">{{ formatBusinessDateTimeMinute(row.created_at) }}</template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load(false)" />
    <section v-if="selected" class="customer-history-selection"><p>已选项目：{{ selected.order_no }} · {{ selected.project_name }}</p><AppForm label-position="top"><el-form-item label="将带入的翻译方向（可增减）"><LanguagePairSelect v-model="directions" :show-hint="false" /></el-form-item></AppForm><p v-if="!selected.language_pair" class="customer-history-note">该历史项目未填写翻译方向，可先选择所需方向。</p><small>这里只调整当前表单的翻译方向，不修改历史项目；同步后仍可调整，保存当前项目后才正式生效。</small></section>
    <template #footer><el-button @click="$emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="loading || !selected || !directions.trim()" @click="apply">同步翻译方向</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import {getCustomerTranslationHistory} from '@/api/translationCustomerHistory'
import {formatBusinessDateTimeMinute} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean,clientId:String,clientName:String,projectId:String})
const emit=defineEmits(['update:modelValue','apply'])
const periods=[{value:'week',label:'最近一周'},{value:'month',label:'最近一个月（30天）'},{value:'year',label:'最近一年（365天）'},{value:'all',label:'全部'}]
const period=ref('week'),keyword=ref(''),rows=ref([]),selected=ref(null),directions=ref(''),total=ref(0),page=ref(1),loading=ref(false),failure=ref(''),expanded=ref(false)
let controller=null,request=0,timer=null,loadedOwner=null
function stop(){clearTimeout(timer);request++;controller?.abort();loading.value=false}
function select(row){selected.value=row;directions.value=row?.language_pair||''}
async function load(autoExpand=false){
 clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++request,owner=localStorage.getItem('user_id'),client=props.clientId
 if(!props.modelValue||!client){rows.value=[];total.value=0;return}
 loading.value=true;failure.value='';select(null);rows.value=[]
 try{
  let index=periods.findIndex(item=>item.value===period.value)
  while(index<periods.length){
   const result=await getCustomerTranslationHistory({client_id:client,period:periods[index].value,keyword:keyword.value.trim()||undefined,skip:(page.value-1)*20,limit:20,exclude_project_id:props.projectId||undefined},{signal:controller.signal})
   if(current!==request||!props.modelValue||client!==props.clientId||owner!==localStorage.getItem('user_id'))return
   period.value=periods[index].value
   if(autoExpand&&!result.total&&index<periods.length-1){expanded.value=true;index++;continue}
   rows.value=result.items||[];total.value=result.total||0;loadedOwner=owner;break
  }
 }catch(error){if(current===request&&error?.code!=='ERR_CANCELED'&&error?.name!=='AbortError')failure.value=getLocalizedErrorMessage(error,'历史项目加载失败，请重试')}
 finally{if(current===request)loading.value=false}
}
function search(autoExpand=false){clearTimeout(timer);page.value=1;expanded.value=false;void load(autoExpand)}
function onInput(value){clearTimeout(timer);controller?.abort();request++;loading.value=false;select(null);if(!value.trim())return search();timer=setTimeout(()=>search(),400)}
function reset(){keyword.value='';period.value='week';search(true)}
function apply(){if(loading.value||!selected.value||!directions.value.trim()||!props.modelValue||loadedOwner!==localStorage.getItem('user_id'))return;emit('apply',{clientId:props.clientId,projectId:props.projectId||'',sourceProjectId:selected.value.id,languagePair:directions.value});emit('update:modelValue',false)}
watch(()=>[props.modelValue,props.clientId,props.projectId],([visible])=>{stop();select(null);rows.value=[];total.value=0;if(visible){keyword.value='';period.value='week';search(true)}},{immediate:true})
onBeforeUnmount(stop)
</script>
<style>
.customer-direction-history-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.customer-direction-history-dialog>.el-dialog__body{min-height:0;overflow-y:auto}.customer-direction-history-dialog>.el-dialog__header,.customer-direction-history-dialog>.el-dialog__footer{flex:none}.customer-history-query{display:flex;gap:10px;margin:12px 0}.customer-history-query>.el-input{flex:1}.customer-history-note,.customer-history-selection small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}.customer-history-selection{margin-top:12px;padding:10px;border:1px solid var(--el-border-color);border-radius:6px}.customer-direction-history-dialog .el-pagination{margin-top:12px}@media(max-width:700px){.customer-history-query{flex-wrap:wrap}.customer-history-query>.el-input{flex-basis:100%}}
</style>
