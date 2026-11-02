<template>
  <div class="customer-reference-rates">
    <el-button :disabled="!clientId" @click="open">客户语种单价</el-button><small v-if="!clientId">请先保存客户，再维护参考价</small>
    <DraggableFormDialog v-model="visible" append-to-body class="customer-reference-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="客户语种参考价" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body" v-loading="loading||saving"><p class="rate-sync-help">这里维护客户参考价。客户参考价自动同步至沿用客户价格的项目；项目单独调整的单价保留，并在财务区域提示差异供你选择同步。</p>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <AppForm ref="form" :model="draft" :disabled="!canWrite||saving||loading" label-position="top"><CustomerTranslationPriceEditor v-model="draft.prices" :readonly="!canWrite" :disabled="saving||!ready" /></AppForm>
        <el-collapse><el-collapse-item :title="`参考价修改记录（${historyTotal}）`" name="history"><el-collapse><el-collapse-item v-for="event in history" :key="event.id" :title="`${event.actorName} · ${formatTime(event.createdAt)} · ${event.origin==='project'?'项目同步':'客户资料'}`"><div v-for="[label,items] in [['变更前',event.before],['变更后',event.after]]" :key="label"><strong>{{label}}</strong><p v-for="item in items" :key="item.id">{{item.languagePair}} · {{item.currency}} {{item.amount}} / {{item.unitSize}} · {{item.metric}}</p></div></el-collapse-item></el-collapse><el-pagination v-model:current-page="historyPage" :page-size="10" :total="historyTotal" layout="total, prev, pager, next" @current-change="loadHistory" /></el-collapse-item></el-collapse>
      </div>
      <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite" type="primary" :disabled="!ready||loading" :loading="saving" @click="save">保存参考价</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import CustomerTranslationPriceEditor from './CustomerTranslationPriceEditor.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getCustomerTranslationRates,saveCustomerTranslationRates,getCustomerTranslationRateHistory} from '@/api/translationCustomerFinance'
import {ratePayload,newCustomerRate} from '@/utils/customerTranslationRates'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const emit=defineEmits(['saved'])
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const visible=ref(false),loading=ref(false),saving=ref(false),ready=ref(false),draft=ref({prices:[]}),history=ref([]),error=ref(''),form=ref(),body=ref()
const historyTotal=ref(0),historyPage=ref(1)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let version='',original='',client='',sequence=0
const signature=()=>JSON.stringify(draft.value.prices.map(ratePayload))
function apply(data){version=data.version;ready.value=data.ready;draft.value.prices=data.items.map(row=>({...newCustomerRate(row.languagePair),...row,amount:Number(row.amount),unitSize:Number(row.unitSize)}));original=signature()}
function applyHistory(data){history.value=data.items||[];historyTotal.value=data.total??history.value.length}
async function loadHistory(){const current=sequence,target=client,page=historyPage.value;try{const data=await getCustomerTranslationRateHistory(target,{page});if(current===sequence&&page===historyPage.value)applyHistory(data)}catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'修改记录加载失败')}}
async function open(){if(!props.clientId)return;const current=++sequence;client=props.clientId;historyPage.value=1;visible.value=true;loading.value=true;error.value='';try{const [data,events]=await Promise.all([getCustomerTranslationRates(client),getCustomerTranslationRateHistory(client).catch(()=>({items:[]}))]);if(current!==sequence)return;apply(data);applyHistory(events);if(!data.ready)error.value='客户语种单价存储尚未初始化'}catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'参考价加载失败')}finally{if(current===sequence)loading.value=false}}
async function close(done){if(saving.value)return;if(signature()!==original&&props.canWrite){try{await ElMessageBox.confirm('参考价有未保存修改，确定放弃？','关闭参考价',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}if(typeof done==='function')done();else visible.value=false}
async function save(){if(!props.canWrite||saving.value||!await form.value?.validate().catch(()=>false))return;const target=client,current=sequence;saving.value=true;error.value='';try{const data=await saveCustomerTranslationRates(target,{version,items:draft.value.prices.map(ratePayload)});if(current!==sequence)return;apply(data);historyPage.value=1;emit('saved');ElMessage.success('客户参考价已保存并自动同步，项目独立调价保留');const events=await getCustomerTranslationRateHistory(target).catch(()=>({items:[]}));if(current===sequence)applyHistory(events)}catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'保存参考价失败')}finally{saving.value=false}}
watch(()=>props.clientId,()=>{sequence++;visible.value=false;draft.value.prices=[];original='';version='';ready.value=false})
onBeforeUnmount(()=>{sequence++})
</script>
<style scoped>
.customer-reference-rates>small,.rate-sync-help{color:#64748b;font-size:12px}.customer-reference-rates>small{margin-left:8px}:global(.customer-reference-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-reference-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.customer-reference-dialog .el-dialog__header),:global(.customer-reference-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-reference-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
</style>
