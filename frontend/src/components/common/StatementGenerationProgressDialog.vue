<template>
  <DraggableFormDialog :model-value="true" title="对账单已生成 · 更新进度" class="statement-generation-progress-dialog" append-to-body destroy-on-close
    width="min(760px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="对账单已生成 · 更新进度" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
    <p>是否将本次生成月份的进度改为“部分完成”或“全部完成”？之后仍可人工调整。</p>
    <AppForm v-loading="loading" :model="form" label-position="top" data-auto-draft="off">
      <el-form-item v-for="row in form.rows" :key="row.month" :label="`${row.month}（当前：${labels[row.progress]}）`">
        <el-select v-model="row.next" :aria-label="`${row.month} 对账单进度`" :disabled="loading||saving">
          <el-option label="保留原状态" value="keep" /><el-option label="部分完成" value="partial" /><el-option label="全部完成" value="completed" />
        </el-select>
      </el-form-item>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link :disabled="saving||loading" @click="load">重新读取进度</el-button></el-alert>
    </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="close">保留原状态</el-button><el-button type="primary" :loading="saving" :disabled="loading||!form.rows.some(row=>row.next!=='keep')" @click="save">保存进度</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import {onBeforeUnmount,onMounted,reactive,ref} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getStatementProgress,setStatementProgress} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:{type:String,required:true},months:{type:Array,required:true},managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['close','saved'])
const form=reactive({rows:[]}),loading=ref(false),saving=ref(false),error=ref('')
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const labels={not_started:'未开始',partial:'部分完成',completed:'全部完成'}
let controller,disposed=false
async function load(){
  controller?.abort();const request=controller=new AbortController();loading.value=true;error.value=''
  try{
    const rows=[]
    for(const month of [...new Set(props.months)].sort()){
      const value=await getStatementProgress(props.clientId,{billing_month:month,...props.managerQuery},{signal:request.signal})
      if(request.signal.aborted||disposed)return
      rows.push({month,progress:value.progress,revision:value.progressRevision,next:'keep'})
    }
    form.rows=rows
  }catch(cause){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(cause,'读取对账单进度失败；已生成的对账单不受影响')}
  finally{if(!request.signal.aborted)loading.value=false}
}
function close(){if(!saving.value)emit('close')}
async function save(){
  if(loading.value||saving.value)return
  saving.value=true;error.value='';let changed=false
  try{
    for(const row of form.rows.filter(row=>row.next!=='keep')){
      const result=await setStatementProgress(props.clientId,{billing_month:row.month,progress:row.next,revision:row.revision,...props.managerQuery})
      row.progress=result.progress;row.revision=result.progressRevision;row.next='keep';changed=true
    }
    ElMessage.success('对账单进度已更新，之后仍可人工调整')
    emit('close')
  }catch(cause){error.value=getLocalizedErrorMessage(cause,'进度保存失败；已生成的对账单不受影响')}
  finally{saving.value=false;if(changed)emit('saved')}
}
onMounted(load)
onBeforeUnmount(()=>{disposed=true;controller?.abort()})
</script>

<style>
.statement-generation-progress-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.statement-generation-progress-dialog .el-dialog__header,.statement-generation-progress-dialog .el-dialog__footer{flex-shrink:0}.statement-generation-progress-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.statement-generation-progress-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter)}
</style>
