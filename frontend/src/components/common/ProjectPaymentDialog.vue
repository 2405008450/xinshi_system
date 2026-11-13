<template>
  <DraggableFormDialog :model-value="modelValue" class="project-payment-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="发票、查账与追账" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template v-if="showFilters" #actions><span class="payment-manager-label">客户经理：<el-button :title="managerLabel" @click="openManagerPicker">{{managerLabel}}</el-button></span></template></DialogFieldSearchHeader></template>
    <div ref="body" v-loading="loading">
      <el-tabs v-model="activeTab" @tab-change="onPaymentTabChanged"><el-tab-pane label="发票" name="invoice" /><el-tab-pane label="查账" name="overview" /><el-tab-pane label="追账" name="collection" /></el-tabs>
      <AppForm v-if="showFilters" :model="paymentFilters" inline class="payment-filter-bar" @submit.prevent="applyPaymentFilters">
        <el-form-item label="账单月份"><el-date-picker v-model="paymentFilters.months" :disabled="mismatchView" type="months" value-format="YYYY-MM" placeholder="全部时间（可多选月份）" clearable style="width:230px" @change="applyPaymentFilters" /></el-form-item>
        <el-form-item label="客户"><el-input v-model="paymentFilters.client" :disabled="mismatchView" placeholder="客户全称或简称" clearable style="width:190px" @input="queueClientSearch" @keyup.enter="applyPaymentFilters" /></el-form-item>
        <el-form-item v-if="activeTab!=='invoice'" label="付款状态"><el-select v-model="paymentFilters.status" clearable placeholder="全部状态" style="width:205px" @change="applyPaymentFilters"><el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        <el-form-item v-if="activeTab==='invoice'" label="是否需发票">
          <el-select v-model="paymentFilters.invoiceRequired" aria-label="是否需发票" clearable placeholder="全部开票需求" style="width:145px" @change="applyPaymentFilters">
            <el-option label="需" value="yes" />
            <el-option label="无需" value="no" />
            <el-option label="待判断" value="unknown" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="activeTab==='invoice'" label="发票状态"><el-select v-model="paymentFilters.invoiceStatus" clearable placeholder="全部状态" style="width:155px" @change="applyPaymentFilters"><el-option v-for="option in invoiceStatusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        <el-form-item v-if="activeTab==='invoice'">
          <el-popover trigger="click" placement="bottom-start" :width="325" @show="searchInvoiceCustomers('')">
            <template #reference>
              <el-button :type="invoiceClientIds.length ? 'primary' : 'default'">
                客户筛选{{ invoiceClientIds.length ? '（' + invoiceClientIds.length + '）' : '' }}
              </el-button>
            </template>
            <el-select v-model="invoiceClientIds" multiple filterable remote clearable
              aria-label="选择开票客户" placeholder="搜索客户全称、简称或编号" style="width:100%"
              :remote-method="searchInvoiceCustomers" :loading="invoiceCustomerLoading" @change="applyInvoiceCustomerFilters">
              <el-option v-for="customer in invoiceCustomerOptions" :key="customer.id" :value="customer.id"
                :label="customer.shortName || customer.name" />
            </el-select>
            <p v-if="invoiceCustomerError" role="alert">{{ invoiceCustomerError }}</p>
          </el-popover>
          <el-button :type="statementCustomerMode === 'include' ? 'primary' : 'default'"
            :aria-pressed="statementCustomerMode === 'include'" title="至少有一个笔译项目需要对账单的客户"
            @click="toggleStatementCustomers('include')">对账单客户</el-button>
          <el-button :type="statementCustomerMode === 'exclude' ? 'primary' : 'default'"
            :aria-pressed="statementCustomerMode === 'exclude'"
            @click="toggleStatementCustomers('exclude')">排除对账单客户</el-button>
        </el-form-item>
        <el-form-item><el-button :loading="searching" @click="applyPaymentFilters">查询</el-button><el-button @click="resetPaymentFilters">重置</el-button></el-form-item>
      </AppForm>
      <p v-if="showFilters" class="payment-filter-summary">匹配 {{projectTotal}} 个项目<span v-if="projectTotal>100">，可输入订单号或项目名称继续搜索</span></p>
      <section class="payment-overview">
        <div class="payment-overview-search"><el-input v-model="projectKeyword" placeholder="搜索订单号、项目名称" clearable style="width:280px" @input="queueProjectSearch" @keyup.enter="searchProjects(projectKeyword)" /><span v-if="mismatchView" class="payment-help">此选项覆盖账单月份和客户筛选。币种不同或金额缺失的项目也列入。</span><span v-if="collectionDefaultView" class="payment-help">未选择付款状态时，仅列未付款、已付定金及已付进度款的项目。</span></div>
        <div v-if="activeTab==='invoice' && canWrite" class="invoice-request-toolbar">
          <el-button type="primary" :disabled="searching || !selectedProjects.length" @click="requestVisible = true">开票需求</el-button>
          <span v-if="selectedProjects.length">已选 {{ selectedProjects.length }} 个项目</span>
        </div>
        <el-table ref="projectTable" v-loading="searching" :data="options" border row-key="id" max-height="460" empty-text="暂无匹配项目" @selection-change="selectedProjects = $event" @sort-change="sortProjects">
          <el-table-column v-if="activeTab==='invoice' && canWrite" type="selection" width="46" reserve-selection :selectable="canSelectInvoice" />
          <el-table-column prop="orderNo" label="订单号" min-width="160">
            <template #default="{row}"><TranslationOrderDetailPopover :order="row" /></template>
          </el-table-column>
          <el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="clientShortName" label="客户简称" min-width="140" sortable="custom" />
          <el-table-column prop="clientManager" label="客户经理" min-width="120" sortable="custom" show-overflow-tooltip>
            <template #default="{row}">{{ row.clientManager || '未分配' }}</template>
          </el-table-column>
          <el-table-column v-if="activeTab==='invoice'" label="是否需发票" width="120">
            <template #default="{row}">
              <el-button v-if="canReviewInvoice" link type="primary" title="在价格与付款中查看发票及价格" @click="emit('review-invoice', row)">{{invoiceRequirementLabel(row)}}</el-button>
              <span v-else>{{invoiceRequirementLabel(row)}}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="activeTab==='invoice'" label="发票状态" width="110">
            <template #default="{row}">
              <el-popover v-if="row.invoiceStatus === 'issued'" trigger="click" placement="left" :width="270">
                <template #reference><el-button link type="primary">{{ invoiceStatusText(row) }}</el-button></template>
                <div>开票人：{{ row.issuedBy?.name || '—' }}</div>
                <div>开票完成通知时间：{{ row.issuedNotification?.at ? formatBusinessDateTime(row.issuedNotification.at) : '—' }}</div>
              </el-popover>
              <span v-else>{{ invoiceStatusText(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="activeTab==='invoice'" label="是否发客户" width="115">
            <template #default="{row}">
              <el-popover v-if="row.customerSent" trigger="click" placement="left" :width="250">
                <template #reference><el-button link type="primary">是</el-button></template>
                <div>操作人：{{ row.customerSent.name }}</div>
                <div>操作日期：{{ formatBusinessDateTime(row.customerSent.at) }}</div>
                <el-button v-if="canWrite" link type="primary" :disabled="customerSentSaving" @click="changeCustomerSent(row, false)">改为否</el-button>
              </el-popover>
              <el-button v-else-if="canWrite && row.invoiceStatus === 'issued'" link type="primary"
                :disabled="customerSentSaving" @click="changeCustomerSent(row, true)">否</el-button>
              <span v-else>否</span>
            </template>
          </el-table-column>
          <el-table-column v-if="activeTab!=='invoice'" label="付款状态" min-width="175"><template #default="{row}">{{paymentStatusLabel(row)}}</template></el-table-column>
          <el-table-column v-if="activeTab!=='invoice'" label="已付金额" min-width="120"><template #default="{row}">{{row.paymentActualTotal==null?'未登记金额':`${row.paymentCurrency||'CNY'} ${row.paymentActualTotal}`}}</template></el-table-column>
          <el-table-column label="不含税总价" min-width="175">
            <template #default="{row}">{{formatPaymentTotals(row.totalsExclTax, row.adjustedTotalsExclTax, row.billingCurrencies.excl_tax)}}</template>
          </el-table-column>
          <el-table-column label="含税总价" min-width="175">
            <template #default="{row}">{{formatPaymentTotals(row.totalsInclTax, row.adjustedTotalsInclTax, row.billingCurrencies.incl_tax)}}</template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right"><template #default="{row}"><el-button v-if="activeTab==='invoice'" link type="primary" @click="emit('invoice',row)">发票</el-button><el-button v-else-if="canWrite" link type="primary" @click="openPaymentRow(row)">价格与付款</el-button></template></el-table-column>
        </el-table>
        <el-pagination v-model:current-page="projectPage" :page-size="20" :total="projectTotal" layout="total,prev,pager,next" @current-change="searchProjects(projectKeyword)" />
      </section>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="reloadPayment">重新加载付款情况</el-button></el-alert>
    </div>
    <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" width="min(560px, calc(100vw - 32px))" top="10vh" append-to-body>
      <el-radio-group v-model="managerDraftScope" class="payment-manager-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds" @options="cacheManagers" />
      <template #footer><el-button @click="managerPickerVisible=false">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <template #footer><el-button @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
  <InvoiceRequestDialog v-if="requestVisible" :project-ids="selectedProjects.map(row => row.id)"
    @close="requestVisible = false" @sent="projectTable?.clearSelection()" />
</template>
<script setup>
import {computed,defineAsyncComponent,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {customerFinanceSort,getCustomerFinancePage,getStatementCustomers} from '@/api/translationCustomerFinance'
import {invoiceStatusOptions as recordedInvoiceStatusOptions,invoiceStatusLabels} from '@/utils/documentRequirements'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import CustomerDepartmentManagerSelect from './CustomerDepartmentManagerSelect.vue'
import TranslationOrderDetailPopover from './TranslationOrderDetailPopover.vue'
import {paymentStatusLabel,paymentStatusFilterOptions,fullPaymentMismatchOption,paymentChangeEvent,connectPaymentSync} from '@/utils/paymentConfirmation'
const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})},initialProjectId:{type:String,default:''},lockProject:Boolean,canReviewInvoice:Boolean})
const emit=defineEmits(['update:modelValue','edit','invoice','review-invoice'])
const canWrite=hasPermission('projects:write')||hasPermission('finance:write')
const body=ref(),options=ref([]),loading=ref(false),searching=ref(false),error=ref('')
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const activeTab=ref('invoice'),projectPage=ref(1),showFilters=computed(()=>!props.lockProject)
const projectSort=ref()
const InvoiceRequestDialog = defineAsyncComponent(() => import('./InvoiceRequestDialog.vue'))
const projectTable = ref()
const selectedProjects = ref([])
const requestVisible = ref(false)
const canSelectInvoice = row => row.invoiceRequired === true && row.billingCurrencies.incl_tax.size > 0
let previousSelectionScope = ''
const invoiceStatusOptions = [...recordedInvoiceStatusOptions, {value:'not_required', label:'无需'}]
const invoiceStatusText = row => row.invoiceRequired === false ? '无需' : invoiceStatusLabels[row.invoiceStatus] || '未开票'
const customerSentSaving = ref(false)
async function changeCustomerSent(row, sent) {
  if (customerSentSaving.value) return
  customerSentSaving.value = true
  try {
    await ElMessageBox.confirm(sent ? '确认这张发票已发给客户？' : '确认将该发票改为未发客户？',
      '是否发客户', {confirmButtonText:'确认',cancelButtonText:'取消'})
  } catch {
    customerSentSaving.value = false
    return
  }
  const projectId = row.rootId || row.id
  try {
    await api.put(`/translation-customer-finance/project/${projectId}/invoice/customer-sent`, {sent})
    window.dispatchEvent(new CustomEvent('translation-invoice-changed', {detail:{projectId}}))
  } catch (e) {
    ElMessage.error(getLocalizedErrorMessage(e, '更新发客户状态失败'))
  } finally {
    customerSentSaving.value = false
  }
}
const paymentFilters=reactive({months:[],client:'',status:'',invoiceStatus:'',invoiceRequired:''}),projectKeyword=ref(''),projectTotal=ref(0)
const statementCustomerMode = ref('')
const invoiceClientIds = ref([])
const invoiceCustomerOptions = ref([])
const invoiceCustomerLoading = ref(false)
const invoiceCustomerError = ref('')
let invoiceCustomerSearch

