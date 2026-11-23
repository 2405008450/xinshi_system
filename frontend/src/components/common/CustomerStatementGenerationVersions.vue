<template>
  <DraggableFormDialog :model-value="modelValue" title="对账单历史版本" append-to-body
    width="min(1140px, calc(100vw - 32px))" top="5vh" class="statement-generation-versions"
    @update:model-value="emit('update:modelValue',$event)">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="selected">
        <p>第 {{selected.revision}} 版 · {{formatBusinessDateTime(selected.created_at)}}</p>
        <section v-for="board in selected.documents" :key="board.id" class="generation-version-paper">
          <h4>{{board.name}} <el-select :model-value="board.status||'void'" :aria-label="`历史账单状态：${board.name}`" :disabled="!canWrite||loading" style="width:100px" @change="status=>changeStatus(board,status)"><el-option value="active" label="有效" /><el-option value="void" label="废除" /></el-select></h4>
          <CustomerStatementPaper :statement="board.statement" />
        </section>
      </template>
      <template v-else>
        <el-table :data="items" row-key="id" border empty-text="暂无历史版本">
          <el-table-column prop="revision" label="版本" width="75" />
          <el-table-column label="记录时间" width="175">
            <template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template>
          </el-table-column>
          <el-table-column prop="actor_name" label="操作人" width="95" />
          <el-table-column label="状态" width="75"><template #default="{row}"><el-tag :type="row.status==='active'?'success':'danger'">{{row.status==='active'?'有效':'废除'}}</el-tag></template></el-table-column>
          <el-table-column prop="action" label="归档原因" min-width="140" />
          <el-table-column label="账单月份" width="165">
            <template #default="{row}">{{row.months.join('、')}}<span v-if="row.period_number"> · 第{{row.period_number}}期</span></template>
          </el-table-column>
          <el-table-column label="订单组合" min-width="260" show-overflow-tooltip>
            <template #default="{row}">{{row.orders.join('、')}}</template>
          </el-table-column>
          <el-table-column label="操作" width="110">
            <template #default="{row}"><el-button link type="primary" @click="openVersion(row.id)">查看 / 调整</el-button></template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
      </template>
    </div>
    <template #footer>
      <el-button v-if="selected" @click="selected=null;load()">返回版本列表</el-button>
      <el-button @click="emit('update:modelValue',false)">关闭</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import {getStatementHistoricalVersions,getStatementHistoricalVersion,previewStatementVersionStatus,changeStatementWorkspace} from '@/api/customerStatements'
import {ElMessageBox,ElMessage} from 'element-plus'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'

const props=defineProps({modelValue:Boolean,clientId:String,settlementScope:String,revision:Number,mode:String,canWrite:Boolean})
const emit=defineEmits(['update:modelValue','changed'])
const items=ref([]),page=ref(1),total=ref(0),selected=ref(null),loading=ref(false),error=ref('')
const selectedId=ref('')
async function changeStatus(board,status){
  if(!props.canWrite||loading.value)return
  loading.value=true;error.value=''
  try{
    const data={version_id:selectedId.value,board_id:board.id,status}
    const preview=await previewStatementVersionStatus(props.clientId,data,props.settlementScope)
    if(status==='void'||preview.conflicts?.length||preview.will_replace_current){
      const names=(preview.conflicts||[]).map(item=>item.name).join('、')
      try{await ElMessageBox.confirm(status==='void'?`废除“${board.name}”这个历史版本？`:`同月份 / 同账期已存在有效对账单${names?`：${names}`:''}。确认后这些账单将废除并进入历史版本，启用当前版本。`,'确认历史版本状态调整',{type:'warning',confirmButtonText:'确认调整并记录',cancelButtonText:'取消',closeOnClickModal:false})}catch{return}
    }
    const result=await changeStatementWorkspace(props.clientId,{revision:props.revision,action:'set_historical_status',data:{...data,expected_plan:preview.plan},confirmed:true},props.mode||'children',props.settlementScope)
    emit('changed',result)
    const id=selectedId.value
    selected.value=await getStatementHistoricalVersion(props.clientId,id,props.settlementScope)
    ElMessage.success('历史版本状态已调整并记录')
  }catch(e){error.value=getLocalizedErrorMessage(e,'历史版本状态调整失败')}finally{loading.value=false}
}
let controller
async function request(fetch,apply){
  controller?.abort()
  const current=controller=new AbortController()
  loading.value=true
  error.value=''
  try{
    const result=await fetch({signal:current.signal})
    if(!current.signal.aborted)apply(result)
  }catch(e){
    if(!current.signal.aborted)error.value=getLocalizedErrorMessage(e,'对账单历史版本加载失败')
  }finally{
    if(!current.signal.aborted)loading.value=false
  }
}
function load(){
  return request(config=>getStatementHistoricalVersions(props.clientId,{
    settlement_scope:props.settlementScope,skip:(page.value-1)*20,limit:20,
  },config),data=>{items.value=data.items;total.value=data.total})
}
function openVersion(id){
  selectedId.value=id
  return request(config=>getStatementHistoricalVersion(props.clientId,id,props.settlementScope,config),data=>{selected.value=data})
}
watch(()=>[props.modelValue,props.clientId],([visible,clientId])=>{
  controller?.abort()
  if(!visible||!clientId)return
  selected.value=null
  items.value=[]
  page.value=1
  total.value=0
  void load()
},{immediate:true})
onBeforeUnmount(()=>controller?.abort())
</script>

<style scoped>
.generation-version-paper{overflow-x:auto}
.el-pagination{margin-top:12px}
:global(.statement-generation-versions){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.statement-generation-versions>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
:global(.statement-generation-versions>.el-dialog__header),:global(.statement-generation-versions>.el-dialog__footer){flex:none}
</style>
