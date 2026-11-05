<template>
  <el-card class="customer-finance" :class="{'finance-editor-only':editorOnly,'statement-client-finance':statementClientView}" shadow="never">
    <template #header><div v-if="!statementClientView" class="finance-heading"><strong>笔译</strong><div class="finance-heading-actions"><el-button @click="quotationVisible=true">报价单</el-button><el-button @click="statementContext=null;statementVisible=true">对账单</el-button><el-button @click="openPaymentManagement">付款情况</el-button><TableColumnSettings v-model="selectedKeys" settings-key="translation-customer-finance" :columns="columns" @reset="resetColumns" /></div></div><strong v-else>客户项目</strong></template>
    <ProjectPaymentDialog v-model="paymentVisible" :projects="rows" :query="financeParams()" :initial-project-id="paymentContextId" @saved="onPaymentSaved" />
    <ProjectPaymentDialog v-model="linkedPaymentVisible" :initial-project-id="editor.rootId" :confirmation-draft="paymentConfirmationDirty?editor.paymentConfirmation:null" lock-project @saved="onLinkedPaymentSaved" />
    <CustomerQuotationDialog v-model="quotationVisible" :projects="rows" :query="financeParams()" />
    <CustomerStatementDialog v-model="statementVisible" :manager-filter-enabled="!statementContext" :client-context="statementContext" @choose-manager="managerPickerVisible=true" :manager-label="managerLabel" :projects="rows" :query="financeParams()" :billing-month="filters.month" />
    <div v-if="statementClientView" class="finance-preview-actions"><el-button :loading="previewLoading" :disabled="loading" @click="previewProjects">对账单预览</el-button><span>已选 {{statementSelected.length}} 项；未勾选时使用全部筛选结果</span></div>
    <AppForm v-if="statementClientView" :inline="true" :model="filters" @submit.prevent="search"><el-form-item label="项目状态"><el-select v-model="filters.projectStatus" multiple collapse-tags collapse-tags-tooltip clearable placeholder="全部状态" style="width:260px;max-width:100%" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item></AppForm>
    <AppForm v-if="!statementClientView" :inline="true" :disabled="editorLoading" :model="filters" class="finance-search" @submit.prevent="search">
      <el-form-item label="关键词"><el-input class="finance-keyword" v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="账单月份"><el-date-picker class="finance-month" v-model="filters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" title="按订单号年月筛选，如 TP-261029-010 对应 2026-10" clearable @change="search" /></el-form-item>
      <el-form-item label="客户经理"><el-button :class="{'manager-filter-active':managerScope!=='all'}" :title="managerLabel" @click="managerPickerVisible=true">{{managerLabel}}</el-button></el-form-item>
      <el-form-item label="订单客户"><el-select v-model="filters.clientOrderCount" style="width:150px" placeholder="全部客户" aria-label="订单客户" @change="search"><el-option label="全部客户" value="" /><el-option label="单订单客户" value="single" /><el-option label="多订单客户" value="multiple" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="resetSearch">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced"><el-form-item label="项目状态"><el-select v-model="filters.projectStatus" multiple collapse-tags collapse-tags-tooltip clearable placeholder="全部状态" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item><el-form-item label="客户"><el-input v-model="filters.client" clearable placeholder="客户全称或简称" @input="queueFilterSearch" @keyup.enter="search" /></el-form-item><el-form-item label="字数统计"><el-checkbox v-model="filters.missingWordCount" @change="search">我司、客户统计均未填写</el-checkbox></el-form-item><el-form-item label="单价"><el-checkbox v-model="filters.missingUnitPrice" @change="search">未填写单价（固定收费除外）</el-checkbox></el-form-item><el-form-item label="总价"><el-select v-model="filters.missingTotal" clearable placeholder="全部" @change="search"><el-option label="不含税总价为空" value="excl" /><el-option label="含税总价为空" value="incl" /><el-option label="两种总价均为空" value="both" /><el-option label="任一种总价为空" value="either" /><el-option label="固定收费金额为空" value="fixed" /></el-select></el-form-item><p class="finance-help">按母订单汇总结果筛选；零值视为已填写，预统计不视为我司或客户统计。</p></AdvancedFilterPopover></el-form-item>
    </AppForm>
    <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" append-to-body :class="['finance-manager-dialog',{'has-manager-select':managerDraftScope==='name'}]" width="min(560px, calc(100vw - 32px))" top="10vh" :close-on-click-modal="false">
      <el-radio-group v-model="managerDraftScope" class="manager-filter-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds" @options="cacheManagers" />
      <p class="finance-help">可多选客户部成员，点击“确定”后更新订单列表及客户金额小计。</p>
      <template #footer><el-button @click="managerPickerVisible=false">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <p v-if="!statementClientView" class="finance-help">按语种方向维护多条单价，默认优先采用客户统计的数量和单位，客户未填时采用我司统计；也可手动选择我司统计，两者均未填时提示补录。母订单单价复制至匹配语种的下级，单独改价的下级保留；按数量时父级汇总下级金额，各币种单独小计；固定收费直接采用登记的一口价。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p v-if="canWrite&&!statementClientView" class="finance-help">字数统计之后的字段可直接填写，修改后自动保存，与编辑收费窗口同步。</p>
    <el-alert v-if="tableError" type="error" :closable="false" :title="tableError"><el-button link type="primary" @click="tableEditing.flush()">重试保存</el-button><el-button link type="primary" @click="discardTableDrafts">放弃未保存内容并重新加载</el-button></el-alert>
    <div v-if="filters.clientOrderCount==='multiple'" class="finance-client-group-toolbar"><span>按当前筛选结果统计：{{total}} 个多订单客户，共 {{groupOrderTotal}} 个母订单；每页 10 个客户，同一客户不拆页。</span><el-button link @click="collapseClientGroups(false)">全部展开</el-button><el-button link @click="collapseClientGroups(true)">全部收起</el-button></div>
    <AppForm :model="tableEditing.states" label-position="top" class="finance-sheet-form">
    <el-table v-loading="loading||editorLoading" ref="statementTableRef" @selection-change="statementSelected=$event;projectPreview=null" class="finance-project-table" :data="tableRows" :span-method="clientGroupSpan" :row-class-name="({row})=>row._clientGroup?'finance-client-group-row':''" row-key="id" border default-expand-all scrollbar-always-on empty-text="暂无笔译项目">
      <el-table-column v-if="statementClientView" type="selection" reserve-selection width="44" />
      <el-table-column type="index" label="序号" :fixed="fixedColumns.length?'left':false" width="60" :index="index => (page-1)*10+index+1"><template #default="{row,$index}"><button v-if="row._clientGroup" type="button" class="finance-client-group-toggle" :aria-expanded="!collapsedClients.includes(row.groupKey)" @click="toggleClientGroup(row.groupKey)">{{collapsedClients.includes(row.groupKey)?'▶':'▼'}} {{row.clientName}} <small>{{row.orderCount}} 个母订单</small></button><span v-else>{{filters.clientOrderCount==='multiple'?row._groupOrderIndex:((page-1)*10+$index+1)}}</span></template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :width="column.width" :fixed="fixedColumns.includes(column.key)?'left':false" :prop="column.key">
        <template #header><div class="finance-column-heading"><span>{{column.label}}</span><button v-if="['orderNo','projectName'].includes(column.key)" type="button" class="finance-pin-toggle" :aria-label="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :title="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :aria-pressed="fixedColumns.includes(column.key)" @click.stop="toggleFixedColumn(column.key)">{{fixedColumns.includes(column.key)?'◆':'◇'}}</button></div></template>
        <template #default="{row}"><span v-if="row._clientGroup" /><CustomerStatementRequiredToggle v-else-if="column.key==='statementRequired'" :row="row" :prepare="tableEditing.flush" @saved="emit('saved')" /><CustomerFinanceTableCell v-else-if="tableFields.includes(column.key)&&(canWrite||['totalPrice','totalInclTax','explanation'].includes(column.key))" :field="column.key" :row="row" :state="tableEditing.stateFor(row)" :prepare="tableEditing.flush" :readonly="!canWrite" @edit-order="openAggregateOrder(row.rootId,$event)" @saved="onTablePriceSaved" @commit="tableEditing.commit(row,$event)" /><TranslationOrderDetailPopover v-else-if="column.key==='orderNo'" :order="row" /><WordCountMatrixPopover v-else-if="column.key==='wordCount'" :model-value="row.wordCountMatrix||{}" :entity-type="row.id===row.rootId?'project':'suborder'" :entity-id="row.id" title="项目字数统计" read-only>
          <template #reference><el-button link type="primary" :title="getWordCountSummary(row).title"><span>{{getWordCountSummary(row).primary}}</span><el-tag v-if="getWordCountSummary(row).extraCount" size="small" type="info" class="finance-word-count-extra">+{{getWordCountSummary(row).extraCount}}</el-tag><el-tag v-if="getWordCountSummary(row).sourceLabel" size="small" type="info">子订单累计</el-tag></el-button></template>
        </WordCountMatrixPopover><div v-else-if="column.key==='unitPrice'"><div v-for="(price,index) in row.prices||[]" :key="price.id||index" class="finance-language-price"><strong>{{price.languagePair||row.languagePair||'待选择语种方向'}}</strong><span class="finance-cell">{{taxPriceSummary(price.taxPrices,price.currency,price.unitSize+'计价单位',false)||'税口径未填写'}}</span><CustomerPriceFields v-if="!price.taxPrices" readonly :amount="price.amount" :currency="price.currency" :unit-size="price.unitSize" :metric-type="price.metric" /></div><span v-if="row.pricingMode==='fixed'">固定收费（不涉及单价）</span><span v-else-if="!row.prices?.length">未设置单价</span></div><span v-else class="finance-cell">{{ cell(row,column.key) }}</span></template>
      </el-table-column>
      <el-table-column v-if="!statementClientView" label="操作" :width="operationsCollapsed?44:220" fixed="right">
        <template #header><div class="finance-operations-header"><span v-if="!operationsCollapsed">操作</span><el-button link type="primary" :aria-label="operationsCollapsed?'展开操作栏':'收起操作栏'" :title="operationsCollapsed?'展开操作栏':'向右收起操作栏'" :aria-expanded="!operationsCollapsed" @click.stop="operationsCollapsed=!operationsCollapsed"><el-icon><DArrowLeft v-if="operationsCollapsed" /><DArrowRight v-else /></el-icon></el-button></div></template>
        <template #default="{row}"><template v-if="!operationsCollapsed"><el-button v-if="canWrite" link type="primary" :disabled="editorLoading" @click="openEditor(row)">编辑收费</el-button><el-button link type="primary" @click="historyOrder=row;historyVisible=true">修改记录</el-button><el-button link type="primary" :disabled="!row.clientId" @click="openRowStatement(row)">对账单</el-button></template></template>
      </el-table-column>
    </el-table>

    </AppForm>
    <el-pagination :disabled="editorLoading" v-model:current-page="page" :page-size="10" :total="total" layout="slot, prev, pager, next, jumper" @current-change="load"><span>{{filters.clientOrderCount==='multiple'?`共 ${total} 个客户（${groupOrderTotal} 个母订单）`:`共 ${total} 条`}}</span></el-pagination>
    <section v-if="statementClientView&&projectPreview" class="finance-project-preview"><h3>对账单预览（尚未生成）</h3><p>客户编号：{{projectPreview.client_code||'—'}}（仅系统可见）</p><CustomerStatementPaper :statement="projectPreview" /></section>
    <section v-if="!statementClientView" class="client-subtotals"><h4>客户金额小计 <small>当前筛选条件下的全部匹配母订单；不重复累加下级订单</small></h4><el-table :data="subtotals" border row-key="clientId" empty-text="暂无客户金额"><el-table-column prop="clientName" label="客户" min-width="180" /><el-table-column prop="projectCount" label="母订单数" width="110" /><el-table-column label="不含税总价小计" min-width="180"><template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsExclTax)}}</span></template></el-table-column><el-table-column label="含税总价小计" min-width="180"><template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsInclTax)}}</span></template></el-table-column><el-table-column label="统计情况" min-width="180"><template #default="{row}">{{row.incomplete?'部分订单缺少数量或单价，当前为已计算金额小计':'完整'}}</template></el-table-column></el-table></section>
    <DraggableFormDialog v-model="editorVisible" class="customer-finance-dialog" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="closeEditor">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`客户财务 · ${editor.orderNo || ''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editorBody" v-loading="saving">
        <CustomerFinanceModuleTabs v-model="financeModule" module="translation" :client-id="editor.clientId"><template #translation>
        <CustomerFinanceAggregateSummary v-if="editor.priceAggregate" :order="editor" :can-edit="canWrite" @edit-order="openAggregateOrder(editor.rootId,$event)" @payment="openLinkedPayment" />
        <AppForm v-else ref="formRef" :model="editor" label-position="top" :disabled="saving" class="finance-pricing-form">
          <PaymentConfirmationFields v-model="editor.paymentConfirmation" :project-id="editor.rootId" prefix="paymentConfirmation"><template #actions><el-button :disabled="!editor.rootId||saving" @click="openLinkedPayment">打开付款情况</el-button></template></PaymentConfirmationFields>
          <p v-if="!editor.rootId" class="finance-help">保存项目后可打开完整付款情况。</p>
          <el-form-item label="项目名称"><ReadonlyField :model-value="editor.sourceFileName || editor.projectName || '-'" source="auto" /></el-form-item>
          <div class="finance-pricing-config">
            <div class="finance-config-grid">
              <el-form-item label="计价模式"><el-radio-group v-model="editor.pricingMode" @change="changePricingMode"><el-radio-button value="metric">按数量</el-radio-button><el-radio-button value="fixed">固定收费</el-radio-button></el-radio-group></el-form-item>
              <el-form-item label="账单月份"><ReadonlyField :model-value="editor.billingMonth||'保存项目后自动生成'" source="auto" /><small>按订单号所属月份生成；跨月调配请在对账单管理中处理。</small></el-form-item>
            </div>
            <el-form-item v-if="editor.pricingMode!=='fixed'" label="客户参考价" class="finance-reference-item"><div class="finance-reference-content"><el-button :disabled="!editor.clientId" @click="adoptReference">采用最新客户参考价</el-button><span>{{referencePrices.length?'按同客户、同语种、同单位、同币种和计价数量选择，保存后生效':'该客户暂无匹配的语种参考价，可在下方直接填写单价'}}</span></div></el-form-item>
          </div>
          <p v-if="localTarget" class="finance-help">本次财务填写随项目表单一起保存。</p>
          <CustomerTranslationPriceEditor v-if="editor.pricingMode!=='fixed'" v-model="editor.prices" :matrix="editor.wordCountMatrix" :disabled="saving" />
          <p v-if="editor.pricingMode!=='fixed'" class="finance-help finance-calculation-hint">有下级订单时按下级汇总；缺少数量时可先保存单价，金额显示待补录。</p>
          <section class="finance-settlement-section">
            <h4>{{editor.pricingMode==='fixed'?'固定收费':'金额与说明'}}</h4>
            <div class="finance-settlement-grid" :class="{'finance-settlement-grid--fixed':editor.pricingMode==='fixed'}">
              <el-form-item v-if="editor.pricingMode==='fixed'" label="货币"><el-select v-model="editor.currency"><el-option v-for="currency in ['CNY','USD','HKD','EUR','GBP','JPY']" :key="currency" :value="currency" /></el-select></el-form-item>
              <el-form-item :label="editor.pricingMode==='fixed'?'不含税固定收费':'不含税总价'" prop="adjustedTotal" :rules="[{validator:(_rule,_value,callback)=>callback(editor.pricingMode==='fixed'&&editor.adjustedTotal==null&&editor.adjustedTotalInclTax==null?new Error('请填写不含税或含税固定收费'):undefined),trigger:'change'}]"><div class="finance-total-line"><ReadonlyField v-if="editor.pricingMode!=='fixed'" :model-value="calculatedTotal('excl')" source="auto" /><el-input-number v-model="editor.adjustedTotal" :disabled="editor.pricingMode!=='fixed' && new Set((editor.prices||[]).map(row=>row.currency)).size>1" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入不含税固定收费':'调整金额（选填）'" /></div></el-form-item>
              <el-form-item :label="editor.pricingMode==='fixed'?'含税固定收费':'含税总价'"><div class="finance-total-line"><ReadonlyField v-if="editor.pricingMode!=='fixed'" :model-value="calculatedTotal('incl')" source="auto" /><el-input-number v-model="editor.adjustedTotalInclTax" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入含税固定收费':'调整金额（选填）'" /></div></el-form-item>
            </div>
            <el-form-item label="内部说明"><el-input v-model="editor.explanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item><el-form-item v-if="!localTarget" label="客户说明"><el-input v-model="editor.customerExplanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item>
          </section>
          <div v-if="!localTarget&&editor.pricingMode!=='fixed'" class="finance-sync-actions">
            <el-form-item v-if="!localTarget&&editor.pricingMode!=='fixed'&&canWriteClients&&editor.clientId" label="同步客户参考价"><el-button :disabled="saving||syncPreviewPending" @click="save(true)">保存并同步单价至客户信息…</el-button></el-form-item>
            <el-form-item v-if="!localTarget&&editor.pricingMode!=='fixed'" label="同步同月订单"><SyncSameMonthPrices v-if="editorVisible" :project-id="editor.rootId" :order-id="editor.id" :client-id="editor.clientId" :version="treeVersion" :month="editor.billingMonth" :disabled="saving||editorDirty||!originalPrices.length" :prepare="prepareEditorSync" @synced="onSameMonthSynced" /></el-form-item>
          </div>
        </AppForm>

        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button :disabled="saving" @click="closeEditor()">取消</el-button><el-button v-if="financeModule==='translation'&&!editor.priceAggregate" type="primary" :loading="saving" @click="save()">保存</el-button></template>
    </DraggableFormDialog>
    <CustomerReferencePriceDialog v-if="editorVisible" ref="referencePickerRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" :matrix="editor.wordCountMatrix" :language-pair="editor.languagePair" :refresh-project="rebaseEditorAfterLibrary" />
    <CustomerRateSyncPreview v-if="editorVisible" ref="rateSyncPreviewRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" :matrix="editor.wordCountMatrix" :refresh-project="rebaseEditorAfterLibrary" />
    <DraggableFormDialog v-model="historyVisible" append-to-body class="customer-finance-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" :title="`财务修改记录 · ${historyOrder?.orderNo||''}`"><TranslationFinanceHistory v-if="historyVisible&&historyOrder" :project-id="historyOrder.rootId" :order-id="historyOrder.id" /><template #footer><el-button @click="historyVisible=false">关闭</el-button></template></DraggableFormDialog>
  </el-card>
</template>

<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import CustomerStatementPaper from '@/components/common/CustomerStatementPaper.vue'
import {previewStatementProjects} from '@/api/customerStatements'
import {calculateTaxOrderPriceTree} from '@/utils/translationQuantityBasis'
import CustomerFinanceModuleTabs from '@/components/common/CustomerFinanceModuleTabs.vue'
import ProjectPaymentDialog from '@/components/common/ProjectPaymentDialog.vue'
import TranslationOrderDetailPopover from '@/components/common/TranslationOrderDetailPopover.vue'
import CustomerFinanceTableCell from '@/components/common/CustomerFinanceTableCell.vue'
import {useFinanceTableEditing} from '@/composables/useFinanceTableEditing'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { getWordCountMatrixListSummary } from '@/utils/wordCountMatrix'
import PaymentConfirmationFields from '@/components/common/PaymentConfirmationFields.vue'
import {paymentConfirmationForm,paymentConfirmationPayload,paymentChangeEvent,notifyPaymentChanged} from '@/utils/paymentConfirmation'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import CustomerStatementDialog from '@/components/common/CustomerStatementDialog.vue'
import {taxPriceForm,taxPriceSummary} from '@/utils/taxPrices'
import { computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
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
import CustomerPriceFields from './components/CustomerPriceFields.vue'
import CustomerTranslationPriceEditor from '@/components/common/CustomerTranslationPriceEditor.vue'
import TranslationFinanceHistory from '@/components/common/TranslationFinanceHistory.vue'
import {orderStatementMonth} from '@/utils/statementRequirementMonth'
import CustomerFinanceAggregateSummary from '@/components/common/CustomerFinanceAggregateSummary.vue'
import CustomerStatementRequiredToggle from '@/components/common/CustomerStatementRequiredToggle.vue'
import CustomerReferencePriceDialog from '@/components/common/CustomerReferencePriceDialog.vue'
import {priceMatch,expectedOrderPrices,replaceMatchedReference} from '@/utils/customerRateMatching'
import SyncSameMonthPrices from '@/components/common/SyncSameMonthPrices.vue'
import {calculateOrderPriceTree,resolveRateQuantity} from '@/utils/translationQuantityBasis'
import {newCustomerRate,ratePayload,referenceDraft,defaultRateMetric} from '@/utils/customerTranslationRates'

const columns = [
  {key:'orderNo',label:'订单号',width:124},{key:'projectName',label:'项目名称',width:240},
  {key:'clientShortName',label:'客户简称',width:105},{key:'projectStatus',label:'项目状态',width:90},
  {key:'languagePair',label:'翻译方向',width:78},{key:'wordCount',label:'字数统计',width:96},
  {key:'pricingMode',label:'计价模式',width:72},{key:'billingMonth',label:'账单月份',width:96},{key:'unitPrice',label:'单价',width:120},{key:'totalPrice',label:'不含税总价',width:120},{key:'totalInclTax',label:'含税总价',width:120},
  {key:'statementRequired',label:'对账单',width:75},{key:'explanation',label:'说明',width:300},
]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('translation-customer-finance',columns,columns.map(item=>item.key),{legacyDefaultKeys:columns.filter(item=>item.key!=='statementRequired').map(item=>item.key)})
const tableFields=['pricingMode','billingMonth','unitPrice','totalPrice','totalInclTax','explanation']
const visibleColumns=computed(()=>columns.filter(item=>props.statementClientView?!['languagePair','wordCount','pricingMode','billingMonth','unitPrice'].includes(item.key):isVisible(item.key)))
const fixedStorageKey=`finance-fixed-columns:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const fixedColumns=ref((()=>{try{return JSON.parse(localStorage.getItem(fixedStorageKey)||'[]').filter(key=>['orderNo','projectName'].includes(key))}catch{return []}})())
function toggleFixedColumn(key){fixedColumns.value=fixedColumns.value.includes(key)?fixedColumns.value.filter(value=>value!==key):[...fixedColumns.value,key];localStorage.setItem(fixedStorageKey,JSON.stringify(fixedColumns.value))}

