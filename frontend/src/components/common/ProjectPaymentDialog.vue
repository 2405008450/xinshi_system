<template>
  <component :is="embedded ? 'section' : DraggableFormDialog" v-bind="dialogProps"
    @update:model-value="emit('update:modelValue',$event)">
    <template v-if="!embedded" #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="dialogTitle" :copyable-title="!!scopeOrder"
        :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch">
        <template v-if="showFilters || mergedOrderNumbers.length || headerClientName" #actions>
          <el-popover v-if="mergedOrderNumbers.length" v-model:visible="mergedOrdersVisible"
            trigger="click" placement="bottom-start" role="dialog" :title="`${settlementGroupLabel}订单号`" :width="250">
            <template #reference>
              <el-button link type="primary">
                {{ settlementGroupLabel }}（{{ mergedOrderNumbers.length }} 单）
              </el-button>
            </template>
            <ul class="payment-merged-order-numbers">
              <li v-for="number in mergedOrderNumbers" :key="number">{{ number }}</li>
            </ul>
          </el-popover>
          <span v-if="headerClientName" class="payment-manager-label">{{headerClientName}}</span>
          <span v-if="showFilters" class="payment-manager-label">客户经理：
            <span v-if="scopeOrder">{{scopeOrder.clientManager || '未分配'}}</span>
            <el-button v-else :title="managerLabel" @click="openManagerPicker">{{managerLabel}}</el-button>
          </span>
        </template>
      </DialogFieldSearchHeader>
    </template>
    <div ref="body" v-loading="loading">
      <el-tabs v-if="!embedded" v-model="activeTab" :before-leave="beforeTabLeave" @tab-change="onPaymentTabChanged">
        <el-tab-pane v-if="!ledgerOnly" label="发票" name="invoice" />
        <el-tab-pane v-if="!ledgerOnly" label="特殊结算发票" name="special_invoice" />
        <el-tab-pane v-if="ledgerOnly" label="查账" name="overview" />
        <el-tab-pane v-if="ledgerOnly" label="追账" name="collection" />
      </el-tabs>
      <ProjectPaymentDialog v-if="modelValue&&activeTab==='special_invoice'" ref="specialInvoiceWorkspace"
        model-value embedded
        :invoice-client-id="scopeOrder?.clientId" :invoice-client-name="scopeOrder?.clientShortName||scopeOrder?.clientName" :initial-month="scopeMonth||undefined"
        :period-number="scopeOrder?.settlementPeriodNumber??scopeOrder?.billingPeriod?.number"
        :manager-query="specialInvoiceManagerQuery" @invoice-saved="emit('invoice-saved',$event)" />
      <template v-else>
      <AppForm data-auto-draft="off" v-if="showFilters" :model="paymentFilters" inline class="payment-filter-bar" @submit.prevent="applyPaymentFilters">
        <el-form-item label="账单月份"><ReadonlyField v-if="scopeOrder" :model-value="scopeBillingPeriod" source="auto" style="width:195px" /><el-date-picker v-else v-model="paymentFilters.months" :disabled="mismatchView" type="months" value-format="YYYY-MM" placeholder="全部时间（可多选月份）" clearable style="width:230px" @change="changeMonths" /></el-form-item>
        <el-form-item v-if="activeTab==='invoice'&&!scopeOrder&&paymentFilters.months?.length===1" label="账期">
          <StatementPeriodSelect v-model="paymentFilters.period" :month="paymentFilters.months[0]" :client-id="invoiceClientId"
            :settlement-scope="embedded?'special':'standard'" @update:model-value="applyPaymentFilters" />
        </el-form-item>
        <el-form-item label="客户"><ReadonlyField v-if="scopeOrder || invoiceClientId" :model-value="formatClientWithSubClient(scopeOrder, scopeOrder?.clientShortName || scopeOrder?.clientName || invoiceClientName || '当前客户')" source="auto" style="width:190px" /><el-input v-else v-model="paymentFilters.client" :disabled="mismatchView" placeholder="客户或子客户名称" clearable style="width:190px" @input="queueClientSearch" @keyup.enter="applyPaymentFilters" /></el-form-item>
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
          <el-popover v-if="!scopeOrder && !invoiceClientId" v-model:visible="invoiceCustomerPickerVisible" trigger="click" placement="bottom-start" title="客户筛选" :width="325" @show="searchInvoiceCustomers('')">
            <template #reference>
              <el-button :type="invoiceClientIds.length ? 'primary' : 'default'">
                客户筛选{{ invoiceClientIds.length ? '（' + invoiceClientIds.length + '）' : '' }}
              </el-button>
            </template>
            <el-select data-auto-draft="off" v-model="invoiceClientIds" multiple filterable remote clearable
              aria-label="选择开票客户" placeholder="搜索客户或子客户名称、简称或编号" style="width:100%"
              :remote-method="searchInvoiceCustomers" :loading="invoiceCustomerLoading" @change="applyInvoiceCustomerFilters">
              <el-option v-for="customer in invoiceCustomerOptions" :key="customer.id" :value="customer.id"
                :label="[customer.parentName,customer.shortName || customer.name,customer.code].filter(Boolean).join(' · ')" />
            </el-select>
            <p v-if="invoiceCustomerError" role="alert">{{ invoiceCustomerError }}</p>
          </el-popover>
          <el-button :type="statementCustomerMode === 'include' ? 'primary' : 'default'"
            :aria-pressed="statementCustomerMode === 'include'" :title="scopeOrder?'仅显示当前范围内需要对账单的订单':'至少有一个笔译项目需要对账单的客户'"
            @click="toggleStatementCustomers('include')">{{scopeOrder?'需对账单':'对账单客户'}}</el-button>
          <el-button :type="statementCustomerMode === 'exclude' ? 'primary' : 'default'"
            :aria-pressed="statementCustomerMode === 'exclude'"
            @click="toggleStatementCustomers('exclude')">{{scopeOrder?'无需对账单':'排除对账单客户'}}</el-button>
        </el-form-item>
        <el-form-item><el-button :loading="searching" @click="applyPaymentFilters">查询</el-button><el-button @click="resetPaymentFilters">重置</el-button></el-form-item>
      </AppForm>
      <p v-if="showFilters" class="payment-filter-summary">匹配 {{displayedProjectTotal}} 个项目<span v-if="displayedProjectTotal>100">，可输入订单号或项目名称继续搜索</span></p>
      <section class="payment-overview">
        <div class="payment-overview-search"><el-input v-model="projectKeyword" placeholder="搜索订单号、项目名称" clearable style="width:280px" @input="queueProjectSearch" @keyup.enter="searchProjects(projectKeyword)" /><span v-if="mismatchView" class="payment-help">{{scopeOrder?'在当前客户及账单月份内核对。':'此选项覆盖账单月份和客户筛选。'}}币种不同或金额缺失的项目也列入。</span><span v-if="collectionDefaultView" class="payment-help">未选择付款状态时，仅列未付款、已付定金及已付进度款的项目。</span></div>
        <div v-if="activeTab==='invoice' && canWrite" class="invoice-request-toolbar">
          <el-button type="primary" :loading="openingRequest"
            :disabled="searching || (!scopeOrder && !selectedProjects.length)" @click="openInvoiceRequest">开票需求</el-button>
          <span v-if="scopeOrder">自动带入当前结算范围内的需开票项目</span>
          <span v-else-if="selectedProjects.length">已选 {{ selectedProjects.length }} 个项目</span>
        </div>
        <el-table ref="projectTable" v-loading="searching" :data="displayedOptions" border row-key="id" max-height="460" empty-text="暂无匹配项目" @selection-change="selectedProjects = $event" @sort-change="sortProjects">
          <el-table-column v-if="activeTab==='invoice' && canWrite && !scopeOrder" type="selection" width="46" reserve-selection :selectable="canSelectInvoice" />
          <el-table-column prop="orderNo" label="订单号" min-width="160">
            <template #default="{row}"><TranslationOrderDetailPopover :order="row" /></template>
          </el-table-column>
          <el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="clientShortName" label="客户简称" show-sub-client min-width="185" sortable="custom">
            <template #default="{row}">
              <span>{{row.clientShortName}}</span>
            </template>
          </el-table-column>
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
                <div>操作日期：{{ row.customerSent.at ? formatBusinessDateTime(row.customerSent.at) : '—' }}</div>
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
            <template #default="{row}">{{formatPaymentTotals(row.totalsExclTax, row.adjustedTotalsExclTax, row.billingCurrencies.excl_tax)}}<OrderPriceDetails :order="row" side="excl" /></template>
          </el-table-column>
          <el-table-column label="含税总价" min-width="175">
            <template #default="{row}">{{formatPaymentTotals(row.totalsInclTax, row.adjustedTotalsInclTax, row.billingCurrencies.incl_tax)}}<OrderPriceDetails :order="row" side="incl" /></template>
          </el-table-column>
          <el-table-column label="操作" :width="embedded?210:activeTab==='invoice'&&scopeOrder?160:120" fixed="right">
            <template #default="{row}">
              <div v-if="activeTab==='invoice'" class="invoice-row-actions">
                <template v-if="!mergedOrderNumbers.length">
                  <span v-if="hasFixedInvoice && inlineInvoice?.orderId===row.id" aria-current="true">当前发票</span>
                  <el-button v-else link type="primary" :aria-expanded="inlineInvoice?.orderId===row.id"
                    @click="toggleInvoice(row)">{{hasFixedInvoice?'切换发票':inlineInvoice?.orderId===row.id?'收起发票':'发票'}}</el-button>
                </template>
                <el-button v-if="embedded" link type="primary" @click="originalInvoice=invoiceContextFor(row)">查看原发票</el-button>
                <template v-if="scopeOrder || embedded">
                  <el-button v-if="row.statementRequired || row.hasStatementRequiredOrders" link type="primary" @click="openInvoiceStatement(row)">查看对账单</el-button>
                  <span v-else class="payment-help">{{row.statementRequired===false?'无需对账单':'对账单待确认'}}</span>
                </template>
              </div>
              <el-button v-else-if="canWrite" link type="primary" @click="openPaymentRow(row)">价格与付款</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="projectPage" :page-size="20" :total="displayedProjectTotal" layout="total,prev,pager,next" @current-change="searchProjects(projectKeyword)" />
      </section>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="reloadPayment">重新加载付款情况</el-button></el-alert>
      </template>
      <div v-if="inlineInvoice" v-show="activeTab==='invoice'" ref="inlineInvoiceAnchor">
        <ProjectInvoiceDialog ref="inlineInvoiceForm" :key="inlineInvoice.orderId" inline
          :model-value="true" :context="inlineInvoice" :persistent-inline="hasFixedInvoice" :special="embedded"
          @update:model-value="closeInlineInvoice"
          @invoice-scope-loaded="setMergedOrders"
          @saved="emit('invoice-saved',$event)" />
      </div>
    </div>
    <DraggableFormDialog ref="managerPicker" v-model="managerPickerVisible" title="客户经理筛选" width="min(560px, calc(100vw - 32px))" top="10vh" append-to-body>
      <el-radio-group data-auto-draft="off" v-model="managerDraftScope" class="payment-manager-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" data-auto-draft="off" v-model="managerDraftIds" @options="cacheManagers" />
      <template #footer><el-button @click="cancelManagerPicker">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <template v-if="!embedded" #footer><el-button @click="beforeClose(()=>emit('update:modelValue',false))">关闭</el-button></template>
  </component>
  <ProjectInvoiceDialog v-if="originalInvoice" :model-value="true" :context="originalInvoice"
    readonly @update:model-value="originalInvoice=null" />
  <SpecialInvoiceStatement v-if="invoiceStatement" :model-value="true" settlement-scope="special" title="特殊结算"
    :client-context="invoiceStatement" @update:model-value="invoiceStatement=null" />
  <InvoiceRequestDialog v-if="requestVisible" :project-ids="requestProjectIds" :merged-settlement="requestMergedSettlement"
    :special-settlement="embedded" @close="requestVisible = false" @sent="projectTable?.clearSelection()" />
