<template>
  <span>
    <el-button :disabled="!targetId" :link="scope==='project'" type="primary" @click="open">{{scope==='client'?'口译参考价及调整记录':canWrite?'编辑收费 / 调整记录':'查看收费 / 调整记录'}}</el-button>
    <DraggableFormDialog v-model="visible" append-to-body class="interpretation-finance-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="scope==='client'?'客户口译参考价':`口译客户财务 · ${context.order_no||''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body" v-loading="loading||saving">
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <CustomerFinanceModuleTabs v-model="financeModule" module="interpretation" :enabled="scope==='project'" :client-id="context.client_id"><template #interpretation>
        <AppForm v-if="draft&&!loading" ref="form" :model="draft" label-position="top" :disabled="saving||!canWrite||!context.ready">
          <template v-if="scope==='project'"><el-form-item label="订单号"><ReadonlyField :model-value="context.order_no" source="auto" /></el-form-item><el-form-item label="项目名称"><ReadonlyField :model-value="context.project_name||'-'" source="auto" /></el-form-item><el-form-item label="客户简称"><ClientManagementLink :value="context.client_short_name" :row="context" /></el-form-item><el-form-item label="项目状态"><ReadonlyField :model-value="getProjectStatusLabel('interpretation',context.project_status)" source="auto" /></el-form-item><el-form-item label="客户参考价"><el-button :disabled="!context.reference_rates?.length" @click="adopt">采用匹配方向的客户参考价</el-button></el-form-item><el-form-item v-if="canWriteClients&&context.client_id" label="同步客户参考价"><el-button @click="save(true)">保存并同步单价至客户信息…</el-button></el-form-item></template>
          <InterpretationFinanceFields v-model="draft" :directions="context.directions||[]" :reference-only="scope==='client'" />
        </AppForm>
        <p v-if="scope==='project'">对应税口径未填写的项目不参与该口径合计；未填写不代表零税率。</p>
        <el-descriptions v-if="scope==='project'" :column="2" border><el-descriptions-item label="不含税总价">{{formatFinanceAmounts(context.totals_excl_tax)}}</el-descriptions-item><el-descriptions-item label="含税总价">{{formatFinanceAmounts(context.totals_incl_tax)}}</el-descriptions-item><el-descriptions-item label="原总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(context.totals)}}</span></el-descriptions-item><el-descriptions-item label="原调整总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(context.adjusted_totals)}}</span></el-descriptions-item></el-descriptions>
        <template v-if="scope==='client' && visible">
          <p v-if="signature()!==original" class="finance-text">请先保存或放弃当前修改，再引入项目单价。</p>
          <CustomerRateDifferences module="interpretation" :client-id="targetId" :revision="context.revision||0" :disabled="saving || signature()!==original" @saved="open" />
        </template>
        <h4>调整记录（{{historyTotal}}）</h4><el-collapse><el-collapse-item v-for="item in history" :key="item.id" :title="`第${item.revision}次 · ${item.actor_name} · ${formatTime(item.created_at)}`"><el-descriptions :column="1" border><el-descriptions-item label="调整前"><span class="finance-text">{{financeSummary(item.before)}}</span></el-descriptions-item><el-descriptions-item label="调整后"><span class="finance-text">{{financeSummary(item.after)}}</span></el-descriptions-item></el-descriptions></el-collapse-item></el-collapse>
        <el-pagination v-model:current-page="historyPage" :total="historyTotal" :page-size="10" layout="total, prev, pager, next" @current-change="loadHistory" />
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite&&(scope==='client'||financeModule==='interpretation')" type="primary" :disabled="loading||!context.ready" :loading="saving" @click="save()">保存</el-button></template>
    </DraggableFormDialog>
  </span>
</template>
<script setup>
import ClientManagementLink from './ClientManagementLink.vue'
import {taxPricePayload} from '@/utils/taxPrices'
import CustomerFinanceModuleTabs from './CustomerFinanceModuleTabs.vue'
import {ref,onBeforeUnmount,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import InterpretationFinanceFields from './InterpretationFinanceFields.vue'
import ReadonlyField from './ReadonlyField.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getInterpretationFinance,saveInterpretationFinance,getInterpretationFinanceHistory} from '@/api/interpretationCustomerFinance'
import {financeDraft,financeSummary,formatFinanceAmounts} from '@/utils/interpretationCustomerFinance'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({scope:{type:String,default:'project'},targetId:{type:[String,Number],default:''},canWrite:Boolean})
const emit=defineEmits(['saved'])
const canWriteClients=hasPermission('clients:write')
const financeModule=ref('interpretation')
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),context=ref({}),draft=ref(null),body=ref(),form=ref(),history=ref([]),historyTotal=ref(0),historyPage=ref(1)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let sequence=0
const original=ref('')
const signature=()=>JSON.stringify(draft.value)
async function loadHistory(){const seq=sequence,page=historyPage.value;try{const data=await getInterpretationFinanceHistory(props.scope,props.targetId,page);if(seq===sequence&&page===historyPage.value){history.value=data.items;historyTotal.value=data.total}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'调整记录加载失败')}}
async function open(){financeModule.value='interpretation';const seq=++sequence;visible.value=true;loading.value=true;error.value='';draft.value=null;history.value=[];historyTotal.value=0;clearFieldSearch();try{const data=await getInterpretationFinance(props.scope,props.targetId);if(seq!==sequence)return;context.value=data;draft.value=financeDraft(data.payload);original.value=signature();if(!data.ready)error.value='口译财务数据表尚未初始化';historyPage.value=1;await loadHistory()}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'财务信息加载失败')}finally{if(seq===sequence)loading.value=false}}
function adopt(){const directions=new Set((context.value.directions||[]).map(row=>row.label));const rates=context.value.reference_rates.filter(row=>directions.has(row.direction));if(!rates.length)return ElMessage.warning('客户参考价没有匹配的口译方向');draft.value.rates=financeDraft({...draft.value,rates}).rates}
async function close(done){if(saving.value)return;if(draft.value&&signature()!==original.value&&props.canWrite){try{await ElMessageBox.confirm('存在未保存的财务调整，确定放弃？','关闭财务表单')}catch{return}}sequence++;if(typeof done==='function')done();else visible.value=false}
async function save(syncToClient=false){if(saving.value||!props.canWrite||!await form.value?.validate().catch(()=>false))return;if(syncToClient){try{await ElMessageBox.confirm('确认将本次口译单价同步至客户信息？客户参考价变更会自动同步至仍沿用原价的项目。项目数量、加班费和总价调整不会同步至客户。','确认同步客户单价',{type:'warning',confirmButtonText:'确认同步',cancelButtonText:'取消'})}catch{return}}saving.value=true;error.value='';try{const payload=JSON.parse(JSON.stringify(draft.value));for(const row of payload.rates){row.tax_prices=taxPricePayload(row.taxPrices);delete row.taxPrices}for(const row of [...payload.adjusted_totals,...(payload.overtime?[payload.overtime]:[])]){row.tax_prices=taxPricePayload(row.taxPrices);delete row.taxPrices}if(!payload.has_overtime)payload.overtime=null;const data=await saveInterpretationFinance(props.scope,props.targetId,{...payload,revision:context.value.revision,update_library:syncToClient,sync_confirmed:syncToClient,library_revision:context.value.library_revision});context.value=data;draft.value=financeDraft(data.payload);original.value=signature();historyPage.value=1;await loadHistory();emit('saved');ElMessage.success('财务调整已保存并记录')}catch(e){error.value=getLocalizedErrorMessage(e,'保存失败')}finally{saving.value=false}}
watch(()=>props.targetId,()=>{sequence++;visible.value=false;draft.value=null})
onBeforeUnmount(()=>sequence++)
</script>
<style scoped>
.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}:global(.interpretation-finance-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.interpretation-finance-dialog .el-dialog__header),:global(.interpretation-finance-dialog .el-dialog__footer){flex-shrink:0}:global(.interpretation-finance-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.interpretation-finance-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