async function searchInvoiceCustomers(keyword = '') {
  invoiceCustomerSearch?.abort()
  const controller = new AbortController()
  invoiceCustomerSearch = controller
  invoiceCustomerLoading.value = true
  invoiceCustomerError.value = ''
  try {
    const result = await getStatementCustomers({keyword:keyword.trim() || undefined, required_only:false, limit:50}, {signal:controller.signal})
    if (controller.signal.aborted) return
    const selected = invoiceCustomerOptions.value.filter(customer => invoiceClientIds.value.includes(customer.id))
    invoiceCustomerOptions.value = [...new Map([...selected, ...result.items].map(customer => [customer.id, customer])).values()]
  } catch (e) {
    if (!controller.signal.aborted) invoiceCustomerError.value = getLocalizedErrorMessage(e, '加载客户失败')
  } finally {
    if (!controller.signal.aborted) invoiceCustomerLoading.value = false
  }
}
function applyInvoiceCustomerFilters() {
  clearTimeout(filterTimer)
  projectPage.value = 1
  return searchProjects(projectKeyword.value)
}
function toggleStatementCustomers(mode) {
  statementCustomerMode.value = statementCustomerMode.value === mode ? '' : mode
  void applyInvoiceCustomerFilters()
}
function clearInvoiceCustomerFilters() {
  invoiceClientIds.value = []
  statementCustomerMode.value = ''
}
const mismatchView=computed(()=>activeTab.value!=='invoice'&&paymentFilters.status===fullPaymentMismatchOption.value)
const collectionDefaultView=computed(()=>activeTab.value==='collection'&&!paymentFilters.status)
const statusOptions=[...paymentStatusFilterOptions,fullPaymentMismatchOption]
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerScope=ref('self'),managerIds=ref([]),managerNames=ref({}),managerPickerVisible=ref(false),managerDraftScope=ref('self'),managerDraftIds=ref([])
const managerLabel=computed(()=>managerScope.value==='self'?`本人（${selfName}）`:managerScope.value==='name'?`指定（${managerIds.value.length}人）：${managerIds.value.map(id=>managerNames.value[id]||'已选人员').join('、')}`:'不指定人（全部订单）')
let filterTimer,projectTimer,searchSequence=0,controller
const invoiceRequirementLabel = row => row.invoiceRequired == null ? '待判断' : row.invoiceRequired ? '需' : '无需'
function formatPaymentTotals(totals, adjustments, billingCurrencies) {
  return Object.entries(totals || {}).map(([currency, amount]) => {
    const suffix = Object.hasOwn(adjustments || {}, currency) ? '（调整后）' : ''
    const check = billingCurrencies.has(currency) ? ' ✓' : ''
    return `${currency} ${amount}${suffix}${check}`
  }).join('；') || '未填写'
}

