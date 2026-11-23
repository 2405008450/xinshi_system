<template>
  <section>
    <AppForm :model="filters" inline @submit.prevent="refresh">
      <el-form-item label="账单月份"><el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" :clearable="false" style="width:160px" @change="refresh" /></el-form-item>
      <el-form-item v-if="settlementScope" label="账期"><StatementPeriodSelect v-model="filters.period" :month="filters.month" :settlement-scope="settlementScope" /></el-form-item>
      <el-form-item label="客户分类"><el-radio-group v-model="filters.mode"><el-radio-button value="required">{{special?'特殊结算客户':'需对账单客户'}}</el-radio-button><el-radio-button value="optional">{{special?'非特殊结算客户':'无需对账单客户'}}</el-radio-button><el-radio-button value="both">并列打开</el-radio-button></el-radio-group></el-form-item>
      <el-form-item :label="special?'特殊结算进度':'对账单进度'"><el-select v-model="filters.progress" clearable placeholder="全部进度" style="width:140px" @change="refresh"><el-option label="未开始" value="not_started" /><el-option label="部分完成" value="partial" /><el-option label="全部完成" value="completed" /></el-select></el-form-item>
      <el-form-item v-if="!settlementScope"><el-button @click="mergeVisible=true">合并客户</el-button></el-form-item>
    </AppForm>
    <p v-if="special" class="client-hint">选择本月（相应账期）需特殊结算的客户，集中筛选项目并进行特殊结算处理；客户档案与原始项目不变。</p>
    <p v-else class="client-hint">按所选月份的项目分类。普通结算的对账单需求随计费口径确定，特殊结算可单独设置。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div class="client-panes" :class="{'is-split':filters.mode==='both'}">
      <CustomerStatementClientGroup v-for="required in visibleGroups" :key="String(required)" :ref="el=>setGroup(required,el)" :manager-query="managerQuery" :required="required" :settlement-scope="settlementScope" :month="filters.month" :period-number="filters.period" :progress-filter="filters.progress" :moving="moving" @drop-client="moveClient($event,required)" @move-client="moveClient($event,!required)" @managers="updateManagers(required,$event)" />
    </div>
    <MergedStatementClientsDialog v-if="!settlementScope" v-model="mergeVisible" :month="filters.month" :manager-query="managerQuery" @saved="refresh();emit('saved',$event)" />
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from '../AppForm.vue'
import StatementPeriodSelect from './BackupStatementPeriodSelect.vue'
import CustomerStatementClientGroup from './BackupCustomerStatementClientGroup.vue'
import MergedStatementClientsDialog from './BackupMergedStatementClientsDialog.vue'
import {moveStatementCustomer} from '@/api/translationCustomerFinance'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({settlementScope:String,billingMonth:String,managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['managers','saved'])
const special=computed(()=>props.settlementScope==='special')
const filters=reactive({month:props.billingMonth||currentStatementMonth(),mode:'required',progress:'',period:undefined})
const visibleGroups=computed(()=>filters.mode==='both'?[true,false]:[filters.mode==='required'])
const groups=new Map(),managerLists=reactive({}),moving=ref(false),error=ref('')
const mergeVisible=ref(false)
function setGroup(required,el){if(el)groups.set(required,el);else groups.delete(required)}
function updateManagers(required,values){managerLists[String(required)]=values}
watch(()=>visibleGroups.value.flatMap(required=>managerLists[String(required)]||[]),values=>emit('managers',[...new Set(values)]),{immediate:true})
function refresh(){for(const group of groups.values())group.refresh()}
defineExpose({refresh})
window.addEventListener('translation-statements-changed',refresh)
onBeforeUnmount(()=>window.removeEventListener('translation-statements-changed',refresh))
async function moveClient(client,required){
  if(!client||moving.value||client.statementRequired===required)return
  try{await ElMessageBox.confirm(`将“${client.shortName||client.name}”在 ${filters.month} 当前客户经理筛选范围内的 ${client.projectCount} 个项目设为“${required?'需':'无需'}对账单”？`,'调整客户单据需求',{confirmButtonText:'确认调整',cancelButtonText:'取消',type:'warning'})}catch{return}
  moving.value=true;error.value=''
  try{const data=await moveStatementCustomer(client.id,{billing_month:filters.month,settlement_scope:props.settlementScope,statement_required:required,expected_version:client.version,...props.managerQuery});ElMessage.success(`已修改 ${data.affectedCount} 个项目`);emit('saved',data);window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{clientId:client.id}}))}
  catch(e){error.value=getLocalizedErrorMessage(e,'客户调整失败');if(e.response?.status===409)refresh()}
  finally{moving.value=false}
}
</script>
<style scoped>
.client-hint{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6;margin:0 0 12px}.client-panes{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}.client-panes.is-split{grid-template-columns:repeat(2,minmax(0,1fr))}@media(max-width:850px){.client-panes.is-split{grid-template-columns:minmax(0,1fr)}}
</style>
