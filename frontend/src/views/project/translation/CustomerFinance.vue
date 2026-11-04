<template>
  <el-card class="customer-finance" :class="{'finance-editor-only':editorOnly}" shadow="never">
    <template #header><div class="finance-heading"><strong>笔译</strong><TableColumnSettings v-model="selectedKeys" settings-key="translation-customer-finance" :columns="columns" @reset="resetColumns" /></div></template>
    <AppForm :inline="true" :model="filters" class="finance-search" @submit.prevent="search">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="账单月份"><el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" title="按订单号年月筛选，如 TP-261029-010 对应 2026-10" clearable @change="search" /></el-form-item>
      <el-form-item label="客户经理"><el-button :class="{'manager-filter-active':managerScope!=='all'}" :title="managerLabel" @click="managerPickerVisible=true">{{managerLabel}}</el-button></el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="resetSearch">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced"><el-form-item label="项目状态"><el-select v-model="filters.projectStatus" clearable placeholder="全部状态" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item><el-form-item label="客户"><el-input v-model="filters.client" clearable placeholder="客户全称或简称" @input="queueFilterSearch" @keyup.enter="search" /></el-form-item></AdvancedFilterPopover></el-form-item>
    </AppForm>
    <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" append-to-body :class="['finance-manager-dialog',{'has-manager-select':managerDraftScope==='name'}]" width="min(560px, calc(100vw - 32px))" top="10vh" :close-on-click-modal="false">
      <el-radio-group v-model="managerDraftScope" class="manager-filter-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds" @options="cacheManagers" />
      <p class="finance-help">可多选客户部成员，点击“确定”后更新订单列表及客户金额小计。</p>
      <template #footer><el-button @click="managerPickerVisible=false">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <p class="finance-help">按语种方向维护多条单价，默认采用客户统计：仅填写一栏时直接采用，多栏时请选择统计口径；也可改用我司统计。母订单单价复制至匹配语种的下级，单独改价的下级保留；按数量时父级汇总下级金额，各币种单独小计；固定收费直接采用登记的一口价。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" row-key="id" border default-expand-all empty-text="暂无笔译项目">
      <el-table-column type="index" label="序号" width="60" :index="index => (page-1)*10+index+1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width" :prop="column.key">
        <template #default="{row}"><div v-if="column.key==='unitPrice'"><div v-for="(price,index) in row.prices||[]" :key="price.id||index" class="finance-language-price"><strong>{{price.languagePair||row.languagePair||'待选择语种方向'}}</strong><span class="finance-cell">{{taxPriceSummary(price.taxPrices,price.currency,price.unitSize+'计价单位',false)||'税口径未填写'}}</span><CustomerPriceFields v-if="!price.taxPrices" readonly :amount="price.amount" :currency="price.currency" :unit-size="price.unitSize" :metric-type="price.metric" /></div><span v-if="row.pricingMode==='fixed'">固定收费（不涉及单价）</span><span v-else-if="!row.prices?.length">未设置单价</span></div><span v-else class="finance-cell">{{ cell(row,column.key) }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right"><template #default="{row}"><el-button v-if="canWrite" link type="primary" :disabled="editorLoading" @click="openEditor(row)">编辑收费</el-button><el-button link type="primary" @click="historyOrder=row;historyVisible=true">修改记录</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next, jumper" @current-change="load" />
    <section class="client-subtotals"><h4>客户金额小计 <small>当前筛选条件下的全部匹配母订单；不重复累加下级订单</small></h4><el-table :data="subtotals" border row-key="clientId" empty-text="暂无客户金额"><el-table-column prop="clientName" label="客户" min-width="180" /><el-table-column prop="projectCount" label="母订单数" width="110" /><el-table-column label="不含税总价小计" min-width="180"><template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsExclTax)}}</span></template></el-table-column><el-table-column label="含税总价小计" min-width="180"><template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsInclTax)}}</span></template></el-table-column><el-table-column label="调整后总价小计" min-width="180"><template #default="{row}"><span class="finance-cell">{{formatAmounts(row.adjustedTotals)}}</span></template></el-table-column><el-table-column label="统计情况" min-width="180"><template #default="{row}">{{row.incomplete?'部分订单缺少数量或单价，当前为已计算金额小计':'完整'}}</template></el-table-column></el-table></section>
    <DraggableFormDialog v-model="editorVisible" class="customer-finance-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="closeEditor">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`客户财务 · ${editor.orderNo || ''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editorBody" v-loading="saving">
        <CustomerFinanceModuleTabs v-model="financeModule" module="translation" :client-id="editor.clientId"><template #translation>
        <AppForm :model="editor" label-position="top" :disabled="saving">
          <el-form-item label="项目名称"><ReadonlyField :model-value="editor.sourceFileName || editor.projectName || '-'" source="auto" /></el-form-item>
        </AppForm>
          <el-tabs v-model="financeSection"><el-tab-pane label="收费设置" name="pricing">
        <AppForm ref="formRef" :model="editor" label-position="top" :disabled="saving">
          <el-form-item label="计价模式"><el-radio-group v-model="editor.pricingMode" @change="changePricingMode"><el-radio value="metric">按数量</el-radio><el-radio value="fixed">固定收费</el-radio></el-radio-group></el-form-item>
          <p v-if="localTarget" class="finance-help">本次财务填写随项目表单一起保存。</p>
          <el-form-item v-if="editor.pricingMode!=='fixed'" label="客户参考价"><el-button :disabled="!referencePrices.length" @click="adoptReference">采用最新客户参考价</el-button><small>{{referencePrices.length?'按同客户、同语种方向带入；保存项目后生效':'该客户暂无匹配的语种参考价'}}</small></el-form-item>
          <CustomerTranslationPriceEditor v-if="editor.pricingMode!=='fixed'" v-model="editor.prices" :matrix="editor.wordCountMatrix" :disabled="saving" />
          <p v-if="editor.pricingMode!=='fixed'" class="finance-help">有下级订单时，列表总价按下级汇总。未登记对应数量时可先保存单价，金额显示待补录。</p>
          <el-form-item v-if="editor.pricingMode!=='fixed'" label="计算总价（按税口径）"><ReadonlyField :model-value="calculatedTotalText" source="auto" /></el-form-item>
          <el-form-item v-if="editor.pricingMode==='fixed'" label="货币"><el-select v-model="editor.currency"><el-option v-for="currency in ['CNY','USD','HKD','EUR','GBP','JPY']" :key="currency" :value="currency" /></el-select></el-form-item>
          <el-form-item :label="editor.pricingMode==='fixed'?'不含税固定收费':'不含税总价（调整）'" prop="adjustedTotal" :rules="[{validator:(_rule,_value,callback)=>callback(editor.pricingMode==='fixed'&&editor.adjustedTotal==null&&editor.adjustedTotalInclTax==null?new Error('请填写不含税或含税固定收费'):undefined),trigger:'change'}]"><el-input-number v-model="editor.adjustedTotal" :disabled="editor.pricingMode!=='fixed' && new Set((editor.prices||[]).map(row=>row.currency)).size>1" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入不含税固定收费':'留空按自动计算金额'" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="editor.explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item>
          <el-form-item label="账单月份"><el-date-picker v-model="editor.billingMonth" type="month" value-format="YYYY-MM" clearable /></el-form-item>
          <el-form-item :label="editor.pricingMode==='fixed'?'含税固定收费':'含税总价（调整）'"><el-input-number v-model="editor.adjustedTotalInclTax" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入含税固定收费':'留空按含税单价与数量计算'" /></el-form-item>
          <el-form-item v-if="!localTarget&&editor.pricingMode!=='fixed'&&canWriteClients&&editor.clientId" label="同步客户参考价"><el-button :disabled="saving||syncPreviewPending" @click="save(true)">保存并同步单价至客户信息…</el-button></el-form-item>
          <el-form-item v-if="!localTarget&&editor.pricingMode!=='fixed'" label="同步同月订单"><SyncSameMonthPrices v-if="editorVisible" :project-id="editor.rootId" :order-id="editor.id" :client-id="editor.clientId" :version="treeVersion" :month="editor.billingMonth" :disabled="saving||editorDirty||!originalPrices.length" @synced="onSameMonthSynced" /></el-form-item>
        </AppForm>
          </el-tab-pane><el-tab-pane label="对账单" name="statement"><div data-dialog-field-search-label="对账单"><CustomerStatementPanel v-if="editorVisible&&financeSection==='statement'" :project-id="editor.rootId" :order-id="editor.id" :client-id="editor.clientId" :billing-month="editor.billingMonth" /></div></el-tab-pane></el-tabs>
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button :disabled="saving" @click="closeEditor()">取消</el-button><el-button v-if="financeModule==='translation'&&financeSection==='pricing'" type="primary" :loading="saving" @click="save()">保存</el-button></template>
    </DraggableFormDialog>
    <CustomerRateSyncPreview v-if="editorVisible" ref="rateSyncPreviewRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" />
    <DraggableFormDialog v-model="historyVisible" append-to-body class="customer-finance-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" :title="`财务修改记录 · ${historyOrder?.orderNo||''}`"><TranslationFinanceHistory v-if="historyVisible&&historyOrder" :project-id="historyOrder.rootId" :order-id="historyOrder.id" /><template #footer><el-button @click="historyVisible=false">关闭</el-button></template></DraggableFormDialog>
  </el-card>