function collectBillingCurrencies(order, result = { excl_tax: new Set(), incl_tax: new Set() }) {
  if (order.priceAggregate) {
    for (const child of order.children || []) collectBillingCurrencies(child, result)
  } else {
    const selected = result[order.effectiveBillingTaxMode]
    for (const currency of Object.keys(order.billingTotals || {})) selected?.add(currency)
  }
  return result
}
function cacheManagers(people){managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[person.id,person.name]))}}
function openManagerPicker(){managerDraftScope.value=managerScope.value;managerDraftIds.value=[...managerIds.value];managerPickerVisible.value=true}
async function applyManager(){managerScope.value=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value;managerIds.value=managerScope.value==='name'?[...managerDraftIds.value]:[];managerPickerVisible.value=false;await applyPaymentFilters()}
function initPaymentFilters(){clearInvoiceCustomerFilters();Object.assign(paymentFilters,{months:[...new Set([props.query.billing_months,props.query.billing_month].flat().filter(Boolean))],client:'',status:'',invoiceStatus:'',invoiceRequired:''});projectKeyword.value='';managerIds.value=[...(props.query.manager_ids||[])];managerScope.value=props.lockProject?'all':managerIds.value.length?'name':props.query.only_mine?'self':'all'}
function paymentQuery(keyword){return {sort:projectSort.value,keyword:keyword?.trim()||undefined,billing_months:mismatchView.value?undefined:paymentFilters.months?.length?paymentFilters.months:undefined,client:mismatchView.value?undefined:paymentFilters.client.trim()||undefined,payment_status:mismatchView.value||activeTab.value==='invoice'?undefined:paymentFilters.status||undefined,manager_ids:managerScope.value==='name'?managerIds.value:undefined,only_mine:managerScope.value==='self',include_payment_status:true,include_invoice_status:activeTab.value==='invoice',invoice_status:activeTab.value==='invoice'?paymentFilters.invoiceStatus||undefined:undefined,invoice_required:activeTab.value==='invoice'?paymentFilters.invoiceRequired||undefined:undefined,client_ids:activeTab.value==='invoice'&&invoiceClientIds.value.length?invoiceClientIds.value:undefined,statement_customers:activeTab.value==='invoice'?statementCustomerMode.value||undefined:undefined,payment_amount_mismatch:mismatchView.value,exclude_full:collectionDefaultView.value,payment_project_id:props.lockProject?props.initialProjectId||undefined:undefined,skip:(projectPage.value-1)*20,limit:20}}
function queueClientSearch(value){clearTimeout(filterTimer);controller?.abort();searchSequence++;if(!value.trim())void applyPaymentFilters();else filterTimer=setTimeout(applyPaymentFilters,400)}
function queueProjectSearch(keyword=''){projectPage.value=1;projectKeyword.value=keyword;clearTimeout(projectTimer);controller?.abort();searchSequence++;if(!keyword.trim())void searchProjects('');else projectTimer=setTimeout(()=>searchProjects(keyword),400)}
async function applyPaymentFilters(){clearTimeout(filterTimer);clearTimeout(projectTimer);projectPage.value=1;projectKeyword.value='';await searchProjects('')}
async function resetPaymentFilters(){clearInvoiceCustomerFilters();Object.assign(paymentFilters,{months:[],client:'',status:'',invoiceStatus:'',invoiceRequired:''});managerIds.value=[];managerScope.value=props.query.only_mine?'self':'all';await applyPaymentFilters()}
async function searchProjects(keyword=''){clearTimeout(projectTimer);const seq=++searchSequence;controller?.abort();controller=new AbortController();searching.value=true;error.value='';
  const query = paymentQuery(keyword)
  const scope = JSON.stringify({...query, skip:undefined, sort:undefined})
  if (scope !== previousSelectionScope) {
    projectTable.value?.clearSelection()
    selectedProjects.value = []
    previousSelectionScope = scope
  }
  try{const data=await getCustomerFinancePage(query,{signal:controller.signal});if(seq===searchSequence){if(activeTab.value==='invoice'&&data.invoiceFilterApplied!==true){options.value=[];projectTotal.value=0;error.value='后端发票功能尚未更新，请更新后端服务后重试';return}if(mismatchView.value&&(data.paymentAmountMismatchFilterApplied!==true||(data.items||[]).some(item=>item.paymentStatus!=='full'||item.paymentAmountMismatch!==true))){options.value=[];projectTotal.value=0;error.value='后端未正确执行已付全款金额核对，请更新后端服务后重试';return}
    options.value = (data.items || []).map(project => ({
      ...project,
      billingCurrencies: collectBillingCurrencies(project),
      children: undefined,
    }))
    projectTotal.value=data.total||0}}catch(e){if(seq===searchSequence&&e.code!=='ERR_CANCELED'){options.value=[];projectTotal.value=0;error.value=getLocalizedErrorMessage(e,'项目搜索失败')}}finally{if(seq===searchSequence)searching.value=false}}
