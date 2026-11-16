<template>
  <el-card class="customer-finance" :class="{'finance-editor-only':editorOnly,'statement-client-finance':statementClientView,'finance-collapsed':isCollapsed}" shadow="never">
    <template #header>
      <div v-if="!statementClientView" class="finance-heading">
        <strong>笔译</strong>
        <div class="finance-heading-actions">
          <el-button v-if="collapsible" :aria-expanded="!isCollapsed" @click="toggleFinancePanel">{{isCollapsed?'展开笔译':'折叠笔译'}}</el-button>
          <template v-if="!isCollapsed">
            <el-button v-if="!editorOnly" :disabled="loading||editorLoading" @click="toggleChildOrders">{{childOrdersExpanded?'折叠子订单':'展开子订单'}}</el-button>
            <el-button @click="quotationVisible=true">报价单</el-button>
            <el-button @click="openStandardStatement()">对账单</el-button>
            <el-button @click="openStatementVariant('backup')">对账单（备份）</el-button>
            <el-button @click="openPaymentManagement">发票、查账与追账</el-button>
            <el-button @click="openStatementVariant('special')">特殊结算</el-button>
            <TableColumnSettings v-model="selectedKeys" settings-key="translation-customer-finance" :columns="columns" @reset="resetColumns" />
          </template>
        </div>
      </div>
      <strong v-else>客户项目</strong>
    </template>
    <MonthlyPaymentProjectsDialog v-if="paymentProjectsContext" :context="paymentProjectsContext" :can-write="canWrite"
      :save-method="saveTablePaymentMethod" :prepare="tableEditing.flush" @close="paymentProjectsContext=null" />
    <ProjectPaymentDialog v-model="paymentVisible" :scope-order="paymentScopeOrder" :can-review-invoice="canWrite" @edit="editPaymentProject" @invoice-saved="onInvoiceSaved" @review-invoice="reviewInvoicePricing" @statement="openInvoiceStatement" />
    <ProjectPaymentDialog v-model="linkedPaymentVisible" :initial-project-id="editor.rootId" lock-project :can-review-invoice="canWrite" @edit="editPaymentProject" @invoice-saved="onInvoiceSaved" @review-invoice="reviewInvoicePricing" />
    <ProjectInvoiceDialog v-model="invoiceVisible" :context="invoiceContext" @saved="onInvoiceSaved" />
    <CustomerQuotationDialog v-model="quotationVisible" :projects="rows" :query="financeParams()" />
    <CustomerQuotationDialog v-model="linkedQuotationVisible" :draft="editor.quotationDraft" :draft-project="editorDocumentProject" defer-save @update:draft="value=>{editor.quotationDraft=value;editor.quotationDraftDirty=true}" />
    <CustomerStatementDialog v-model="statementVisible" settlement-scope="standard" :client-context="statementContext" :billing-month="filters.month"
      :manager-label="managerLabel" :manager-query="activeManagerQuery" />
    <CustomerStatementDialog v-model="backupStatementVisible" title="对账单（备份）" :billing-month="filters.month"
      :manager-label="managerLabel" :manager-query="activeManagerQuery" />
    <CustomerStatementDialog v-model="specialStatementVisible" :client-context="specialStatementContext" settlement-scope="special" title="特殊结算" :billing-month="filters.month"
      :manager-label="managerLabel" :manager-query="activeManagerQuery" />
    <div v-if="specialSettlementView" v-loading="loading" class="finance-preview-actions">
      <strong>客户原始总价（财务主表）</strong>
      <span>不含税 {{formatAmounts(subtotals[0]?.totalsExclTax)}}</span>
      <span>含税 {{formatAmounts(subtotals[0]?.totalsInclTax)}}</span>
    </div>
    <div v-if="statementClientView" class="finance-preview-actions"><el-button :loading="previewLoading" :disabled="loading" @click="previewProjects">{{specialSettlementView?'特殊结算预览':'对账单预览'}}</el-button><span v-if="requireStatementForSelection">已选 {{statementSelected.length}} 项。未勾选时使用筛选结果中标记为「需」的项目。「无需」项目可在对账单列重新确认。</span><span v-else>已选 {{statementSelected.length}} 项；未勾选时使用全部筛选结果</span></div>
    <AppForm v-if="statementClientView" :inline="true" :model="filters" @submit.prevent="search">
      <el-form-item label="项目状态"><el-select v-model="filters.projectStatus" multiple collapse-tags collapse-tags-tooltip clearable placeholder="全部状态" style="width:260px;max-width:100%" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item>
      <el-form-item><el-button native-type="button" :disabled="loading||!statementParentIds.length" @click="toggleStatementChildren">{{statementExpandedIds.length?'折叠子订单':'展开子订单'}}</el-button></el-form-item>
    </AppForm>
    <AppForm v-if="!statementClientView" :inline="true" :disabled="editorLoading" :model="filters" class="finance-search" @submit.prevent="search">
      <slot name="project-type-filter" />
      <el-form-item label="关键词"><el-input class="finance-keyword" v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="账单月份"><el-date-picker class="finance-month" :model-value="filters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" title="按订单号年月筛选，如 TP-261029-010 对应 2026-10" clearable @update:model-value="setBillingMonth" /></el-form-item>
      <el-form-item label="客户经理"><el-button :class="{'manager-filter-active':managerScope!=='all'}" :title="managerLabel" @click="managerPickerVisible=true">{{managerLabel}}</el-button></el-form-item>
      <el-form-item label="订单客户"><el-select v-model="filters.clientOrderCount" style="width:150px" placeholder="全部客户" aria-label="订单客户" @change="search"><el-option label="全部客户" value="" /><el-option label="单订单客户" value="single" /><el-option label="多订单客户" value="multiple" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="resetSearch">重置</el-button><AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" @clear="clearAdvanced"><el-form-item label="项目状态"><el-select v-model="filters.projectStatus" multiple collapse-tags collapse-tags-tooltip clearable placeholder="全部状态" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item><el-form-item label="客户"><el-input v-model="filters.client" clearable placeholder="客户全称或简称" @input="queueFilterSearch" @keyup.enter="search" /></el-form-item><el-form-item label="账期"><StatementPeriodSelect :model-value="filters.billingPeriod" :month="filters.month" :client-id="clientId" allow-unassigned @update:model-value="value=>{filters.billingPeriod=value;search()}" /><small v-if="!filters.month">选择账单月份后可筛选编号期次。</small></el-form-item><el-form-item label="字数统计"><el-checkbox v-model="filters.missingWordCount" @change="search">我司、客户统计均未填写</el-checkbox></el-form-item><el-form-item label="单价"><el-checkbox v-model="filters.missingUnitPrice" @change="search">未填写单价（固定收费除外）</el-checkbox></el-form-item><el-form-item label="总价"><el-select v-model="filters.missingTotal" clearable placeholder="全部" @change="search"><el-option label="不含税总价为空" value="excl" /><el-option label="含税总价为空" value="incl" /><el-option label="两种总价均为空" value="both" /><el-option label="任一种总价为空" value="either" /><el-option label="固定收费金额为空" value="fixed" /></el-select></el-form-item><p class="finance-help">按母订单汇总结果筛选；零值视为已填写，预统计不视为我司或客户统计。</p></AdvancedFilterPopover></el-form-item>
    </AppForm>
    <DraggableFormDialog v-model="managerPickerVisible" title="客户经理筛选" append-to-body :class="['finance-manager-dialog',{'has-manager-select':managerDraftScope==='name'}]" width="min(560px, calc(100vw - 32px))" top="10vh" :close-on-click-modal="false">
      <el-radio-group v-model="managerDraftScope" class="manager-filter-choices"><el-radio value="self">本人（{{selfName}}）</el-radio><el-radio value="all">不指定人（全部订单）</el-radio><el-radio value="name">指定客户经理</el-radio></el-radio-group>
      <CustomerDepartmentManagerSelect v-if="managerDraftScope==='name'" v-model="managerDraftIds" @options="cacheManagers" />
      <p class="finance-help">可多选客户部成员，点击“确定”后更新订单列表及客户金额小计。</p>
      <template #footer><el-button @click="managerPickerVisible=false">取消</el-button><el-button type="primary" @click="applyManager">确定</el-button></template>
    </DraggableFormDialog>
    <p v-if="!statementClientView" class="finance-help">按语种方向维护多条单价，默认优先采用客户统计的数量和单位，客户未填时采用我司统计；也可手动选择我司统计，两者均未填时提示补录。母订单单价复制至匹配语种的下级，单独改价的下级保留；工作量时父级汇总下级金额，各币种单独小计；固定收费直接采用登记的一口价。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link type="primary" :disabled="loading" @click="load()">重试</el-button>
    </el-alert>
    <p v-if="canWrite&&!statementClientView" class="finance-help">字数统计之后的字段可直接填写，修改后自动保存，与“价格与付款”窗口同步。</p>
    <el-alert v-if="tableError" type="error" :closable="false" :title="tableError"><el-button link type="primary" @click="tableEditing.flush()">重试保存</el-button><el-button link type="primary" @click="discardTableDrafts">放弃未保存内容并重新加载</el-button></el-alert>
    <div v-if="filters.clientOrderCount==='multiple'" class="finance-client-group-toolbar"><span>按当前筛选结果统计：{{total}} 个多订单客户，共 {{groupOrderTotal}} 个母订单；每页 10 个客户。</span><el-button link @click="collapseClientGroups(false)">全部展开</el-button><el-button link @click="collapseClientGroups(true)">全部收起</el-button></div>
    <AppForm :model="tableEditing.states" label-position="top" class="finance-sheet-form" data-auto-draft="off">
    <el-table v-loading="loading||editorLoading" ref="statementTableRef" @selection-change="statementSelected=$event;projectPreview=null" @sort-change="sortFinanceRows" @expand-change="onStatementExpandChange" class="finance-project-table" :class="{'finance-project-table--order-controls':!statementClientView}" :data="tableRows" :span-method="clientGroupSpan" :row-class-name="({row})=>row._clientGroup?'finance-client-group-row':''" row-key="id" border :default-expand-all="!statementClientView" :expand-row-keys="statementClientView?statementExpandedIds:undefined" scrollbar-always-on empty-text="暂无笔译项目">
      <OrderedTableColumns settings-key="translation-customer-finance" preserve-fixed>
      <el-table-column v-if="statementClientView" type="selection" :selectable="canSelectStatementProject" reserve-selection width="44" />
      <el-table-column type="index" label="序号" class-name="finance-order-index-cell" :fixed="fixedColumns.length?'left':false" :width="statementClientView?60:orderTree.width" :index="index => (page-1)*10+index+1">
        <template #default="{row,$index}">
          <div v-if="row._clientGroup" class="finance-client-group-header">
            <button type="button" class="finance-client-group-toggle" :aria-expanded="!row.collapsed" @click="toggleClientGroup(row.groupKey)">{{row.collapsed?'▶':'▼'}} {{row.clientName}}</button>
            <small>共 {{row.pageCount}} 页，{{row.orderTotal}} 条</small>
            <el-pagination v-if="!row.collapsed && row.pageCount>1" small layout="prev, pager, next" :pager-count="5"
              :aria-label="`${row.clientName}订单分页`" :current-page="row.currentPage" :page-size="clientOrderPageSize" :total="row.orderTotal"
              @update:current-page="changeClientOrderPage(row.groupKey,$event)" />
          </div>
          <div v-else class="finance-order-index" :style="orderTree.rows.get(row.id)?.indent">
            <template v-if="orderTree.rows.has(row.id)">
              <span v-for="line in orderTree.rows.get(row.id).lines" :key="line.level" aria-hidden="true"
                class="finance-order-tree-line" :class="'finance-order-tree-line--'+line.kind" :style="line.position" />
            </template>
            <span>{{filters.clientOrderCount==='multiple'||childPagination?displayIndexes.get(row.id):((page-1)*10+$index+1)}}</span>
            <TableExpandButton v-if="!statementClientView && (row.childOrderCount || (row.hasChildren ?? !!row.children?.length))"
              :expanded="isOrderExpanded(row.id)" :count="row.childOrderCount"
              :expand-label="financeChildOrdersLabel(row,'展开')"
              :collapse-label="financeChildOrdersLabel(row,'收起')" @click="toggleOrderExpansion(row.id)" />
          </div>
        </template>
      </el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :width="column.width" :fixed="fixedColumns.includes(column.key)?'left':false" :prop="column.key" :sortable="!statementClientView && ['clientShortName','clientManager'].includes(column.key) ? 'custom' : false">
        <template #header><div class="finance-column-heading"><ConfiguredColumnHeaderFilter v-if="headerFilterDefinitions[column.key] && !(requireStatementForSelection && column.key==='statementRequired')" :definition="headerFilterDefinitions[column.key]" :model-value="filters[column.key]" @update:model-value="filters[column.key]=$event" @change="search" @clear="search" /><span v-else>{{column.key==='statementRequired' && statementClientView ? '对账单' : column.label}}</span><button v-if="['orderNo','projectName'].includes(column.key)" type="button" class="finance-pin-toggle" :aria-label="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :title="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :aria-pressed="fixedColumns.includes(column.key)" @click.stop="toggleFixedColumn(column.key)">{{fixedColumns.includes(column.key)?'◆':'◇'}}</button></div></template>
        <template #default="{row}"><span v-if="row._clientGroup" />
          <div v-else-if="column.key==='paymentMethod'" class="finance-statement-payment">
            <el-select v-if="canWrite && row.id===row.rootId" :model-value="paymentMethodFor(row)" size="small"
              :disabled="savingTableDocuments.has(row.id)" :aria-label="`${row.orderNo} 结算模式`"
              @change="saveTablePaymentMethod(row,$event)">
              <el-option v-for="method in paymentMethods" :key="method.value" :value="method.value" :label="method.label" />
            </el-select>
            <span v-else>{{row.id!==row.rootId?'随母订单：':''}}{{settlementModeLabels[paymentMethodFor(row)]}}</span>
            <el-button v-if="paymentMethodFor(row)==='monthly' && row.clientId" link type="primary"
              @click="openPaymentProjects(row,'monthly')">查看汇总项目</el-button>
            <small v-if="row.customerDocumentSources?.paymentMethod">来自客户管理</small>
            <el-button v-if="row.clientId&&row.id===row.rootId" link type="primary" @click="openCustomerFinanceSettings('settings',row.clientId)">客户结算设置</el-button>
          </div>
          <div v-else-if="column.key==='statementRequired'" class="finance-statement-payment">
            <div v-if="!statementClientView" class="finance-document-flag">
              <span>报价单：</span>
              <el-checkbox v-if="canWrite&&row.id===row.rootId" :model-value="row.quotationRequired"
                :disabled="savingTableDocuments.has(row.id)" :aria-label="`${row.orderNo} 是否需报价单`"
                @change="saveTableQuotationRequired(row,$event)">{{row.quotationRequired?'需':'无需'}}</el-checkbox>
              <span v-else>{{row.id!==row.rootId?'随母订单：':''}}{{row.quotationRequired?'需':'无需'}}</span>
            </div>
            <div class="finance-document-flag">
              <span v-if="!statementClientView">对账单：</span>
              <el-checkbox v-if="specialSettlementView" :model-value="row.statementRequired"
                :disabled="!canWrite||savingTableDocuments.has(row.rootId)" :aria-label="`${row.orderNo} 是否需对账单`"
                @change="changeSpecialSettlement(row,{statement_required:$event})">{{row.statementRequired?'需':'无需'}}</el-checkbox>
              <CustomerStatementRequiredToggle v-else :row="row" :allow-month-sync="!requireStatementForSelection" :prepare="tableEditing.flush" @saved="onTableStatementSaved(row,$event)" />
            </div>
            <div v-if="specialSettlementView" class="finance-document-flag">
              <el-select :model-value="row.specialTaxMode||'unknown'" size="small" :aria-label="`${row.orderNo} 计费口径`"
                :disabled="!canWrite||savingTableDocuments.has(row.rootId)" @change="changeSpecialSettlement(row,{tax_mode:$event})">
                <el-option label="含税" value="incl_tax" /><el-option label="不含税" value="excl_tax" />
                <el-option v-if="row.specialTaxMode==='mixed'" label="混合口径" value="mixed" disabled />
                <el-option v-if="!row.specialTaxMode" label="待选择" value="unknown" disabled />
              </el-select>
              <span>发票 {{row.invoiceRequired==null?'待判断':row.invoiceRequired?'需':'无需'}}</span>
            </div>
            <template v-if="!statementClientView">
              <el-button v-if="row.statementRequired && row.clientId" link type="primary" @click="openPaymentProjects(row,'statement')">对账单项目</el-button>
              <div class="finance-document-flag finance-document-flag--invoice">
                <span>发票：</span>
                <el-select v-if="canWrite&&row.id===row.rootId&&paymentMethodFor(row)==='special'" :model-value="row.invoiceRequirementOverride ?? 'auto'" size="small"
                  :disabled="savingTableDocuments.has(row.id)" :aria-label="`${row.orderNo} 是否需发票`"
                  @change="saveTableInvoiceRequired(row,$event)">
                  <el-option label="需" :value="true" />
                  <el-option label="无需" :value="false" />
                  <el-option v-if="row.invoiceRequirementOverride==null" :label="row.invoiceRequired==null?'待判断':row.invoiceRequired?'需（按计费口径）':'无需（按计费口径）'" value="auto" disabled />
                </el-select>
                <span v-else>{{row.invoiceRequired==null?'待判断':row.invoiceRequired?'需':'无需'}}</span>
              </div>
              <small v-if="row.customerDocumentSources?.quotationRequired||row.customerDocumentSources?.statementRequired||row.customerDocumentSources?.invoiceRequired">部分单据设置来自客户管理</small>
              <el-button v-if="row.clientId&&row.id===row.rootId" link type="primary" @click="openCustomerFinanceSettings('settings',row.clientId)">客户单据设置</el-button>
            </template>
          </div>
          <CustomerFinanceTableCell v-else-if="!specialSettlementView&&tableFields.includes(column.key)&&(canWrite||['totalPrice','totalInclTax','explanation'].includes(column.key)||column.key==='unitPrice'&&row.priceAggregate)" :field="column.key" :row="row" :state="tableEditing.stateFor(row)" :prepare="tableEditing.flush" :readonly="!canWrite || !!row.fixedPricingFrom" @edit-order="openAggregateOrder(row.rootId,$event)" @saved="onTablePriceSaved" @commit="tableEditing.commit(row,$event)" /><TranslationOrderDetailPopover v-else-if="column.key==='orderNo'&&!row.fixedPricingFrom" :order="row" /><WordCountMatrixPopover v-else-if="column.key==='wordCount'" :model-value="row.wordCountMatrix||{}" :entity-type="row.id===row.rootId?'project':'suborder'" :entity-id="row.id" title="项目字数统计" :read-only="!canWrite || statementClientView || row.wordCountMatrixSource === 'suborder_aggregate'">
          <template #reference><el-button link type="primary" :aria-label="`${row.orderNo} 字数统计`" :title="getWordCountSummary(row).title"><span>{{getWordCountSummary(row).primary}}</span><el-tag v-if="getWordCountSummary(row).extraCount" size="small" type="info" class="finance-word-count-extra">+{{getWordCountSummary(row).extraCount}}</el-tag><el-tag v-if="getWordCountSummary(row).sourceLabel" size="small" type="info">子订单累计</el-tag></el-button></template>
        </WordCountMatrixPopover>
          <div v-else-if="column.key==='languagePair'" class="finance-language-directions">
            <span class="finance-direction-text" :title="row.languagePair">{{languageDirections(row.languagePair)[0]||'—'}}</span>
            <template v-if="languageDirections(row.languagePair).length>1">
              <small v-if="row.fixedPricingFrom" :title="row.languagePair">+{{languageDirections(row.languagePair).length-1}}</small>
              <el-popover v-else title="翻译方向" trigger="click" placement="bottom-start" :width="320" :persistent="false" popper-class="finance-price-settings-popper">
                <template #reference><el-button link type="primary" aria-label="查看全部翻译方向">+{{languageDirections(row.languagePair).length-1}}</el-button></template>
                <ul class="finance-direction-details"><li v-for="(direction,index) in languageDirections(row.languagePair)" :key="index">{{direction}}</li></ul>
              </el-popover>
            </template>
          </div>
          <div v-else-if="column.key==='unitPrice'"><div v-for="(price,index) in row.prices||[]" :key="price.id||index" class="finance-language-price"><strong>{{price.languagePair||row.languagePair||'待选择语种方向'}}</strong><span class="finance-cell">{{taxPriceSummary(price.taxPrices,price.currency,price.unitSize+'计价单位',false)||'税口径未填写'}}</span><CustomerPriceFields v-if="!price.taxPrices" readonly :amount="price.amount" :currency="price.currency" :unit-size="price.unitSize" :metric-type="price.metric" /></div><span v-if="row.pricingMode==='fixed'">固定收费（不涉及单价）</span><span v-else-if="!row.prices?.length">未设置单价</span></div><span v-else class="finance-cell">{{ cell(row,column.key) }}</span>
          <div v-if="row.missingChildOrders?.[column.key]?.length" class="finance-missing-orders">
            <el-popover :title="`未填${column.label}的子订单`" trigger="click" placement="bottom-start" :width="260" :persistent="false">
              <template #reference>
                <el-button link type="warning" :aria-label="`查看${column.label}缺填的子订单`">{{row.missingChildOrders[column.key].length}} 个未填</el-button>
              </template>
              <ul class="finance-missing-order-list">
                <li v-for="orderNo in row.missingChildOrders[column.key]" :key="orderNo">{{orderNo}}</li>
              </ul>
            </el-popover>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="!statementClientView" label="操作" width="68" align="center" fixed="right">
        <template #default="{row}">
          <ProjectListRowActions v-if="!row._clientGroup" :editable="false" :show-start-request="false"
            :extra-actions="financeRowActions(row)" @extra-command="handleFinanceRowAction(row,$event)" />
        </template>
      </el-table-column>
      </OrderedTableColumns>
    </el-table>

    </AppForm>
    <el-pagination :disabled="editorLoading" v-model:current-page="page" :page-size="10" :total="total" layout="slot, prev, pager, next, jumper" @current-change="load"><span v-if="!statementClientView">{{appliedBillingMonth||'全部月份'}} · </span><span>{{filters.clientOrderCount==='multiple'?`共 ${total} 个客户（${groupOrderTotal} 个母订单）`:`共 ${total} 条`}}</span></el-pagination>
    <section v-if="statementClientView&&projectPreview" class="finance-project-preview"><h3>对账单预览</h3><p>客户编号：{{projectPreview.client_code||'—'}}（仅系统可见）</p><CustomerStatementPaper :statement="projectPreview" /></section>
    <SpecialSettlementPayment v-if="specialSettlementView" :client-id="String(clientId)" :month="initialMonth"
      :period-number="periodNumber" :original-totals="subtotals[0]" @saved="emit('special-payment-saved')" />
    <section v-if="!statementClientView" class="client-subtotals">
      <h4>客户金额小计 <small>当前筛选条件下的全部匹配母订单；不重复累加下级订单</small></h4>
      <el-table :data="subtotalPageRows" border row-key="clientId" empty-text="暂无客户金额">
        <el-table-column prop="clientName" label="客户" min-width="180" />
        <el-table-column prop="projectCount" label="母订单数" width="110" />
        <el-table-column label="不含税总价小计" min-width="180">
          <template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsExclTax)}}</span></template>
        </el-table-column>
        <el-table-column label="含税总价小计" min-width="180">
          <template #default="{row}"><span class="finance-cell">{{formatAmounts(row.totalsInclTax)}}</span></template>
        </el-table-column>
        <el-table-column label="统计情况" min-width="180">
          <template #default="{row}">{{row.incomplete?'部分订单缺少数量或单价，当前为已计算金额小计':'完整'}}</template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="subtotalPage" :page-size="subtotalPageSize" :total="subtotals.length"
        aria-label="客户金额小计分页" :layout="subtotalPageCount > 1 ? 'slot, prev, pager, next, jumper' : 'slot'">
        <span>共 {{subtotalPageCount}} 页，{{subtotals.length}} 条</span>
      </el-pagination>
    </section>
    <DraggableFormDialog v-model="editorVisible" class="customer-finance-dialog" data-auto-draft="off" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="closeEditor" @opened="locateInvoiceRequirement">
      <template #header>
        <DialogFieldSearchHeader class="finance-editor-heading" ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editorTitle" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch">
          <template #actions>
            <span class="finance-editor-project-name">{{ editor.sourceFileName || editor.projectName || '-' }}</span>
            <span class="finance-editor-manager" @mousedown.stop>客户简称：{{ editor.clientShortName || editor.clientName || '未填写' }}</span>
            <span class="finance-editor-manager">客户经理：{{ editor.clientManager || '未分配' }}</span>
          </template>
        </DialogFieldSearchHeader>
        <div v-if="orderNavigation && !localTarget && financeModule === 'translation'" class="finance-sibling-actions" role="group" aria-label="子订单导航">
          <el-button size="small" :title="orderNavigation.previous?.orderNo" :disabled="orderNavigationDisabled || !orderNavigation.previous" @click="navigateOrder(-1)">‹ 上一个同级子订单</el-button>
          <el-button size="small" :title="orderNavigation.next?.orderNo" :disabled="orderNavigationDisabled || !orderNavigation.next" @click="navigateOrder(1)">下一个同级子订单 ›</el-button>
          <el-button size="small" :title="orderNavigation.parent.orderNo" :disabled="orderNavigationDisabled" @click="navigateOrder('parent')">返回上一级订单</el-button>
        </div>
      </template>
      <div ref="editorBody" v-loading="saving || editorLoading" :class="{'finance-invoice-review': invoiceReview}">
        <CustomerFinanceModuleTabs :key="editor.id" v-model="financeModule" module="translation" :client-id="editor.clientId"><template #translation>
        <AppForm ref="formRef" :model="editor" :rules="documentRules" label-position="top" :disabled="saving||!!editor.fixedPricingFrom" class="finance-pricing-form">
          <el-tabs :model-value="showMergedSettlement?'merged':'order'" :class="{'finance-settlement-tabs--single':!mergedSettlement||settlementChild}"
            aria-label="订单结算信息" @update:model-value="settlementTab=$event">
          <el-tab-pane label="本订单情况" name="order">
          <div ref="orderSettlementBody">
          <div class="finance-order-config">
            <section class="finance-pricing-region" data-dialog-field-search-group>
              <h3 class="finance-pricing-region-title" data-dialog-field-search-group-title>{{regionTitle('结算模式')}}</h3>
              <el-radio-group :model-value="editor.paymentMethod" aria-label="结算模式" class="finance-payment-methods" @update:model-value="changeEditorSettlementMode">
                <div v-for="method in paymentMethods" :key="method.value" :data-dialog-field-search-label="method.label">
                  <el-radio :value="method.value">{{method.label}}</el-radio>
                  <p class="finance-payment-method-hint">{{method.hint}}</p>
                </div>
              </el-radio-group>
              <div v-if="editor.clientId">
                <el-button link type="primary" @click="openCustomerFinanceSettings('settings')">{{editor.customerDocumentSources?.paymentMethod && !changedPaymentMethod()?'来自客户管理 → 财务信息 → 笔译 → 对账单设置':'查看客户结算模式设置'}}</el-button>
                <el-tag v-if="editor.customerDocumentSources?.paymentMethod && !changedPaymentMethod()" size="small" type="info">已从客户管理带入</el-tag>
              </div>
            </section>
            <section class="finance-pricing-region" data-dialog-field-search-group>
              <h3 class="finance-pricing-region-title" data-dialog-field-search-group-title>{{regionTitle('计价方式')}}</h3>
              <el-form-item data-dialog-field-search-label="计价方式">
                <el-radio-group aria-label="计价方式" :model-value="editor.priceAggregate ? 'aggregate' : editor.pricingMode" :disabled="pricingModeSwitching||!!editor.fixedPricingFrom" @update:model-value="changePricingMode">
                  <el-radio-button v-if="editor.priceAggregate || editor.children?.length" value="aggregate">子订单汇总</el-radio-button>
                  <el-radio-button v-else value="metric">工作量</el-radio-button>
                  <el-radio-button value="fixed">固定收费</el-radio-button>
                </el-radio-group>
                <small v-if="editor.fixedPricingFrom">随上级订单 {{editor.fixedPricingFrom}} 固定收费</small>
              </el-form-item>
            </section>
            <section class="finance-pricing-region" data-dialog-field-search-group>
              <h3 class="finance-pricing-region-title" data-dialog-field-search-group-title>{{regionTitle('单据需求与账单月份')}}</h3>
              <TranslationDocumentRequirements :model-value="editor" :editable-invoice="editor.paymentMethod==='special'" :persist-statement="localTarget?undefined:saveEditorStatementRequirement"
                @customer-settings="openCustomerFinanceSettings('settings')"
                @update:model-value="updateEditorDocuments" @quotation="linkedQuotationVisible=true" @statement="openEditorStatement" @invoice="openEditorInvoice" />
              <el-form-item label="账单月份">
                <div class="finance-billing-period">
                  <ReadonlyField :model-value="billingPeriodLabel(editor)" source="auto" />
                  <el-button v-if="canWrite && editor.rootId && editor.clientId && !localTarget" @click="billingPeriodVisible=true">调整账期</el-button>
                </div>
                <small>按母订单设置，适用于各级子订单。</small>
              </el-form-item>
            </section>
          </div>
          <section v-if="reviewApplicable || editor.priceAggregate || taxAmountPending || showMotherBillingTotal" class="finance-pricing-region finance-document-review" data-dialog-field-search-group>
            <h4 v-if="reviewApplicable || editor.priceAggregate || taxAmountPending" data-dialog-field-search-group-title>{{regionTitle(reviewApplicable ? '订单单据核对与收费明细' : editor.priceAggregate ? '子订单收费明细' : '收费核对')}}</h4>
            <el-form-item v-if="showMotherBillingTotal" :label="motherBillingTotal.label">
              <ReadonlyField type="textarea" autosize :model-value="formatAmounts(motherBillingTotal.amounts)" source="auto" />
            </el-form-item>
            <el-alert v-if="reviewApplicable || taxAmountPending" :type="orderReviewType" :closable="false">
              <template #title>{{orderReviewMessage}}</template>
              <div v-if="orderReviewIssues.length" class="finance-review-orders">
                <div v-for="{order, reason} in orderReviewIssues" :key="order.id">
                  <el-button v-if="canWrite && !order.fixedPricingFrom" link type="primary" :disabled="saving || editorLoading"
                    @click="openOrderPricing(order)">{{order.orderNo}}</el-button>
                  <span v-else>{{order.orderNo}}</span>
                  <span> · {{reason}}</span>
                </div>
              </div>
            </el-alert>
            <details v-if="reviewApplicable || editor.priceAggregate" :key="editor.id" :open="!!reviewSnapshot.length">
              <summary>{{reviewApplicable ? '查看各级订单单据与价格' : '查看各级订单计价明细'}}</summary>
              <el-table :data="orderPricingReviewRows" row-key="id" size="small" border max-height="360"
                class="finance-order-pricing-review" aria-label="各级订单计价明细">
                <el-table-column prop="orderNo" label="订单号" min-width="160" />
                <template v-if="reviewApplicable">
                  <el-table-column v-for="column in reviewColumns" :key="column.key" :label="column.label" min-width="86">
                    <template #default="{row}">
                      <el-tag v-if="row[column.key]!==reviewRows[0]?.[column.key]" type="warning">{{documentRequirementLabel(row[column.key])}}</el-tag>
                      <span v-else>{{documentRequirementLabel(row[column.key])}}</span>
                    </template>
                  </el-table-column>
                </template>
                <el-table-column label="计费口径" min-width="120">
                  <template #default="{row}">
                    <el-tag v-if="reviewApplicable && row.tax!==reviewRows[0]?.tax" type="warning">{{billingTaxLabel(row.tax)}}</el-tag>
                    <span v-else>{{billingTaxLabel(row.tax)}}</span>
                  </template>
                </el-table-column>
                <el-table-column label="单价" min-width="200">
                  <template #default="{row}">
                    <span v-if="row.fixedPricingFrom">随上级收费</span>
                    <span v-else-if="row.pricingMode==='fixed'">固定收费</span>
                    <el-popover v-else-if="row.priceAggregate && row.prices?.length" trigger="click" :width="320">
                      <template #reference><el-button link type="primary">查看汇总单价</el-button></template>
                      <CustomerAggregatePrices :prices="row.prices" :can-edit="canWrite"
                        @edit-order="openAggregateOrder(editor.rootId,$event)" />
                    </el-popover>
                    <span v-else class="finance-pricing-review-unit">{{reviewUnitPrice(row)}}</span>
                  </template>
                </el-table-column>
                <el-table-column :label="serverDocumentReview ? '拟保存不含税总价' : '已保存不含税总价'" min-width="150"><template #default="{row}">{{formatAmounts(row.totalsExclTax)}}</template></el-table-column>
                <el-table-column :label="serverDocumentReview ? '拟保存含税总价' : '已保存含税总价'" min-width="150"><template #default="{row}">{{formatAmounts(row.totalsInclTax)}}</template></el-table-column>
                <el-table-column label="操作" min-width="100">
                  <template #default="{row}">
                    <span v-if="row.id===editor.id">当前订单</span>
                    <span v-else-if="row.fixedPricingFrom" :title="row.fixedPricingFrom">随上级收费</span>
                    <el-button v-else-if="canWrite" link type="primary" @click="openAggregateOrder(editor.rootId,row.id)">打开订单</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <CustomerFinanceAggregateSummary v-if="editor.priceAggregate" :order="editor" />
            </details>
            <template v-if="reviewSnapshot.length">
              <div v-if="editor.paymentMethod==='special' && reviewRows.some(row=>row.invoice!==reviewRows[0].invoice)" class="finance-document-review-actions">
                <span>统一母订单及各级子订单的发票需求</span>
                <el-button size="small" @click="setUnifiedInvoice(true)">统一为需发票</el-button>
                <el-button size="small" @click="setUnifiedInvoice(false)">统一为无需发票</el-button>
              </div>
              <el-form-item label="保留差异的理由" :error="reviewReasonError">
                <el-input ref="reviewReasonInput" v-model="editor.documentReviewReason" data-screenshot-editor="own" type="textarea" :rows="2" maxlength="2000" show-word-limit placeholder="如需保留差异，请说明原因" />
              </el-form-item>
            </template>
          </section>
          <p v-if="localTarget" class="finance-help">本次财务填写随项目表单一起保存。</p>
          <WordCountDeadlineHint v-if="editorVisible && (editor.pricingMode!=='fixed' || editor.rootId)"
            kind="unit_price" :history-only="editor.pricingMode==='fixed' && editor.id===editor.rootId" :project-id="editor.rootId"
            :matrix="localPaymentParent?.wordCountMatrix || editor.wordCountMatrix"
            :received-at="localPaymentParent?.customerReceptionTime" :manager-id="localPaymentParent?.clientManagerId" :revision="editor.prices" />
          <section v-if="!editor.priceAggregate" class="finance-pricing-region">
          <CustomerTranslationPriceEditor :section-prefix="regionPrefix" compact-actions hide-calculation-summary v-if="editor.pricingMode!=='fixed'" v-model="editor.prices" :language-pair="editor.languagePair" :matrix="editor.wordCountMatrix" :disabled="saving" :reference-prices="referencePrices"><template #before-prices="{row}"><el-form-item label="客户参考价" class="finance-reference-item"><div class="finance-reference-content"><el-button :disabled="!editor.clientId" :type="row?.referenceId?'success':undefined" :plain="!!row?.referenceId" @click="adoptReference(row)">{{hasCustomerRateConflict(row,referencePrices,editor.wordCountMatrix)?'比较并选择客户参考价':row?.referenceId?'重新选择客户参考价':'选择客户参考价'}}</el-button><el-button v-if="editor.clientId" link type="primary" @click="openCustomerFinanceSettings('rates')">{{row?.referenceId?'来自客户管理 → 财务信息 → 笔译 → 客户单价':'打开客户管理的笔译单价'}}</el-button><el-button v-if="row?.referenceId" link @click="stopUsingReference(row)">改用人工单价</el-button><span v-if="hasCustomerRateConflict(row,referencePrices,editor.wordCountMatrix)" class="finance-reference-conflict">当前保留项目单价。可比较后选择采用客户参考价。</span><span v-else>{{referencePrices.length?'按同客户、同语种、同单位、同币种和计价数量选择，保存后生效':'该客户暂无匹配的语种参考价，可在下方直接填写单价'}}</span></div></el-form-item></template><template #price-actions="{row}">
          <div v-if="editor.pricingMode!=='fixed'" class="finance-sync-actions">
            <el-form-item v-if="editor.pricingMode!=='fixed'" label="同步单价"><SyncSameMonthPrices compact v-if="editorVisible" :project-id="editor.rootId" :order-id="editor.id" :source-order-no="editor.orderNo" :client-id="editor.clientId" :version="treeVersion" :month="editor.billingMonth" :disabled="saving||!canSyncEditorPrices||!!localTarget" :prepare="prepareEditorSync" @synced="onSameMonthSynced" /></el-form-item>
          </div>
