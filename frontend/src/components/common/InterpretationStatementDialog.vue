<template>
  <DraggableFormDialog :model-value="modelValue" class="interpretation-statement-dialog"
    width="min(1160px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close
    @update:model-value="$emit('update:modelValue',$event)">
    <template #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="口译对账单"
        :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
    </template>
    <div ref="body" v-loading="loading">
      <AppForm :model="filters" inline @submit.prevent="load">
        <el-form-item label="项目">
          <el-select v-model="filters.id" filterable remote :remote-method="searchProjects" :loading="searching"
            placeholder="搜索订单号、项目名称或客户" style="width:300px;max-width:100%" @change="changeProject">
            <el-option v-for="row in options" :key="row.id" :value="row.id" :label="`${row.order_no} · ${row.project_name||'-'}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="账单月份">
          <el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" :clearable="false" @change="load" />
        </el-form-item>
        <el-form-item label="对账范围">
          <el-select v-model="filters.scope" style="width:130px" @change="load">
            <el-option label="单个项目" value="project" /><el-option label="同客户汇总" value="customer" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额口径">
          <el-select v-model="filters.basis" style="width:140px" @change="load">
            <el-option label="按项目设置" value="" /><el-option label="不含税" value="excl_tax" />
            <el-option label="含税" value="incl_tax" /><el-option label="税口径未确认" value="legacy" />
          </el-select>
        </el-form-item>
      </AppForm>
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <div v-if="statement?.rows.length" class="interpretation-statement-paper"><CustomerStatementPaper :statement="statement" /></div>
      <el-empty v-else-if="!loading&&!error" :description="filters.id?'所选月份暂无对账明细':'请选择口译项目'" />
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue',false)">关闭</el-button>
      <el-button :disabled="!statement?.rows.length||!!exporting" :loading="exporting==='excel'" @click="download('excel')">导出 Excel</el-button>
      <el-button :disabled="!statement?.rows.length||!!exporting" :loading="exporting==='pdf'" @click="download('pdf')">下载 PDF</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {onBeforeUnmount,reactive,ref,watch} from 'vue'
import {getInterpretationFinancePage,getInterpretationStatement} from '@/api/interpretationCustomerFinance'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {businessDateTimeInputValue} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {statementFileName} from '@/utils/statementFormatting'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'

const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})}})
defineEmits(['update:modelValue'])
const body=ref(),options=ref([]),statement=ref(null),loading=ref(false),searching=ref(false),error=ref(''),exporting=ref('')
const filters=reactive({id:'',month:'',scope:'project',basis:''})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let searchController,loadController
const params=()=>({month:filters.month,scope:filters.scope,basis:filters.basis||undefined})

async function searchProjects(keyword=''){
  searchController?.abort()
  const controller=searchController=new AbortController()
  searching.value=true
  try{
    const data=await getInterpretationFinancePage({...props.query,keyword,skip:0,limit:40},controller.signal)
    if(controller.signal.aborted)return
    const selected=options.value.find(row=>row.id===filters.id)
    options.value=data.items
    if(selected&&!options.value.some(row=>row.id===selected.id))options.value.unshift(selected)
  }catch(e){
    if(!controller.signal.aborted)error.value=getLocalizedErrorMessage(e,'口译项目搜索失败')
  }finally{if(!controller.signal.aborted)searching.value=false}
}

function changeProject(){
  const row=options.value.find(item=>item.id===filters.id)
  const orderDate=row?.order_no?.match(/^IP-(?:20)?(\d{2})(\d{2})\d{2}-/)
  filters.month=row?.payload?.settlement?.billing_month||(orderDate?`20${orderDate[1]}-${orderDate[2]}`:businessDateTimeInputValue().slice(0,7))
  void load()
}

async function load(){
  loadController?.abort()
  statement.value=null;error.value='';loading.value=false
  if(!filters.id||!filters.month)return
  const controller=loadController=new AbortController()
  loading.value=true
  try{
    const data=await getInterpretationStatement(filters.id,params(),{signal:controller.signal})
    if(!controller.signal.aborted)statement.value=data
  }catch(e){
    if(!controller.signal.aborted)error.value=getLocalizedErrorMessage(e,'口译对账单生成失败')
  }finally{if(!controller.signal.aborted)loading.value=false}
}

async function download(format){
  const data=statement.value
  if(!data||exporting.value)return
  exporting.value=format
  try{
    const blob=await getInterpretationStatement(filters.id,{...params(),format,version:data.statement_version},{responseType:'blob'})
    const url=URL.createObjectURL(blob),link=document.createElement('a')
    link.href=url
    link.download=statementFileName(`${data.client_name} 口译对账单 ${data.month}`,format)
    link.click()
    setTimeout(()=>URL.revokeObjectURL(url),30000)
  }catch(e){error.value=getLocalizedErrorMessage(e,'导出失败，请重新生成对账单后重试')}
  finally{exporting.value=''}
}

function cancelRequests(){searchController?.abort();loadController?.abort()}
watch(()=>props.modelValue,visible=>{
  cancelRequests()
  if(!visible)return
  clearFieldSearch()
  options.value=[...props.projects]
  Object.assign(filters,{id:options.value[0]?.id||'',scope:'project',basis:''})
  changeProject()
  void searchProjects()
},{immediate:true})
onBeforeUnmount(cancelRequests)
</script>

<style scoped>
:global(.interpretation-statement-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.interpretation-statement-dialog>.el-dialog__header),:global(.interpretation-statement-dialog>.el-dialog__footer){flex:none}
:global(.interpretation-statement-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}
:global(.interpretation-statement-dialog>.el-dialog__footer){border-top:1px solid var(--el-border-color-light)}
.interpretation-statement-paper{overflow:auto}
</style>