async function onPaymentTabChanged(){projectPage.value=1;await searchProjects(projectKeyword.value)}
function sortProjects(change){
  projectSort.value=customerFinanceSort(change)
  projectPage.value=1
  void searchProjects(projectKeyword.value)
}
function openPaymentRow(row){emit('edit',row);emit('update:modelValue',false)}
function reloadPayment(){void searchProjects(projectKeyword.value)}
function beforeClose(done){done()}
function onExternalPayment(event){if(props.modelValue&&event.detail?.projectId)void searchProjects(projectKeyword.value)}
connectPaymentSync();window.addEventListener(paymentChangeEvent,onExternalPayment);window.addEventListener('translation-invoice-changed',onExternalPayment)
watch(()=>props.modelValue,visible=>{searchSequence++;controller?.abort();clearTimeout(filterTimer);clearTimeout(projectTimer);clearFieldSearch();error.value='';if(!visible){managerPickerVisible.value=false;return}activeTab.value='invoice';projectPage.value=1;projectSort.value=undefined;initPaymentFilters();options.value=[];void searchProjects()})
onBeforeUnmount(()=>{invoiceCustomerSearch?.abort();clearTimeout(filterTimer);clearTimeout(projectTimer);window.removeEventListener(paymentChangeEvent,onExternalPayment);window.removeEventListener('translation-invoice-changed',onExternalPayment);searchSequence++;controller?.abort()})
</script>
<style scoped>
.invoice-request-toolbar { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
:global(.project-payment-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-payment-dialog>.el-dialog__header),:global(.project-payment-dialog>.el-dialog__footer){flex:none}:global(.project-payment-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-summary{margin-bottom:14px}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
.payment-overview-search{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}.payment-overview .el-pagination{margin-top:10px}.payment-filter-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.payment-filter-bar :deep(.el-form-item){margin-right:0;margin-bottom:8px}.payment-filter-summary{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 8px}.payment-manager-label{font-size:14px;font-weight:400;color:var(--el-text-color-secondary)}.payment-manager-label .el-button{max-width:300px;white-space:normal;height:auto;min-height:30px}.payment-manager-choices{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
</style>