const statuses=getProjectStatusOptions('translation'),canWrite=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const emit=defineEmits(['saved'])
const props=defineProps({clientId:{type:[String,Number],default:''},clientIds:{type:Array,default:()=>[]},statementPreview:Function,editorOnly:Boolean,clientScope:Boolean,statementClientView:Boolean,previewMode:String,previewMonths:Array,initialMonth:String,managerQuery:{type:Object,default:()=>({})}})
const statementTableRef=ref(),statementSelected=ref([]),projectPreview=ref(null),previewLoading=ref(false)
async function statementSelection(){
  if(!await tableEditing.flush())throw new Error('请先处理未保存的内容')
  if(statementSelected.value.length)return statementSelected.value.map(row=>row.id)
  const ids=new Set()
  const months=props.previewMonths?.length?props.previewMonths:[filters.month]
  for(const month of months){let skip=0;while(true){const data=await getCustomerFinancePage({...financeParams(),billing_month:month||undefined,skip,limit:100});for(const row of data.items||[])ids.add(row.id);skip+=100;if(skip>=data.total||!data.items?.length)break}}
  return [...ids]
}
async function previewProjects(){
  previewLoading.value=true
  try{const order_ids=await statementSelection();projectPreview.value=props.statementPreview?await props.statementPreview(order_ids):await previewStatementProjects({client_id:props.clientId,month:filters.month,months:props.previewMonths,mode:props.previewMode||'children',order_ids})}
  catch(e){ElMessage.error(getLocalizedErrorMessage(e,'对账单预览失败'))}
  finally{previewLoading.value=false}
}
const financeModule=ref('translation')
const operationsCollapsed=ref(false)
const financePaymentSource=`finance-editor-${Math.random().toString(36).slice(2)}`
const paymentContextId=ref('')
const paymentVisible=ref(false),quotationVisible=ref(false),statementVisible=ref(false),statementContext=ref(null)
function openRowStatement(row){const month=orderStatementMonth(row.orderNo)||row.billingMonth;if(!row.clientId||!month){ElMessage.warning('请先确认客户及账单月份');return}statementContext.value={id:row.clientId,name:row.clientShortName||row.clientName||'客户',month,manager:row.clientManager};statementVisible.value=true}
const filters=reactive({clientOrderCount:'',keyword:'',projectStatus:[],client:'',month:props.initialMonth||'',manager:'',missingWordCount:false,missingUnitPrice:false,missingTotal:''}),rows=ref([]),subtotals=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),advancedVisible=ref(false)
const tableEditing=useFinanceTableEditing(async(result)=>{notifyPaymentChanged(result.item.id,result.item.paymentConfirmation,financePaymentSource);emit('saved');await load({fromTable:true})})
watch(rows,values=>tableEditing.syncRows(values),{flush:'sync',deep:true})
const clientGroups=ref([]),groupOrderTotal=ref(0),collapsedClients=ref([])
const tableRows=computed(()=>{
  if(filters.clientOrderCount!=='multiple')return rows.value
  return clientGroups.value.map(group=>{let index=0;const number=node=>({...node,_groupOrderIndex:++index,children:(node.children||[]).map(number)});return {id:'client-group:'+group.key,_clientGroup:true,groupKey:group.key,clientName:group.name,orderCount:group.count,children:collapsedClients.value.includes(group.key)?[]:rows.value.filter(row=>row.clientGroupKey===group.key).map(number)}})
})
function clientGroupSpan({row,columnIndex}){if(row._clientGroup)return columnIndex===0?[1,visibleColumns.value.length+2]:[0,0]}
async function toggleClientGroup(key){if(!await tableEditing.flush())return;collapsedClients.value=collapsedClients.value.includes(key)?collapsedClients.value.filter(value=>value!==key):[...collapsedClients.value,key]}
async function collapseClientGroups(collapse){if(!await tableEditing.flush())return;collapsedClients.value=collapse?clientGroups.value.map(group=>group.key):[]}