</template>

<script setup>
import {calculateTaxOrderPriceTree} from '@/utils/translationQuantityBasis'
import CustomerFinanceModuleTabs from '@/components/common/CustomerFinanceModuleTabs.vue'
import CustomerStatementPanel from '@/components/common/CustomerStatementPanel.vue'
import {taxPriceForm,taxPriceSummary} from '@/utils/taxPrices'
import { computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCustomerTranslationRates, getCustomerFinanceProject, getCustomerFinancePage, saveCustomerFinanceProject } from '@/api/translationCustomerFinance'
import { getProjectStatusLabel, getProjectStatusOptions } from '@/utils/projectStatus'
import { hasPermission } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { useTableColumns } from '@/composables/useTableColumns'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import CustomerDepartmentManagerSelect from '@/components/common/CustomerDepartmentManagerSelect.vue'
import CustomerRateSyncPreview from '@/components/common/CustomerRateSyncPreview.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import {businessDateTimeInputValue} from '@/utils/dateTime'
import CustomerPriceFields from './components/CustomerPriceFields.vue'
import CustomerTranslationPriceEditor from '@/components/common/CustomerTranslationPriceEditor.vue'
import TranslationFinanceHistory from '@/components/common/TranslationFinanceHistory.vue'
import SyncSameMonthPrices from '@/components/common/SyncSameMonthPrices.vue'
import {calculateOrderPriceTree,basisLabel,resolveRateQuantity} from '@/utils/translationQuantityBasis'
import {newCustomerRate,ratePayload,referenceDraft,defaultRateMetric} from '@/utils/customerTranslationRates'

