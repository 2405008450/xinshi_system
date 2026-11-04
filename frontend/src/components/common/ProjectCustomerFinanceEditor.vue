<template>
  <DraggableFormDialog v-model="visible" append-to-body class="project-customer-finance-editor" width="min(1200px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${moduleLabel}客户财务 · ${context.order_no||''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading||saving">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <CustomerFinanceModuleTabs v-model="activeModule" :module="module" :client-id="context.client_id">
        <template #[module]>
          <AppForm v-if="context.id&&!loading" ref="form" :model="draft" label-position="top" :disabled="saving||!canWrite">
            <el-form-item label="项目名称"><ReadonlyField :model-value="context.project_name||'-'" source="auto" /></el-form-item>
            <el-form-item label="客户"><ReadonlyField :model-value="context.client_name||'-'" source="auto" /></el-form-item>
            <template v-if="module==='annotation'">
              <el-button v-if="canWrite" :disabled="!projectTypes.length||saving" @click="addPrice">新增客户报价</el-button>
              <small v-if="!projectTypes.length">请先在项目管理中设置项目类型</small>
              <section v-for="(row,index) in draft.prices" :key="row.id||row._key" class="finance-price-card" data-dialog-field-search-group :data-dialog-field-search-group-title="`客户报价 ${index+1}`">
                <div class="price-heading"><strong>客户报价 {{index+1}}</strong><el-button v-if="canWrite" link type="danger" @click="draft.prices.splice(index,1)">移除此项</el-button></div>
                <el-form-item label="标注类型" :prop="`prices.${index}.project_type`" :rules="row.id?[]:[{required:true,message:'请选择标注类型',trigger:'change'}]"><el-select v-model="row.project_type" clearable><el-option v-for="option in projectTypes" :key="option.value" v-bind="option" /></el-select></el-form-item>
                <p v-if="row.language_display">语言范围：{{row.language_display}}</p>
                <p v-if="!taxPriceSummary(row.taxPrices)&&row.amount!=null">原单价（税口径未确认）：{{row.currency}} {{row.amount}}/{{row.unit}}</p>
                <el-form-item label="客户报价" :prop="`prices.${index}.amount`" :rules="[{required:true,type:'number',min:0.000001,message:'请填写大于零的不含税或含税单价',trigger:'change'}]">
                  <TaxPriceFields v-model="row.taxPrices" :prefix="`prices.${index}.taxPrices`" @change="value=>row.amount=taxUnitAmount(value,row.amount)" />
                </el-form-item>
                <el-form-item label="货币"><el-select v-model="row.currency"><el-option v-for="option in currencyOptions" :key="option.value" v-bind="option" /></el-select></el-form-item>
                <el-form-item label="计价单位" :prop="`prices.${index}.unit`" :rules="[{required:true,message:'请选择计价单位',trigger:'change'}]"><el-select v-model="row.unit" filterable><el-option v-for="option in unitOptions(row.unit)" :key="option.value" v-bind="option" /></el-select></el-form-item>
                <el-form-item label="报价说明"><el-input v-model="row.remarks" type="textarea" :rows="2" maxlength="5000" /></el-form-item>
              </section>
              <el-empty v-if="!draft.prices.length" description="暂无客户报价" />
            </template>
            <template v-else>
              <el-form-item label="货币"><el-select v-model="draft.currency"><el-option v-for="option in currencyOptions" :key="option.value" v-bind="option" /></el-select></el-form-item>
              <p v-if="context.legacy_amount!=null">原服务费用（税口径未确认）：{{context.currency}} {{context.legacy_amount}}</p>
              <TaxPriceFields v-model="draft.taxPrices" prefix="taxPrices" />
            </template>
          </AppForm>
          <el-collapse v-if="context.id" class="finance-history"><el-collapse-item :title="`财务修改记录（${historyTotal}）`" name="history">
            <el-collapse><el-collapse-item v-for="row in history" :key="row.id" :title="`${row.actor_name} · ${formatTime(row.created_at)}`"><p class="finance-text">变更前：{{snapshotText(row.before)}}</p><p class="finance-text">变更后：{{snapshotText(row.after)}}</p></el-collapse-item></el-collapse>
            <el-pagination v-model:current-page="historyPage" :page-size="10" :total="historyTotal" layout="total, prev, pager, next" @current-change="loadHistory" />
          </el-collapse-item></el-collapse>
        </template>
      </CustomerFinanceModuleTabs>
    </div>
    <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button v-if="canWrite&&activeModule===module" type="primary" :disabled="loading||!context.id" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import ReadonlyField from './ReadonlyField.vue'
