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
        </el-select>
      </el-form-item>
      <p v-if="form.period==='new' && options?.boards.length===1 && !options.boards[0].number">
        保存后原账单成为第1期，本订单归入第2期。
      </p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </AppForm>
    <template #footer>
      <el-button :disabled="saving" @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="loading || !form.period || !options" :loading="saving" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import AppForm from './AppForm.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {getOrderBillingPeriods,saveOrderBillingPeriod} from '@/api/customerStatements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'

const props=defineProps({projectId:String,month:String,version:String})
const emit=defineEmits(['close','saved'])
const form=reactive({month:props.month || currentStatementMonth(),period:''})
const options=ref(null),loading=ref(false),saving=ref(false),error=ref('')
const nextPeriod=computed(()=>{
  const boards=options.value?.boards || []
  return boards.length ? Math.max(1,...boards.map(board=>board.number || 0))+1 : 1
})
let request
async function load(){
  request?.abort()
  const current=new AbortController()
  request=current
  loading.value=true
  options.value=null
  form.period=''
  error.value=''
  try{
    const result=await getOrderBillingPeriods(props.projectId,form.month,current.signal)
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
  if(loading.value || saving.value || !options.value || !form.period)return
  saving.value=true
  error.value=''
  try{
    const {period,month}=form
    await saveOrderBillingPeriod(props.projectId,{
      month,board_id:options.value.boards.some(board=>board.id===period)?period:null,
      create_period:period==='new',revision:options.value.revision,version:props.version,
    })
    emit('saved')
  }catch(e){
    error.value=getLocalizedErrorMessage(e,'账期保存失败')
  }finally{
    saving.value=false
  }
}
</script>
