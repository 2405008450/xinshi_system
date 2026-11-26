<template>
  <DraggableFormDialog :model-value="true" title="调整账单月份与账期" append-to-body destroy-on-close
    width="min(500px, calc(100vw - 32px))" :close-on-click-modal="false" :before-close="beforeClose">
    <AppForm :model="form" label-position="top" @submit.prevent="save">
      <el-form-item label="账单月份">
        <el-date-picker v-model="form.month" type="month" value-format="YYYY-MM" :clearable="false" :disabled="saving" />
      </el-form-item>
      <el-form-item label="账期">
        <el-select v-model="form.period" aria-label="账期" :loading="loading" :disabled="loading || saving || !options">
          <el-option v-for="board in options?.boards || []" :key="board.id" :value="board.id"
            :label="board.number ? `第${board.number}期 · ${board.name}` : board.name" />
          <el-option v-if="options && !options.boards.length" value="monthly" label="整月（不分期）" />
          <el-option v-if="options?.can_create" value="new" :label="`新增第${nextPeriod}期`" />
          <el-option v-if="options?.can_create_custom" value="custom" label="新增指定期次" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.period==='custom'" label="指定期次" :error="customPeriodError">
        <el-input-number v-model="form.periodNumber" aria-label="指定期次" :min="1" :max="Number.MAX_SAFE_INTEGER"
          :step="1" step-strictly :controls="false" :disabled="saving" placeholder="例如 2">
          <template #prefix>第</template>
          <template #suffix>期</template>
        </el-input-number>
      </el-form-item>
      <p v-if="form.period==='new' && options?.boards.length===1 && !options.boards[0].number">
        保存后原账单成为第1期，本订单归入第2期。
      </p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </AppForm>
    <template #footer>
      <el-button :disabled="saving" @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="!canSave" :loading="saving" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import AppForm from './AppForm.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {getOrderBillingPeriods,saveOrderBillingPeriod} from '@/api/customerStatements'
import {readOralBillingPeriods,saveOralBillingPeriod} from '@/api/interpretationSettlementSettings'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'

const props=defineProps({projectId:String,month:String,version:String,module:{type:String,default:'translation'}})
const emit=defineEmits(['close','saved'])
const form=reactive({month:props.month || currentStatementMonth(),period:'',periodNumber:undefined})
const options=ref(null),loading=ref(false),saving=ref(false),error=ref('')
const nextPeriod=computed(()=>{
  const boards=options.value?.boards || []
  return boards.length ? Math.max(1,...boards.map(board=>board.number || 0))+1 : 1
})
const customPeriodError=computed(()=>form.period==='custom'&&options.value?.boards.some(board=>board.number===form.periodNumber)
  ? `第${form.periodNumber}期已存在，请在账期中直接选择` : '')
const canSave=computed(()=>!loading.value&&!!options.value&&!!form.period&&
  (form.period!=='custom'||Number.isSafeInteger(form.periodNumber)&&form.periodNumber>0&&!customPeriodError.value))
let request
async function load(){
  request?.abort()
  const current=new AbortController()
  request=current
  loading.value=true
  options.value=null
  form.period=''
  form.periodNumber=undefined
  error.value=''
  try{
    const result=await (props.module==='interpretation'?readOralBillingPeriods(props.projectId,form.month,current.signal):getOrderBillingPeriods(props.projectId,form.month,current.signal))
    if(current.signal.aborted)return
    options.value=result
    form.period=result.boards.find(board=>board.id===result.board_id)?.id ||
      (result.boards.length===1 ? result.boards[0].id : result.boards.length ? '' : 'monthly')
  }catch(e){
    if(!current.signal.aborted)error.value=getLocalizedErrorMessage(e,'账期读取失败')
  }finally{
    if(!current.signal.aborted)loading.value=false
  }
}
watch(()=>form.month,load,{immediate:true})
onBeforeUnmount(()=>request?.abort())
function beforeClose(){
  if(!saving.value)emit('close')
}
async function save(){
  if(saving.value || !canSave.value)return
  saving.value=true
  error.value=''
  try{
    const {period,month}=form
    await (props.module==='interpretation'?saveOralBillingPeriod:saveOrderBillingPeriod)(props.projectId,{
      month,board_id:options.value.boards.some(board=>board.id===period)?period:null,
      create_period:period==='new',period_number:period==='custom'?form.periodNumber:undefined,
      revision:options.value.revision,version:props.version,
    })
    emit('saved')
  }catch(e){
    error.value=getLocalizedErrorMessage(e,'账期保存失败')
  }finally{
    saving.value=false
  }
}
</script>