</template></CustomerTranslationPriceEditor>


          <section class="finance-settlement-section">
            <div class="finance-settlement-heading"><h4>{{regionTitle(editor.pricingMode==='fixed'?'固定收费':'总价与说明')}}</h4><BillingTaxModeField :model-value="editor.billingTaxMode" :order="editor" :disabled="saving||!!editor.fixedPricingFrom" @update:model-value="changeEditorBillingTax" /></div>
            <div class="finance-settlement-row" :class="{'finance-settlement-row--fixed':editor.pricingMode==='fixed'}">
            <div class="finance-settlement-grid" :class="{'finance-settlement-grid--fixed':editor.pricingMode==='fixed'}">
              <el-form-item v-if="editor.pricingMode==='fixed'" label="货币"><el-select v-model="editor.currency" :disabled="!!editor.fixedPricingFrom"><el-option v-for="currency in ['CNY','USD','HKD','EUR','GBP','JPY']" :key="currency" :value="currency" /></el-select></el-form-item>
              <el-form-item :label="projectTotalLabel('不含税')" prop="adjustedTotal" :rules="[{validator:(_rule,_value,callback)=>callback(!editor.fixedPricingFrom&&editor.pricingMode==='fixed'&&!isClearedFinanceForm(editor)&&!hasFixedFeeAmount(editor)?new Error('请填写不含税或含税固定收费'):undefined),trigger:'change'}]"><template #label><span class="finance-total-heading" :class="{'finance-total-heading--filled':hasTotalAmount('excl')}">{{projectTotalLabel('不含税')}}<small>{{editor.pricingMode==='fixed'?editor.currency:calculatedCurrency('excl')}}</small></span></template><div class="finance-total-line"><div v-if="editor.pricingMode!=='fixed'" class="finance-calculated-amount"><small>自动计算</small><ReadonlyField :class="{'finance-amount-filled':Object.keys(calculatedTotals.excl.totals).length>0}" :model-value="calculatedTotal('excl')" source="auto" /></div><div class="finance-adjusted-amount"><small v-if="editor.pricingMode!=='fixed'">调整金额</small><el-input-number v-model="editor.adjustedTotal" :class="{'finance-amount-filled':editor.adjustedTotal!=null&&editor.adjustedTotal!==''}" :disabled="!!editor.fixedPricingFrom || editor.pricingMode!=='fixed' && new Set((editor.prices||[]).map(row=>row.currency)).size>1" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入不含税固定收费':'选填'" /></div></div></el-form-item>
              <el-form-item :label="projectTotalLabel('含税')"><template #label><span class="finance-total-heading" :class="{'finance-total-heading--filled':hasTotalAmount('incl')}">{{projectTotalLabel('含税')}}<small>{{editor.pricingMode==='fixed'?editor.currency:calculatedCurrency('incl')}}</small></span></template><div class="finance-total-line"><div v-if="editor.pricingMode!=='fixed'" class="finance-calculated-amount"><small>自动计算</small><ReadonlyField :class="{'finance-amount-filled':Object.keys(calculatedTotals.incl.totals).length>0}" :model-value="calculatedTotal('incl')" source="auto" /></div><div class="finance-adjusted-amount"><small v-if="editor.pricingMode!=='fixed'">调整金额</small><el-input-number v-model="editor.adjustedTotalInclTax" :disabled="!!editor.fixedPricingFrom" :class="{'finance-amount-filled':editor.adjustedTotalInclTax!=null&&editor.adjustedTotalInclTax!==''}" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入含税固定收费':'选填'" /></div></div></el-form-item>
            </div>
            <div class="finance-notes-grid"><el-form-item label="内部说明"><el-input v-model="editor.explanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item><el-form-item label="客户说明"><el-input v-model="editor.customerExplanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item></div>
            </div>
          </section>

          </section>
          <el-alert v-if="mergedSettlement" class="finance-pricing-region" type="info" :closable="false">
            <template v-if="settlementChild">
              在多单合并结算模式下，子订单不直接结算，请查看母订单的
              <el-button link type="primary" @click="openMotherSettlement">多单合并结算</el-button>。
            </template>
            <template v-else>
              在多单合并结算模式下，单独订单不直接结算/付款，请点击
              <el-button link type="primary" @click="openMergedSettlementTab">多单合并结算</el-button> 查看结算情况。
            </template>
          </el-alert>
          <el-alert v-else-if="independentSettlementChild" class="finance-pricing-region" type="info" :closable="false">
            在母子订单项目中，子订单不直接结算/付款，请在母订单号查看结算情况
            <el-button v-if="editor.rootId" link type="primary" @click="openMotherSettlement">{{editor.documentOrderNo || '打开母订单'}}</el-button>
          </el-alert>
          <el-alert v-if="paymentSummaryError" class="finance-pricing-region" :title="paymentSummaryError" type="warning" :closable="false">
            <el-button link @click="loadPaymentSummary">重新加载</el-button>
          </el-alert>
          <PaymentRegistrationFields
            v-if="!mergedSettlement && !independentSettlementChild && !paymentSummaryLoading && !paymentSummaryError"
            class="finance-pricing-region"
            :section-prefix="regionPrefix"
            v-model="editor"
            :draft-totals="!editor.priceAggregate && (editor.id===editor.rootId || localTarget) ? paymentDraftTotals(editor,calculatedTotals) : null"
            :project-id="editor.rootId"
            :match-orders="settlementChild ? [] : editor.children || []"
            match-label="匹配子订单金额"
            prefix="paymentConfirmation"
            :can-confirm="canManageHr() && !localTarget && !!editor.paymentVersion"
            :confirm-disabled="editorDirty || saving || documentReviewOutstanding"
            @confirm-payment="confirmPayment"
          >
            <template #actions><el-button :disabled="!editor.rootId||saving" @click="openLinkedPayment">打开发票、查账与追账</el-button></template>
            <template v-if="!editor.rootId" #footer><p class="finance-help">保存项目后可打开完整付款情况。</p></template>
          </PaymentRegistrationFields>
          </div>
          </el-tab-pane>
          <el-tab-pane v-if="mergedSettlement && !settlementChild" label="多单合并结算" name="merged">
        <section v-if="showMergedSettlement" v-loading="paymentSummaryLoading" class="finance-pricing-region finance-order-summary" data-dialog-field-search-group>
            <h3 class="finance-pricing-region-title" data-dialog-field-search-group-title>多订单·费用汇总</h3>
            <el-alert v-if="paymentSummaryError" :title="paymentSummaryError" type="warning" :closable="false">
              <el-button link @click="loadPaymentSummary">重新加载</el-button>
            </el-alert>
            <div v-if="!paymentSummaryError" class="finance-merged-totals">
              <el-alert v-if="paymentSummary?.pending" title="汇总金额待核对，请补齐金额后再登记全款。" type="warning" :closable="false" />
              <div class="finance-settlement-grid finance-payment-totals">
                <el-form-item :label="mergedTotalLabel" class="finance-merged-total"><ReadonlyField type="textarea" autosize :model-value="formatAmounts(paymentSummary?.billingTotals)" source="auto" /></el-form-item>
                <el-form-item :label="`${paymentSummaryTitle}不含税总价`"><ReadonlyField type="textarea" autosize :model-value="formatAmounts(paymentSummary?.totalsExclTax)" source="auto" /></el-form-item>
                <el-form-item :label="`${paymentSummaryTitle}含税总价`"><ReadonlyField type="textarea" autosize :model-value="formatAmounts(paymentSummary?.totalsInclTax)" source="auto" /></el-form-item>
              </div>
              <el-alert v-if="paymentSummaryDifferences.length" class="finance-calculation-hint" type="info" title="费用总价与含税总价存在差额" :closable="false" show-icon>
                <div v-for="difference in paymentSummaryDifferences" :key="difference.currency">
                  {{ difference.currency }}：费用总价比含税总价{{ difference.direction }} {{ difference.amount }}
                </div>
                <div>费用总价按各订单所选的计费口径汇总，可作为全款登记的参考金额。</div>
              </el-alert>
              <div v-if="paymentSummary?.internalNotes?.length || paymentSummary?.customerNotes?.length" class="finance-settlement-grid finance-summary-notes">
                <el-form-item v-if="paymentSummary.internalNotes?.length" :label="`${paymentSummaryTitle}内部说明`"><ReadonlyField type="textarea" :autosize="{minRows:1,maxRows:5}" :model-value="paymentSummary.internalNotes.join('\n')" source="auto" /></el-form-item>
                <el-form-item v-if="paymentSummary.customerNotes?.length" :label="`${paymentSummaryTitle}客户说明`"><ReadonlyField type="textarea" :autosize="{minRows:1,maxRows:5}" :model-value="paymentSummary.customerNotes.join('\n')" source="auto" /></el-form-item>
              </div>
            </div>
            <el-alert v-if="!paymentSummaryError && !paymentSummaryLoading && mergedReviewRows.length > 1"
              :type="mergedReviewIssue ? 'warning' : 'success'" :closable="false" :title="mergedReviewMessage" />
            <small v-if="canWrite && !localTarget" class="finance-help">下拉选项更改后立即保存；汇总订单的计费口径随子订单更新。</small>
            <el-alert v-if="mergedEditError" type="error" :title="mergedEditError" :closable="false" />
            <el-table v-if="!paymentSummaryError" :data="mergedReviewRows" row-key="id" border max-height="360"
              class="finance-merged-orders" aria-label="合并结算订单">
              <el-table-column prop="orderNo" label="订单号" min-width="145" />
              <el-table-column prop="projectName" label="项目名称" min-width="165" show-overflow-tooltip />
              <el-table-column v-for="column in mergedReviewColumns" :key="column.key" :label="column.label"
                :min-width="column.key==='tax' ? 155 : 105">
                <template #default="{ row }">
                  <el-select v-if="canEditMergedField(row,column)" size="small" :model-value="row[column.key]"
                    :placeholder="column.format(row[column.key])"
                    :aria-label="`${row.orderNo} ${column.label}`"
                    :class="{'finance-merged-difference':isMergedDifference(row,column)}"
                    :disabled="saving || paymentSummaryLoading"
                    @change="saveMergedField(row,column,$event)">
                    <el-option v-for="value in mergedFieldChoices(row,column)" :key="String(value)"
                      :value="value" :label="column.format(value)" />
                  </el-select>
                  <template v-else>
                    <el-tag v-if="isMergedDifference(row,column)" type="warning">{{column.format(row[column.key])}}</el-tag>
                    <span v-else>{{column.format(row[column.key])}}</span>
                    <el-button v-if="column.key==='tax' && canWrite && !localTarget && !row.fixedPricingFrom &&
                      !row.priceAggregate && (mergedReviewIssue || row.tax==null)"
                      link type="primary" :disabled="saving" @click="openOrderPricing(row)">修改价格</el-button>
                  </template>
                </template>
              </el-table-column>
              <el-table-column v-for="column in settlementAmountColumns" :key="column.key" :label="column.label" min-width="130">
                <template #default="{row}">{{formatAmounts(row[column.key])}}</template>
              </el-table-column>
              <el-table-column label="付款状态" min-width="105"><template #default="{row}">{{row.id===row.rootId ? paymentStatusLabel(row) : '—'}}</template></el-table-column>
              <el-table-column label="实付金额" min-width="130">
                <template #default="{row}">{{row.id!==row.rootId||row.paymentStatus==='unpaid'||row.paymentActualTotal==null?'—':`${row.paymentCurrency} ${row.paymentActualTotal}`}}</template>
              </el-table-column>
            </el-table>
          </section>
          <PaymentRegistrationFields
            v-if="showMergedSettlement && !paymentSummaryLoading && !paymentSummaryError"
            class="finance-pricing-region"
            section-prefix="多订单 · "
            v-model="editor"
            :draft-totals="paymentSummaryTotals"
            summary-label="订单汇总"
            :project-id="editor.rootId"
            :match-orders="paymentSummary.orders"
            match-label="匹配各订单金额"
            prefix="paymentConfirmation"
            :can-confirm="canManageHr() && !localTarget && !!editor.paymentVersion"
            :confirm-disabled="editorDirty || saving || documentReviewOutstanding"
            @confirm-payment="confirmPayment"
          >
            <template #actions><el-button :disabled="!editor.rootId||saving" @click="openLinkedPayment">打开发票、查账与追账</el-button></template>
          </PaymentRegistrationFields>
          </el-tab-pane>
          </el-tabs>
        </AppForm>

        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button v-if="canWrite&&financeModule==='translation'&&!editor.fixedPricingFrom&&!showMergedSettlement" type="danger" plain :disabled="saving||editorLoading" @click="clearAllFinance">清空</el-button><el-button :disabled="saving" @click="closeEditor()">取消</el-button><el-button v-if="financeModule==='translation'" :type="editorDirty?'primary':'default'" :disabled="editorLoading||!!editor.fixedPricingFrom" :loading="saving" @click="save()">保存</el-button></template>
    </DraggableFormDialog>
    <OrderBillingPeriodDialog v-if="editorVisible && billingPeriodVisible" :project-id="editor.rootId"
      :month="editor.billingMonth" :version="treeVersion" @close="billingPeriodVisible=false" @saved="onBillingPeriodSaved" />
    <CustomerReferencePriceDialog v-if="editorVisible" ref="referencePickerRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" :matrix="editor.wordCountMatrix" :language-pair="editor.languagePair" :refresh-project="rebaseEditorAfterLibrary" />
    <SubOrderStructureDialog v-model="structureVisible" :project-id="structureProjectId" :selected-order-no="structureOrderNo" />
    <DraggableFormDialog v-model="historyVisible" append-to-body class="customer-finance-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" :title="`财务修改记录 · ${historyOrder?.orderNo||''}`"><TranslationFinanceHistory v-if="historyVisible&&historyOrder" :project-id="historyOrder.rootId" :order-id="historyOrder.id" /><template #footer><el-button @click="historyVisible=false">关闭</el-button></template></DraggableFormDialog>
  </el-card>