</template>
<script setup>
import {computed,defineAsyncComponent,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import { useManagerFilterDraft } from '@/composables/useManagerFilterDraft'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {customerFinanceSort,getCustomerFinancePage,getProjectInvoiceScope,getStatementCustomers} from '@/api/translationCustomerFinance'
import {invoiceStatusOptions as recordedInvoiceStatusOptions,invoiceStatusLabels} from '@/utils/documentRequirements'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {formatClientWithSubClient} from '@/utils/clientManagementWindow'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import CustomerDepartmentManagerSelect from './CustomerDepartmentManagerSelect.vue'
import TranslationOrderDetailPopover from './TranslationOrderDetailPopover.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
import ReadonlyField from './ReadonlyField.vue'
import StatementPeriodSelect from './StatementPeriodSelect.vue'
import {financeOrderLevel} from '@/utils/financeOrderLevel'
import {translationSettlementModeLabels} from '@/utils/settlementModes'
import {orderStatementMonth} from '@/utils/statementRequirementMonth'
import {paymentStatusLabel,paymentStatusFilterOptions,fullPaymentMismatchOption,paymentChangeEvent,connectPaymentSync} from '@/utils/paymentConfirmation'
import {connectInvoiceParties,invoicePartiesEvent,notifyInvoiceParties} from '@/api/invoiceParties'
const props=defineProps({modelValue:Boolean,scopeOrder:Object,initialProjectId:{type:String,default:''},lockProject:Boolean,canReviewInvoice:Boolean,
  embedded:Boolean,ledgerOnly:Boolean,invoiceClientId:[String,Number],invoiceClientName:String,initialMonth:String,periodNumber:Number,managerQuery:Object})
const emit=defineEmits(['update:modelValue','edit','invoice-saved','review-invoice','statement'])
const canWrite=hasPermission('projects:write')||hasPermission('finance:write')
const body=ref(),options=ref([]),loading=ref(false),searching=ref(false),error=ref('')
const dialogProps=computed(()=>props.embedded?{}:{modelValue:props.modelValue,class:'project-payment-dialog',
  width:'min(1100px, calc(100vw - 32px))',top:'5vh',appendToBody:true,destroyOnClose:true,
  closeOnClickModal:false,beforeClose})
const specialInvoiceWorkspace=ref(),originalInvoice=ref(null),invoiceStatement=ref(null)
const SpecialInvoiceStatement=defineAsyncComponent(()=>import('./CustomerStatementDialog.vue'))
function openInvoiceStatement(row){
  if(!props.embedded){emit('statement',row);return}
  const month=row.billingMonth||orderStatementMonth(row.orderNo)
  if(!row.clientId||!month){ElMessage.warning('请先确认客户及账单月份');return}
  invoiceStatement.value={id:row.clientId,name:row.clientShortName,manager:row.clientManager,
    month,period:row.settlementPeriodNumber??row.billingPeriod?.number}
}
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const activeTab=ref(props.ledgerOnly?'overview':'invoice'),projectPage=ref(1),showFilters=computed(()=>!props.lockProject)
const scopeMonth=computed(()=>props.scopeOrder && (props.scopeOrder.billingMonth || orderStatementMonth(props.scopeOrder.orderNo)))
const scopeBillingPeriod=computed(()=>{
  if(!scopeMonth.value)return '未登记'
  const period=props.scopeOrder?.settlementPeriodNumber??props.scopeOrder?.billingPeriod?.number
  return `${scopeMonth.value} · ${period ? `第 ${period} 期` : '未分账期'}`
})
const dialogTitle=computed(()=>{
  const title=props.ledgerOnly?'查账追账':'发票'
  if(!props.scopeOrder || mergedOrderNumbers.value.length)return title
  const level=financeOrderLevel(props.scopeOrder)
  return `${title} · ${props.scopeOrder.orderNo}${level ? `（${level}）` : ''}`
})
const projectSort=ref()
const InvoiceRequestDialog = defineAsyncComponent(() => import('./InvoiceRequestDialog.vue'))
const specialInvoiceManagerQuery=computed(()=>({
  only_mine:!props.scopeOrder && managerScope.value==='self',
  manager_ids:props.scopeOrder?.clientManagerId?[props.scopeOrder.clientManagerId]:
    !props.scopeOrder && managerScope.value==='name'?managerIds.value:undefined,
  fixed_manager_name:props.scopeOrder&&!props.scopeOrder.clientManagerId?props.scopeOrder.clientManager||'':undefined,
}))
const projectTable = ref()
const inlineInvoice=ref(null),inlineInvoiceForm=ref(null),inlineInvoiceAnchor=ref(null)
const mergedOrderNumbers=ref([]),mergedOrdersVisible=ref(false)
const mergedScopeInfo=ref(null)
const settlementGroupLabel=computed(()=>translationSettlementModeLabels[mergedScopeInfo.value?.settlementMode || props.scopeOrder?.paymentMethod]||translationSettlementModeLabels.monthly)
const headerClientName=computed(()=>{
  const row=props.scopeOrder || mergedScopeInfo.value
  return row ? formatClientWithSubClient({...row,subClientName:row.subClientShortName || row.subClientName},row.clientShortName||row.clientName) : ''
})
function setMergedOrders(scope,projectId){
  const anchor=props.scopeOrder?.rootId||props.scopeOrder?.id
    || (props.lockProject?props.initialProjectId:undefined)
  if(anchor!==projectId)return
  mergedScopeInfo.value=scope
  mergedOrderNumbers.value=scope.merged?scope.items.map(item=>item.orderNo):[]
  if(!mergedOrderNumbers.value.length)mergedOrdersVisible.value=false
}
const hasFixedInvoice=computed(()=>Boolean(props.scopeOrder || (props.lockProject && props.initialProjectId)))
function invoiceContextFor(row){
  return {projectId:row.rootId||row.id,orderId:row.id,order:row,level:financeOrderLevel(row)}
}
function openInitialInvoice(){
  if(props.scopeOrder)inlineInvoice.value=invoiceContextFor(props.scopeOrder)
  else if(props.lockProject&&props.initialProjectId){
    inlineInvoice.value={projectId:props.initialProjectId,orderId:props.initialProjectId}
  }
}
function closeInlineInvoice(){inlineInvoice.value=null}
function toggleInvoice(row){
  beforeClose(async ()=>{
    if(inlineInvoice.value?.orderId===row.id){closeInlineInvoice();return}
    inlineInvoice.value=invoiceContextFor(row)
    await nextTick()
    inlineInvoiceAnchor.value?.scrollIntoView({block:'nearest'})
  })
}
const selectedProjects = ref([])
const requestProjectIds = ref([])
const requestMergedSettlement = ref(false)
const openingRequest = ref(false)
let requestController
async function openInvoiceRequest(){
  if(openingRequest.value)return
  if(!props.scopeOrder){
    requestProjectIds.value=selectedProjects.value.map(row=>row.id)
    requestMergedSettlement.value=false
    requestVisible.value=true
    return
  }
  const order=props.scopeOrder
  const request=new AbortController()
  requestController=request
  openingRequest.value=true
  try{
    const scope=await getProjectInvoiceScope(order.rootId||order.id,{signal:request.signal})
    if(request.signal.aborted || !props.modelValue || activeTab.value!=='invoice' || props.scopeOrder!==order)return
    if(!scope.merged && order.rootId && order.rootId!==order.id){
      ElMessage.info('请从母订单发起开票需求')
      return
    }
    const projects=scope.items.filter(item=>item.invoiceRequired===true)
    if(!projects.length){ElMessage.info('当前结算范围内暂无需开票项目');return}
    const missing=projects.filter(item=>!item.hasInvoiceAmount)
    if(missing.length){ElMessage.warning(`请补录含税金额后再发起开票需求：${missing.map(item=>item.orderNo).join('、')}`);return}
    if(projects.length>100){ElMessage.warning('当前结算范围超过开票需求单次上限（100 个项目）');return}
    requestProjectIds.value=projects.map(item=>item.id)
    requestMergedSettlement.value=scope.merged===true
    requestVisible.value=true
  }catch(error){
    if(!request.signal.aborted)ElMessage.error(getLocalizedErrorMessage(error,'开票项目加载失败'))
  }finally{
    if(requestController===request)openingRequest.value=false
  }
}
const requestVisible = ref(false)
const canSelectInvoice = row => row.invoiceRequired === true && (props.embedded
  ? Object.keys(row.specialInvoiceTotals||{}).length>0
  : (!row.rootId || row.rootId === row.id) && row.billingCurrencies.incl_tax.size > 0)
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
    await api.put(`/translation-customer-finance/project/${projectId}/invoice/customer-sent`, {sent},
      {params:props.embedded?{special:true,order_id:row.id}:undefined})
    if(props.embedded)notifyInvoiceParties({kind:'special-settlement',clientId:row.clientId,projectId})
    window.dispatchEvent(new CustomEvent('translation-invoice-changed', {detail:{projectId}}))
  } catch (e) {
    ElMessage.error(getLocalizedErrorMessage(e, '更新发客户状态失败'))
  } finally {
    customerSentSaving.value = false
  }
}
const paymentFilters=reactive({months:[],period:undefined,client:'',status:'',invoiceStatus:'',invoiceRequired:''}),projectKeyword=ref(''),projectTotal=ref(0)
const statementCustomerMode = ref('')
const completeInvoiceScope = ref(false)
const locallyFiltered = computed(()=>activeTab.value==='invoice' && !!props.scopeOrder && completeInvoiceScope.value)
const displayedOptions = computed(()=>locallyFiltered.value && statementCustomerMode.value
  ? options.value.filter(row=>!!(row.statementRequired || row.hasStatementRequiredOrders)===(statementCustomerMode.value==='include'))
  : options.value)
