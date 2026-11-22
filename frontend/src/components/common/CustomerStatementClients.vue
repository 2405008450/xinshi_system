<template>
  <section>
    <AppForm data-auto-draft="off" :model="filters" inline @submit.prevent="refresh">
      <el-form-item label="账单月份"><el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" :clearable="false" style="width:280px;max-width:100%" @change="changeMonths" /></el-form-item>
      <el-form-item v-if="settlementScope && settlementScope!=='special'" label="账期"><StatementPeriodSelect v-model="filters.period" :month="filters.months[0]" :months="filters.months" :settlement-scope="settlementScope" /></el-form-item>
      <el-form-item label="客户分类"><el-radio-group v-model="filters.mode"><el-radio-button value="required">{{special?'特殊结算客户':'需对账单客户'}}</el-radio-button><el-radio-button value="optional">{{special?'非特殊结算客户':'无需对账单客户'}}</el-radio-button><el-radio-button value="both">并列打开</el-radio-button></el-radio-group></el-form-item>
      <el-form-item :label="special?'特殊结算进度':'对账单进度'"><el-select v-model="filters.progress" clearable placeholder="全部进度" style="width:140px" @change="refresh"><el-option label="未开始" value="not_started" /><el-option label="部分完成" value="partial" /><el-option label="全部完成" value="completed" /></el-select></el-form-item>
      <el-form-item label="展示方式"><el-radio-group v-model="filters.layout" aria-label="展示方式"><el-radio-button value="month">月份 → 客户</el-radio-button><el-radio-button value="client">客户 → 月份</el-radio-button></el-radio-group></el-form-item>
      <el-form-item v-if="!settlementScope||special"><el-button @click="mergeMode='customers';mergeVisible=true">合并客户</el-button><el-button v-if="special" @click="mergeMode='projects';mergeVisible=true">合并筛选项目</el-button></el-form-item>
    </AppForm>
    <p v-if="special" class="client-hint">选择本月（相应账期）需特殊结算的客户，集中筛选项目并进行特殊结算处理；客户档案与原始项目不变。</p>
    <p v-else class="client-hint">可拖动客户在两栏之间调整对账单需求，保存后自动同步对应客户或子客户的结算设置。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="filters.layout==='month'">
    <section v-for="month in selectedMonths" :key="month" class="statement-month-group">
      <h3 v-if="selectedMonths.length>1">{{month}}</h3>
      <div class="client-panes" :class="{'is-split':filters.mode==='both'}">
        <CustomerStatementClientGroup v-for="required in visibleGroups" :key="`${month}:${required}`" :ref="el=>setGroup(`${month}:${required}`,el)" :manager-query="managerQuery" :required="required" :settlement-scope="settlementScope" :month="month" :period-number="filters.period" :progress-filter="filters.progress" :moving="moving" :keyword-value="keywords[String(required)]" @keyword-change="keywords[String(required)]=$event" @drop-client="moveClient($event,required,month)" @move-client="moveClient($event,!required,month)" @managers="updateManagers(`${month}:${required}`,$event)" />
      </div>
    </section>
    </template>
    <div v-else class="client-panes" :class="{'is-split':filters.mode==='both'}">
      <CustomerStatementClientMonths v-for="required in visibleGroups" :key="`client:${required}`" :ref="el=>setGroup(`client:${required}`,el)"
        :months="selectedMonths" :required="required" :settlement-scope="settlementScope" :manager-query="managerQuery"
        :period-number="filters.period" :progress-filter="filters.progress" :moving="moving" :keyword-value="keywords[String(required)]"
        @keyword-change="keywords[String(required)]=$event" @managers="updateManagers(`client:${required}`,$event)"
        @drop-client="moveClient($event,required,$event.statementBillingMonth)" @move-client="moveClient($event,!required,$event.statementBillingMonth)" />
    </div>
    <MergedStatementClientsDialog v-if="!settlementScope||special" :settlement-scope="settlementScope" :merge-mode="mergeMode" v-model="mergeVisible" :month="filters.months[0]" :manager-query="managerQuery" @saved="refresh();emit('saved',$event)" />
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import StatementPeriodSelect from './StatementPeriodSelect.vue'
import CustomerStatementClientGroup from './CustomerStatementClientGroup.vue'
import CustomerStatementClientMonths from './CustomerStatementClientMonths.vue'
import MergedStatementClientsDialog from './MergedStatementClientsDialog.vue'
import {moveStatementCustomer} from '@/api/translationCustomerFinance'
import {currentStatementMonth} from '@/utils/statementRequirementMonth'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {connectInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
const props=defineProps({settlementScope:String,billingMonth:String,managerQuery:{type:Object,default:()=>({})}})
const emit=defineEmits(['managers','saved'])
const special=computed(()=>props.settlementScope==='special')
const filters=reactive({months:[props.billingMonth||currentStatementMonth()],mode:'required',layout:'month',progress:'',period:undefined})
const selectedMonths=computed(()=>[...new Set(filters.months||[])].sort())
function changeMonths(){if(!filters.months?.length)filters.months=[props.billingMonth||currentStatementMonth()];filters.period=undefined}
const visibleGroups=computed(()=>filters.mode==='both'?[true,false]:[filters.mode==='required'])
const groups=new Map(),managerLists=reactive({}),moving=ref(false),error=ref('')
const mergeMode=ref('customers'),mergeVisible=ref(false),keywords=reactive({'true':'','false':''})
function setGroup(required,el){if(el)groups.set(required,el);else groups.delete(required)}
function updateManagers(required,values){managerLists[String(required)]=values}
watch(()=>filters.layout==='client'?visibleGroups.value.flatMap(required=>managerLists[`client:${required}`]||[]):selectedMonths.value.flatMap(month=>visibleGroups.value.flatMap(required=>managerLists[`${month}:${required}`]||[])),values=>emit('managers',[...new Set(values)]),{immediate:true})
function refresh(){for(const group of groups.values())group.refresh()}
defineExpose({refresh})
window.addEventListener('translation-statements-changed',refresh)
function refreshSubClient(event){if(event.detail?.kind==='sub-client-finance')refresh()}
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,refreshSubClient)
onBeforeUnmount(()=>{
  window.removeEventListener('translation-statements-changed',refresh)
  window.removeEventListener(invoicePartiesEvent,refreshSubClient)
})
async function moveClient(client,required,month){
  if(!client||moving.value||client.statementRequired===required)return
  if(client.statementBillingMonth&&client.statementBillingMonth!==month)return ElMessage.warning('请在同一月份的需／无需对账单两栏之间拖动，跨月份请使用调整账期')
  try{await ElMessageBox.confirm(`将“${client.shortName||client.name}”在 ${month} 当前客户经理筛选范围内的 ${client.projectCount} 个项目及对应客户或子客户设置同步为“${required?'需':'无需'}对账单”？对应设置及其他账期的关联订单也会自动同步。`,'调整客户单据需求',{confirmButtonText:'确认调整',cancelButtonText:'取消',type:'warning'})}catch{return}
  moving.value=true;error.value=''
  try{const data=await moveStatementCustomer(client.id,{billing_month:month,settlement_scope:props.settlementScope,period_number:filters.period,statement_required:required,expected_version:client.version,...props.managerQuery});ElMessage.success(`已修改 ${data.affectedCount} 个项目`);emit('saved',data);window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{clientId:client.id}}))}
  catch(e){error.value=getLocalizedErrorMessage(e,'客户调整失败');if(e.response?.status===409)refresh()}
  finally{moving.value=false}
}
</script>
<style scoped>
.statement-month-group{margin-bottom:16px}.statement-month-group h3{font-size:15px;margin:10px 0}.client-hint{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6;margin:0 0 12px}.client-panes{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}.client-panes.is-split{grid-template-columns:repeat(2,minmax(0,1fr))}@media(max-width:850px){.client-panes.is-split{grid-template-columns:minmax(0,1fr)}}
</style>