const tableError=computed(()=>[...tableEditing.states.values()].find(state=>state.error)?.error||'')
async function discardTableDrafts(){try{await ElMessageBox.confirm('放弃尚未保存的单元格内容并重新加载？','重新加载',{type:'warning'})}catch{return}tableEditing.discard();await load({fromTable:true})}
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerScope=ref(props.clientScope?'all':'self'),managerDraftScope=ref(props.clientScope?'all':'self'),managerIds=ref([]),managerDraftIds=ref([]),managerPickerVisible=ref(false),managerNames=ref({})
function cacheManagers(people){managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[person.id,`${person.name}${person.username&&person.username!==person.name?`（${person.username}）`:''}`]))}}
const managerLabel=computed(()=>managerScope.value==='self'?`本人（${selfName}）`:managerScope.value==='name'?`指定（${managerIds.value.length}人）：${managerIds.value.map(id=>managerNames.value[id]||'已选人员').join('、')}`:'不指定人（全部订单）')
watch(managerPickerVisible,visible=>{if(visible){managerDraftScope.value=managerScope.value;managerDraftIds.value=[...managerIds.value]}})
function applyManager(){managerScope.value=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value;managerIds.value=managerScope.value==='name'?[...managerDraftIds.value]:[];filters.manager='';managerPickerVisible.value=false;search()}
const advancedCount=computed(()=>Number(filters.projectStatus.length>0)+Number(!!filters.client.trim())+Number(filters.missingWordCount)+Number(filters.missingUnitPrice)+Number(!!filters.missingTotal))
function clearAdvanced(){filters.projectStatus=[];filters.client='';filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';search()}
let timer,controller,sequence=0,disposed=false
function financeParams(){return {client_order_count:filters.clientOrderCount||undefined,client_id:props.clientId||undefined,client_ids:props.clientIds.length?props.clientIds:undefined,keyword:filters.keyword.trim()||undefined,project_statuses:filters.projectStatus.length?filters.projectStatus:undefined,client:filters.client.trim()||undefined,billing_month:filters.month||undefined,manager_ids:managerScope.value==='name'?managerIds.value:undefined,only_mine:managerScope.value==='self',...(props.statementClientView?props.managerQuery:{}),missing_word_count:filters.missingWordCount||undefined,missing_unit_price:filters.missingUnitPrice||undefined,missing_total:filters.missingTotal||undefined}}
async function load(options={}){
  if(editorLoading.value)return
  if(!options?.fromTable&&!await tableEditing.flush())return false
  const current=++sequence;controller?.abort();controller=new AbortController();if(!options?.fromTable)loading.value=true;error.value=''
  try{const data=await getCustomerFinancePage({...financeParams(),skip:(page.value-1)*10,limit:10},{signal:controller.signal});if(current===sequence){rows.value=data.items||[];subtotals.value=data.clientSubtotals||[];total.value=data.total||0;clientGroups.value=data.clientGroups||[];groupOrderTotal.value=data.orderTotal||0}}
  catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务列表加载失败')}
  finally{if(current===sequence)loading.value=false}
}
function search(){if(props.statementClientView){statementTableRef.value?.clearSelection();projectPreview.value=null}clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function queueFilterSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function resetSearch(){filters.clientOrderCount='';collapsedClients.value=[];filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';filters.keyword='';filters.projectStatus=[];filters.client='';filters.month='';filters.manager='';managerIds.value=[];managerScope.value=props.clientScope?'all':'self';search()}
const formatAmounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-'
function cell(row,key){
  if(key==='pricingMode')return row.priceAggregate?'子订单累计':row.pricingMode==='fixed'?'固定收费':'按数量'
  if(key==='projectName')return row.sourceFileName||row.projectName||'-'
  if(key==='projectStatus')return getProjectStatusLabel('translation',row.projectStatus)
  if(key==='wordCount')return getWordCountSummary(row).primary
  if(key==='totalInclTax')return formatAmounts(row.totalsInclTax);if(key==='totalPrice'||key==='adjustedTotal'){const values=key==='totalPrice'?row.totalsExclTax:row.adjustedTotals;return (Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-')+(row.incomplete?'\n待补录数量或单价':'')}
  return row[key]||'-'
}
const localTarget=ref(null),localPaymentParent=ref(null),linkedPaymentVisible=ref(false)
let originalPaymentConfirmation=''
const editorVisible=ref(false),editorLoading=ref(false),saving=ref(false),saveError=ref(''),editor=ref({}),formRef=ref(),editorBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
let original='',treeVersion='',libraryVersion=''
const referencePrices=ref([]),updateLibrary=ref(false),referencePickerRef=ref()
const historyVisible=ref(false),historyOrder=ref(null)
const getWordCountSummary=row=>getWordCountMatrixListSummary(row.wordCountMatrix||{},{source:row.wordCountMatrixSource})
const paymentConfirmationDirty=computed(()=>JSON.stringify(editor.value.paymentConfirmation)!==originalPaymentConfirmation)
const originalPrices=ref([])
const rateSyncPreviewRef=ref(),syncPreviewPending=ref(false)
const editorDirty=computed(()=>editorVisible.value&&editorSignature()!==original)
const calculatedTotals=computed(()=>calculateTaxOrderPriceTree(editor.value,originalPrices.value))
function calculatedTotal(kind){const result=calculatedTotals.value[kind];return '自动计算：'+formatAmounts(result.totals)+(result.incomplete?'（待补录）':'')}
async function onTablePriceSaved(result){if(result?.item)notifyPaymentChanged(result.item.id,result.item.paymentConfirmation,financePaymentSource);emit('saved');await load({fromTable:true})}
async function onSameMonthSynced(){editorVisible.value=false;emit('saved');await load()}
function editorSignature(){return JSON.stringify([editor.value.pricingMode,editor.value.currency,(editor.value.prices||[]).map(ratePayload),editor.value.adjustedTotal,editor.value.adjustedTotalInclTax,editor.value.explanation,editor.value.billingMonth,updateLibrary.value,editor.value.paymentConfirmation,editor.value.customerExplanation||''])}
function referenceDefaults(){return expectedOrderPrices([],editor.value.languagePair,editor.value.wordCountMatrix).map(price=>referencePrices.value.find(ref=>priceMatch(ref,price,editor.value.wordCountMatrix).matched)).filter(Boolean).map(referenceDraft)}
async function adoptReference(){const choice=await referencePickerRef.value?.confirm();if(!choice)return;try{const values=expectedOrderPrices(editor.value.prices,editor.value.languagePair,editor.value.wordCountMatrix).map(row=>({...row}));const index=replaceMatchedReference(values,choice.price,editor.value.wordCountMatrix);values[index]={...referenceDraft(choice.price),id:values[index].id,metric:values[index].metric};editor.value.prices=values;editor.value.adjustedTotal=undefined}catch(e){ElMessage.warning(e.message)}}
let editorSequence=0
async function openEditor(row){
  if(!canWrite||editorLoading.value||saving.value)return
  if(!await tableEditing.flush())return ElMessage.warning('有单元格尚未保存，请先处理提示')
  if(editorVisible.value&&!await guardEditor())return
  const current=++editorSequence
  clearTimeout(timer);controller?.abort();sequence++;loading.value=false
  financeModule.value='translation'
  paymentContextId.value=row.rootId
  localTarget.value=null;localPaymentParent.value=null
  editorLoading.value=true
  try{
    const data=await getCustomerFinanceProject(row.rootId)
    if(disposed||current!==editorSequence)return
    const find=node=>node.id===row.id?node:(node.children||[]).map(find).find(Boolean)
    const selected=find(data.item)
    if(!selected)throw new Error('订单已变化，请刷新')
    originalPrices.value=structuredClone(selected.prices||[])
    editor.value={...structuredClone(selected),paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation),prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),billingMonth:orderStatementMonth(selected.orderNo)||selected.billingMonth||null}
    referencePrices.value=data.referencePrices?.items||[];libraryVersion=data.referencePrices?.version||'';updateLibrary.value=false
    if(!editor.value.prices.length){
      const suggested=referenceDefaults()
      editor.value.prices=suggested.length?suggested:String(selected.languagePair||'').split('；').filter(Boolean).map(newCustomerRate)
      if(!editor.value.prices.length)editor.value.prices=[newCustomerRate()]
    }
    treeVersion=data.version;saveError.value='';clearFieldSearch()
    editorVisible.value=true
    await nextTick()
    original=editorSignature();originalPaymentConfirmation=JSON.stringify(editor.value.paymentConfirmation)
  }catch(e){if(current===editorSequence)ElMessage.error(getLocalizedErrorMessage(e,'收费明细加载失败'))}
  finally{if(current===editorSequence)editorLoading.value=false}
}

async function rebaseEditorAfterLibrary(){
  if(!editor.value.rootId||localTarget.value)return
  const data=await getCustomerFinanceProject(editor.value.rootId)
  const find=node=>node.id===editor.value.id?node:(node.children||[]).map(find).find(Boolean)
  const selected=find(data.item);if(!selected)throw new Error('订单已变化，请重新打开')
  const before=JSON.parse(original),draft=editor.value,signature=JSON.parse(editorSignature())
  const fresh={...structuredClone(selected),prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation)}
  editor.value=fresh;updateLibrary.value=false;original=editorSignature();originalPaymentConfirmation=JSON.stringify(fresh.paymentConfirmation)
  const fields=['pricingMode','currency','prices','adjustedTotal','adjustedTotalInclTax','explanation','billingMonth']
  fields.forEach((field,index)=>{if(JSON.stringify(signature[index])!==JSON.stringify(before[index]))fresh[field]=draft[field]})
  if(JSON.stringify(signature[8])!==JSON.stringify(before[8]))fresh.paymentConfirmation=draft.paymentConfirmation
  if(JSON.stringify(signature[9])!==JSON.stringify(before[9]))fresh.customerExplanation=draft.customerExplanation
  originalPrices.value=structuredClone(selected.prices||[]);treeVersion=data.version;referencePrices.value=data.referencePrices?.items||[];libraryVersion=data.referencePrices?.version||''
}
async function prepareEditorSync(){await rebaseEditorAfterLibrary();return {order_id:editor.value.id,version:treeVersion,billing_month:editor.value.billingMonth}}

async function openAggregateOrder(rootId,id){
  const find=node=>node.id===id?node:(node.children||[]).map(find).find(Boolean)
  let target=rows.value.map(find).find(Boolean)
  if(!target){const data=await getCustomerFinanceProject(rootId);target=find(data.item)}
  if(target)await openEditor(target)
}
async function closeEditor(done){
  if(saving.value)return
  if(editorSignature()!==original){try{await ElMessageBox.confirm('收费明细有未保存修改，确定放弃？','关闭编辑',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}
  if(typeof done==='function')done();else editorVisible.value=false
}
async function save(syncToClient=false){
  const activeForm=formRef.value
  if(saving.value||!canWrite||!await activeForm?.validate().catch(()=>false))return
  if(editor.value.pricingMode!=='fixed'&&!editor.value.prices.length)return ElMessage.warning('请至少填写一条语种单价')
  if(editor.value.pricingMode==='fixed'&&editor.value.adjustedTotal==null&&editor.value.adjustedTotalInclTax==null)return ElMessage.warning('请填写固定收费金额')
  if(localTarget.value){saveLocalFinance();return}
  if(syncToClient){if(syncPreviewPending.value)return;syncPreviewPending.value=true;let confirmed;try{confirmed=await rateSyncPreviewRef.value.confirm()}finally{syncPreviewPending.value=false}if(!confirmed)return;libraryVersion=confirmed.version}
  saving.value=true;saveError.value=''
  try{const savedFinance=await saveCustomerFinanceProject(editor.value.rootId,{version:treeVersion,payment_confirmation:paymentConfirmationDirty.value?paymentConfirmationPayload(editor.value.paymentConfirmation):undefined,order_id:editor.value.id,pricing_mode:editor.value.pricingMode||'metric',currency:editor.value.currency||'CNY',prices:editor.value.pricingMode==='fixed'?null:editor.value.prices.map(ratePayload),update_library:syncToClient,sync_confirmed:syncToClient,library_version:libraryVersion,adjusted_total:editor.value.adjustedTotal??null,adjusted_total_incl_tax:editor.value.adjustedTotalInclTax??null,explanation:editor.value.explanation||'',customer_explanation:editor.value.customerExplanation||'',billing_month:editor.value.billingMonth||null});editor.value.paymentConfirmation=paymentConfirmationForm(savedFinance.item.paymentConfirmation);original=editorSignature();originalPaymentConfirmation=JSON.stringify(editor.value.paymentConfirmation);notifyPaymentChanged(editor.value.rootId,editor.value.paymentConfirmation,financePaymentSource);editorVisible.value=false;ElMessage.success('语种单价已保存，下级继承及金额小计已更新');emit('saved');await load()}
  catch(e){saveError.value=getLocalizedErrorMessage(e,'保存失败，请检查收费明细；如项目已被其他人修改，请重新打开后编辑')}
  finally{saving.value=false}
}

function changePricingMode(){editor.value.adjustedTotal=undefined;editor.value.adjustedTotalInclTax=undefined;formRef.value?.clearValidate()}
async function openForForm(target,parent=target){
  if(target.id&&(target.wordCountMatrixSource==='suborder_aggregate'||target.wordCountSubOrderCount>0))return openEditor({id:target.id,rootId:parent.id||target.id})
  financeModule.value='translation'
  if(!canWrite)return
  localTarget.value=target;localPaymentParent.value=parent
  const charges=target.customerChargeItems||[],first=charges[0]
  const prices=charges.filter(row=>row.pricingMode==='metric').map(row=>({id:row.id,languagePair:row.languagePair||target.languagePair||parent.languagePair||'',amount:row.unitPriceExclTax??row.unitPriceInclTax,taxPrices:taxPriceForm(row),currency:row.currency||'CNY',metric:row.quantityBasis||row.metricType,unitSize:Number(row.unitSize||1)}))
  editor.value={paymentConfirmation:paymentConfirmationForm(parent.paymentConfirmation),id:target.id||'',rootId:parent.id||'',orderNo:target.orderNo||target.subOrderNo||'新增项目',projectName:target.sourceFileName||target.projectName||target.subProjectName||'',languagePair:target.languagePair||parent.languagePair||'',clientId:parent.clientId,wordCountMatrix:JSON.parse(JSON.stringify(target.wordCountMatrix||{})),children:[],pricingMode:first?.pricingMode||'metric',currency:first?.currency||'CNY',prices:prices.length?prices:[newCustomerRate(String(target.languagePair||parent.languagePair||'').split('；')[0]||'')],adjustedTotal:first?.totalExclTax==null?undefined:Number(first.totalExclTax),adjustedTotalInclTax:first?.totalInclTax==null?undefined:Number(first.totalInclTax),billingMonth:orderStatementMonth(target.orderNo||target.subOrderNo||parent.orderNo)||first?.billingMonth||null,explanation:first?.remarks||''}
  originalPrices.value=JSON.parse(JSON.stringify(editor.value.prices));referencePrices.value=[];saveError.value='';clearFieldSearch();editorVisible.value=true;await nextTick();original=editorSignature();originalPaymentConfirmation=JSON.stringify(editor.value.paymentConfirmation)
  if(parent.clientId){try{const data=await getCustomerTranslationRates(parent.clientId);if(editorVisible.value&&localTarget.value===target)referencePrices.value=data.items||[]}catch(e){saveError.value=getLocalizedErrorMessage(e,'客户参考价加载失败')}}
}
function saveLocalFinance(){
  localPaymentParent.value.paymentConfirmation=JSON.parse(JSON.stringify(editor.value.paymentConfirmation))
  const old=localTarget.value.customerChargeItems||[]
  if(editor.value.pricingMode==='fixed')localTarget.value.customerChargeItems=[{id:old.length===1&&old[0].pricingMode==='fixed'?old[0].id:null,sequenceNo:1,itemName:'翻译费',pricingMode:'fixed',currency:editor.value.currency||'CNY',totalExclTax:editor.value.adjustedTotal??null,totalInclTax:editor.value.adjustedTotalInclTax??null,unitPriceExclTax:null,unitPriceInclTax:null,unitSize:null,metricType:null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}]
  else localTarget.value.customerChargeItems=editor.value.prices.map((price,index)=>({id:price.id||null,sequenceNo:index+1,itemName:'翻译费',pricingMode:'metric',metricType:resolveRateQuantity(editor.value.wordCountMatrix,price.metric).metric,quantityBasis:price.metric,languagePair:price.languagePair,unitSize:price.unitSize||1,unitPriceExclTax:price.taxPrices?.unitPriceExclTax??null,unitPriceInclTax:price.taxPrices?.unitPriceInclTax??null,currency:price.currency||'CNY',totalExclTax:index===0?editor.value.adjustedTotal??null:price.taxPrices?.totalExclTax??null,totalInclTax:index===0?editor.value.adjustedTotalInclTax??null:price.taxPrices?.totalInclTax??null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}))
  original=editorSignature();originalPaymentConfirmation=JSON.stringify(editor.value.paymentConfirmation);editorVisible.value=false;emit('saved');ElMessage.success('财务填写已保留，保存项目后生效')
}
function openPaymentManagement(){paymentVisible.value=true}
async function openLinkedPayment(){if(editor.value.rootId)linkedPaymentVisible.value=true}
function onPaymentSaved(result){
  paymentContextId.value=String(result.project_id||result.projectId||paymentContextId.value)
  if(editor.value.rootId===paymentContextId.value){
    if(!paymentConfirmationDirty.value)onLinkedPaymentSaved(result)
    else saveError.value='该订单付款已在另一窗口保存，当前付款草稿保留，请打开付款情况核对'
  }
  if(!props.editorOnly)void load()
}
function onPaymentChanged(event){
  if(!event.detail?.projectId||event.detail.source===financePaymentSource)return
  onPaymentSaved({project_id:event.detail?.projectId,confirmation:event.detail?.confirmation})
}

function onLinkedPaymentSaved(result){
  if(!original||!editor.value.rootId)return
  saveError.value=''
  const before=JSON.parse(original);editor.value.paymentConfirmation=paymentConfirmationForm(result.confirmation);originalPaymentConfirmation=JSON.stringify(editor.value.paymentConfirmation);before[8]=editor.value.paymentConfirmation;original=JSON.stringify(before)
  if(localPaymentParent.value)localPaymentParent.value.paymentConfirmation=JSON.parse(originalPaymentConfirmation)
  emit('saved')
}
watch(()=>[filters.projectStatus,props.initialMonth,props.previewMonths,props.previewMode,JSON.stringify(props.managerQuery)],()=>{projectPreview.value=null},{deep:true})
watch(rows,()=>{projectPreview.value=null},{deep:true})
watch(()=>props.clientIds.join(','),()=>{if(props.statementClientView)search()})
defineExpose({openForForm,statementSelection,reloadProjects:load})

watch(()=>props.clientId,search)
watch(()=>[props.initialMonth,JSON.stringify(props.managerQuery)],()=>{if(props.statementClientView){filters.month=props.initialMonth||'';search()}})
onMounted(()=>{if(props.clientId||props.clientIds.length)void load()})
onActivated(()=>{if(props.editorOnly)return;managerScope.value=props.clientScope?'all':'self';managerIds.value=[];managerDraftScope.value='self';managerDraftIds.value=[];filters.manager='';managerPickerVisible.value=false;page.value=1;void load()})
function refreshStatementStatus(){if(!props.editorOnly)void load()}
onMounted(()=>{window.addEventListener('translation-statements-changed',refreshStatementStatus);window.addEventListener(paymentChangeEvent,onPaymentChanged)})
onDeactivated(()=>{editorSequence++;editorLoading.value=false;paymentVisible.value=false;quotationVisible.value=false;statementVisible.value=false;rateSyncPreviewRef.value?.cancel();managerPickerVisible.value=false;historyVisible.value=false;clearTimeout(timer);sequence++;controller?.abort();loading.value=false})
async function guardEditor(){if(!await tableEditing.flush())return false;if(!editorVisible.value)return true;if(saving.value)return false;await closeEditor();return !editorVisible.value}
onBeforeRouteLeave(guardEditor)
onBeforeRouteUpdate((to,from)=>to.query.section!==from.query.section?guardEditor():true)
onBeforeUnmount(()=>{window.removeEventListener('translation-statements-changed',refreshStatementStatus);window.removeEventListener(paymentChangeEvent,onPaymentChanged);disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
useProjectStatusSync('translation',rows,{enabled:()=>!props.editorOnly,onChanged:()=>{if(!loading.value&&!editorLoading.value)void load({fromTable:true})}})
</script>

<style scoped>
.finance-sheet-form :deep(.el-table__cell){vertical-align:top;padding:5px 0}
.finance-sheet-form :deep(.cell){padding:0 5px}
.finance-column-heading{display:flex;align-items:center;gap:4px;white-space:normal;overflow-wrap:anywhere}
.finance-pin-toggle{border:0;background:transparent;color:var(--el-color-primary);font:inherit;cursor:pointer;padding:0;font-size:12px}
.finance-operations-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.customer-finance { overflow: visible; }
.customer-finance > :deep(.el-card__body) { overflow: visible; }
.finance-project-table { overflow: visible; }
.finance-project-table :deep(.el-table__body-wrapper),
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar) { overflow: visible; }
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar > .el-scrollbar__bar.is-horizontal) {
  position: sticky;
  bottom: -24px;
  width: calc(100% - 4px);
  height: 10px;
  z-index: 5;
  background: var(--el-fill-color-light);
}
.finance-project-table :deep(.el-table__header-wrapper) {
  position: sticky;
  top: -12px;
  z-index: 4;
  background: var(--el-table-header-bg-color);
}
.finance-word-count-extra { margin-left: 6px; }
.finance-editor-only { display:none; }
:global(.finance-manager-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.el-dialog.draggable-form-dialog.finance-manager-dialog.has-manager-select > .el-dialog__body){min-height:min(440px,55vh)}
:global(.finance-manager-dialog .el-dialog__header),:global(.finance-manager-dialog .el-dialog__footer){flex-shrink:0}
:global(.finance-manager-dialog .el-dialog__footer){border-top:1px solid #dbe3ec;background:#f8fafc}
.manager-filter-choices{display:flex;flex-direction:column;align-items:flex-start}.manager-filter-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.manager-filter-active{background:#f1f5f9;border-color:#94a3b8}
.customer-finance{min-width:0}.finance-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.finance-heading-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.finance-search{display:flex;flex-wrap:wrap;gap:8px}.finance-search :deep(.el-form-item){margin:0 8px 12px 0}.finance-search .el-input{width:220px;max-width:100%}.finance-search .finance-keyword{width:220px}.finance-search :deep(.finance-month){width:160px;max-width:100%}.finance-search .el-select{width:180px}.finance-help{color:#64748b;font-size:12px;margin:0 0 12px}.finance-cell{white-space:pre-wrap;overflow-wrap:anywhere}.el-pagination{margin-top:16px;justify-content:flex-end;flex-wrap:wrap}
:global(.customer-finance-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-finance-dialog .el-dialog__header),:global(.customer-finance-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-finance-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.customer-finance-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
.finance-pricing-config{padding:14px 16px;border:1px solid var(--el-border-color);border-radius:8px;margin-bottom:16px}.finance-config-grid,.finance-settlement-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.finance-config-grid :deep(.el-form-item){margin-bottom:0}.finance-pricing-form :deep(.el-date-editor),.finance-pricing-form :deep(.el-input-number),.finance-pricing-form :deep(.el-select){width:100%;max-width:100%}.finance-reference-item{margin:12px 0 0;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}.finance-reference-content{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.finance-reference-content>span{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}.finance-calculation-hint{margin-top:10px}.finance-settlement-section{margin-top:16px;padding-top:14px;border-top:1px solid var(--el-border-color-lighter)}.finance-settlement-section h4{font-size:14px;margin:0 0 12px}.finance-settlement-grid{gap:0 16px}.finance-total-line{display:flex;align-items:center;gap:8px;width:100%;min-width:0}.finance-total-line>*{flex:1;min-width:0}.finance-total-line :deep(.readonly-field){min-width:0}.finance-settlement-grid--fixed{grid-template-columns:repeat(3,minmax(0,1fr))}.finance-sync-actions{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}.finance-sync-actions :deep(.el-form-item){margin-bottom:8px}@media(max-width:720px){.finance-config-grid,.finance-settlement-grid,.finance-settlement-grid--fixed{grid-template-columns:minmax(0,1fr)}.finance-pricing-config{padding:12px}.finance-sync-actions{gap:8px}}
.statement-client-finance .finance-project-table :deep(.el-table__header-wrapper){top:0}.statement-client-finance{margin:12px 0}
</style>

<style scoped>
.finance-client-group-toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0;color:var(--el-text-color-secondary);font-size:12px}.finance-client-group-toggle{display:flex;gap:12px;align-items:center;border:0;background:transparent;font:inherit;font-weight:700;color:var(--el-color-primary);cursor:pointer;padding:6px 4px;white-space:nowrap}.finance-client-group-toggle small{font-weight:400;color:var(--el-text-color-secondary)}.finance-project-table :deep(.finance-client-group-row td){background:#e8eef5!important;border-top:2px solid #b9c9dc;border-bottom:1px solid #cbd5e1}.finance-project-table :deep(.finance-client-group-row .cell){overflow:visible}
</style>