const displayedProjectTotal = computed(()=>locallyFiltered.value?displayedOptions.value.length:projectTotal.value)
const invoiceClientIds = ref([])
const invoiceCustomerPickerVisible = ref(false)
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
    const result = await getStatementCustomers({keyword:keyword.trim() || undefined, required_only:false, include_sub_clients:true, limit:50}, {signal:controller.signal})
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
  if(locallyFiltered.value && !searching.value)return
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
const managerPicker=ref()
const managerScope=ref('self'),managerIds=ref([]),managerNames=ref({})
const { managerPickerVisible, managerDraftScope, managerDraftIds, resetManagerDraft, cancelManagerPicker, getManagerSelection } = useManagerFilterDraft(() => ({
  only_mine: managerScope.value === 'self', manager_ids: managerIds.value,
}))
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
function openManagerPicker(){managerPickerVisible.value=true}
async function applyManager(){
  const { scope, ids } = getManagerSelection()
  managerScope.value=scope
  managerIds.value=ids
  resetManagerDraft()
  managerPickerVisible.value=false
  await applyPaymentFilters()
}
const defaultManagerScope = () => props.scopeOrder || props.invoiceClientId || props.embedded ? 'all' : 'self'
watch(invoiceCustomerPickerVisible, visible => {
  if (visible) return
  invoiceCustomerSearch?.abort()

})
function initPaymentFilters(){
  invoiceCustomerPickerVisible.value=false
  clearInvoiceCustomerFilters()
  Object.assign(paymentFilters,{months:props.initialMonth?[props.initialMonth]:[],period:props.periodNumber,client:'',status:'',invoiceStatus:'',invoiceRequired:''})
  projectKeyword.value=''
  managerIds.value=[]
  managerScope.value=defaultManagerScope()
  resetManagerDraft()
}
function paymentQuery(keyword){
  const order=props.scopeOrder
  const invoice=activeTab.value==='invoice'
  const scoped=Boolean(order?.clientId && scopeMonth.value && !invoice)
  const assignedManagerId=scoped?order.clientManagerId:undefined
  const requestedManagerIds=!order&&managerScope.value==='name'?managerIds.value:undefined
  return {
    sort:projectSort.value,
    keyword:keyword?.trim()||undefined,
    billing_month:scoped?scopeMonth.value:undefined,
    billing_months:!order&&!mismatchView.value&&paymentFilters.months?.length?paymentFilters.months:undefined,
    client:!order&&!mismatchView.value?paymentFilters.client.trim()||undefined:undefined,
    payment_status:invoice||(!order&&mismatchView.value)?undefined:paymentFilters.status||undefined,
    manager_ids:assignedManagerId?[assignedManagerId]:requestedManagerIds,
    fixed_manager_name:scoped&&!assignedManagerId?order.clientManager||'':undefined,
    only_mine:!order&&managerScope.value==='self',
    include_payment_status:!props.embedded,
    include_invoice_status:invoice,
    settlement_scope:invoice?(props.embedded?'special':'standard'):undefined,
    special_invoice_tracking:props.embedded||undefined,
    period_number:invoice&&!order&&paymentFilters.months?.length===1?paymentFilters.period:undefined,
    invoice_status:invoice?paymentFilters.invoiceStatus||undefined:undefined,
    invoice_required:invoice?paymentFilters.invoiceRequired||undefined:undefined,
    client_ids:props.invoiceClientId?[props.invoiceClientId]:scoped?[order.clientId]:invoice&&!order&&invoiceClientIds.value.length?invoiceClientIds.value:undefined,
    sub_client_id:scoped?order.subClientId:undefined,
    statement_customers:invoice&&!order?statementCustomerMode.value||undefined:undefined,
    statement_required:invoice&&order&&!completeInvoiceScope.value&&statementCustomerMode.value?statementCustomerMode.value==='include':undefined,
    payment_amount_mismatch:!order&&mismatchView.value,
    exclude_full:collectionDefaultView.value,
    settlement_project_id:invoice&&order?(order.rootId||order.id):undefined,
    payment_project_id:order&&!invoice&&!scoped?(order.rootId||order.id):props.lockProject?props.initialProjectId||undefined:undefined,
    skip:(projectPage.value-1)*20,
    limit:20,
    ...props.managerQuery,
  }
}
function queueClientSearch(value){clearTimeout(filterTimer);controller?.abort();searchSequence++;if(!value.trim())void applyPaymentFilters();else filterTimer=setTimeout(applyPaymentFilters,400)}
function queueProjectSearch(keyword=''){projectPage.value=1;projectKeyword.value=keyword;clearTimeout(projectTimer);controller?.abort();searchSequence++;if(!keyword.trim())void searchProjects('');else projectTimer=setTimeout(()=>searchProjects(keyword),400)}
async function applyPaymentFilters(){clearTimeout(filterTimer);clearTimeout(projectTimer);projectPage.value=1;projectKeyword.value='';await searchProjects('')}
function changeMonths(){paymentFilters.period=undefined;void applyPaymentFilters()}
async function resetPaymentFilters(){initPaymentFilters();await applyPaymentFilters()}
async function searchProjects(keyword=''){clearTimeout(projectTimer);const seq=++searchSequence;controller?.abort();if(activeTab.value==='special_invoice'){searching.value=false;return}controller=new AbortController();searching.value=true;error.value='';
  const query = paymentQuery(keyword)
  const scope = JSON.stringify({...query, skip:undefined, sort:undefined})
  if (scope !== previousSelectionScope) {
    projectTable.value?.clearSelection()
    selectedProjects.value = []
    previousSelectionScope = scope
  }
  try{const data=await getCustomerFinancePage(query,{signal:controller.signal});if(seq===searchSequence){if(activeTab.value==='invoice'&&data.invoiceFilterApplied!==true){options.value=[];projectTotal.value=0;error.value='后端发票功能尚未更新，请更新后端服务后重试';return}if(mismatchView.value&&(data.paymentAmountMismatchFilterApplied!==true||(data.items||[]).some(item=>item.paymentStatus!=='full'||item.paymentAmountMismatch!==true))){options.value=[];projectTotal.value=0;error.value='后端未正确执行已付全款金额核对，请更新后端服务后重试';return}
    const projects=data.items||[]
    const order=props.scopeOrder
    const selectedChild=activeTab.value==='invoice'&&order?.rootId&&order.id!==order.rootId&&!data.mergedInvoiceScope
    function findOrder(nodes,id){
      for(const node of nodes){
        if(node.id===id)return node
        const match=findOrder(node.children||[],id)
        if(match)return match
      }
    }
    const visibleProjects=selectedChild?[findOrder(projects,order.id)].filter(Boolean):projects
    options.value = visibleProjects.map(project => ({
      ...project,
      hasChildren: Boolean(project.hasChildren || project.children?.length),
      billingCurrencies: props.embedded ? {
        excl_tax:new Set(Object.keys(project.specialExclTotals||{})),
        incl_tax:new Set(Object.keys(project.specialInvoiceTotals||{})),
      } : collectBillingCurrencies(project),
      children: undefined,
    }))
    if(activeTab.value==='invoice'&&props.lockProject&&inlineInvoice.value&&!inlineInvoice.value.order){
      const current=options.value.find(row=>row.id===inlineInvoice.value.orderId)
      if(current)inlineInvoice.value=invoiceContextFor(current)
    }
    projectTotal.value=selectedChild?visibleProjects.length:data.total||0
    if(activeTab.value==='invoice'&&order){
      completeInvoiceScope.value=query.statement_required===undefined&&projectTotal.value===visibleProjects.length
      if(!completeInvoiceScope.value&&query.statement_required===undefined&&statementCustomerMode.value){
        await searchProjects(keyword)
      }
    }
  }}catch(e){if(seq===searchSequence&&e.code!=='ERR_CANCELED'){options.value=[];projectTotal.value=0;error.value=getLocalizedErrorMessage(e,'项目搜索失败')}}finally{if(seq===searchSequence)searching.value=false}}