</template>

<script setup>
import { translationSettlementModeLabels as settlementModeLabels, translationSettlementMode as paymentMethodFor } from '@/utils/settlementModes'
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import CustomerStatementPaper from '@/components/common/CustomerStatementPaper.vue'
import StatementPeriodSelect from '@/components/common/StatementPeriodSelect.vue'
import WordCountDeadlineHint from './components/WordCountDeadlineHint.vue'
import {previewStatementProjects,getStatementPreference} from '@/api/customerStatements'
import {clientManagementTarget} from '@/utils/clientManagementWindow'
import {calculateTaxOrderPriceTree} from '@/utils/translationQuantityBasis'
import CustomerFinanceModuleTabs from '@/components/common/CustomerFinanceModuleTabs.vue'
import ProjectPaymentDialog from '@/components/common/ProjectPaymentDialog.vue'
import ProjectInvoiceDialog from '@/components/common/ProjectInvoiceDialog.vue'
import TranslationOrderDetailPopover from '@/components/common/TranslationOrderDetailPopover.vue'
import CustomerFinanceTableCell from '@/components/common/CustomerFinanceTableCell.vue'
import {getProject} from '@/api/projects'
import BillingTaxModeField from '@/components/common/BillingTaxModeField.vue'
import {requestPricingModeSwitch} from '@/utils/pricingModeSwitch'
import {billingTaxLabel,effectiveBillingTaxMode,hasFixedFeeAmount} from '@/utils/billingTaxMode'
import {saveCustomerFinanceTable} from '@/api/translationCustomerFinance'
import {useFinanceTableEditing} from '@/composables/useFinanceTableEditing'
import {financeDisplayIndexes,financeOrderPageRows,financeParentOrderRows,indexFinanceClientOrders,sliceFinanceClientOrders} from '@/utils/financeClientOrderPagination'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { getWordCountMatrixListSummary } from '@/utils/wordCountMatrix'
import PaymentRegistrationFields from '@/components/common/PaymentRegistrationFields.vue'
import SpecialSettlementPayment from '@/components/common/SpecialSettlementPayment.vue'
import MonthlyPaymentProjectsDialog from '@/components/common/MonthlyPaymentProjectsDialog.vue'
import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '@/utils/paymentDetails'
import {paymentStatusLabel,paymentStatusFilterOptions,fullPaymentMismatchOption,paymentConfirmationForm,paymentConfirmationPayload,paymentChangeEvent,notifyPaymentChanged,connectPaymentSync} from '@/utils/paymentConfirmation'
import {paymentDraftTotals} from '@/utils/paymentDraftTotals'
import {clearFinanceForm,isClearedFinanceForm} from '@/utils/clearFinanceForm'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import TranslationDocumentRequirements from '@/components/common/TranslationDocumentRequirements.vue'
import {notifyStatementCustomerSync} from '@/utils/confirmStatementRequirement'
import {documentNotesForm,invoiceRequirement,documentConsistencyRows,documentConsistencySnapshot,documentRequirementLabel} from '@/utils/documentRequirements'
import CustomerStatementDialog from '@/components/common/CustomerStatementDialog.vue'
import {taxPriceForm,taxPriceSummary} from '@/utils/taxPrices'
import {copySavedValue} from '@/utils/savedDataMerge'
import { computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import SubOrderStructureDialog from './components/SubOrderStructureDialog.vue'
import { customerFinanceSort, getCustomerTranslationRates, getCustomerFinanceProject, getCustomerFinancePage, getFinancePaymentSummary, getFinanceRowFilterOptions, saveCustomerFinanceProject, confirmProjectPayment, setProjectStatementRequired, saveSpecialSettlement } from '@/api/translationCustomerFinance'
import { getProjectStatusLabel, getProjectStatusOptions } from '@/utils/projectStatus'
import { canManageHr, hasPermission } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { useTableColumns } from '@/composables/useTableColumns'
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { scrollFormTarget } from '@/utils/formNavigation'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import CustomerDepartmentManagerSelect from '@/components/common/CustomerDepartmentManagerSelect.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CustomerPriceFields from './components/CustomerPriceFields.vue'
import CustomerTranslationPriceEditor from '@/components/common/CustomerTranslationPriceEditor.vue'
import TranslationFinanceHistory from '@/components/common/TranslationFinanceHistory.vue'
import {orderStatementMonth} from '@/utils/statementRequirementMonth'
import {customerStatementContext} from '@/utils/customerStatementContext'
import {financeOrderLevel} from '@/utils/financeOrderLevel'
import CustomerFinanceAggregateSummary from '@/components/common/CustomerFinanceAggregateSummary.vue'
import CustomerAggregatePrices from '@/components/common/CustomerAggregatePrices.vue'
import CustomerStatementRequiredToggle from '@/components/common/CustomerStatementRequiredToggle.vue'
import CustomerReferencePriceDialog from '@/components/common/CustomerReferencePriceDialog.vue'
import OrderBillingPeriodDialog from '@/components/common/OrderBillingPeriodDialog.vue'
import {expectedOrderPrices,replaceMatchedReference,fillCustomerReferencePrice,customerPricesForDirections,hasCustomerRateConflict} from '@/utils/customerRateMatching'
import SyncSameMonthPrices from '@/components/common/SyncSameMonthPrices.vue'
import {basisLabel,calculateOrderPriceTree,resolveRateQuantity} from '@/utils/translationQuantityBasis'
import {newCustomerRate,ratePayload,referenceDraft,defaultRateMetric} from '@/utils/customerTranslationRates'

const columns = [
  {key:'orderNo',label:'订单号',width:124},{key:'projectName',label:'项目名称',width:240},
  {key:'clientShortName',label:'客户简称',width:105},{key:'clientManager',label:'客户经理',width:105},{key:'projectStatus',label:'项目状态',width:110},
  {key:'languagePair',label:'翻译方向',width:136},{key:'wordCount',label:'字数统计',width:96},
  {key:'pricingMode',label:'计价方式',width:110},{key:'billingMonth',label:'账单月份',width:96},{key:'unitPrice',label:'单价',width:160},{key:'totalPrice',label:'不含税总价',width:120},{key:'totalInclTax',label:'含税总价',width:120},
  {key:'paymentMethod',label:'结算模式',width:170},{key:'statementRequired',label:'报价单/对账单',width:148},{key:'explanation',label:'说明',width:150},{key:'paymentStatus',label:'付款状态',width:88},
]
const defaultColumnKeys=columns.map(item=>item.key)
const previousColumnKeys=defaultColumnKeys.filter(key=>!['clientManager','paymentMethod'].includes(key))
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('translation-customer-finance',columns,defaultColumnKeys,{
  legacyDefaultKeys:[
    defaultColumnKeys.filter(key=>key!=='paymentMethod'),
    previousColumnKeys,
    previousColumnKeys.filter(key=>key!=='paymentStatus'),
    previousColumnKeys.filter(key=>!['statementRequired','paymentStatus'].includes(key)),
  ],
})
const tableFields=['pricingMode','billingMonth','unitPrice','totalPrice','totalInclTax','explanation']
const visibleColumns=computed(()=>columns.filter(item=>props.statementClientView?!['clientManager','languagePair','wordCount','billingMonth','paymentMethod'].includes(item.key):isVisible(item.key)))
const fixedStorageKey=`finance-fixed-columns:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const fixedColumns=ref((()=>{try{return JSON.parse(localStorage.getItem(fixedStorageKey)||'[]').filter(key=>['orderNo','projectName'].includes(key))}catch{return []}})())
function toggleFixedColumn(key){fixedColumns.value=fixedColumns.value.includes(key)?fixedColumns.value.filter(value=>value!==key):[...fixedColumns.value,key];localStorage.setItem(fixedStorageKey,JSON.stringify(fixedColumns.value))}

const statuses=getProjectStatusOptions('translation'),canWrite=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const emit=defineEmits(['saved','document-requirements-saved','special-payment-saved','statement-selection-change'])
const props=defineProps({clientId:{type:[String,Number],default:''},clientIds:{type:Array,default:()=>[]},statementPreview:Function,editorOnly:Boolean,clientScope:Boolean,collapsible:Boolean,statementClientView:Boolean,periodNumber:Number,settlementScope:String,requireStatementForSelection:Boolean,previewMode:String,previewMonths:Array,initialMonth:String,managerQuery:{type:Object,default:()=>({})}})
const statementTableRef=ref(),statementSelected=ref([]),projectPreview=ref(null),previewLoading=ref(false)
const specialSettlementView=computed(()=>props.statementClientView&&props.settlementScope==='special')
const financeCollapsed=ref(props.collapsible)
const isCollapsed=computed(()=>props.collapsible&&financeCollapsed.value)
async function toggleFinancePanel(){
  financeCollapsed.value=!financeCollapsed.value
  if(!isCollapsed.value){
    await nextTick()
    statementTableRef.value?.doLayout()
  }
}
function canSelectStatementProject(row){return !row.fixedPricingFrom&&(!props.requireStatementForSelection||row.statementRequired===true)}
async function statementSelection({flush=true,signal}={}){
  if(flush&&!await tableEditing.flush())throw new Error('请先处理未保存的内容')
  if(statementSelected.value.length)return statementSelected.value.filter(canSelectStatementProject).map(row=>row.id)
  const requiredFilter = {settlement_scope:props.settlementScope,statement_required:props.requireStatementForSelection?true:undefined}
  const ids=new Set()
  const months=props.previewMonths?.length?props.previewMonths:[filters.month]
  for(const month of months){let skip=0;while(true){const data=await getCustomerFinancePage({...financeParams(),...requiredFilter,billing_month:month||undefined,skip,limit:100},{signal});for(const row of data.items||[])ids.add(row.id);skip+=100;if(skip>=data.total||!data.items?.length)break}}
  return [...ids]
}
async function previewProjects(){
  previewLoading.value=true
  try{const order_ids=await statementSelection();projectPreview.value=props.statementPreview?await props.statementPreview(order_ids):await previewStatementProjects({period_number:props.periodNumber,settlement_scope:props.settlementScope,client_id:props.clientId,month:filters.month,months:props.previewMonths,mode:props.previewMode||'children',order_ids})}
  catch(e){ElMessage.error(getLocalizedErrorMessage(e,'对账单预览失败'))}
  finally{previewLoading.value=false}
}
const financeModule=ref('translation')
const financePaymentSource=`finance-editor-${Math.random().toString(36).slice(2)}`
const paymentContextId=ref('')
const paymentVisible=ref(false),quotationVisible=ref(false),statementVisible=ref(false),statementContext=ref(null)
const specialStatementVisible=ref(false),specialStatementContext=ref(null)
const backupStatementVisible=ref(false)
const invoiceVisible=ref(false),invoiceContext=ref({})
const paymentScopeOrder=ref(null)
const structureVisible = ref(false)
const structureProjectId = ref('')
const structureOrderNo = ref('')

function openOrderStructure(row) {
  structureProjectId.value = row.rootId || row.id
  structureOrderNo.value = row.orderNo
  structureVisible.value = true
}

function financeRowActions(row){
  const structure = {command:'structure',label:'子订单结构'}
  if(paymentMethodFor(row)==='special')return [
    {command:'special',label:'特殊结算',disabled:!row.clientId},
    {command:'history',label:'修改记录'},structure,
  ]
  if(row.fixedPricingFrom)return [structure,{command:'history',label:'修改记录'}]
  const actions = [
    {command:'statement',label:'对账单',disabled:!row.clientId},
    {command:'invoice',label:'发票'},
    {command:'history',label:'修改记录'},
    structure,
  ]
  if(canWrite)actions.unshift({command:'price',label:'价格与付款',disabled:editorLoading.value})
  return actions
}
function handleFinanceRowAction(row,command){
  if(command==='structure')return openOrderStructure(row)
  if(command==='history'){historyOrder.value=row;historyVisible.value=true;return}
  if(command==='special'){
    const context=customerStatementContext(row)
    if(!context){ElMessage.warning('请先确认客户及账单月份');return}
    return openStatementVariant('special',{...context,month:row.billingMonth||context.month,period:row.settlementPeriodNumber})
  }
  if(row.fixedPricingFrom)return
  if(command==='price')return openEditor(row)
  if(command==='statement')return openRowStatement(row)
  if(command==='invoice'){paymentScopeOrder.value=row;paymentVisible.value=true}
}
function openEditorInvoice(){
  const order=editor.value
  invoiceContext.value={
    projectId:order.rootId,orderId:localTarget.value?undefined:order.id,
    order:localTarget.value?undefined:order,level:financeOrderLevel(order),
    preview:{orderNo:order.orderNo,clientName:order.clientShortName,required:invoiceRequirement(order),totals:Object.fromEntries(paymentDraftTotals(order,calculatedTotals.value).filter(item=>item.key.startsWith('billing:')).map(item=>[item.currency,item.amount])),note:order.documentNotes?.invoice||''},
  }
  invoiceVisible.value=true
}
function onInvoiceSaved(result){if(editor.value.rootId===result.projectId&&editor.value.paymentVersion===result.previousPaymentVersion)editor.value.paymentVersion=result.paymentVersion;emit('saved');if(!props.editorOnly)void load()}
function openStandardStatement(context=null){
  backupStatementVisible.value=false
  specialStatementVisible.value=false
  statementContext.value=context
  statementVisible.value=true
}
function openStatementVariant(variant,context=null){
  statementVisible.value=false
  backupStatementVisible.value=variant==='backup'
  specialStatementContext.value=context
  specialStatementVisible.value=variant==='special'
}
function openRowStatement(row){
  const context=customerStatementContext(row)
  if(!context){ElMessage.warning('请先确认客户及账单月份');return}
  openStandardStatement(context)
  if(row.statementRequired===false){
    ElMessage.warning(`${row.orderNo} 已标为「无需对账单」。如需纳入，请在客户项目的对账单列重新确认。`)
  }
}
function openInvoiceStatement(row){
  const context=customerStatementContext(row)
  if(!context){ElMessage.warning('请先确认客户及账单月份');return}
  const links=(row.statementStatus||[]).filter(board=>board.clientId===row.clientId&&board.months?.includes(context.month))
  const period=row.settlementPeriodNumber??row.billingPeriod?.number
  const samePeriod=links.filter(board=>board.periodNumber===period)
  const board=samePeriod.length===1?samePeriod[0]:links.length===1?links[0]:null
  openStandardStatement({...context,period:board?.periodNumber??period,boardId:board?.boardId})
}
const filters=reactive({clientOrderCount:'',keyword:'',projectStatus:[],paymentStatus:'',statementRequired:[],paymentMethod:'',billingPeriod:undefined,pricingMode:'',client:'',month:props.initialMonth||'',manager:'',missingWordCount:false,missingUnitPrice:false,missingTotal:''}),rows=ref([]),subtotals=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),advancedVisible=ref(false)
const subtotalPageSize = 10
const subtotalPage = ref(1)
const subtotalPageCount = computed(() => Math.ceil(subtotals.value.length / subtotalPageSize))
const subtotalPageRows = computed(() => {
  const start = (subtotalPage.value - 1) * subtotalPageSize
  return subtotals.value.slice(start, start + subtotalPageSize)
})
watch(subtotalPageCount, count => {
  subtotalPage.value = Math.min(subtotalPage.value, Math.max(1, count))
})
const appliedBillingMonth=ref(filters.month)
const clientFilterOptions=ref([]),directionFilterOptions=ref([])
Object.assign(filters,{clientShortName:'',languagePair:''})
const headerFilterDefinitions={
  ...(!props.statementClientView?{
    clientShortName:{key:'clientShortName',label:'客户简称',type:'select',multiple:false,options:()=>clientFilterOptions.value},
    languagePair:{key:'languagePair',label:'翻译方向',type:'select',multiple:false,headerWidth:320,options:()=>directionFilterOptions.value},
  }:{}),
  paymentStatus:{key:'paymentStatus',label:'付款状态',type:'select',multiple:false,options:[...paymentStatusFilterOptions,fullPaymentMismatchOption]},
  statementRequired:{key:'statementRequired',label:props.statementClientView?'对账单':'报价单/对账单',type:'select',options:[
    {value:'required',label:'需对账单'},{value:'not_required',label:'无需对账单'},
    ...(!props.statementClientView?[
      {value:'invoice_required',label:'需发票'},{value:'invoice_not_required',label:'无需发票'},
      {value:'quotation_required',label:'需报价单'},{value:'quotation_not_required',label:'无需报价单'},
    ]:[]),
  ]},
  paymentMethod:{key:'paymentMethod',label:'结算模式',type:'select',multiple:false,options:()=>paymentMethods},
  projectStatus:{key:'projectStatus',label:'项目状态',type:'select',options:statuses},
  pricingMode:{key:'pricingMode',label:'计价方式',type:'select',multiple:false,options:[{value:'metric',label:'工作量'},{value:'fixed',label:'固定收费'},{value:'aggregate',label:'子订单汇总'}]},
}
const tableEditing=useFinanceTableEditing(onTablePriceSaved)
watch(rows,values=>tableEditing.syncRows(values),{flush:'sync'})
const clientGroups=ref([]),groupOrderTotal=ref(0),collapsedClients=ref([]),childPagination=ref(false)
const orderDisplayOffset = ref(0)
const childOrdersExpanded=ref(true)
const orderExpansionOverrides=ref(new Set())
const isOrderExpanded=id=>childOrdersExpanded.value!==orderExpansionOverrides.value.has(id)
const financeChildOrdersLabel=(row,action)=>`${action} ${row.orderNo} 的子订单${row.childOrderCount ? `（${row.childOrderCount} 条）` : ''}`
const clientOrderPageSize=10,clientOrderPages=ref({})
const clientOrderGroups=computed(()=>{
  const rootsByClient=new Map()
  for(const row of rows.value){
    const roots=rootsByClient.get(row.clientGroupKey)||[]
    roots.push(row)
    rootsByClient.set(row.clientGroupKey,roots)
  }
  return clientGroups.value.map(group=>{
    const roots=rootsByClient.get(group.key)||[]
    return {...group,...indexFinanceClientOrders(roots,isOrderExpanded)}
  })
})
const tableRows=computed(()=>{
  if(filters.clientOrderCount!=='multiple'){
    if(props.statementClientView)return rows.value
    return childPagination.value?financeOrderPageRows(rows.value):financeParentOrderRows(rows.value)
  }
  return clientOrderGroups.value.map(group=>{
    const orderTotal=group.total
    const pageCount=Math.ceil(orderTotal/clientOrderPageSize)
    const currentPage=Math.min(clientOrderPages.value[group.key]||1,pageCount||1)
    const collapsed=collapsedClients.value.includes(group.key)
    const displayOffset=(currentPage-1)*clientOrderPageSize
    const children=collapsed?[]:financeOrderPageRows(sliceFinanceClientOrders(group.orders,currentPage,clientOrderPageSize))
    return {id:'client-group:'+group.key,_clientGroup:true,groupKey:group.key,clientName:group.name,
      orderTotal,pageCount,currentPage,collapsed,displayOffset,children}
  })
})
const displayIndexes = computed(() => {
  if(filters.clientOrderCount!=='multiple') return financeDisplayIndexes(tableRows.value, orderDisplayOffset.value)
  const indexes = new Map()
  for(const group of tableRows.value) financeDisplayIndexes(group.children, group.displayOffset, indexes)
  return indexes
})
const statementExpandAll = ref(true)
const statementExpansionOverrides = ref(new Set())
const statementParentIds = computed(() => {
  const ids = []
  function visit(nodes) {
    for (const node of nodes) {
      if (!node.children?.length) continue
      ids.push(node.id)
      visit(node.children)
    }
  }
  if (props.statementClientView) visit(tableRows.value)
  return ids
})
const statementExpandedIds = computed(() => statementParentIds.value.filter(
  id => statementExpandAll.value !== statementExpansionOverrides.value.has(id)
))
function toggleStatementChildren() {
  statementExpandAll.value = !statementExpandedIds.value.length
  statementExpansionOverrides.value.clear()
}
function onStatementExpandChange(row, expanded) {
  if (!props.statementClientView || typeof expanded !== 'boolean') return
  if (expanded === statementExpandAll.value) statementExpansionOverrides.value.delete(row.id)
  else statementExpansionOverrides.value.add(row.id)
}
const orderTree = computed(() => {
  const rows = new Map()
  let width = 92
  const step = 14
  const line = (level, kind) => ({ level, kind, position: { '--finance-tree-x': `${9 + level * step}px` } })
  function visit(siblings, continuations = []) {
    siblings.forEach((row, index) => {
      if (row._clientGroup) {
        visit(row.children)
        return
      }
      const level = continuations.length
      const hasNext = index < siblings.length - 1
      const lines = continuations.flatMap((continues, ancestor) => {
        if (ancestor === level - 1) return [line(ancestor, hasNext ? 'branch' : 'end')]
        return continues ? [line(ancestor, 'through')] : []
      })
      if (row.children?.length) lines.push(line(level, 'start'))
      rows.set(row.id, { indent: { paddingInlineStart: `${step * level}px` }, lines })
      width = Math.max(width, 64 + step * level)
      if (row.children?.length) visit(row.children, [...continuations, hasNext])
    })
  }
  if (!props.statementClientView) visit(tableRows.value)
  return { rows, width }
})
async function changeClientOrderPage(key,nextPage){
  if(await tableEditing.flush())clientOrderPages.value={...clientOrderPages.value,[key]:nextPage}
}
function clientGroupSpan({row,columnIndex}){if(row._clientGroup)return columnIndex===0?[1,visibleColumns.value.length+2]:[0,0]}
async function toggleClientGroup(key){if(!await tableEditing.flush())return;collapsedClients.value=collapsedClients.value.includes(key)?collapsedClients.value.filter(value=>value!==key):[...collapsedClients.value,key]}
async function collapseClientGroups(collapse){if(!await tableEditing.flush())return;collapsedClients.value=collapse?clientGroups.value.map(group=>group.key):[]}

const tableError=computed(()=>[...tableEditing.states.values()].find(state=>state.error)?.error||'')
async function discardTableDrafts(){try{await ElMessageBox.confirm('放弃尚未保存的单元格内容并重新加载？','重新加载',{type:'warning'})}catch{return}tableEditing.discard();await load({fromTable:true})}
const selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const managerScope=ref(props.clientScope?'all':'self'),managerDraftScope=ref(props.clientScope?'all':'self'),managerIds=ref([]),managerDraftIds=ref([]),managerPickerVisible=ref(false),managerNames=ref({})
function cacheManagers(people){managerNames.value={...managerNames.value,...Object.fromEntries(people.map(person=>[person.id,`${person.name}${person.username&&person.username!==person.name?`（${person.username}）`:''}`]))}}
const managerLabel=computed(()=>managerScope.value==='self'?`本人（${selfName}）`:managerScope.value==='name'?`指定（${managerIds.value.length}人）：${managerIds.value.map(id=>managerNames.value[id]||'已选人员').join('、')}`:'不指定人（全部订单）')
const activeManagerQuery = computed(() => ({
  manager_ids: managerScope.value === 'name' ? managerIds.value : undefined,
  only_mine: managerScope.value === 'self',
}))
watch(managerPickerVisible,visible=>{if(visible){managerDraftScope.value=managerScope.value;managerDraftIds.value=[...managerIds.value]}})
function applyManager(){
  const scope=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value
  const ids=scope==='name'?[...managerDraftIds.value]:[]
  if(scope!==managerScope.value||ids.length!==managerIds.value.length||ids.some(id=>!managerIds.value.includes(id)))clearRowFilters()
  managerScope.value=scope
  managerIds.value=ids
  filters.manager=''
  managerPickerVisible.value=false
  search()
}
function clearRowFilters(){filters.clientShortName='';filters.languagePair=''}
watch(()=>[filters.month,activeManagerQuery.value,props.clientId,props.clientIds],async ([month,manager,clientId,clientIds],_,onCleanup)=>{
  if(props.editorOnly||props.statementClientView)return
  const request=new AbortController()
  onCleanup(()=>request.abort())
  clientFilterOptions.value=[]
  directionFilterOptions.value=[]
  try{
    const data=await getFinanceRowFilterOptions({
      billing_month:month||undefined,client_id:clientId||undefined,
      client_ids:clientIds.length?clientIds:undefined,...manager,
    },request.signal)
    if(request.signal.aborted)return
    clientFilterOptions.value=data.clients.map(({id,name,code})=>({value:id,label:code?`${name}（${code}）`:name}))
    directionFilterOptions.value=data.directions.map(direction=>({value:direction,label:direction}))
  }catch(e){
    if(!request.signal.aborted)ElMessage.error(getLocalizedErrorMessage(e,'客户和翻译方向选项加载失败'))
  }
},{immediate:true})
const advancedCount=computed(()=>Number(filters.projectStatus.length>0)+Number(!!filters.client.trim())+Number(filters.missingWordCount)+Number(filters.missingUnitPrice)+Number(!!filters.missingTotal)+Number(!!filters.billingPeriod))
function clearAdvanced(){filters.projectStatus=[];filters.client='';filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';filters.billingPeriod=undefined;search()}
let timer,controller,sequence=0,disposed=false
const financeSort=ref()
function documentFilterValue(required, notRequired){
  const selected=filters.statementRequired
  if(!Array.isArray(selected))return undefined
  return selected.includes(required)===selected.includes(notRequired)?undefined:selected.includes(required)
}
function financeParams(){
  const invoiceRequired=documentFilterValue('invoice_required','invoice_not_required')
  const clientIds=filters.clientShortName?[filters.clientShortName]:props.clientIds
  return {
    period_number:props.periodNumber??(typeof filters.billingPeriod==='number'?filters.billingPeriod:undefined),
    unassigned_period:filters.billingPeriod==='unassigned'||undefined,
    settlement_scope:props.settlementScope,sort:financeSort.value,include_payment_status:true,
    payment_status:filters.paymentStatus||undefined,statement_required:documentFilterValue('required','not_required'),
    quotation_required:documentFilterValue('quotation_required','quotation_not_required'),
    invoice_required:invoiceRequired===undefined?undefined:invoiceRequired?'yes':'no',
    settlement_mode:filters.paymentMethod||undefined,pricing_mode:filters.pricingMode||undefined,
    client_order_count:filters.clientOrderCount||undefined,
    client_id:props.statementClientView?undefined:props.clientId||undefined,
    client_ids:props.statementClientView&&props.clientId?[props.clientId]:clientIds.length?clientIds:undefined,
    keyword:filters.keyword.trim()||undefined,project_statuses:filters.projectStatus.length?filters.projectStatus:undefined,
    client:filters.client.trim()||undefined,language_direction:filters.languagePair||undefined,billing_month:filters.month||undefined,
    ...activeManagerQuery.value,...(props.statementClientView?props.managerQuery:{}),
    missing_word_count:filters.missingWordCount||undefined,missing_unit_price:filters.missingUnitPrice||undefined,
    missing_total:filters.missingTotal||undefined,
  }
}
async function load(options={}){
  if(editorLoading.value)return
  if(!options?.fromTable&&!options?.skipFlush&&!await tableEditing.flush()){
    // The row editor keeps drafts by order ID while the main list is filtered or paginated.
    if(props.statementClientView)return false
  }
  const current=++sequence;controller?.abort();controller=new AbortController();if(!options?.fromTable)loading.value=true;error.value=''
  try{
    const params=financeParams()
    const paginateChildren=(childOrdersExpanded.value||orderExpansionOverrides.value.size>0)&&!props.statementClientView&&filters.clientOrderCount!=='multiple'
    const data=await getCustomerFinancePage({...params,paginate_children:paginateChildren,count_parent_orders:paginateChildren,
      expand_all_orders:paginateChildren?childOrdersExpanded.value:undefined,
      order_expansion_ids:paginateChildren?[...orderExpansionOverrides.value]:undefined,
      skip:(page.value-1)*10,limit:10},{signal:controller.signal})
    if(current===sequence){
      appliedBillingMonth.value=params.billing_month||''
      childPagination.value=data.paginationUnit==='child_orders'
      orderDisplayOffset.value=data.displayOffset ?? 0
      rows.value=data.items||[];subtotals.value=data.clientSubtotals||[];total.value=data.total||0;clientGroups.value=data.clientGroups||[];groupOrderTotal.value=data.orderTotal||0
    }
  }
  catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务列表加载失败')}
  finally{if(current===sequence)loading.value=false}
}
function search(){if(props.statementClientView){statementTableRef.value?.clearSelection();projectPreview.value=null}clearTimeout(timer);page.value=1;subtotalPage.value=1;clientOrderPages.value={};void load()}
async function toggleChildOrders(){
  if(!await tableEditing.flush())return
  childOrdersExpanded.value=!childOrdersExpanded.value
  orderExpansionOverrides.value.clear()
  search()
}
async function toggleOrderExpansion(id){
  if(loading.value||editorLoading.value||!await tableEditing.flush())return
  const overrides=orderExpansionOverrides.value
  if(!overrides.delete(id))overrides.add(id)
  if(filters.clientOrderCount!=='multiple')await load({skipFlush:true})
}
function sortFinanceRows(change){
  financeSort.value=customerFinanceSort(change)
  search()
}
function setBillingMonth(month){
  if((month||'')!==filters.month){
    if(typeof filters.billingPeriod==='number')filters.billingPeriod=undefined
    clearRowFilters()
  }
  filters.month=month||''
  search()
}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function queueFilterSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function resetSearch(){clearRowFilters();filters.clientOrderCount='';collapsedClients.value=[];filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';filters.keyword='';filters.projectStatus=[];filters.paymentStatus='';filters.statementRequired=[];filters.paymentMethod='';filters.billingPeriod=undefined;filters.pricingMode='';filters.client='';filters.month='';filters.manager='';managerIds.value=[];managerScope.value=props.clientScope?'all':'self';search()}
const formatAmounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-'
const languageDirections=value=>String(value||'').split('；').map(direction=>direction.trim()).filter(Boolean)
function cell(row,key){
  if(key==='clientManager')return row.clientManager||'未分配'
  if(key==='paymentStatus')return paymentStatusLabel(row)
  if(key==='pricingMode')return row.priceAggregate?'子订单汇总':row.pricingMode==='fixed'?'固定收费':'工作量'
  if(key==='projectName')return row.sourceFileName||row.projectName||'-'
  if(key==='projectStatus')return getProjectStatusLabel('translation',row.projectStatus)
  if(key==='wordCount')return getWordCountSummary(row).primary
  if(key==='totalInclTax')return formatAmounts(row.totalsInclTax);if(key==='totalPrice'||key==='adjustedTotal'){const values=key==='totalPrice'?row.totalsExclTax:row.adjustedTotals;return (Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-')+(row.incomplete?'\n待补录数量或单价':'')}
  return row[key]||'-'
}
const localTarget=ref(null),localPaymentParent=ref(null),linkedPaymentVisible=ref(false)
const projectFormTarget=ref(null),pendingFormFinance=new WeakMap()
const documentParent=ref(null),linkedQuotationVisible=ref(false)
const documentRules={statementRequired:[{required:true,type:'boolean',message:'请选择是否需对账单',trigger:'change'}]}
const paymentMethods=[
  {value:'individual',label:settlementModeLabels.individual,hint:'每个项目单独结算。'},
  {value:'monthly',label:settlementModeLabels.monthly,hint:'自动合并同一客户、同一账单月份且同一期的订单。'},
  {value:'special',label:settlementModeLabels.special,hint:'可分别设置各订单的计费口径与发票需求。'},
]
const savingTableDocuments=reactive(new Set())
const paymentProjectsContext=ref(null)
const paymentMethodSignatureIndex=21

function openPaymentProjects(row,type,summary=null) {
  paymentProjectsContext.value={
    type, clientId:row.clientId, clientName:row.clientShortName,
    projectId:row.rootId || row.id, periodNumber:row.settlementPeriodNumber,
    month:customerStatementContext(row)?.month || summary?.month || filters.month || undefined,
    boardName:summary?.boardName, statementProjects:summary?.statementProjects,
  }
}

function updateEditorDocuments(next) {
  editor.value=next
}

async function saveTablePaymentMethod(row, method) {
  if (method===paymentMethodFor(row)) return
  return saveTableDocument(row,{payment_method:method},'paymentMethod','结算模式')
}

async function changeSpecialSettlement(row, fields) {
  if(!canWrite||savingTableDocuments.has(row.rootId))return
  savingTableDocuments.add(row.rootId)
  try {
    let applyToOrder=true
    if(row.id!==row.rootId||row.children?.length){
      try{
        await ElMessageBox.confirm('请选择调整范围。应用整单会覆盖母订单和各级子订单在此字段的设置。',
          '调整特殊结算',{confirmButtonText:'应用整单',cancelButtonText:'仅当前订单',distinguishCancelAndClose:true})
      }catch(action){
        if(action!=='cancel')return
        applyToOrder=false
      }
    }
    await saveSpecialSettlement(row.rootId,{order_id:row.id,apply_to_order:applyToOrder,...fields})
    projectPreview.value=null
    await load()
    window.dispatchEvent(new CustomEvent('translation-statements-changed'))
  }catch(error){
    ElMessage.error(getLocalizedErrorMessage(error,'特殊结算设置保存失败'))
  }finally{
    savingTableDocuments.delete(row.rootId)
  }
}

function saveTableQuotationRequired(row, required) {
  if (required===row.quotationRequired)return
  return saveTableDocument(row,{quotation_required:required},'quotationRequired','报价单需求')
}

function saveTableInvoiceRequired(row, required) {
  if(typeof required!=='boolean'||required===row.invoiceRequirementOverride)return
  return saveTableDocument(row,{invoice_required:required},'invoiceRequirementOverride','发票需求')
}

async function saveTableDocument(row, patch, field, label) {
  if (!canWrite || savingTableDocuments.has(row.id)) return
  savingTableDocuments.add(row.id)
  try {
    if (!await tableEditing.flush()) {
      ElMessage.warning('有单元格尚未保存，请先处理提示')
      return
    }
    const current=await getCustomerFinanceProject(row.id)
    if (current.item[field] !== row[field]) {
      await load({fromTable:true})
      ElMessage.warning(`${label}已更新，请核对后重试`)
      return
    }
    const saved=await saveCustomerFinanceProject(row.id,{
      version:current.version,order_id:row.id,documents_only:true,...patch,
    })
    syncSavedFinanceRows(saved.item)
    const financeFields=[field==='invoiceRequirementOverride'?'invoiceRequired':field]
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{
      detail:{projectId:row.id,financeItem:saved.item,financeFields},
    }))
    notifyCustomerFinanceHistory(row.clientId)
    emit('saved',saved.item)
    return saved.item
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error,`${label}保存失败`))
  } finally {
    savingTableDocuments.delete(row.id)
  }
}
const editorDocumentProject=computed(()=>({...editor.value,id:editor.value.rootId,orderNo:editor.value.documentOrderNo||editor.value.orderNo,clientShortName:editor.value.documentClientShortName||editor.value.clientShortName}))
function openEditorStatement(){
  const context=customerStatementContext(editorDocumentProject.value)
  if(!context)return ElMessage.warning('请先选择或保存客户，并确认订单号所属月份')
  openStandardStatement(context)
}
function documentDraft(root,order=root){
  const special=paymentMethodFor(root)==='special'
  return {quotationRequired:!!root.quotationRequired,invoiceRequirementOverride:special?order.invoiceRequirementOverride:undefined,
    statementRequired:(special?order.statementRequired:root.statementRequired)!==false,
    statementUpdatedAt:root.updatedAt,quotationDraft:copySavedValue(root.quotationDraft||null),
    statementRequiredDirty:false,quotationDraftDirty:false,documentNotes:documentNotesForm(root.documentNotes),
    documentNotesDirty:false,documentOrderNo:root.orderNo,documentClientShortName:root.clientShortName,
    clientManager:root.clientManager,paymentMethod:paymentMethodFor(root),customerDocumentDefaults:root.customerDocumentDefaults||{},
    customerDocumentSources:root.customerDocumentSources||{},customerPreferenceRevision:root.customerPreferenceRevision}
}
function openCustomerFinanceSettings(financeSection,clientId=editor.value.clientId){
  if(clientId)clientManagementTarget.value={client_id:clientId,...(canWriteClients?{financeSection}:{})}
}
function onTableStatementSaved(row,result){
  notifyCustomerFinanceHistory(row.clientId)
  emit('saved',result)
}
function notifyCustomerFinanceHistory(clientId){
  if(clientId)window.dispatchEvent(new CustomEvent('customer-order-finance-saved',{detail:{clientId:String(clientId)}}))
}
async function saveEditorStatementRequirement(value,confirmation){
  if(saving.value)return
  saving.value=true
  const draft=editor.value
  const baseline=JSON.parse(original.value)
  try{
    const saved=await setProjectStatementRequired(draft.rootId,{
      statement_required:value,
      expected_statement_required:baseline[11],
      expected_updated_at:draft.statementUpdatedAt||null,
      statement_sync:confirmation.scope,
      statement_customer_sync:confirmation.customerScope,
    })
    editor.value.statementRequired=saved.statementRequired
    editor.value.statementRequiredDirty=false
    editor.value.statementSync=null
    editor.value.statementCustomerSync=null
    editor.value.statementUpdatedAt=saved.updatedAt
    baseline[11]=saved.statementRequired
    baseline[paymentMethodSignatureIndex]=paymentMethodFor({...draft,...saved})
    original.value=JSON.stringify(baseline)
    if(documentParent.value?.id===draft.rootId){
      documentParent.value.statementRequired=saved.statementRequired
      documentParent.value.paymentMethod=baseline[paymentMethodSignatureIndex]
    }
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{
      detail:{projectId:draft.rootId,syncScope:confirmation.scope||confirmation.customerScope},
    }))
    notifyStatementCustomerSync(confirmation.customerScope)
    notifyCustomerFinanceHistory(draft.clientId)
    await rebaseEditorAfterLibrary().catch(error=>{
      saveError.value=getLocalizedErrorMessage(error,'对账单需求已保存，请重新打开价格与付款读取最新数据')
    })
    emit('saved',saved)
    ElMessage.success(confirmation.customerScope?'已保存并同步客户管理':'是否需对账单已保存')
  }finally{
    saving.value=false
  }
}
function changedPaymentMethod(){
  const previous=JSON.parse(original.value||'[]')[paymentMethodSignatureIndex]
  return editor.value.paymentMethod!==previous?editor.value.paymentMethod:undefined
}
function changeEditorSettlementMode(mode){
  const order=editor.value
  order.paymentMethod=mode
  if(mode!=='special'){
    order.statementRequired=effectiveBillingTaxMode(order)==='incl_tax'
    order.statementRequiredDirty=false
    order.statementSync=null
    order.statementCustomerSync=null
  }
}
function statementPayload(){
  const draft=editor.value
  if(!draft.statementRequiredDirty||draft.paymentMethod!=='special')return {}
  return {statement_required:draft.statementRequired,statement_sync:draft.statementSync,statement_customer_sync:draft.statementCustomerSync}
}
const changedCustomerDocuments=computed(()=>{
  if(!original.value)return []
  const baseline=JSON.parse(original.value)
  return [
    editor.value.quotationRequired!==baseline[10]&&'quotationRequired',
    editor.value.statementRequired!==baseline[11]&&'statementRequired',
    (editor.value.invoiceRequirementOverride??null)!==baseline[22]&&'invoiceRequired',
  ].filter(Boolean)
})
const documentRequirementsChanged=computed(()=>changedCustomerDocuments.value.some(field=>field!=='statementRequired'))
function documentPayload(){
  const draft=editor.value
  const baseline=JSON.parse(original.value||'[]')
  return {quotation_required:draft.quotationRequired!==baseline[10]?draft.quotationRequired:undefined,
    invoice_required:draft.paymentMethod==='special' && (draft.invoiceRequirementOverride??null)!==baseline[22]?draft.invoiceRequirementOverride:undefined,
    ...statementPayload(),quotation_draft:draft.quotationDraftDirty?draft.quotationDraft:undefined,
    document_notes:draft.documentNotesDirty?draft.documentNotes:undefined,documents_only:!!(draft.priceAggregate||draft.fixedPricingFrom)}
}
function applyDocumentDraft(persisted){
  const parent=documentParent.value||localPaymentParent.value
  const value={id:editor.value.rootId,quotationRequired:editor.value.quotationRequired,statementRequired:editor.value.statementRequired,statementRequiredChanged:!settlementChild.value&&editor.value.statementRequiredDirty,quotationDraft:editor.value.quotationDraft,quotationDraftChanged:editor.value.quotationDraftDirty,documentNotes:documentNotesForm(editor.value.documentNotes),documentNotesChanged:editor.value.documentNotesDirty,persisted}
  if(parent){parent.quotationRequired=value.quotationRequired;if(value.statementRequiredChanged){parent.statementRequired=value.statementRequired;parent.statementRequiredExplicit=true}if(value.quotationDraftChanged)parent.quotationDraft=value.quotationDraft;if(value.documentNotesChanged)parent.documentNotes=value.documentNotes}
  emit('document-requirements-saved',value)
}
const originalPaymentConfirmation=ref(''),originalPaymentDetails=ref('[]')
const editorVisible=ref(false),editorLoading=ref(false),saving=ref(false),saveError=ref(''),editor=ref({}),formRef=ref(),editorBody=ref()
const billingPeriodVisible=ref(false)
watch(editorVisible,visible=>{if(!visible)billingPeriodVisible.value=false})
function billingPeriodLabel(order){
  if(!order.billingMonth)return '保存项目后自动生成'
  const linked=(order.statementStatus || []).filter(board=>board.months?.includes(order.billingMonth))
  const number=order.settlementPeriodNumber || order.billingPeriod?.number || (linked.length===1 ? linked[0].periodNumber : null)
  return number ? `${order.billingMonth} 第${number}期` : order.billingMonth
}
async function onBillingPeriodSaved(){
  billingPeriodVisible.value=false
  const projectId=editor.value.rootId
  try{
    await rebaseEditorAfterLibrary()
  }catch(error){
    saveError.value=getLocalizedErrorMessage(error,'账期已保存，请重新打开价格与付款查看')
  }
  window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{projectId,syncScope:true}}))
  window.dispatchEvent(new CustomEvent('customer-statement-history-refresh'))
  ElMessage.success('账期已保存')
}
const invoiceReview = ref(false)
watch(editorVisible, visible => { if (!visible) invoiceReview.value = false })
function locateInvoiceRequirement() {
  if (invoiceReview.value) scrollFormTarget(editorBody.value?.querySelector('[data-field-key="invoiceRequired"]'), editorBody.value)
}
const orderNavigation = ref(null)
const editorHasChildren = computed(() => {
  const {children, childOrderCount, hasChildren} = editor.value
  return Boolean(children?.length || childOrderCount || hasChildren)
})
const editorLevelLabel = computed(() => financeOrderLevel(editor.value))
const showMotherBillingTotal = computed(() => editorLevelLabel.value === '母订单')
const motherBillingTotal = computed(() => {
  const {billingTotals, totalsInclTax, totalsExclTax} = editor.value
  if (!Object.keys(billingTotals || {}).length) {
    if (Object.keys(totalsInclTax || {}).length) return {label:'母订单含税总价', amounts:totalsInclTax}
    if (Object.keys(totalsExclTax || {}).length) return {label:'母订单不含税总价', amounts:totalsExclTax}
  }
  return {label:'母订单计费总价', amounts:billingTotals}
})
const editorTitle = computed(() => {
  const baseTitle = `价格与付款 · ${editor.value.orderNo || ''}`
  return editorLevelLabel.value ? `${baseTitle}（${editorLevelLabel.value}）` : baseTitle
})
const regionPrefix = computed(() => editorHasChildren.value ? `${editorLevelLabel.value} · ` : '')
const regionTitle = title => regionPrefix.value + title
const switchingOrder = ref(false)
const orderNavigationDisabled = computed(() => switchingOrder.value || editorLoading.value || saving.value || pricingModeSwitching.value  || !!editor.value.fixedPricingFrom)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const original=ref(''), pricingModeOnlySignature=ref(null)
let pricingModeBeforeSwitch=null
let treeVersion=''
const referencePrices=ref([]),referencePickerRef=ref()
const historyVisible=ref(false),historyOrder=ref(null)
const getWordCountSummary=row=>getWordCountMatrixListSummary(row.wordCountMatrix||{},{source:row.wordCountMatrixSource})
const paymentConfirmationDirty=computed(()=>JSON.stringify(paymentConfirmationInput(editor.value.paymentConfirmation))!==JSON.stringify(paymentConfirmationInput(JSON.parse(originalPaymentConfirmation.value||'null'))))
const paymentDetailsDirty=computed(()=>paymentDetailsSignature(editor.value.paymentDraft)!==originalPaymentDetails.value)
const originalPrices=ref([])
const editorDirty=computed(()=>editorVisible.value&&!editorLoading.value&&!!original.value&&editorSignature()!==original.value)
const calculatedTotals=computed(()=>calculateTaxOrderPriceTree(editor.value,originalPrices.value))
const settlementTab=ref('order')
const orderSettlementBody=ref()
const settlementChild=computed(()=>editor.value.id!==editor.value.rootId||!!(localTarget.value&&localTarget.value!==localPaymentParent.value))
const independentSettlementChild=computed(()=>settlementChild.value&&!mergedSettlement.value)
const mergedSettlement=computed(()=>editor.value.paymentMethod==='monthly' && (paymentSummary.value?.orderCount||0)>1)
const showMergedSettlement=computed(()=>mergedSettlement.value&&!settlementChild.value&&settlementTab.value==='merged')
const settlementAmountColumns=[
  {key:'totalsExclTax',label:'不含税总价'},
  {key:'totalsInclTax',label:'含税总价'},
  {key:'billingTotals',label:'计费总价'},
]
watch(()=>[editorVisible.value,editor.value.id],()=>{settlementTab.value='order'},{flush:'sync'})
const reviewRoot = ref(null)
const savedDocumentReview = ref(null)
const serverDocumentReview = ref(null)
const reviewReasonInput = ref()
const reviewReasonError = ref('')
const reviewColumns = [{key:'quotation',label:'报价单'},{key:'statement',label:'对账单'},{key:'invoice',label:'发票'}]
const mergedReviewColumns = [
  {key:'quotation',label:'报价单',field:'quotation_required',sourceKey:'quotationRequired',format:documentRequirementLabel},
  {key:'statement',label:'对账单',field:'statement_required',sourceKey:'statementRequired',format:documentRequirementLabel},
  {key:'invoice',label:'发票',field:'invoice_required',sourceKey:'invoiceRequired',format:documentRequirementLabel},
  {key:'tax',label:'计费口径',field:'billing_tax_mode',sourceKey:'effectiveBillingTaxMode',format:billingTaxLabel},
]
const mergedEditError=ref('')
watch(()=>[editorVisible.value,editor.value.rootId],()=>{mergedEditError.value=''})
const mergedReviewRows = computed(() => {
  const mapOrder=(order,rootId)=>({
    ...order,rootId,
    ...order.documentRequirements,
    children:(order.children||[]).map(child=>mapOrder(child,rootId)),
  })
  return (paymentSummary.value?.orders || []).map(order=>mapOrder(order,order.id))
})
const mergedTotalLabel = computed(() => {
  const modes = new Set(mergedReviewRows.value.map(row => row.tax))
  if (modes.size === 1 && modes.has('incl_tax')) return '费用总价（含税）'
  if (modes.size === 1 && modes.has('excl_tax')) return '费用总价（不含税）'
  if (modes.has('mixed') || (modes.has('incl_tax') && modes.has('excl_tax'))) return '费用总价（按各订单口径汇总）'
  return '费用总价'
})
const mergedReviewDifferences = computed(() => mergedReviewColumns.filter(({key}) =>
  new Set(mergedReviewRows.value.map(row => row[key] ?? null)).size > 1))
const mergedReviewPending = computed(() => mergedReviewRows.value.some(row =>
  mergedReviewColumns.some(({key}) => row[key] == null)))
const mergedReviewMixed = computed(() => mergedReviewRows.value.some(row => row.tax === 'mixed'))
const mergedReviewIssue = computed(() => !!mergedReviewDifferences.value.length || mergedReviewPending.value || mergedReviewMixed.value)
const mergedReviewMessage = computed(() => {
  if (!mergedReviewIssue.value) return '参与合并结算的各订单，单据需求及计费口径一致。'
  return [
    mergedReviewDifferences.value.length && `各订单的${mergedReviewDifferences.value.map(column=>column.label).join('、')}不同`,
    mergedReviewMixed.value && '部分订单的子订单计费口径不统一或待核对',
    mergedReviewPending.value && '部分设置待核对',
  ].filter(Boolean).join('；')+'。'
})
function isMergedDifference(row,column){
  return row[column.key]==null || row[column.key]==='mixed' ||
    (row.id===row.rootId && mergedReviewDifferences.value.includes(column))
}
function mergedFieldChoices(row,column){
  if(column.key!=='tax')return [true,false]
  if(row.priceAggregate || row.fixedPricingFrom)return []
  return ['excl_tax','incl_tax']
}
function canEditMergedField(row,column){
  if(!canWrite || localTarget.value || row.fixedPricingFrom)return false
  if(column.key==='invoice'||column.key==='statement')return false
  return column.key==='tax' ? mergedFieldChoices(row,column).length>1 : row.id===row.rootId
}
async function confirmBillingTaxChange(mode, merged){
  const label=billingTaxLabel(mode)
  const scope=merged?'参与本次合并结算的全部订单及各级子订单':'本订单及各级子订单'
  try{
    await ElMessageBox.confirm(
      `将${scope}的计费口径统一为「${label}」，发票需求会随之更新。缺少该口径金额的订单需补录。`,
      '确认统一计费口径',{type:'warning',confirmButtonText:'确认调整',cancelButtonText:'取消'},
    )
    return true
  }catch{return false}
}
async function changeEditorBillingTax(mode){
  const order=editor.value
  if(mode===effectiveBillingTaxMode(order))return
  if(order.paymentMethod!=='special'){
    if(!await confirmBillingTaxChange(mode,order.paymentMethod==='monthly'&&mergedSettlement.value) || editor.value!==order)return
    order.unifiedBillingTaxMode=mode
    order.statementRequired=mode==='incl_tax'
  }
  order.billingTaxMode=mode
}
async function saveMergedField(row,column,value){
  if(saving.value || !canEditMergedField(row,column) || row[column.key]===value)return
  if(editorDirty.value && editor.value.rootId===row.rootId){
    mergedEditError.value='请先保存或取消当前订单的未保存修改，再在此处调整。'
    return
  }
  saving.value=true
  mergedEditError.value=''
  try{
    if(column.key==='tax' && !await confirmBillingTaxChange(value,true))return
    const current=await getCustomerFinanceProject(row.rootId)
    const order=findFinanceOrder(current.item,row.id)?.order
    if(!order || order[column.sourceKey]!==row[column.key]){
      await loadPaymentSummary()
      mergedEditError.value='订单设置已更新，请核对后重试。'
      return
    }
    if(column.key==='tax' && (order.priceAggregate || order.fixedPricingFrom)){
      await loadPaymentSummary()
      mergedEditError.value='该订单的计费口径已变化，请核对可选口径。'
      return
    }
    const saved=await saveCustomerFinanceProject(row.rootId,{
      version:current.version,order_id:row.id,documents_only:true,[column.field]:value,
    })
    syncSavedFinanceRows(saved.item)
    const financeFields=column.key==='tax'?[column.sourceKey,'statementRequired']: [column.sourceKey]
    syncMergedFinanceForm(saved.item,financeFields)
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{
      detail:{projectId:row.rootId,clientId:saved.item.clientId,source:financePaymentSource,
        financeItem:saved.item,financeFields,syncScope:column.key==='tax'},
    }))
    notifyCustomerFinanceHistory(saved.item.clientId)
    notifyPaymentChanged(saved.item.id,saved.item.paymentConfirmation,financePaymentSource)
    emit('saved',saved.item)
    if(editor.value.rootId===row.rootId || column.key==='tax'){
      try{
        const latest=editor.value.rootId===row.rootId?saved:await getCustomerFinanceProject(editor.value.rootId)
        await rebaseEditorAfterLibrary(latest)
        if(column.key==='tax')syncMergedFinanceForm(latest.item,financeFields)
      }
      catch(error){mergedEditError.value=getLocalizedErrorMessage(error,'已保存，请重新打开价格与付款查看最新设置。')}
    }
    await loadPaymentSummary()
    if(column.key==='tax'&&!props.editorOnly)await load({fromTable:true})
    ElMessage.success(`${column.label}已保存`)
  }catch(error){
    if(error.response?.status===409)await loadPaymentSummary()
    mergedEditError.value=getLocalizedErrorMessage(error,`${column.label}保存失败`)
  }finally{
    saving.value=false
  }
}
async function openOrderPricing(row){
  try{
    if(editor.value.id===row.id || await openEditor({id:row.id,rootId:row.rootId})){
      settlementTab.value='order'
      await nextTick()
      const target=orderSettlementBody.value?.querySelector('[data-dialog-field-search-label="计费口径"]')
      if(target)scrollFormTarget(target,editorBody.value)
    }
  }catch(error){
    const message=getLocalizedErrorMessage(error,'订单价格加载失败')
    if(showMergedSettlement.value)mergedEditError.value=message
    else ElMessage.error(message)
  }
}
const reviewApplicable = computed(() => !localTarget.value && !!reviewRoot.value?.children?.length && editor.value.paymentMethod==='monthly')
const draftReviewRows = computed(() => reviewApplicable.value ? documentConsistencyRows(reviewRoot.value,editor.value) : [])
const reviewRows = computed(() => reviewApplicable.value ? serverDocumentReview.value?.rows || draftReviewRows.value : [])
const orderPricingReviewRows = computed(() => {
  if (!reviewApplicable.value && !editor.value.priceAggregate) return []
  const pricing = new Map()
  function collect(order) {
    // 明细已逐行展开，保留 children 会让表格再渲染一次原始子订单。
    const {children, ...fields} = order.id===editor.value.id ? editor.value : order
    pricing.set(order.id, fields)
    for (const child of order.children || []) collect(child)
  }
  const root = reviewApplicable.value ? reviewRoot.value : editor.value
  collect(root)
  if (reviewApplicable.value) {
    return reviewRows.value.map(row => ({...pricing.get(row.id),...row}))
  }
  return [...pricing.values()].map(order => ({...order,tax:order.effectiveBillingTaxMode}))
})
function reviewUnitPrice(row) {
  return (row.prices || []).map(price => {
    const unit = `${price.unitSize || 1} ${basisLabel(price.metric)}`
    const amount = taxPriceSummary(price.taxPrices,price.currency,unit,false) ||
      (price.amount==null ? '待填写' : `${price.currency} ${price.amount} / ${unit}`)
    return [price.languagePair,amount].filter(Boolean).join(' · ')
  }).join('\n') || '—'
}
const reviewSnapshot = computed(() => documentConsistencySnapshot(reviewRows.value))
const taxAmountPending = computed(() => editor.value.paymentMethod!=='special' && !!editor.value.billingTaxPending)
const orderReviewIssues = computed(() => {
  const issues = new Map()
  function add(order, reason) {
    const entry = issues.get(order.id)
    if(entry)entry.reason += '、'+reason
    else issues.set(order.id,{order,reason})
  }
  function collectMissingAmounts(order) {
    if(order.fixedPricingFrom)return
    if(order.priceAggregate){
      for(const child of order.children || [])collectMissingAmounts(child)
    }else if(order.billingTaxPending){
      add(order,`缺少${billingTaxLabel(order.effectiveBillingTaxMode)}金额`)
    }
  }
  if(taxAmountPending.value)collectMissingAmounts(editor.value)
  const [mother,...children]=reviewRows.value
  for(const order of children){
    const differences=reviewColumns.filter(({key})=>order[key]!==mother[key]).map(({label})=>label)
    if(order.tax!==mother.tax)differences.push('计费口径')
    if(differences.length)add({...order,rootId:editor.value.rootId},`${differences.join('、')}与母订单不同`)
  }
  return [...issues.values()]
})
const orderReviewType=computed(()=>taxAmountPending.value || documentReviewOutstanding.value
  ? 'warning' : reviewSnapshot.value.length ? 'info' : 'success')
const orderReviewMessage=computed(()=>{
  const missing=taxAmountPending.value
  const different=reviewSnapshot.value.length>0
  if(missing && different)return '部分订单的单据需求或计费口径有差异，且有订单缺少所选税口径的金额。'
  if(missing && reviewApplicable.value)return '单据需求及计费口径一致，但部分订单缺少对应金额。请打开下方订单补录。'
  if(missing)return '部分订单缺少所选税口径的金额，请打开对应订单补录。'
  if(different)return documentReviewOutstanding.value
    ? '单据需求或计费口径不一致，请打开对应订单核对，或填写保留差异的理由。'
    : '单据需求或计费口径存在差异，已记录保留差异的理由。'
  return '母订单与各级子订单的单据需求及计费口径一致。'
})
const reviewKey = computed(() => JSON.stringify(['monthly',reviewSnapshot.value]))
const documentReviewOutstanding = computed(() => reviewSnapshot.value.length > 0 &&
  reviewKey.value!==JSON.stringify([savedDocumentReview.value?.method,savedDocumentReview.value?.snapshot]))
watch(() => JSON.stringify([editor.value.id,editor.value.paymentMethod,editor.value.quotationRequired,editor.value.statementRequired,
  editor.value.invoiceRequirementOverride,editor.value.pricingMode,editor.value.billingTaxMode,editor.value.adjustedTotal,
  editor.value.adjustedTotalInclTax,editor.value.prices?.map(ratePayload),editor.value.clearedAll]), () => {
  serverDocumentReview.value=null
})
watch(reviewKey, () => {
  const saved=savedDocumentReview.value
  editor.value.documentReviewReason=reviewKey.value===JSON.stringify([saved?.method,saved?.snapshot]) ? saved.reason : ''
  reviewReasonError.value=''
}, {flush:'sync'})
watch(() => editor.value.documentReviewReason, () => {reviewReasonError.value=''})
async function setUnifiedInvoice(required){
  const currentOrderId=editor.value.id
  try{
    await ElMessageBox.confirm(`将母订单与各级子订单统一设置为「${required?'需':'无需'}发票」，点击保存后生效。`,
      '统一发票需求',{type:'warning',confirmButtonText:'确定',cancelButtonText:'取消'})
  }catch{return}
  if(editorVisible.value && editor.value.id===currentOrderId)editor.value.invoiceRequirementOverride=required
}
function loadDocumentReview(data){
  serverDocumentReview.value=null
  savedDocumentReview.value=data.documentConsistencyReview||null
  reviewRoot.value=data.item
  editor.value.documentReviewReason=documentReviewOutstanding.value ? '' : savedDocumentReview.value?.reason||''
}
const paymentSummaryTitle='订单汇总'
function projectTotalLabel(tax){
  const prefix=mergedSettlement.value?'本项目':''
  return prefix+tax+(editor.value.pricingMode==='fixed'?'固定收费':'总价')
}
const paymentSummary=ref(null),paymentSummaryLoading=ref(false),paymentSummaryError=ref('')
const paymentSummaryDifferences=computed(()=>{
  const summary=paymentSummary.value
  if(!summary||summary.pending)return []
  return Object.entries(summary.billingTotals||{}).flatMap(([currency,billing])=>{
    const inclusive=summary.totalsInclTax?.[currency]
    if(billing==null||inclusive==null||billing===''||inclusive==='')return []
    const cents=value=>Math.round(Number(Number(value).toFixed(2))*100)
    const difference=cents(billing)-cents(inclusive)
    if(!Number.isFinite(difference)||!difference)return []
    return [{currency,direction:difference>0?'高':'低',amount:(Math.abs(difference)/100).toFixed(2)}]
  })
})
const paymentSummaryTotals=computed(()=>paymentSummary.value?.pending?[]:Object.entries(paymentSummary.value?.billingTotals||{}).map(([currency,amount])=>({
  key:`monthly:${currency}`,label:'订单汇总总价',currency,amount:Number(amount).toFixed(2),
})))
let paymentSummaryRequest
async function loadPaymentSummary(){
  paymentSummaryRequest?.abort()
  paymentSummaryError.value=''
  paymentSummaryLoading.value=false
  const {rootId,clientId,paymentMethod}=editor.value
  if(!editorVisible.value||paymentMethod!=='monthly'||!rootId||!clientId){
    paymentSummary.value=null
    return
  }
  if(paymentSummary.value?.rootId!==rootId)paymentSummary.value=null
  const request=new AbortController()
  paymentSummaryRequest=request
  paymentSummaryLoading.value=true
  try{
    const result=await getFinancePaymentSummary(rootId,'monthly',{signal:request.signal})
    if(!request.signal.aborted)paymentSummary.value={...result,rootId}
  }catch(error){
    if(!request.signal.aborted)paymentSummaryError.value=getLocalizedErrorMessage(error,'汇总金额加载失败')
  }finally{
    if(!request.signal.aborted)paymentSummaryLoading.value=false
  }
}
watch(()=>[editorVisible.value,editor.value.rootId,editor.value.clientId,editor.value.paymentMethod],loadPaymentSummary)
onBeforeUnmount(()=>paymentSummaryRequest?.abort())
function hasTotalAmount(kind){const value=kind==='excl'?editor.value.adjustedTotal:editor.value.adjustedTotalInclTax;return (value!=null&&value!=='')||(editor.value.pricingMode!=='fixed'&&Object.keys(calculatedTotals.value[kind].totals).length>0)}
function calculatedCurrency(kind){const currencies=Object.keys(calculatedTotals.value[kind].totals);return (currencies.length?currencies:[...new Set((editor.value.prices||[]).map(row=>row.currency||'CNY'))]).join('\n')||editor.value.currency||'CNY'}
function calculatedTotal(kind){const result=calculatedTotals.value[kind];return (Object.values(result.totals).map(value=>Number(value).toFixed(2)).join('\n')||'-')+(result.incomplete?'（待补录）':'')}
function syncSavedFinanceRows(item){
  if(!item?.id||!rows.value.some(row=>row.id===item.id))return
  function merge(previous,saved){
    if(childPagination.value){
      const savedChildren=new Map((saved.children||[]).map(row=>[row.id,row]))
      return {...previous,...saved,children:(previous.children||[]).map(row=>savedChildren.has(row.id)?merge(row,savedChildren.get(row.id)):row)}
    }
    const previousChildren=new Map((previous?.children||[]).map(row=>[row.id,row]))
    return {...previous,...saved,children:(saved.children||[]).map(child=>merge(previousChildren.get(child.id),child))}
  }
  rows.value=rows.value.map(row=>row.id===item.id?merge(row,item):row)
}
function syncMergedFinanceForm(item,fields=[]){
  const parent=documentParent.value
  if(parent?.id!==item.id)return
  Object.assign(parent,{
    invoiceRequired:item.invoiceRequired,
    paymentConfirmation:copySavedValue(item.paymentConfirmation),
  })
  if(fields.includes('quotationRequired'))parent.quotationRequired=item.quotationRequired
  if(fields.includes('statementRequired'))Object.assign(parent,{
    statementRequired:item.statementRequired,statementRequiredExplicit:item.statementRequiredExplicit,
  })
  if(fields.includes('invoiceRequired'))parent.invoiceRequirementOverride=item.invoiceRequirementOverride
  const target=projectFormTarget.value
  const order=target && findFinanceOrder(item,target.id)?.order
  if(order){
    target.billingTaxMode=order.billingTaxMode
    target.effectiveBillingTaxMode=order.effectiveBillingTaxMode
  }
}
async function onTablePriceSaved(result){
  const item=result?.item
  if(item){
    syncSavedFinanceRows(item)
    notifyCustomerFinanceHistory(item.clientId)
    if(editorVisible.value&&!saving.value&&!localTarget.value&&editor.value.rootId===item.id){
      try{await rebaseEditorAfterLibrary(result)}
      catch(e){saveError.value=getLocalizedErrorMessage(e,'价格与付款同步失败，当前输入已保留')}
    }
    notifyPaymentChanged(item.id,item.paymentConfirmation,financePaymentSource)
  }
  emit('saved')
  await load({fromTable:true})
}
function onSameMonthSynced(){emit('saved')}
function paymentConfirmationInput(value){
  if(!value)return null
  const {revision,fullPaymentTotalKey,fullReferenceLabel,fullReferenceAmount,fullMatchStatus,fullPaymentConfirmedByName,fullPaymentConfirmedAt,...input}=value
  return input
}
function editorSignature(){return JSON.stringify([editor.value.pricingMode,editor.value.currency,(editor.value.prices||[]).map(ratePayload),editor.value.adjustedTotal,editor.value.adjustedTotalInclTax,editor.value.explanation,editor.value.billingMonth,null,paymentConfirmationInput(editor.value.paymentConfirmation),editor.value.customerExplanation||'',editor.value.quotationRequired,editor.value.statementRequired,editor.value.quotationDraft,editor.value.statementRequiredDirty,editor.value.quotationDraftDirty,editor.value.billingTaxMode||null,paymentDetailsPayload(editor.value.paymentDraft),editor.value.documentNotes,editor.value.documentNotesDirty,editor.value.statementSync||null,editor.value.statementCustomerSync||null,editor.value.paymentMethod,editor.value.invoiceRequirementOverride??null,editor.value.unifiedBillingTaxMode??null,editor.value.documentReviewReason||''])}
function stopUsingReference(row){
  Object.assign(row,{referenceId:null,referenceRevision:null,amount:undefined,taxPrices:taxPriceForm(),manualReference:true})
}
async function adoptReference(target){
  const choice=await referencePickerRef.value?.confirm({prices:target?[target]:undefined})
  if(!choice)return
  try{
    const draft=editor.value
    const values=expectedOrderPrices(draft.prices,draft.languagePair,draft.wordCountMatrix).map(row=>({...row}))
    const targetIndex=target?draft.prices.indexOf(target):-1
    const index=targetIndex>=0?targetIndex:replaceMatchedReference(values,choice.price,draft.wordCountMatrix)
    replaceMatchedReference([values[index]],choice.price,draft.wordCountMatrix)
    values[index]={...referenceDraft(choice.price),id:values[index].id,metric:values[index].metric}
    draft.prices=values
    const client=draft.clientShortName||draft.clientName||'当前客户'
    const order=draft.orderNo?`订单 ${draft.orderNo}`:'当前订单'
    ElMessage.info(`已将客户管理中${client}的笔译报价带入${order}，保存后生效`)
  }catch(e){ElMessage.warning(e.message)}
}
let editorSequence=0,editorReadSequence=0
function findFinanceOrder(order, id, parent = null, index = -1){
  if(order.id === id) return {order, parent, index}
  const children = order.children || []
  for(const [childIndex, child] of children.entries()){
    const match = findFinanceOrder(child, id, order, childIndex)
    if(match) return match
  }
  return null
}

function updateOrderNavigation({parent, index}){
  orderNavigation.value = parent && {
    parent,
    previous: parent.children[index - 1],
    next: parent.children[index + 1],
  }
}

async function navigateOrder(direction){
  if(orderNavigationDisabled.value)return
  switchingOrder.value = true
  try{
    await openEditor(editor.value, direction)
  }finally{
    switchingOrder.value = false
  }
}

async function openEditor(row, direction = 0, reviewInvoice = false){
  if(!canWrite||row.fixedPricingFrom||editorLoading.value||saving.value)return
  if(!await tableEditing.flush())return ElMessage.warning('有单元格尚未保存，请先处理提示')
  if(direction){
    const title = direction === 'parent' ? '返回上一级订单' : '切换同级子订单'
    if(!await confirmEditorDiscard(title))return
  }else if(editorVisible.value&&!await guardEditor())return
  const current=++editorSequence
  clearTimeout(timer);controller?.abort();sequence++;loading.value=false
  editorLoading.value=true
  try{
    const data=await getCustomerFinanceProject(row.rootId)
    if(disposed||current!==editorSequence)return
    const match = findFinanceOrder(data.item, row.id)
    if(!match)throw new Error('订单已变化，请刷新')
    const selected = direction === 'parent' ? match.parent
      : direction ? match.parent?.children[match.index + direction] : match.order
    if(!selected){
      updateOrderNavigation(match)
      return ElMessage.warning(direction === 'parent' ? '当前订单没有上一级订单' : '该方向已没有同级子订单')
    }
    if(selected.fixedPricingFrom)return ElMessage.warning(`随上级订单 ${selected.fixedPricingFrom} 固定收费，请在上级订单操作`)
    financeModule.value='translation'
    paymentContextId.value=row.rootId
    localTarget.value=null;localPaymentParent.value=null;linkedQuotationVisible.value=false
    if(!direction){projectFormTarget.value=null;documentParent.value=null}
    updateOrderNavigation(direction ? findFinanceOrder(data.item, selected.id) : match)
    originalPrices.value=copySavedValue(selected.prices||[])
    editor.value={...copySavedValue(selected),...documentDraft(data.item,selected),clientId:data.item.clientId,clientShortName:data.item.clientShortName,paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation),paymentDraft:paymentDetailsForm(data.payment?.payments),paymentVersion:data.payment?.version||'',prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),billingMonth:selected.billingMonth||orderStatementMonth(selected.orderNo)||null}
    referencePrices.value=data.referencePrices?.items||[]
    if(!editor.value.prices.length){
      // 空单价代表尚未填写或已清空，客户参考价必须由用户明确采用。
      editor.value.clearedAll=true
    }
    treeVersion=data.version;saveError.value='';pricingModeBeforeSwitch=null;pricingModeOnlySignature.value=null;original.value='';clearFieldSearch()
    invoiceReview.value = reviewInvoice
    editorVisible.value=true
    loadDocumentReview(data)
    await nextTick()
    original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft)
    if(direction)editorBody.value?.closest('.el-dialog__body')?.scrollTo({top:0})
    return true
  }catch(e){if(current===editorSequence)ElMessage.error(getLocalizedErrorMessage(e,'收费明细加载失败'))}
  finally{if(current===editorSequence)editorLoading.value=false}
}

async function rebaseEditorAfterLibrary(saved,{preserveDraft=true}={}){
  if(!editor.value.rootId||localTarget.value||!original.value)return
  const readSequence=++editorReadSequence
  const rootId=editor.value.rootId,orderId=editor.value.id,current=editorSequence
  const data=saved??await getCustomerFinanceProject(rootId)
  if(disposed||readSequence!==editorReadSequence||current!==editorSequence||editor.value.rootId!==rootId||editor.value.id!==orderId)return
  const match = findFinanceOrder(data.item, orderId)
  if(!match)throw new Error('订单已变化，请重新打开')
  const selected = match.order
  const before=JSON.parse(original.value),draft=editor.value,currentSignature=editorSignature(),signature=JSON.parse(currentSignature)
  const previousReviewKey=reviewKey.value
  const previousReviewReason=draft.documentReviewReason
  const modeOnly=pricingModeOnlySignature.value===currentSignature
  if(preserveDraft&&selected.pricingMode!==before[0]&&[0,1,2,3,4,15].some(index=>JSON.stringify(signature[index])!==JSON.stringify(before[index]))){
    throw new Error('计价方式已在另一处修改，当前价格草稿已保留，请核对后重新打开')
  }
  updateOrderNavigation(match)
  const fresh={...copySavedValue(selected),...documentDraft(data.item,selected),clientId:data.item.clientId,clientShortName:data.item.clientShortName,prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation),paymentDraft:paymentDetailsForm(data.payment?.payments),paymentVersion:data.payment?.version||''}
  if(preserveDraft&&draft.clearedAll)fresh.clearedAll=true
  editor.value=fresh;loadDocumentReview(data);await nextTick();original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(fresh.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(fresh.paymentDraft)
  originalPrices.value=copySavedValue(selected.prices||[]);treeVersion=data.version;referencePrices.value=data.referencePrices?.items||[]
  if(!preserveDraft){
    pricingModeBeforeSwitch=null
    pricingModeOnlySignature.value=null
    return
  }
  if(modeOnly)pricingModeBeforeSwitch=pricingModeSnapshot(fresh)
  const fields=['pricingMode','currency','prices','adjustedTotal','adjustedTotalInclTax','explanation','billingMonth']
  fields.forEach((field,index)=>{if(JSON.stringify(signature[index])!==JSON.stringify(before[index]))fresh[field]=draft[field]})
  if(signature[0]!==before[0])fresh.priceAggregate=draft.priceAggregate
  if(JSON.stringify(signature[8])!==JSON.stringify(before[8]))fresh.paymentConfirmation=draft.paymentConfirmation
  if(paymentDetailsSignature(signature[16]||[])!==paymentDetailsSignature(before[16]||[])){fresh.paymentDraft=draft.paymentDraft;fresh.paymentVersion=draft.paymentVersion}
  if(JSON.stringify(signature[9])!==JSON.stringify(before[9]))fresh.customerExplanation=draft.customerExplanation
  if(signature[15]!==before[15] || signature[23]!==before[23]){
    fresh.billingTaxMode=draft.billingTaxMode
    fresh.unifiedBillingTaxMode=draft.unifiedBillingTaxMode
  }
  for(const [field,index] of [['quotationRequired',10],['statementRequired',11],['quotationDraft',12],['statementRequiredDirty',13],['quotationDraftDirty',14]]){if(JSON.stringify(signature[index])!==JSON.stringify(before[index]))fresh[field]=draft[field]}
  if(JSON.stringify(signature[17])!==JSON.stringify(before[17])){fresh.documentNotes=draft.documentNotes;fresh.documentNotesDirty=draft.documentNotesDirty}
  if(draft.statementRequiredDirty){fresh.statementSync=draft.statementSync;fresh.statementCustomerSync=draft.statementCustomerSync}
  if(signature[paymentMethodSignatureIndex]!==before[paymentMethodSignatureIndex]){
    fresh.paymentMethod=draft.paymentMethod
  }
  if(signature[22]!==before[22])fresh.invoiceRequirementOverride=draft.invoiceRequirementOverride
  editor.value={...fresh}
  if(previousReviewKey===reviewKey.value)editor.value.documentReviewReason=previousReviewReason
  pricingModeOnlySignature.value=modeOnly?editorSignature():null
}
const canSyncEditorPrices=computed(()=>!!editor.value.prices?.length&&editor.value.prices.every(row=>row.languagePair&&row.currency&&Number(row.unitSize||1)>0&&resolveRateQuantity(editor.value.wordCountMatrix,row.metric).metric&&(row.taxPrices?.unitPriceExclTax!=null||row.taxPrices?.unitPriceInclTax!=null)))
async function prepareEditorSync(){await rebaseEditorAfterLibrary();if(!canSyncEditorPrices.value){ElMessage.warning('请填写语种方向、币种、明确计量单位及至少一个单价');return false}return {order_id:editor.value.id,version:treeVersion,billing_month:editor.value.billingMonth,prices:editor.value.prices.map(ratePayload)}}

async function openAggregateOrder(rootId,id){
  const find=node=>node.id===id?node:(node.children||[]).map(find).find(Boolean)
  let target=rows.value.map(find).find(Boolean)
  if(!target){const data=await getCustomerFinanceProject(rootId);target=find(data.item)}
  return target ? openEditor(target) : false
}
async function openMotherSettlement(){
  const rootId=editor.value.rootId
  const openMerged=mergedSettlement.value
  if(rootId&&await openAggregateOrder(rootId,rootId)&&openMerged){
    openMergedSettlementTab()
  }
}
function openMergedSettlementTab(){
  settlementTab.value='merged'
  editorBody.value?.closest('.el-dialog__body')?.scrollTo({top:0})
}
async function confirmEditorDiscard(title){
  if(!editorDirty.value)return true
  try{
    await ElMessageBox.confirm('放弃后，本次对计价方式、价格和付款信息的修改均不会保存。',title,{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})
    return true
  }catch{return false}
}
async function closeEditor(done){
  if(saving.value||editorLoading.value||switchingOrder.value||!await confirmEditorDiscard('关闭编辑'))return
  pricingModeBeforeSwitch=null
  pricingModeOnlySignature.value=null
  if(typeof done==='function')done();else editorVisible.value=false
}
async function clearAllFinance(){
  try{await ElMessageBox.confirm('将清空当前窗口可填写的单价、金额、内部说明、客户说明、单据需求及付款信息。订单号、关联项目、字数统计和下级汇总信息保留。保存后生效，原数据保留在修改记录中。是否继续？','清空价格与付款',{type:'warning',confirmButtonText:'确认清空',cancelButtonText:'取消',closeOnClickModal:false})}catch{return}
  editor.value=clearFinanceForm(editor.value,newCustomerRate)
  saveError.value='';formRef.value?.clearValidate()
}
async function save(){
  if(saving.value||!canWrite||editor.value.fixedPricingFrom)return
  const reviewReason=editor.value.documentReviewReason?.trim()||''
  if(reviewApplicable.value && reviewSnapshot.value.length && !reviewReason){
    settlementTab.value='order'
    reviewReasonError.value='请填写保留差异的理由，或先统一单据需求和计费口径'
    await nextTick()
    reviewReasonInput.value?.focus()
    return
  }
  const activeForm=formRef.value
  if((localTarget.value||pricingModeOnlySignature.value!==editorSignature())&&!await activeForm?.validate().catch(()=>false)){
    if(showMergedSettlement.value&&orderSettlementBody.value?.querySelector('.is-error')){
      settlementTab.value='order'
      await nextTick()
      await activeForm?.locateFirstError()
    }
    return
  }
  const signature=editorSignature()
  const modeOnly=!localTarget.value&&pricingModeOnlySignature.value===signature
  const paymentChanged=paymentConfirmationDirty.value||paymentDetailsDirty.value
  const draft=editor.value
  const paymentMethod=changedPaymentMethod()
  const baseline=JSON.parse(original.value||'[]')
  const taxChange=(draft.billingTaxMode!==baseline[15] || (draft.unifiedBillingTaxMode??null)!==baseline[23]) && draft.billingTaxMode!=null
    ? draft.billingTaxMode : undefined
  let paymentOnly=false
  const reviewChanged=reviewApplicable.value && (documentReviewOutstanding.value ||
    reviewReason!==(savedDocumentReview.value?.reason||''))
  if(!localTarget.value&&(paymentChanged||paymentMethod||taxChange||documentRequirementsChanged.value||reviewChanged)&&original.value){
    // These two positions in editorSignature represent the payment confirmation and details.
    paymentOnly=JSON.parse(signature).every((value,index)=>
      index===8||index===15||index===16||index===paymentMethodSignatureIndex||
      (!draft.quotationRequired&&index===12&&value==null)||
      [10,22,23,24].includes(index)||
      ([11,13,19,20].includes(index)&&draft.statementRequiredDirty)||
      JSON.stringify(value)===JSON.stringify(baseline[index]))
  }
  if(!modeOnly&&!paymentOnly&&!editor.value.priceAggregate&&editor.value.pricingMode!=='fixed'&&!editor.value.prices.length&&!isClearedFinanceForm(editor.value))return ElMessage.warning('请至少填写一条语种单价')
  if(!modeOnly&&!paymentOnly&&!editor.value.fixedPricingFrom&&!editor.value.priceAggregate&&editor.value.pricingMode==='fixed'&&editor.value.adjustedTotal==null&&editor.value.adjustedTotalInclTax==null&&!isClearedFinanceForm(editor.value))return ElMessage.warning('请填写固定收费金额')
  if(localTarget.value){saving.value=true;try{await saveLocalFinance()}catch(e){saveError.value=getLocalizedErrorMessage(e,'付款保存失败，当前输入已保留')}finally{saving.value=false}return}
  saving.value=true;saveError.value=''
  try{
    const mode=draft.pricingMode||'metric'
    const orderMode=draft.children?.length&&mode!==JSON.parse(original.value)[0]?mode:undefined
    const cleared=isClearedFinanceForm(draft)
    const paymentPayload={
      version:treeVersion,order_id:draft.id,
      payment_method:paymentMethod,
      payment_draft:paymentDetailsDirty.value?paymentDetailsPayload(draft.paymentDraft):undefined,
      payment_version:paymentDetailsDirty.value?draft.paymentVersion:undefined,
      payment_confirmation:paymentChanged?paymentConfirmationPayload(draft.paymentConfirmation):undefined,
    }
    const documents=documentPayload()
    const taxPayload={billing_tax_mode:!draft.priceAggregate&&!draft.fixedPricingFrom?taxChange:undefined}
    const reviewPayload=reviewApplicable.value||savedDocumentReview.value
      ? {document_consistency_review:{snapshot:reviewSnapshot.value,reason:reviewReason}} : {}
    const savedFinance=modeOnly
      ?await saveCustomerFinanceTable(draft.rootId,{version:treeVersion,order_id:draft.id,pricing_mode:mode,...reviewPayload})
      :await saveCustomerFinanceProject(draft.rootId,paymentOnly?{...documents,...paymentPayload,...reviewPayload,...taxPayload,documents_only:true}:{
        ...documents,
        ...paymentPayload,
        ...reviewPayload,
        order_pricing_mode:orderMode,clear_finance:cleared,
        ...taxPayload,
        pricing_mode:draft.priceAggregate?'metric':mode,currency:draft.currency||'CNY',
        prices:draft.priceAggregate||mode==='fixed'||cleared?null:draft.prices.map(ratePayload),
        adjusted_total:draft.adjustedTotal??null,adjusted_total_incl_tax:draft.adjustedTotalInclTax??null,
        explanation:draft.explanation||'',customer_explanation:draft.customerExplanation||'',billing_month:draft.billingMonth||null,
      })
    syncSavedFinanceRows(savedFinance.item)
    if(paymentPayload.payment_method||draft.statementRequiredDirty||taxChange){
      const savedOrder=findFinanceOrder(savedFinance.item,draft.id)?.order||savedFinance.item
      draft.paymentMethod=savedFinance.item.paymentMethod
      draft.statementRequired=savedOrder.statementRequired
      draft.statementUpdatedAt=savedFinance.item.updatedAt
      if(documentParent.value?.id===draft.rootId){
        documentParent.value.paymentMethod=draft.paymentMethod
        documentParent.value.statementRequired=savedFinance.item.statementRequired
        documentParent.value.statementRequiredExplicit=savedFinance.item.statementRequiredExplicit
      }
    }
    notifyStatementCustomerSync(documents.statement_customer_sync)
    if(paymentOnly && !paymentChanged){
      applyDocumentDraft(true)
    }else{
      await updateProjectFormFinance(savedFinance.item.paymentConfirmation)
    }
    if(!paymentOnly)applyDocumentDraft(true)
    draft.paymentConfirmation=paymentConfirmationForm(savedFinance.item.paymentConfirmation)
    draft.paymentDraft=paymentDetailsForm(savedFinance.payment?.payments)
    draft.paymentVersion=savedFinance.payment?.version||''
    original.value=editorSignature()
    originalPaymentConfirmation.value=JSON.stringify(draft.paymentConfirmation)
    originalPaymentDetails.value=paymentDetailsSignature(draft.paymentDraft)
    pricingModeOnlySignature.value=null
    editorVisible.value=false
    ElMessage.success('价格与付款已保存')
    notifyCustomerFinanceHistory(draft.clientId)
    const financeFields=[
      documents.quotation_required!==undefined && 'quotationRequired',
      documents.statement_required!==undefined && 'statementRequired',
      (taxChange||paymentPayload.payment_method) && 'statementRequired',
      documents.invoice_required!==undefined && 'invoiceRequired',
    ].filter(Boolean)
    if(financeFields.length || paymentPayload.payment_method || taxChange || draft.statementRequiredDirty || !paymentOnly){
      window.dispatchEvent(new CustomEvent('translation-statements-changed',{
        detail:{projectId:draft.rootId,clientId:savedFinance.item.clientId,source:financePaymentSource,
          financeItem:savedFinance.item,financeFields,syncScope:!!taxChange&&draft.paymentMethod==='monthly'},
      }))
    }
    notifyPaymentChanged(draft.rootId,editor.value.paymentConfirmation,financePaymentSource)
    emit('saved')
    await load({fromTable:true})
  }
  catch(e){
    const review=e.rawDetail||e.response?.data?.detail
    if(review?.code==='document_consistency_review'){
      serverDocumentReview.value=review
      reviewReasonError.value=review.message
      await nextTick()
      reviewReasonInput.value?.focus()
    }else saveError.value=getLocalizedErrorMessage(e,'保存失败，请检查收费明细；如项目已被其他人修改，请重新打开后编辑')
  }
  finally{saving.value=false}
}

watch(()=>[editor.value.pricingMode,editor.value.adjustedTotal,editor.value.adjustedTotalInclTax],()=>{if(isClearedFinanceForm(editor.value)||editor.value.pricingMode==='fixed'&&hasFixedFeeAmount(editor.value))formRef.value?.clearValidate('adjustedTotal')})
const pricingModeSwitching=ref(false)
function pricingModeSnapshot(order){
  const fields=['pricingMode','priceAggregate','prices','adjustedTotal','adjustedTotalInclTax','billingTaxMode','effectiveBillingTaxMode','totalsExclTax','totalsInclTax','billingTotals']
  return Object.fromEntries(fields.map(field=>[field,copySavedValue(order[field])]))
}
async function changePricingMode(next){
  if(pricingModeSwitching.value||saving.value||editor.value.fixedPricingFrom||next===editor.value.pricingMode)return
  const priorSignature=editorSignature()
  const clean=!editorDirty.value
  const modeOnly=clean||pricingModeOnlySignature.value===priorSignature
  if(modeOnly&&pricingModeBeforeSwitch&&pricingModeOnlySignature.value===priorSignature&&next===pricingModeBeforeSwitch.pricingMode){
    Object.assign(editor.value,pricingModeBeforeSwitch)
    pricingModeBeforeSwitch=null
    pricingModeOnlySignature.value=null
    formRef.value?.clearValidate()
    return
  }
  const snapshot=clean?pricingModeSnapshot(editor.value):pricingModeBeforeSwitch
  pricingModeSwitching.value=true
  try{
    const switched=await requestPricingModeSwitch(editor.value,next,{
      createRate:newCustomerRate,
      confirm:message=>ElMessageBox.confirm(message,'切换计价方式',{type:'warning',confirmButtonText:'继续并清除',cancelButtonText:'取消',closeOnClickModal:false}),
    })
    if(switched){
      pricingModeBeforeSwitch=modeOnly?snapshot:null
      pricingModeOnlySignature.value=modeOnly?editorSignature():null
      formRef.value?.clearValidate()
    }
  }finally{pricingModeSwitching.value=false}
}
async function updateProjectFormFinance(paymentConfirmation){
  const target=projectFormTarget.value?.id===editor.value.id?projectFormTarget.value:null
  if(!target){
    if(documentParent.value)documentParent.value.paymentConfirmation=copySavedValue(paymentConfirmation)
    return
  }
  const project=await getProject(editor.value.rootId)
  const owner=target.id===project.id?project:(project.subOrders||[]).find(row=>row.id===target.id)
  if(!owner)throw new Error('已保存价格，但项目表单关联订单已变化，请重新打开项目')
  target.customerChargeItems=copySavedValue(owner.customerChargeItems||[])
  if(documentParent.value)documentParent.value.paymentConfirmation=copySavedValue(project.paymentConfirmation)
}
async function persistForForm(target,saved,parent=saved){
  const draft=pendingFormFinance.get(target)
  if(!draft)return
  const rootId=saved.parentProjectId||parent.id||saved.id
  const data=await getCustomerFinanceProject(rootId)
  const find=node=>node.id===saved.id?node:(node.children||[]).map(find).find(Boolean)
  const owner=find(data.item)
  if(!owner)throw new Error('项目已保存，请重新打开价格与付款补充客户说明')
  const payload={version:data.version,order_id:owner.id,record_initial_finance:true,customer_explanation:draft.customerExplanation}
  if(!owner.priceAggregate&&draft.pricingMode!=='fixed'&&draft.prices.length)payload.prices=draft.prices.map((row,index)=>ratePayload({...row,id:owner.prices?.[index]?.id||null}))
  await saveCustomerFinanceTable(rootId,payload)
  if(draft.statementChanged||draft.paymentMethod||Object.keys(draft.documents||{}).length||draft.billingTaxMode){
    const latest=await getCustomerFinanceProject(rootId)
    await saveCustomerFinanceProject(rootId,{
      version:latest.version,order_id:owner.id,documents_only:true,record_initial_finance:true,
      ...draft.documents,
      payment_method:draft.paymentMethod,
      billing_tax_mode:!owner.priceAggregate&&!owner.fixedPricingFrom&&draft.billingTaxMode?draft.billingTaxMode:undefined,
      statement_required:draft.statementChanged?draft.statementRequired:undefined,
      statement_sync:draft.statementSync,
    })
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{projectId:rootId}}))
  }
  notifyCustomerFinanceHistory(draft.clientId)
  pendingFormFinance.delete(target)
}
async function openForForm(target,parent=target){
  if(target.id){
    if(await openEditor({id:target.id,rootId:parent.id||target.id})){
      documentParent.value=parent;projectFormTarget.value=target
    }
    return
  }
  financeModule.value='translation'
  if(!canWrite)return
  localTarget.value=target;localPaymentParent.value=parent;documentParent.value=parent;linkedQuotationVisible.value=false
  const rootPayment=parent.id?await getCustomerFinanceProject(parent.id):null
  const charges=target.customerChargeItems||[],first=charges[0]
  const prices=charges.filter(row=>row.pricingMode==='metric').map(row=>({id:row.id,languagePair:row.languagePair||target.languagePair||parent.languagePair||'',amount:row.unitPriceExclTax??row.unitPriceInclTax,taxPrices:taxPriceForm(row),currency:row.currency||'CNY',metric:row.quantityBasis||row.metricType,unitSize:Number(row.unitSize||1)}))
  editor.value={...documentDraft(parent),clientShortName:parent.clientShortName,paymentConfirmation:paymentConfirmationForm(rootPayment?.item.paymentConfirmation||parent.paymentConfirmation),paymentDraft:paymentDetailsForm(rootPayment?.payment?.payments||parent.paymentDraft||[]),paymentVersion:rootPayment?.payment?.version||parent.paymentVersion||'',id:target.id||'',rootId:parent.id||'',orderNo:target.orderNo||target.subOrderNo||'新增项目',projectName:target.sourceFileName||target.projectName||target.subProjectName||'',languagePair:target.languagePair||parent.languagePair||'',clientId:parent.clientId,wordCountMatrix:JSON.parse(JSON.stringify(target.wordCountMatrix||{})),children:[],pricingMode:first?.pricingMode||'metric',currency:first?.currency||'CNY',prices:prices.length?prices:[newCustomerRate(String(target.languagePair||parent.languagePair||'').split('；')[0]||'')],adjustedTotal:first?.totalExclTax==null?undefined:Number(first.totalExclTax),adjustedTotalInclTax:first?.totalInclTax==null?undefined:Number(first.totalInclTax),billingMonth:orderStatementMonth(target.orderNo||target.subOrderNo||parent.orderNo)||first?.billingMonth||null,explanation:first?.remarks||'',customerExplanation:pendingFormFinance.get(target)?.customerExplanation||'',billingTaxMode:pendingFormFinance.get(target)?.billingTaxMode||null}
  if(pendingFormFinance.has(target))editor.value.prices=copySavedValue(pendingFormFinance.get(target).prices)
  const pendingDocuments=pendingFormFinance.get(target)?.documents||{}
  editor.value.clientName=parent.clientName
  if(rootPayment){
    editor.value.customerDocumentDefaults=rootPayment.item.customerDocumentDefaults||{}
    editor.value.customerDocumentSources=rootPayment.item.customerDocumentSources||{}
  }
  if(pendingDocuments.invoice_required!=null)editor.value.invoiceRequirementOverride=pendingDocuments.invoice_required
  const pendingPaymentMethod=pendingFormFinance.get(target)?.paymentMethod
  if(rootPayment){
    editor.value.statementRequired=rootPayment.item.statementRequired
    editor.value.paymentMethod=paymentMethodFor(rootPayment.item)
  }
  if(pendingPaymentMethod)editor.value.paymentMethod=pendingPaymentMethod
  if(pendingFormFinance.get(target)?.statementChanged)editor.value.statementRequired=pendingFormFinance.get(target).statementRequired
  editor.value.statementSync=pendingFormFinance.get(target)?.statementSync||null
  editor.value.statementCustomerSync=pendingFormFinance.get(target)?.statementCustomerSync||null
  editor.value.statementRequiredDirty=!!pendingFormFinance.get(target)?.statementChanged
  originalPrices.value=JSON.parse(JSON.stringify(editor.value.prices));referencePrices.value=[];saveError.value='';pricingModeOnlySignature.value=null;original.value='';clearFieldSearch();editorVisible.value=true;await nextTick();original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft)
  if(parent.clientId){
    editorLoading.value=true
    try{await loadNewOrderCustomerSettings(target,parent)}
    finally{editorLoading.value=false}
  }
}
async function loadNewOrderCustomerSettings(target,parent){
  const draft=editor.value
  const clientId=parent.clientId
  const baseline=editorSignature()
  const [preference,rates]=await Promise.allSettled([getStatementPreference(clientId),getCustomerTranslationRates(clientId)])
  if(!editorVisible.value||localTarget.value!==target||editor.value!==draft||parent.clientId!==clientId)return
  const dirty=editorSignature()!==baseline||baseline!==original.value
  if(preference.status==='fulfilled'){
    const data=preference.value
    const defaults={
      quotationRequired:data.quotation_required,
      statementRequired:['required','not_required'].includes(data.statement_default)?data.statement_default==='required':null,
      invoiceRequired:data.invoice_required,
      paymentMethod:data.payment_method?paymentMethodFor({paymentMethod:data.payment_method}):null,
    }
    const fields={quotationRequired:'quotationRequired',statementRequired:'statementRequired',invoiceRequired:'invoiceRequirementOverride',paymentMethod:'paymentMethod'}
    const explicit={quotationRequired:parent.quotationRequired===true||pendingFormFinance.get(target)?.documents?.quotation_required!=null,statementRequired:parent.statementRequiredExplicit,
      invoiceRequired:typeof draft.invoiceRequirementOverride==='boolean',paymentMethod:!!pendingFormFinance.get(target)?.paymentMethod}
    draft.customerDocumentDefaults=defaults
    draft.customerPreferenceRevision=data.revision
    if(!dirty&&!parent.id){
      const full= draft.paymentConfirmation?.isPaid && draft.paymentConfirmation?.paymentOption==='full'
      for(const [field,key] of Object.entries(fields)){
        if(defaults[field]==null||explicit[field])continue
        if(full && field==='statementRequired'&&defaults[field]===true)continue
        draft[key]=defaults[field]
        draft.customerDocumentSources[field]=true
      }
      if(!draft.customerDocumentSources.paymentMethod)draft.paymentMethod=paymentMethodFor(draft)
    }
  }
  if(rates.status==='fulfilled'){
    referencePrices.value=rates.value.items||[]
    if(!dirty&&draft.pricingMode!=='fixed'){
      const inherited = !target.customerChargeItems?.length && !pendingFormFinance.has(target)
        ? customerPricesForDirections(draft.languagePair,referencePrices.value,draft.wordCountMatrix) : []
      if(inherited.length)draft.prices=inherited
      else for(const price of draft.prices)fillCustomerReferencePrice(price,referencePrices.value,draft.wordCountMatrix)
    }
  }
  if(!dirty)original.value=editorSignature()
  const failure=[preference,rates].find(result=>result.status==='rejected')
  if(failure)saveError.value=getLocalizedErrorMessage(failure.reason,'客户笔译财务设置加载失败')
}
async function saveLocalFinance(){
  if(editor.value.rootId&&(paymentDetailsDirty.value||paymentConfirmationDirty.value)){
    const fresh=await getCustomerFinanceProject(editor.value.rootId)
    const saved=await saveCustomerFinanceProject(editor.value.rootId,{version:fresh.version,order_id:editor.value.rootId,documents_only:true,payment_draft:paymentDetailsDirty.value?paymentDetailsPayload(editor.value.paymentDraft):undefined,payment_version:editor.value.paymentVersion,payment_confirmation:paymentConfirmationPayload(editor.value.paymentConfirmation)})
    editor.value.paymentConfirmation=paymentConfirmationForm(saved.item.paymentConfirmation)
    editor.value.paymentDraft=paymentDetailsForm(saved.payment?.payments);editor.value.paymentVersion=saved.payment?.version||''
    notifyPaymentChanged(editor.value.rootId,editor.value.paymentConfirmation,financePaymentSource)
  }
  const paymentMethod=changedPaymentMethod()||pendingFormFinance.get(localTarget.value)?.paymentMethod
  const previous=pendingFormFinance.get(localTarget.value)
  const documents={...previous?.documents}
  if(changedCustomerDocuments.value.includes('quotationRequired'))documents.quotation_required=editor.value.quotationRequired
  if(editor.value.paymentMethod!=='special')delete documents.invoice_required
  else if(changedCustomerDocuments.value.includes('invoiceRequired'))documents.invoice_required=editor.value.invoiceRequirementOverride
  pendingFormFinance.set(localTarget.value,{prices:copySavedValue(editor.value.prices),customerExplanation:editor.value.customerExplanation||'',pricingMode:editor.value.pricingMode,billingTaxMode:editor.value.billingTaxMode||null,statementSync:editor.value.paymentMethod==='special'?editor.value.statementSync:undefined,statementCustomerSync:editor.value.paymentMethod==='special'?editor.value.statementCustomerSync:undefined,statementRequired:editor.value.statementRequired,statementChanged:editor.value.paymentMethod==='special'&&(editor.value.statementRequiredDirty||previous?.statementChanged),paymentMethod,documents,clientId:editor.value.clientId})
  applyDocumentDraft(false)
  localPaymentParent.value.paymentConfirmation=JSON.parse(JSON.stringify(editor.value.paymentConfirmation))
  localPaymentParent.value.paymentDraft=paymentDetailsPayload(editor.value.paymentDraft)
  localPaymentParent.value.paymentVersion=editor.value.paymentVersion
  const old=localTarget.value.customerChargeItems||[]
  if(editor.value.pricingMode==='fixed')localTarget.value.customerChargeItems=[{id:old.length===1&&old[0].pricingMode==='fixed'?old[0].id:null,sequenceNo:1,itemName:'翻译费',pricingMode:'fixed',currency:editor.value.currency||'CNY',totalExclTax:editor.value.adjustedTotal??null,totalInclTax:editor.value.adjustedTotalInclTax??null,unitPriceExclTax:null,unitPriceInclTax:null,unitSize:null,metricType:null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}]
  else localTarget.value.customerChargeItems=editor.value.prices.map((price,index)=>({id:price.id||null,sequenceNo:index+1,itemName:'翻译费',pricingMode:'metric',metricType:resolveRateQuantity(editor.value.wordCountMatrix,price.metric).metric,quantityBasis:price.metric,languagePair:price.languagePair,unitSize:price.unitSize||1,unitPriceExclTax:price.taxPrices?.unitPriceExclTax??null,unitPriceInclTax:price.taxPrices?.unitPriceInclTax??null,currency:price.currency||'CNY',totalExclTax:index===0?editor.value.adjustedTotal??null:price.taxPrices?.totalExclTax??null,totalInclTax:index===0?editor.value.adjustedTotalInclTax??null:price.taxPrices?.totalInclTax??null,billingMonth:editor.value.billingMonth||null,remarks:editor.value.explanation||''}))
  original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft);editorVisible.value=false;emit('saved');ElMessage.success('财务填写已保留，保存项目后生效')
}
async function editPaymentProject(row){if(editorVisible.value&&editor.value.rootId===row.id)return;await openAggregateOrder(row.id,row.id)}
async function reviewInvoicePricing(row) {
  if (editorVisible.value && editor.value.id === row.id) {
    financeModule.value = 'translation'
    invoiceReview.value = true
  } else if (!await openEditor({ ...row, rootId: row.rootId || row.id }, 0, true)) {
    return
  }
  paymentVisible.value = false
  linkedPaymentVisible.value = false
  await nextTick()
  locateInvoiceRequirement()
}
function openPaymentManagement(){paymentScopeOrder.value=null;paymentVisible.value=true}
async function openLinkedPayment(){if(editor.value.rootId)linkedPaymentVisible.value=true}
function onPaymentSaved(result){
  paymentContextId.value=String(result.project_id||result.projectId||paymentContextId.value)
  if(editor.value.rootId===paymentContextId.value){
    if(!paymentConfirmationDirty.value&&!paymentDetailsDirty.value)void onLinkedPaymentSaved(result)
    else {
      saveError.value='该订单付款已在另一窗口保存，当前付款草稿保留，请打开付款情况核对'
      // 付款草稿冲突不应阻止其他已保存价格字段同步。
      if(editorVisible.value)void rebaseEditorAfterLibrary().catch(e=>{saveError.value=getLocalizedErrorMessage(e,'关联价格同步失败，当前输入已保留')})
    }
  }
  if(!props.editorOnly)void load()
}
async function confirmPayment(paymentId){
  const {rootId,paymentVersion,fixedPricingFrom}=editor.value
  if(!canManageHr()||!rootId||!paymentVersion||fixedPricingFrom||localTarget.value||saving.value||editorDirty.value)return
  if(documentReviewOutstanding.value)return ElMessage.warning('请先核对各级子订单的单据需求和计费口径并保存')
  saving.value=true;saveError.value=''
  try{
    const result=await confirmProjectPayment(rootId,{version:paymentVersion,payment_id:paymentId})
    await onLinkedPaymentSaved(result)
    notifyPaymentChanged(rootId,result.confirmation,financePaymentSource)
    ElMessage.success('付款已确认')
  }catch(e){saveError.value=getLocalizedErrorMessage(e,'付款确认失败')}
  finally{saving.value=false}
}
function onPaymentChanged(event){
  if(!event.detail?.projectId||[financePaymentSource,`${financePaymentSource}-management`,`${financePaymentSource}-linked`].includes(event.detail.source))return
  if(paymentSummary.value?.orders?.some(order=>order.id===event.detail.projectId))void loadPaymentSummary()
  onPaymentSaved({project_id:event.detail?.projectId,confirmation:event.detail?.confirmation})
}

async function onLinkedPaymentSaved(result){
  if(!original.value||!editor.value.rootId)return
  saveError.value=''
  const before=JSON.parse(original.value)
  editor.value.paymentConfirmation=paymentConfirmationForm(result.confirmation)
  originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation)
  before[8]=paymentConfirmationInput(editor.value.paymentConfirmation)
  if(result.payments){
    editor.value.paymentDraft=paymentDetailsForm(result.payments)
    editor.value.paymentVersion=result.version
    before[16]=paymentDetailsPayload(editor.value.paymentDraft)
  }
  originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft)
  original.value=JSON.stringify(before)
  for(const parent of new Set([documentParent.value,localPaymentParent.value]))if(parent)parent.paymentConfirmation=JSON.parse(originalPaymentConfirmation.value)
  try{await rebaseEditorAfterLibrary()}catch(e){saveError.value=getLocalizedErrorMessage(e,'付款已保存，价格版本读取失败，请重新打开价格与付款核对')}
  void loadPaymentSummary()
  emit('saved')
}
watch(()=>[filters.projectStatus,props.initialMonth,props.previewMonths,props.previewMode,JSON.stringify(props.managerQuery)],()=>{projectPreview.value=null},{deep:true})
watch(rows,()=>{projectPreview.value=null})
watch([statementSelected,rows],()=>{if(props.statementClientView)emit('statement-selection-change')},{flush:'post'})
watch(()=>props.clientIds.join(','),()=>{if(props.statementClientView)search()})
defineExpose({openForForm,persistForForm,statementSelection,reloadProjects:load,flushTableEdits:()=>tableEditing.flush()})

watch(()=>props.clientId,search)
watch(()=>[props.initialMonth,props.periodNumber,JSON.stringify(props.managerQuery)],()=>{if(props.statementClientView){filters.month=props.initialMonth||'';search()}})
onMounted(()=>{if(props.clientId||props.clientIds.length)void load()})
onActivated(()=>{if(props.editorOnly)return;managerScope.value=props.clientScope?'all':'self';managerIds.value=[];managerDraftScope.value='self';managerDraftIds.value=[];filters.manager='';managerPickerVisible.value=false;page.value=1;subtotalPage.value=1;void load()})
function showsCustomer(clientId){
  return !!clientId&&((editorVisible.value&&String(editor.value.clientId)===String(clientId))||
    (!props.editorOnly&&rows.value.some(row=>String(row.clientId)===String(clientId))))
}
function onCustomerRatesSaved(event){
  refreshStatementStatus(event)
  if(event.detail?.fromCustomer&&showsCustomer(event.detail?.clientId)){
    ElMessage.info('客户参考价已更新。如与项目单价不同，可在项目中比较后选择。')
  }
}
function refreshStatementStatus(event){
  void loadPaymentSummary()
  if(event?.detail?.source===financePaymentSource)return
  if(!props.editorOnly)void load({fromTable:true})
  if(event?.detail?.financeItem)syncMergedFinanceForm(event.detail.financeItem,event.detail.financeFields)
  const {projectId,clientId}=event?.detail||{}
  if(!editorVisible.value||saving.value||localTarget.value||!original.value)return
  if(clientId&&String(editor.value.clientId)!==String(clientId))return
  if(projectId&&editor.value.rootId!==projectId&&!event.detail?.syncScope)return
  const refresh=async()=>{
    if(event?.detail?.syncScope===true && editor.value.rootId!==projectId){
      const latest=await getCustomerFinanceProject(editor.value.rootId)
      await rebaseEditorAfterLibrary(latest)
      syncMergedFinanceForm(latest.item,event.detail.financeFields)
      return
    }
    await rebaseEditorAfterLibrary()
  }
  void refresh().catch(error=>{
    saveError.value=getLocalizedErrorMessage(error,'项目财务刷新失败，当前填写已保留')
  })
}
function onCustomerStatementPreferenceSaved(event){
  if(!event.detail?.fromProject&&showsCustomer(event.detail?.clientId)){
    ElMessage.info('客户管理已更新单据和结算设置，请核对同步结果')
  }
  if(localTarget.value&&editorVisible.value&&String(event.detail?.clientId)===String(editor.value.clientId)){
    void loadNewOrderCustomerSettings(localTarget.value,localPaymentParent.value)
  }
  if(!event.detail?.fromProject||!saving.value)refreshStatementStatus(event)
}
function refreshWordCounts(event){
  const {entityType,entityId}=event.detail||{}
  refreshStatementStatus({detail:{projectId:entityType==='project'?entityId:undefined}})
}
onMounted(()=>window.addEventListener('translation-word-count-saved',refreshWordCounts))
onBeforeUnmount(()=>window.removeEventListener('translation-word-count-saved',refreshWordCounts))
onMounted(()=>{connectPaymentSync();window.addEventListener('customer-statement-preference-saved',onCustomerStatementPreferenceSaved);window.addEventListener('translation-statements-changed',refreshStatementStatus);window.addEventListener('translation-finance-changed',onCustomerRatesSaved);window.addEventListener(paymentChangeEvent,onPaymentChanged)})
onDeactivated(()=>{editorSequence++;editorLoading.value=false;paymentVisible.value=false;invoiceVisible.value=false;quotationVisible.value=false;statementVisible.value=false;specialStatementVisible.value=false;backupStatementVisible.value=false;managerPickerVisible.value=false;historyVisible.value=false;clearTimeout(timer);sequence++;controller?.abort();loading.value=false})
async function guardEditor(){if(!await tableEditing.flush())return false;if(!editorVisible.value)return true;if(saving.value)return false;await closeEditor();return !editorVisible.value}
onBeforeRouteLeave(guardEditor)
onBeforeRouteUpdate((to,from)=>to.query.section!==from.query.section?guardEditor():true)
onBeforeUnmount(()=>{window.removeEventListener('customer-statement-preference-saved',onCustomerStatementPreferenceSaved);window.removeEventListener('translation-statements-changed',refreshStatementStatus);window.removeEventListener('translation-finance-changed',onCustomerRatesSaved);window.removeEventListener(paymentChangeEvent,onPaymentChanged);disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
useProjectStatusSync('translation',rows,{enabled:()=>!props.editorOnly,onChanged:()=>{if(!loading.value&&!editorLoading.value)void load({fromTable:true})}})
</script>

<style scoped>
.finance-reference-content>.finance-reference-conflict{color:var(--el-color-warning-dark-2)}
.finance-settlement-tabs--single > :deep(.el-tabs__header) { display: none; }
.finance-order-index{display:flex;align-items:center;gap:4px;min-height:20px;line-height:20px;white-space:nowrap}
.finance-project-table--order-controls :deep(td.finance-order-index-cell > .cell){overflow:visible}
.finance-order-tree-line{
  position:absolute;
  inset-block:0;
  inset-inline-start:var(--finance-tree-x);
  border-inline-start:1px solid var(--el-text-color-placeholder);
  pointer-events:none;
}
.finance-order-tree-line--start{inset-block-start:19px}
.finance-order-tree-line--end{inset-block-end:auto;height:15px}
.finance-order-tree-line--branch::after,.finance-order-tree-line--end::after{
  content:'';
  position:absolute;
  inset-block-start:14px;
  inset-inline-start:-1px;
  width:9px;
  border-block-end:1px solid var(--el-text-color-placeholder);
}
.finance-project-table--order-controls :deep(.el-table__expand-icon){display:none}
.finance-client-group-header{display:inline-flex;align-items:center;gap:12px;white-space:nowrap}.finance-client-group-header small{color:var(--el-text-color-secondary)}.finance-client-group-header .el-pagination{margin:0}
.finance-language-directions{display:flex;align-items:center;gap:4px;min-width:0}.finance-direction-text{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.finance-language-directions .el-button{flex:none;padding:0}.finance-direction-details{max-height:min(360px,calc(100vh - 160px));overflow-y:auto;margin:0;padding-inline-start:20px;overflow-wrap:anywhere}
.finance-missing-orders{margin-top:4px}.finance-missing-orders :deep(.el-button){padding:0}.finance-missing-order-list{max-height:min(340px,calc(100vh - 150px));overflow:auto;margin:0;padding-inline-start:20px;overflow-wrap:anywhere;user-select:text}
.finance-settlement-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.finance-settlement-heading>h4{margin:0}
:global(.main-content:has(.finance-workspace)){padding-bottom:0!important;scroll-padding-bottom:0}
:global(.el-dialog.draggable-form-dialog.customer-statement-dialog>.el-dialog__body){padding-bottom:0;scroll-padding-bottom:0}
.customer-finance>:deep(.el-card__body){padding-bottom:0}
.finance-invoice-review :deep([data-field-key="invoiceRequired"]) {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 4px;
  border-radius: 4px;
}
.finance-invoice-review :deep(.price-amount-filled .el-input-number .el-input__wrapper),
.finance-invoice-review :deep(.finance-adjusted-amount .finance-amount-filled .el-input__wrapper) {
  outline: 2px solid var(--el-color-primary);
}
.finance-total-heading.finance-total-heading--filled{background:#111;color:#fff;font-weight:400;border:1px solid #111;border-radius:4px;padding:2px 8px;box-sizing:border-box}.finance-total-heading.finance-total-heading--filled>small{color:#fff;font-weight:400}
.finance-settlement-row{--finance-total-caption-height:18px}.finance-settlement-row--fixed{--finance-total-caption-height:0px}@media(min-width:1001px){.finance-settlement-row .finance-notes-grid :deep(.el-textarea__inner){height:calc(5mm + var(--finance-total-caption-height) + var(--el-component-size,32px));min-height:calc(5mm + var(--finance-total-caption-height) + var(--el-component-size,32px))}}
.finance-total-line>.finance-calculated-amount,.finance-total-line>.finance-adjusted-amount{display:flex;flex-direction:column;gap:4px;align-self:flex-start}.finance-total-line>.finance-calculated-amount>small,.finance-total-line>.finance-adjusted-amount>small{position:static;display:block;height:14px;line-height:14px}.finance-amount-filled :deep(.el-input__inner){color:#111;font-weight:700;-webkit-text-fill-color:#111}
.finance-pricing-region{margin:16px 0;padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.finance-pricing-region-title{font-size:14px;font-weight:700;margin:0 0 12px}
.finance-order-config{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:12px;margin:16px 0}
.finance-order-config>.finance-pricing-region{margin:0;min-width:0}
.finance-order-config>.finance-pricing-region:first-child{grid-row:span 2}
.finance-order-config :deep(.el-form-item:last-child){margin-bottom:0}
@media(max-width:880px){.finance-order-config{grid-template-columns:minmax(0,1fr)}.finance-order-config>.finance-pricing-region:first-child{grid-row:auto}}
.finance-statement-payment{display:flex;flex-direction:column;align-items:flex-start}
.finance-document-flag{display:flex;align-items:center;gap:2px;flex-wrap:wrap}
.finance-document-flag .el-checkbox{height:24px}
.finance-document-flag .el-select{width:100%;max-width:126px}
.finance-document-flag--invoice{width:100%;flex-wrap:nowrap;gap:4px}
.finance-document-flag--invoice>span:first-child{flex:none;white-space:nowrap}
.finance-document-flag--invoice .el-select{flex:1;min-width:0;width:auto}
.finance-payment-methods{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;width:100%}
.finance-payment-method-hint{margin:4px 0;color:var(--el-text-color-secondary);line-height:1.5;font-size:13px}
.finance-editor-heading :deep(.dialog-field-search-header__heading){flex:1 1 auto;min-width:0}
.finance-editor-heading :deep(.dialog-field-search-header__extra){flex:1 1 180px;min-width:0}
.finance-editor-project-name{display:block;user-select:text;cursor:text;overflow-wrap:anywhere;font-size:14px;line-height:1.5;color:var(--el-text-color-regular)}
.finance-editor-manager{display:block;user-select:text;cursor:text;overflow-wrap:anywhere;font-size:13px;color:var(--el-text-color-secondary)}
.finance-sibling-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.finance-sibling-actions :deep(.el-button + .el-button){margin-left:0}
.finance-document-review{margin:16px 0;display:grid;gap:12px}.finance-document-review h4{margin:0}.finance-document-review-actions{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.finance-document-review-actions .el-button+.el-button{margin:0}
.finance-document-review summary{cursor:pointer}
.finance-review-orders{display:grid;gap:4px;max-height:180px;overflow:auto}
.finance-billing-period{display:flex;gap:8px;align-items:center;width:100%}
.finance-billing-period :deep(.readonly-field){flex:1;min-width:0}
.finance-order-pricing-review{margin-top:8px}
.finance-pricing-review-unit{white-space:pre-line}
.finance-order-summary-heading{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.finance-order-summary-heading h4{margin:0;font-size:14px}
.finance-order-summary :deep(.el-alert + .el-alert){margin-top:8px}
.finance-merged-orders{margin:10px 0 16px}
.finance-merged-totals{margin-bottom:16px}
.finance-merged-total :deep(.el-form-item__label),.finance-merged-total :deep(.el-textarea__inner){font-weight:700}
.finance-merged-difference :deep(.el-select__wrapper){box-shadow:0 0 0 1px var(--el-color-warning) inset}
.finance-order-summary .finance-payment-totals{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:12px}
.finance-summary-notes,.finance-summary-breakdown{margin-top:12px}
.finance-summary-breakdown{padding-top:8px;border-top:1px solid var(--el-border-color-lighter)}
@media(max-width:720px){.finance-order-summary .finance-payment-totals{grid-template-columns:minmax(0,1fr)}}
.finance-settlement-row{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:16px;align-items:start}.finance-settlement-row>*{min-width:0}@media(max-width:1000px){.finance-settlement-row{grid-template-columns:minmax(0,1fr)}}
.finance-calculated-amount{position:relative}.finance-calculated-amount>small{position:absolute;bottom:100%;left:2px;font-size:10px;line-height:14px;color:var(--el-text-color-secondary);white-space:nowrap}.finance-calculated-amount :deep(.readonly-field){width:100%}
.finance-settlement-section .finance-total-line{margin-top:5mm}
.finance-total-heading{display:inline-flex;align-items:baseline;gap:8px}.finance-total-heading>small{font-size:12px;font-weight:400;color:var(--el-text-color-secondary);white-space:pre-line}.finance-adjusted-amount{position:relative}.finance-adjusted-amount>small{position:absolute;bottom:100%;left:2px;font-size:10px;line-height:14px;color:var(--el-text-color-secondary);white-space:nowrap}
.finance-notes-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.finance-notes-grid>*{min-width:0}.finance-notes-grid--single{grid-template-columns:minmax(0,1fr)}@media(max-width:680px){.finance-notes-grid{grid-template-columns:minmax(0,1fr)}}
.finance-sheet-form :deep(.el-table__cell){vertical-align:top;padding:5px 0}
.finance-sheet-form :deep(.cell){padding:0 5px}
.finance-column-heading{display:flex;align-items:center;gap:4px;white-space:normal;overflow-wrap:anywhere}
.finance-pin-toggle{border:0;background:transparent;color:var(--el-color-primary);font:inherit;cursor:pointer;padding:0;font-size:12px}
.customer-finance { overflow: visible; }
.customer-finance > :deep(.el-card__body) { overflow: visible; }
.finance-collapsed > :deep(.el-card__header) { border-bottom: 0; }
.finance-collapsed > :deep(.el-card__body) { display: none; }
.finance-project-table { overflow: visible; }
.finance-project-table :deep(.el-table__body-wrapper),
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar) { overflow: visible; }
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar > .el-scrollbar__bar.is-horizontal) {
  position: sticky;
  bottom: 0;
  width: calc(100% - 4px);
  height: 14px;
  z-index: 5;
  background: var(--el-fill-color-light);
}
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar > .el-scrollbar__bar.is-horizontal > .el-scrollbar__thumb) {
  opacity: 0.7;
}
.finance-project-table :deep(.el-table__body-wrapper > .el-scrollbar > .el-scrollbar__bar.is-horizontal > .el-scrollbar__thumb:hover) {
  opacity: 0.9;
}
.finance-project-table :deep(.el-table__header-wrapper:not(.app-table-persistent-header)) {
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
.finance-pricing-config{padding:14px 16px;border:1px solid var(--el-border-color);border-radius:8px;margin-bottom:16px}.finance-config-grid,.finance-settlement-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.finance-config-grid :deep(.el-form-item){margin-bottom:0}.finance-pricing-form :deep(.el-date-editor),.finance-pricing-form :deep(.el-input-number),.finance-pricing-form :deep(.el-select){width:100%;max-width:100%}.finance-reference-item{margin:0 0 12px}.finance-reference-content{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.finance-reference-content>span{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}.finance-calculation-hint{margin-top:10px}.finance-settlement-section{margin-top:16px;padding-top:14px;border-top:1px solid var(--el-border-color-lighter)}.finance-settlement-section h4{font-size:14px;margin:0 0 12px}.finance-settlement-grid{gap:0 16px}.finance-total-line{display:flex;align-items:center;gap:8px;width:100%;min-width:0}.finance-total-line>*{flex:1;min-width:0}.finance-total-line :deep(.readonly-field){min-width:0}.finance-settlement-grid--fixed{grid-template-columns:repeat(3,minmax(0,1fr))}.finance-sync-actions{margin-top:12px;padding-top:12px;border-top:1px solid var(--el-border-color-lighter);display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}.finance-sync-actions :deep(.el-form-item){margin-bottom:8px}@media(max-width:720px){.finance-config-grid,.finance-settlement-grid,.finance-settlement-grid--fixed{grid-template-columns:minmax(0,1fr)}.finance-pricing-config{padding:12px}.finance-sync-actions{gap:8px}}
.statement-client-finance .finance-project-table :deep(.el-table__header-wrapper:not(.app-table-persistent-header)){top:0}.statement-client-finance{margin:12px 0}
</style>

<style scoped>
.finance-language-directions{display:flex;align-items:center;gap:4px;min-width:0}.finance-direction-text{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.finance-language-directions .el-button{flex:none;padding:0}.finance-direction-details{max-height:min(360px,calc(100vh - 160px));overflow-y:auto;margin:0;padding-inline-start:20px;overflow-wrap:anywhere}
.finance-client-group-toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0;color:var(--el-text-color-secondary);font-size:12px}.finance-client-group-toggle{display:flex;gap:12px;align-items:center;border:0;background:transparent;font:inherit;font-weight:700;color:var(--el-color-primary);cursor:pointer;padding:6px 4px;white-space:nowrap}.finance-client-group-toggle small{font-weight:400;color:var(--el-text-color-secondary)}.finance-project-table :deep(.finance-client-group-row td){background:#e8eef5!important;border-top:2px solid #b9c9dc;border-bottom:1px solid #cbd5e1}.finance-project-table :deep(.finance-client-group-row .cell){overflow:visible}
</style>