import TaxPriceFields from './TaxPriceFields.vue'
import CustomerFinanceModuleTabs from './CustomerFinanceModuleTabs.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {annotationProjectTypeOptions} from '@/utils/annotationCatalog'
import {settlementCurrencyOptions,settlementUnitOptions,settlementLabel} from '@/utils/talentSettlement'
import {taxPriceForm,taxPricePayload,taxUnitAmount,taxPriceSummary} from '@/utils/taxPrices'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {getProjectCustomerFinance,saveProjectCustomerFinance,getProjectCustomerFinanceHistory} from '@/api/projectCustomerFinance'
const props=defineProps({module:{type:String,required:true}})
const emit=defineEmits(['saved'])
const moduleLabel=computed(()=>props.module==='annotation'?'标注':'招聘')
const canWrite=hasPermission('projects:write')
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),context=ref({}),body=ref(),form=ref(),activeModule=ref(props.module)
const draft=reactive({prices:[],currency:'CNY',taxPrices:taxPriceForm()})
const history=ref([]),historyTotal=ref(0),historyPage=ref(1)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const projectTypes=computed(()=>annotationProjectTypeOptions.filter(option=>(context.value.project_types||[]).includes(option.value)))
const currencyOptions=computed(()=>[...settlementCurrencyOptions,...[...new Set([draft.currency,...draft.prices.map(row=>row.currency)])].filter(value=>value&&!settlementCurrencyOptions.some(row=>row.value===value)).map(value=>({value,label:value}))])
const unitOptions=value=>{const choices=settlementUnitOptions.map(row=>({value:row.label,label:row.label}));if(value&&!choices.some(row=>row.value===value))choices.push({value,label:settlementLabel(settlementUnitOptions,value)});return choices}
let sequence=0,controller,original='',target=''
const signature=()=>JSON.stringify(draft)
function apply(data){context.value=data;draft.prices=(data.prices||[]).map(row=>({...row,amount:Number(row.amount),taxPrices:taxPriceForm(row.tax_prices)}));draft.currency=data.currency||'CNY';draft.taxPrices=taxPriceForm(data.tax_prices);original=signature()}
function addPrice(){draft.prices.push({_key:crypto.randomUUID(),project_type:projectTypes.value[0]?.value||'',amount:null,currency:'CNY',unit:'条',taxPrices:taxPriceForm(),remarks:''})}
function snapshotText(value){return props.module==='annotation'?(value.prices||[]).map(row=>`${settlementLabel(annotationProjectTypeOptions,row.project_type)}：${taxPriceSummary(row.tax_prices,row.currency,row.unit)||`原单价 ${row.currency} ${row.amount}/${row.unit}`}`).join('\n')||'无报价':taxPriceSummary(value.tax_prices,value.currency)||'税口径未填写'}
async function loadHistory(){const seq=sequence,page=historyPage.value;try{const data=await getProjectCustomerFinanceHistory(props.module,target,page);if(seq===sequence&&page===historyPage.value){history.value=data.items||[];historyTotal.value=data.total||0}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'修改记录加载失败')}}
async function open(id){controller?.abort();controller=new AbortController();const seq=++sequence;target=id;context.value={};history.value=[];historyTotal.value=0;historyPage.value=1;error.value='';activeModule.value=props.module;visible.value=true;loading.value=true;clearFieldSearch();try{const data=await getProjectCustomerFinance(props.module,id,{signal:controller.signal});if(seq!==sequence)return;apply(data);await nextTick();form.value?.clearValidate();await loadHistory()}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目财务加载失败')}finally{if(seq===sequence)loading.value=false}}
async function save(){if(saving.value||!canWrite||activeModule.value!==props.module||!await form.value?.validate().catch(()=>false))return;saving.value=true;error.value='';try{const payload=props.module==='annotation'?{version:context.value.version,prices:draft.prices.map(row=>({id:row.id||null,project_type:row.project_type||null,amount:row.amount,currency:row.currency,unit:row.unit,source_language_id:row.source_language_id||null,target_language_id:row.target_language_id||null,remarks:row.remarks||null,tax_prices:taxPricePayload(row.taxPrices)}))}:{version:context.value.version,currency:draft.currency,tax_prices:taxPricePayload(draft.taxPrices)};apply(await saveProjectCustomerFinance(props.module,target,payload));historyPage.value=1;await loadHistory();emit('saved');ElMessage.success('客户财务已保存并记录')}catch(e){await form.value?.applyServerErrors(e);error.value=getLocalizedErrorMessage(e,'保存失败，请重新打开后重试')}finally{saving.value=false}}
async function close(done){if(saving.value)return;if(context.value.id&&signature()!==original&&canWrite){try{await ElMessageBox.confirm('存在未保存的财务修改，确定放弃？','关闭客户财务',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑',type:'warning'})}catch{return}}sequence++;controller?.abort();if(typeof done==='function')done();else visible.value=false}
async function guardClose(){if(!visible.value)return true;await close();return !visible.value}
watch(()=>props.module,()=>{sequence++;controller?.abort();visible.value=false})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
defineExpose({open,guardClose})
</script>
<style scoped>
.finance-price-card{padding:16px;margin:12px 0;border:1px solid var(--el-border-color-lighter);border-radius:8px}.price-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-history{margin-top:20px}.el-select{width:100%}
:global(.project-customer-finance-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-customer-finance-editor .el-dialog__header),:global(.project-customer-finance-editor .el-dialog__footer){flex:none}:global(.project-customer-finance-editor .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.project-customer-finance-editor .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-bg-color)}
</style>
