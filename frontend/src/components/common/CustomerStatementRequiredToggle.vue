<template>
  <span v-if="row.rootId&&row.id!==row.rootId" class="statement-inherited">随母订单：{{row.statementRequired?'需':'不需'}}</span>
  <el-checkbox v-else v-model="checked" :disabled="!canWrite||saving" :aria-label="`${row.orderNo} 是否需对账单`" @change="save">{{saving?'保存中':row.statementRequired?'需':allowMonthSync?'不需':'无需'}}</el-checkbox>
</template>
<script setup>
import {ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {hasPermission} from '@/utils/permission'
import {setProjectStatementRequired} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {confirmStatementRequirement,notifyStatementCustomerSync} from '@/utils/confirmStatementRequirement'
const props=defineProps({row:Object,month:String,prepare:Function,allowMonthSync:{type:Boolean,default:true}})
const emit=defineEmits(['saved'])
const canWrite=hasPermission('projects:write'),saving=ref(false)
const checked=ref(props.row.statementRequired)
watch(()=>[props.row.id,props.row.statementRequired],()=>{checked.value=props.row.statementRequired})
async function save(value){
  if(!canWrite||saving.value||value===props.row.statementRequired)return
  saving.value=true
  try{
    if(props.prepare&&!await props.prepare())return ElMessage.warning('有单元格尚未保存，请先处理提示')
    const row=props.row
    const confirmation=await confirmStatementRequirement({projectId:row.id,value,allowMonthSync:props.allowMonthSync})
    if(!confirmation || props.row.id!==row.id)return
    const data=await setProjectStatementRequired(row.id,{statement_required:value,expected_statement_required:row.statementRequired,expected_updated_at:row.updatedAt||null,statement_sync:confirmation.scope,statement_customer_sync:confirmation.customerScope})
    emit('saved',data)
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{
      detail:{projectId:row.id,syncScope:confirmation.scope||confirmation.customerScope},
    }))
    notifyStatementCustomerSync(confirmation.customerScope)
    ElMessage.success(confirmation.scope?`已同步，修改 ${data.affectedCount} 个项目`:confirmation.customerScope?'已保存并同步客户管理':'是否需对账单已保存')
  }catch(e){ElMessage.error(getLocalizedErrorMessage(e,'保存失败'));if(e.response?.status===409)window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
  finally{checked.value=props.row.statementRequired;saving.value=false}
}
</script>
<style scoped>.statement-inherited{font-size:12px;color:var(--el-text-color-secondary)}</style>
