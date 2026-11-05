<template>
  <span v-if="row.rootId&&row.id!==row.rootId" class="statement-inherited">随母订单：{{row.statementRequired?'需':'不需'}}</span>
  <el-checkbox v-else :model-value="row.statementRequired" :disabled="!canWrite||saving" :aria-label="`${row.orderNo} 是否需对账单`" @update:model-value="save">{{saving?'保存中':row.statementRequired?'需':'不需'}}</el-checkbox>
</template>
<script setup>
import {ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {hasPermission} from '@/utils/permission'
import {setProjectStatementRequired} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {orderStatementMonth} from '@/utils/statementRequirementMonth'
const props=defineProps({row:Object,month:String,prepare:Function})
const emit=defineEmits(['saved'])
const canWrite=hasPermission('projects:write'),saving=ref(false)
async function save(value){
  if(!canWrite||saving.value||value===props.row.statementRequired)return
  saving.value=true;let copy=false
  const month=props.month||orderStatementMonth(props.row.orderNo)
  try{
    if(props.prepare&&!await props.prepare())return ElMessage.warning('有单元格尚未保存，请先处理提示')
    if(value&&props.row.clientId&&month){
      try{await ElMessageBox.confirm(`是否将“需对账单”复制至“${props.row.clientShortName}”在 ${month} 的其他母订单？`,'复制对账单选择',{confirmButtonText:'同步同月其他项目',cancelButtonText:'仅修改当前项目',distinguishCancelAndClose:true,type:'warning'});copy=true}
      catch(action){if(action!=='cancel')return}
    }
    const data=await setProjectStatementRequired(props.row.id,{statement_required:value,expected_statement_required:props.row.statementRequired,expected_updated_at:props.row.updatedAt||null,copy_to_same_month:copy,billing_month:month||null})
    emit('saved',data);window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{projectId:props.row.id}}))
    ElMessage.success(copy?`已同步，修改 ${data.affectedCount} 个项目`:'是否需对账单已保存')
  }catch(e){ElMessage.error(getLocalizedErrorMessage(e,'保存失败'));if(e.response?.status===409)window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
  finally{saving.value=false}
}
</script>
<style scoped>.statement-inherited{font-size:12px;color:var(--el-text-color-secondary)}</style>