async function onPaymentTabChanged(){projectPage.value=1;await searchProjects(projectKeyword.value)}
function sortProjects(change){
  projectSort.value=customerFinanceSort(change)
  projectPage.value=1
  void searchProjects(projectKeyword.value)
}
function openPaymentRow(row){beforeClose(()=>{emit('edit',row);emit('update:modelValue',false)})}
function reloadPayment(){void searchProjects(projectKeyword.value)}
function confirmClose(){
  return (specialInvoiceWorkspace.value || inlineInvoiceForm.value)?.confirmClose() ?? true
}
function beforeTabLeave(){return confirmClose()}
async function beforeClose(done){if(await confirmClose())done()}
defineExpose({confirmClose})
function onExternalPayment(event){if(props.modelValue&&event.detail?.projectId)void searchProjects(projectKeyword.value)}
function onSpecialInvoiceChange(event){
  if(props.modelValue && (event.detail?.kind==='sub-client-finance'||props.embedded&&event.detail?.kind==='special-settlement')){
    void searchProjects(projectKeyword.value)
  }
}
connectPaymentSync();window.addEventListener(paymentChangeEvent,onExternalPayment);window.addEventListener('translation-invoice-changed',onExternalPayment)
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,onSpecialInvoiceChange)
if(props.embedded){
  watch(()=>[props.invoiceClientId,props.initialMonth,props.periodNumber],()=>{initPaymentFilters();void applyPaymentFilters()})
  watch(()=>props.managerQuery,()=>{void applyPaymentFilters()},{deep:true})
}
watch(()=>props.modelValue,visible=>{
  searchSequence++;controller?.abort();clearTimeout(filterTimer);clearTimeout(projectTimer);clearFieldSearch();error.value=''
  mergedOrderNumbers.value=[];mergedOrdersVisible.value=false;mergedScopeInfo.value=null
  if(!visible){requestController?.abort();managerPickerVisible.value=false;initPaymentFilters();closeInlineInvoice();return}
  activeTab.value=props.ledgerOnly?'overview':'invoice';projectPage.value=1;projectSort.value=undefined;completeInvoiceScope.value=false
  initPaymentFilters();options.value=[]
  if(!props.ledgerOnly)openInitialInvoice()
  void searchProjects()
},{immediate:true})
onBeforeUnmount(()=>{requestController?.abort();invoiceCustomerSearch?.abort();clearTimeout(filterTimer);clearTimeout(projectTimer);window.removeEventListener(paymentChangeEvent,onExternalPayment);window.removeEventListener('translation-invoice-changed',onExternalPayment);window.removeEventListener(invoicePartiesEvent,onSpecialInvoiceChange);searchSequence++;controller?.abort()})
</script>
<style scoped>
.payment-merged-order-numbers{margin:0;padding-inline-start:20px;max-height:240px;overflow:auto;line-height:1.75;user-select:text}
.invoice-request-toolbar { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.invoice-row-actions{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}.invoice-row-actions .el-button{margin-left:0;padding-inline:0}
:global(.project-payment-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.project-payment-dialog>.el-dialog__header),:global(.project-payment-dialog>.el-dialog__footer){flex:none}:global(.project-payment-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-summary{margin-bottom:14px}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
.payment-overview-search{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}.payment-overview .el-pagination{margin-top:10px}.payment-filter-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.payment-filter-bar :deep(.el-form-item){margin-right:0;margin-bottom:8px}.payment-filter-summary{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 8px}.payment-manager-label{font-size:14px;font-weight:400;color:var(--el-text-color-secondary)}.payment-manager-label .el-button{max-width:300px;white-space:normal;height:auto;min-height:30px}.payment-manager-choices{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
</style>