const columns = [
  {key:'orderNo',label:'订单号',width:165},{key:'projectName',label:'项目名称',width:240},
  {key:'clientShortName',label:'客户简称',width:140},{key:'projectStatus',label:'项目状态',width:110},
  {key:'languagePair',label:'翻译方向',width:130},{key:'wordCount',label:'字数统计',width:160},
  {key:'pricingMode',label:'计价模式',width:120},{key:'unitPrice',label:'单价',width:360},{key:'totalPrice',label:'不含税总价',width:180},{key:'totalInclTax',label:'含税总价',width:180},
  {key:'adjustedTotal',label:'调整后总价',width:180},{key:'explanation',label:'说明',width:220},
]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('translation-customer-finance',columns,columns.map(item=>item.key))
const visibleColumns=computed(()=>columns.filter(item=>isVisible(item.key)))
const statuses=getProjectStatusOptions('translation'),canWrite=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const emit=defineEmits(['saved'])
const props=defineProps({clientId:{type:[String,Number],default:''},editorOnly:Boolean,clientScope:Boolean})
const financeModule=ref('translation')
const financeSection=ref('pricing')
const filters=reactive({keyword:'',projectStatus:'',client:'',month:'',manager:''}),rows=ref([]),subtotals=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),advancedVisible=ref(false)
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerScope=ref(props.clientScope?'all':'self'),managerDraftScope=ref(props.clientScope?'all':'self'),managerIds=ref([]),managerDraftIds=ref([]),managerPickerVisible=ref(false),managerNames=ref({})
function cacheManagers(people){managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[person.id,`${person.name}${person.username&&person.username!==person.name?`（${person.username}）`:''}`]))}}
const managerLabel=computed(()=>managerScope.value==='self'?`本人（${selfName}）`:managerScope.value==='name'?`指定（${managerIds.value.length}人）：${managerIds.value.map(id=>managerNames.value[id]||'已选人员').join('、')}`:'不指定人（全部订单）')
watch(managerPickerVisible,visible=>{if(visible){managerDraftScope.value=managerScope.value;managerDraftIds.value=[...managerIds.value]}})
function applyManager(){managerScope.value=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value;managerIds.value=managerScope.value==='name'?[...managerDraftIds.value]:[];filters.manager='';managerPickerVisible.value=false;search()}
const advancedCount=computed(()=>Number(!!filters.projectStatus)+Number(!!filters.client.trim()))
function clearAdvanced(){filters.projectStatus='';filters.client='';search()}
let timer,controller,sequence=0,disposed=false
async function load(){
  const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value=''
  try{const data=await getCustomerFinancePage({client_id:props.clientId||undefined,keyword:filters.keyword.trim()||undefined,project_status:filters.projectStatus||undefined,client:filters.client.trim()||undefined,billing_month:filters.month||undefined,manager_ids:managerScope.value==='name'?managerIds.value:undefined,only_mine:managerScope.value==='self',skip:(page.value-1)*10,limit:10},{signal:controller.signal});if(current===sequence){rows.value=data.items||[];subtotals.value=data.clientSubtotals||[];total.value=data.total||0}}
  catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务列表加载失败')}
  finally{if(current===sequence)loading.value=false}
}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function queueFilterSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function resetSearch(){filters.keyword='';filters.projectStatus='';filters.client='';filters.month='';filters.manager='';managerIds.value=[];managerScope.value=props.clientScope?'all':'self';search()}
const formatAmounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-'
function cell(row,key){
  if(key==='pricingMode')return row.pricingMode==='fixed'?'固定收费':'按数量'
  if(key==='projectName')return row.sourceFileName||row.projectName||'-'
  if(key==='projectStatus')return getProjectStatusLabel('translation',row.projectStatus)
  if(key==='wordCount')return row.prices?.length?row.prices.map(price=>`${price.languagePair}：${price.quantity==null?'未登记':Number(price.quantity).toLocaleString('zh-CN')}（${metricLabel(price.metric)}）`).join('\n'):'未登记'
  if(key==='totalInclTax')return formatAmounts(row.totalsInclTax);if(key==='totalPrice'||key==='adjustedTotal'){const values=key==='totalPrice'?row.totalsExclTax:row.adjustedTotals;return (Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-')+(row.incomplete?'\n待补录数量或单价':'')}
  return row[key]||'-'
}
const localTarget=ref(null)
const editorVisible=ref(false),editorLoading=ref(false),saving=ref(false),saveError=ref(''),editor=ref({}),formRef=ref(),editorBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
let original='',treeVersion='',libraryVersion=''
const referencePrices=ref([]),updateLibrary=ref(false)
const historyVisible=ref(false),historyOrder=ref(null)
const metricLabel=basisLabel
const originalPrices=ref([])
const rateSyncPreviewRef=ref(),syncPreviewPending=ref(false)
const editorDirty=computed(()=>editorVisible.value&&editorSignature()!==original)
const calculatedTotalText=computed(()=>{const result=calculateTaxOrderPriceTree(editor.value,originalPrices.value);return '不含税：'+formatAmounts(result.excl.totals)+(result.excl.incomplete?'（待补录）':'')+'；含税：'+formatAmounts(result.incl.totals)+(result.incl.incomplete?'（待补录）':'')})
async function onSameMonthSynced(){editorVisible.value=false;emit('saved');await load()}
function editorSignature(){return JSON.stringify([editor.value.pricingMode,editor.value.currency,(editor.value.prices||[]).map(ratePayload),editor.value.adjustedTotal,editor.value.adjustedTotalInclTax,editor.value.explanation,editor.value.billingMonth,updateLibrary.value])}
function referenceDefaults(){const choices=String(editor.value.languagePair||'').split('；').filter(Boolean);return choices.map(direction=>{const options=referencePrices.value.filter(row=>row.languagePair===direction);return options.find(row=>row.metric===defaultRateMetric(direction)&&row.currency==='CNY'&&Number(row.unitSize)===1)||options[0]}).filter(Boolean).map(referenceDraft)}
function adoptReference(){const values=referenceDefaults();if(!values.length)return ElMessage.warning('没有与此订单语种方向匹配的客户参考价');editor.value.prices=values;editor.value.adjustedTotal=undefined}
async function openEditor(row){
  financeSection.value='pricing'
  financeModule.value='translation'
  if(!canWrite||editorLoading.value)return
  localTarget.value=null
  editorLoading.value=true
  try{const data=await getCustomerFinanceProject(row.rootId);if(disposed)return;const find=node=>node.id===row.id?node:(node.children||[]).map(find).find(Boolean);const selected=find(data.item);if(!selected)throw new Error('订单已变化，请刷新');originalPrices.value=structuredClone(selected.prices||[]);editor.value={...structuredClone(selected),prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),billingMonth:selected.billingMonth||businessDateTimeInputValue().slice(0,7)};referencePrices.value=data.referencePrices?.items||[];libraryVersion=data.referencePrices?.version||'';updateLibrary.value=false;if(!editor.value.prices.length){const suggested=referenceDefaults();editor.value.prices=suggested.length?suggested:(String(selected.languagePair||'').split('；').filter(Boolean).map(newCustomerRate));if(!editor.value.prices.length)editor.value.prices=[newCustomerRate()]};treeVersion=data.version;saveError.value='';clearFieldSearch();editorVisible.value=true;await nextTick();original=editorSignature()}
  catch(e){ElMessage.error(getLocalizedErrorMessage(e,'收费明细加载失败'))}finally{editorLoading.value=false}
}
async function closeEditor(done){
  if(saving.value)return
  if(editorSignature()!==original){try{await ElMessageBox.confirm('收费明细有未保存修改，确定放弃？','关闭编辑',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}
  if(typeof done==='function')done();else editorVisible.value=false
}
async function save(syncToClient=false){
  if(saving.value||!canWrite||!await formRef.value?.validate().catch(()=>false))return
  if(editor.value.pricingMode!=='fixed'&&!editor.value.prices.length)return ElMessage.warning('请至少填写一条语种单价')
  if(editor.value.pricingMode==='fixed'&&editor.value.adjustedTotal==null&&editor.value.adjustedTotalInclTax==null)return ElMessage.warning('请填写固定收费金额')
  if(localTarget.value){saveLocalFinance();return}
  if(syncToClient){if(syncPreviewPending.value)return;syncPreviewPending.value=true;let confirmed;try{confirmed=await rateSyncPreviewRef.value.confirm()}finally{syncPreviewPending.value=false}if(!confirmed)return;libraryVersion=confirmed.version}
  saving.value=true;saveError.value=''
  try{await saveCustomerFinanceProject(editor.value.rootId,{version:treeVersion,order_id:editor.value.id,pricing_mode:editor.value.pricingMode||'metric',currency:editor.value.currency||'CNY',prices:editor.value.pricingMode==='fixed'?null:editor.value.prices.map(ratePayload),update_library:syncToClient,sync_confirmed:syncToClient,library_version:libraryVersion,adjusted_total:editor.value.adjustedTotal??null,adjusted_total_incl_tax:editor.value.adjustedTotalInclTax??null,explanation:editor.value.explanation||'',billing_month:editor.value.billingMonth||null});original=editorSignature();editorVisible.value=false;ElMessage.success('语种单价已保存，下级继承及金额小计已更新');emit('saved');await load()}
  catch(e){saveError.value=getLocalizedErrorMessage(e,'保存失败，请检查收费明细；如项目已被其他人修改，请重新打开后编辑')}
  finally{saving.value=false}
}

function changePricingMode(){editor.value.adjustedTotal=undefined;editor.value.adjustedTotalInclTax=undefined;formRef.value?.clearValidate()}
async function openForForm(target,parent=target){
  financeSection.value='pricing'
  financeModule.value='translation'
  if(!canWrite)return
  localTarget.value=target
  const charges=target.customerChargeItems||[],first=charges[0]
  const prices=charges.filter(row=>row.pricingMode==='metric').map(row=>({id:row.id,languagePair:row.languagePair||target.languagePair||parent.languagePair||'',amount:row.unitPriceExclTax??row.unitPriceInclTax,taxPrices:taxPriceForm(row),currency:row.currency||'CNY',metric:row.quantityBasis||row.metricType,unitSize:Number(row.unitSize||1)}))
  editor.value={id:target.id||'',rootId:parent.id||'',orderNo:target.orderNo||target.subOrderNo||'新增项目',projectName:target.sourceFileName||target.projectName||target.subProjectName||'',languagePair:target.languagePair||parent.languagePair||'',clientId:parent.clientId,wordCountMatrix:JSON.parse(JSON.stringify(target.wordCountMatrix||{})),children:[],pricingMode:first?.pricingMode||'metric',currency:first?.currency||'CNY',prices:prices.length?prices:[newCustomerRate(String(target.languagePair||parent.languagePair||'').split('；')[0]||'')],adjustedTotal:first?.totalExclTax==null?undefined:Number(first.totalExclTax),adjustedTotalInclTax:first?.totalInclTax==null?undefined:Number(first.totalInclTax),billingMonth:first?.billingMonth||businessDateTimeInputValue().slice(0,7),explanation:first?.remarks||''}
  originalPrices.value=JSON.parse(JSON.stringify(editor.value.prices));referencePrices.value=[];saveError.value='';clearFieldSearch();editorVisible.value=true;await nextTick();original=editorSignature()
  if(parent.clientId){try{const data=await getCustomerTranslationRates(parent.clientId);if(editorVisible.value&&localTarget.value===target)referencePrices.value=data.items||[]}catch(e){saveError.value=getLocalizedErrorMessage(e,'客户参考价加载失败')}}
}
function saveLocalFinance(){
  const old=localTarget.value.customerChargeItems||[]
  if(editor.value.pricingMode==='fixed')localTarget.value.customerChargeItems=[{id:old.length===1&&old[0].pricingMode==='fixed'?old[0].id:null,sequenceNo:1,itemName:'翻译费',pricingMode:'fixed',currency:editor.value.currency||'CNY',totalExclTax:editor.value.adjustedTotal??null,totalInclTax:editor.value.adjustedTotalInclTax??null,unitPriceExclTax:null,unitPriceInclTax:null,unitSize:null,metricType:null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}]
  else localTarget.value.customerChargeItems=editor.value.prices.map((price,index)=>({id:price.id||null,sequenceNo:index+1,itemName:'翻译费',pricingMode:'metric',metricType:resolveRateQuantity(editor.value.wordCountMatrix,price.metric).metric,quantityBasis:price.metric,languagePair:price.languagePair,unitSize:price.unitSize||1,unitPriceExclTax:price.taxPrices?.unitPriceExclTax??null,unitPriceInclTax:price.taxPrices?.unitPriceInclTax??null,currency:price.currency||'CNY',totalExclTax:index===0?editor.value.adjustedTotal??null:price.taxPrices?.totalExclTax??null,totalInclTax:index===0?editor.value.adjustedTotalInclTax??null:price.taxPrices?.totalInclTax??null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}))
  original=editorSignature();editorVisible.value=false;emit('saved');ElMessage.success('财务填写已保留，保存项目后生效')
}
defineExpose({openForForm})

watch(()=>props.clientId,search)
onMounted(()=>{if(props.clientId)void load()})
let firstEntry=true,active=false
onActivated(async()=>{if(props.editorOnly)return;active=true;managerScope.value=props.clientScope?'all':'self';managerIds.value=[];managerDraftScope.value='self';managerDraftIds.value=[];filters.manager='';page.value=1;await load();if(firstEntry&&active&&!disposed&&!props.clientScope){firstEntry=false;await nextTick();managerPickerVisible.value=true}})
onDeactivated(()=>{active=false;rateSyncPreviewRef.value?.cancel();managerPickerVisible.value=false;historyVisible.value=false;clearTimeout(timer);sequence++;controller?.abort();loading.value=false})
async function guardEditor(){if(!editorVisible.value)return true;if(saving.value)return false;await closeEditor();return !editorVisible.value}
onBeforeRouteLeave(guardEditor)
onBeforeRouteUpdate((to,from)=>to.query.section!==from.query.section?guardEditor():true)
onBeforeUnmount(()=>{disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
</script>

<style scoped>
.finance-editor-only { display:none; }
:global(.finance-manager-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.el-dialog.draggable-form-dialog.finance-manager-dialog.has-manager-select > .el-dialog__body){min-height:min(440px,55vh)}
:global(.finance-manager-dialog .el-dialog__header),:global(.finance-manager-dialog .el-dialog__footer){flex-shrink:0}
:global(.finance-manager-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
.manager-filter-choices{display:flex;flex-direction:column;align-items:flex-start}.manager-filter-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.manager-filter-active{background:#f1f5f9;border-color:#94a3b8}
.customer-finance{min-width:0}.finance-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.finance-search{display:flex;flex-wrap:wrap;gap:8px}.finance-search :deep(.el-form-item){margin:0 8px 12px 0}.finance-search .el-input{width:300px;max-width:100%}.finance-search .el-select{width:180px}.finance-help{color:#64748b;font-size:12px;margin:0 0 12px}.finance-cell{white-space:pre-wrap;overflow-wrap:anywhere}.el-pagination{margin-top:16px;justify-content:flex-end;flex-wrap:wrap}
:global(.customer-finance-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-finance-dialog .el-dialog__header),:global(.customer-finance-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-finance-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.customer-finance-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
