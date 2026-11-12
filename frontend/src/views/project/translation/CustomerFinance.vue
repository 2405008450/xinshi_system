<template>
  <el-card class="customer-finance" :class="{'finance-editor-only':editorOnly,'statement-client-finance':statementClientView}" shadow="never">
    <template #header><div v-if="!statementClientView" class="finance-heading"><strong>笔译</strong><div class="finance-heading-actions"><el-button @click="quotationVisible=true">报价单</el-button><el-button @click="statementContext=null;statementVisible=true">对账单</el-button><el-button @click="openPaymentManagement">发票、查账与追账</el-button><el-button @click="revenueVisible=true">营收统计</el-button><TableColumnSettings v-model="selectedKeys" settings-key="translation-customer-finance" :columns="columns" @reset="resetColumns" /></div></div><strong v-else>客户项目</strong></template>
    <RevenueStatisticsDialog v-model="revenueVisible" :query="financeParams()" :scope-label="managerLabel" />
    <ProjectPaymentDialog v-model="paymentVisible" :query="financeParams()" :can-review-invoice="canWrite" @edit="editPaymentProject" @invoice="openRowInvoice" @review-invoice="reviewInvoicePricing" />
    <ProjectPaymentDialog v-model="linkedPaymentVisible" :initial-project-id="editor.rootId" lock-project :can-review-invoice="canWrite" @edit="editPaymentProject" @invoice="openRowInvoice" @review-invoice="reviewInvoicePricing" />
    <ProjectInvoiceDialog v-model="invoiceVisible" :context="invoiceContext" @saved="onInvoiceSaved" />
    <CustomerQuotationDialog v-model="quotationVisible" :projects="rows" :query="financeParams()" />
    <CustomerQuotationDialog v-model="linkedQuotationVisible" :draft="editor.quotationDraft" :draft-project="editorDocumentProject" defer-save @update:draft="value=>{editor.quotationDraft=value;editor.quotationDraftDirty=true}" />
    <CustomerStatementDialog v-model="statementVisible" :client-context="statementContext" :billing-month="filters.month"
      :manager-label="managerLabel" :manager-query="activeManagerQuery" />
    <div v-if="statementClientView" class="finance-preview-actions"><el-button :loading="previewLoading" :disabled="loading" @click="previewProjects">对账单预览</el-button><span v-if="requireStatementForSelection">已选 {{statementSelected.length}} 项。未勾选时使用筛选结果中标记为「需」的项目。「无需」项目可在对账单列重新确认。</span><span v-else>已选 {{statementSelected.length}} 项；未勾选时使用全部筛选结果</span></div>
    <AppForm v-if="statementClientView" :inline="true" :model="filters" @submit.prevent="search"><el-form-item label="项目状态"><el-select v-model="filters.projectStatus" multiple collapse-tags collapse-tags-tooltip clearable placeholder="全部状态" style="width:260px;max-width:100%" @change="search"><el-option v-for="status in statuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item></AppForm>
    <AppForm v-if="!statementClientView" :inline="true" :disabled="editorLoading" :model="filters" class="finance-search" @submit.prevent="search">
      <slot name="project-type-filter" />
      <el-form-item label="关键词"><el-input class="finance-keyword" v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="账单月份"><el-date-picker class="finance-month" :model-value="filters.month" type="month" value-format="YYYY-MM" placeholder="全部月份" title="按订单号年月筛选，如 TP-261029-010 对应 2026-10" clearable @update:model-value="setBillingMonth" /></el-form-item>
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
    <p v-if="!statementClientView" class="finance-help">按语种方向维护多条单价，默认优先采用客户统计的数量和单位，客户未填时采用我司统计；也可手动选择我司统计，两者均未填时提示补录。母订单单价复制至匹配语种的下级，单独改价的下级保留；工作量时父级汇总下级金额，各币种单独小计；固定收费直接采用登记的一口价。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p v-if="canWrite&&!statementClientView" class="finance-help">字数统计之后的字段可直接填写，修改后自动保存，与“价格与付款”窗口同步。</p>
    <el-alert v-if="tableError" type="error" :closable="false" :title="tableError"><el-button link type="primary" @click="tableEditing.flush()">重试保存</el-button><el-button link type="primary" @click="discardTableDrafts">放弃未保存内容并重新加载</el-button></el-alert>
    <div v-if="filters.clientOrderCount==='multiple'" class="finance-client-group-toolbar"><span>按当前筛选结果统计：{{total}} 个多订单客户，共 {{groupOrderTotal}} 个母订单；每页 10 个客户。</span><el-button link @click="collapseClientGroups(false)">全部展开</el-button><el-button link @click="collapseClientGroups(true)">全部收起</el-button></div>
    <AppForm :model="tableEditing.states" label-position="top" class="finance-sheet-form" data-auto-draft="off">
    <el-table v-loading="loading||editorLoading" ref="statementTableRef" @selection-change="statementSelected=$event;projectPreview=null" class="finance-project-table" :data="tableRows" :span-method="clientGroupSpan" :row-class-name="({row})=>row._clientGroup?'finance-client-group-row':''" row-key="id" border default-expand-all scrollbar-always-on empty-text="暂无笔译项目">
      <OrderedTableColumns settings-key="translation-customer-finance" preserve-fixed>
      <el-table-column v-if="statementClientView" type="selection" :selectable="canSelectStatementProject" reserve-selection width="44" />
      <el-table-column type="index" label="序号" :fixed="fixedColumns.length?'left':false" width="60" :index="index => (page-1)*10+index+1">
        <template #default="{row,$index}">
          <div v-if="row._clientGroup" class="finance-client-group-header">
            <button type="button" class="finance-client-group-toggle" :aria-expanded="!row.collapsed" @click="toggleClientGroup(row.groupKey)">{{row.collapsed?'▶':'▼'}} {{row.clientName}}</button>
            <small>共 {{row.pageCount}} 页，{{row.orderTotal}} 条</small>
            <el-pagination v-if="!row.collapsed && row.pageCount>1" small layout="prev, pager, next" :pager-count="5"
              :aria-label="`${row.clientName}订单分页`" :current-page="row.currentPage" :page-size="clientOrderPageSize" :total="row.orderTotal"
              @update:current-page="changeClientOrderPage(row.groupKey,$event)" />
          </div>
          <span v-else>{{filters.clientOrderCount==='multiple'||childPagination?displayIndexes.get(row.id):((page-1)*10+$index+1)}}</span>
        </template>
      </el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :width="column.width" :fixed="fixedColumns.includes(column.key)?'left':false" :prop="column.key">
        <template #header><div class="finance-column-heading"><ConfiguredColumnHeaderFilter v-if="headerFilterDefinitions[column.key] && !(requireStatementForSelection && column.key==='statementRequired')" :definition="headerFilterDefinitions[column.key]" :model-value="filters[column.key]" @update:model-value="filters[column.key]=$event" @change="search" @clear="search" /><span v-else>{{column.label}}</span><button v-if="['orderNo','projectName'].includes(column.key)" type="button" class="finance-pin-toggle" :aria-label="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :title="`${fixedColumns.includes(column.key)?'取消固定':'固定'}${column.label}`" :aria-pressed="fixedColumns.includes(column.key)" @click.stop="toggleFixedColumn(column.key)">{{fixedColumns.includes(column.key)?'◆':'◇'}}</button></div></template>
        <template #default="{row}"><span v-if="row._clientGroup" /><CustomerStatementRequiredToggle v-else-if="column.key==='statementRequired'" :row="row" :allow-month-sync="!requireStatementForSelection" :prepare="tableEditing.flush" @saved="emit('saved',$event)" /><CustomerFinanceTableCell v-else-if="tableFields.includes(column.key)&&(canWrite||['totalPrice','totalInclTax','explanation'].includes(column.key)||column.key==='unitPrice'&&row.priceAggregate)" :field="column.key" :row="row" :state="tableEditing.stateFor(row)" :prepare="tableEditing.flush" :readonly="!canWrite || !!row.fixedPricingFrom" @edit-order="openAggregateOrder(row.rootId,$event)" @saved="onTablePriceSaved" @commit="tableEditing.commit(row,$event)" /><TranslationOrderDetailPopover v-else-if="column.key==='orderNo'&&!row.fixedPricingFrom" :order="row" /><WordCountMatrixPopover v-else-if="column.key==='wordCount'" :model-value="row.wordCountMatrix||{}" :entity-type="row.id===row.rootId?'project':'suborder'" :entity-id="row.id" title="项目字数统计" :read-only="!canWrite || statementClientView || row.wordCountMatrixSource === 'suborder_aggregate'">
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
    <section v-if="statementClientView&&projectPreview" class="finance-project-preview"><h3>对账单预览（尚未生成）</h3><p>客户编号：{{projectPreview.client_code||'—'}}（仅系统可见）</p><CustomerStatementPaper :statement="projectPreview" /></section>
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
        <DialogFieldSearchHeader class="finance-editor-heading" ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`价格与付款 · ${editor.orderNo || ''}`" copyable-title :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch">
          <template #actions>
            <span class="finance-editor-project-name">{{ editor.sourceFileName || editor.projectName || '-' }}</span>
            <span class="finance-editor-manager">客户经理：{{ editor.clientManager || '未分配' }}</span>
          </template>
        </DialogFieldSearchHeader>
        <div v-if="siblingOrders && !localTarget && financeModule === 'translation'" class="finance-sibling-actions" role="group" aria-label="切换同级子订单">
          <el-button size="small" :title="siblingOrders.previous?.orderNo" :disabled="siblingNavigationDisabled || !siblingOrders.previous" @click="openSibling(-1)">‹ 上一个同级子订单</el-button>
          <el-button size="small" :title="siblingOrders.next?.orderNo" :disabled="siblingNavigationDisabled || !siblingOrders.next" @click="openSibling(1)">下一个同级子订单 ›</el-button>
        </div>
      </template>
      <div ref="editorBody" v-loading="saving || editorLoading" :class="{'finance-invoice-review': invoiceReview}">
        <CustomerFinanceModuleTabs :key="editor.id" v-model="financeModule" module="translation" :client-id="editor.clientId"><template #translation>
        <AppForm v-if="editor.priceAggregate" ref="formRef" :model="editor" :rules="documentRules" label-position="top" :disabled="saving"><h3>计价方式与单据</h3><el-form-item label="计价方式"><el-radio-group model-value="aggregate" :disabled="pricingModeSwitching" @update:model-value="changePricingMode"><el-radio-button value="aggregate">子订单汇总</el-radio-button><el-radio-button value="fixed">固定收费</el-radio-button></el-radio-group></el-form-item><TranslationDocumentRequirements v-model="editor" :persist-statement="localTarget?undefined:saveEditorStatementRequirement" @quotation="linkedQuotationVisible=true" @statement="openEditorStatement" @invoice="openEditorInvoice" /><CustomerFinanceAggregateSummary :order="editor" :can-edit="canWrite" @edit-order="openAggregateOrder(editor.rootId,$event)" @payment="openLinkedPayment" /><PaymentRegistrationFields v-model="editor" :project-id="editor.rootId" prefix="paymentConfirmation" :can-confirm="canManageHr() && !localTarget && !!editor.paymentVersion" :confirm-disabled="editorDirty || saving" @confirm-payment="confirmPayment"><template #actions><el-button @click="openLinkedPayment">发票、查账与追账</el-button></template></PaymentRegistrationFields></AppForm>
        <AppForm v-else ref="formRef" :model="editor" :rules="documentRules" label-position="top" :disabled="saving||!!editor.fixedPricingFrom" class="finance-pricing-form">
          <section class="finance-pricing-region" data-dialog-field-search-group data-dialog-field-search-group-title="计价方式与单据">
          <h3 class="finance-pricing-region-title">计价方式与单据</h3>
          <div class="finance-pricing-config">
            <div class="finance-config-grid">
              <el-form-item label="计价方式"><el-radio-group :model-value="editor.pricingMode" :disabled="pricingModeSwitching||!!editor.fixedPricingFrom" @update:model-value="changePricingMode"><el-radio-button v-if="editor.children?.length" value="aggregate">子订单汇总</el-radio-button><el-radio-button v-else value="metric">工作量</el-radio-button><el-radio-button value="fixed">固定收费</el-radio-button></el-radio-group><small v-if="editor.fixedPricingFrom">随上级订单 {{editor.fixedPricingFrom}} 固定收费</small></el-form-item>
              <div><TranslationDocumentRequirements v-model="editor" :persist-statement="localTarget?undefined:saveEditorStatementRequirement" @quotation="linkedQuotationVisible=true" @statement="openEditorStatement" @invoice="openEditorInvoice" /><el-form-item label="账单月份"><ReadonlyField :model-value="editor.billingMonth||'保存项目后自动生成'" source="auto" /><small>按订单号所属月份生成；跨月调配请在对账单管理中处理。</small></el-form-item></div>
            </div>
          </div>
          <p v-if="localTarget" class="finance-help">本次财务填写随项目表单一起保存。</p>
          <CustomerTranslationPriceEditor compact-actions hide-calculation-summary v-if="editor.pricingMode!=='fixed'" v-model="editor.prices" :language-pair="editor.languagePair" :matrix="editor.wordCountMatrix" :disabled="saving" :reference-prices="referencePrices" @price-edit-finished="offerPriceSync"><template #before-prices="{row,index}"><el-form-item label="客户参考价" class="finance-reference-item"><div class="finance-reference-content"><el-button :disabled="!editor.clientId" :type="row?.referenceId?'success':undefined" :plain="!!row?.referenceId" @click="adoptReference(row)">{{row?.referenceId?'来自客户管理 · 重新选择':'采用最新客户参考价'}}</el-button><el-button v-if="row?.referenceId" link @click="stopUsingReference(row)">改用人工单价</el-button><CustomerTranslationRates v-if="editor.clientId&&(!row||index===0)" :client-id="editor.clientId" :can-write="canWriteClients" button-label="客户管理报价" /><span>{{referencePrices.length?'按同客户、同语种、同单位、同币种和计价数量选择，保存后生效':'该客户暂无匹配的语种参考价，可在下方直接填写单价'}}</span></div></el-form-item></template><template #price-actions="{row}">
          <div v-if="editor.pricingMode!=='fixed'" class="finance-sync-actions">
            <el-form-item v-if="editor.pricingMode!=='fixed'&&canWriteClients&&editor.clientId" label="同步客户参考价"><el-tooltip :content="localTarget?'新增项目请先保存项目，再同步至客户报价。':'保存当前收费并同步单价至客户信息；已采用客户参考价时无需反向同步。'" placement="top"><span><el-button :disabled="saving||syncPreviewPending||!!row?.referenceId||!!localTarget" @click="save(true)">同步至客户报价</el-button></span></el-tooltip></el-form-item>
            <el-form-item v-if="editor.pricingMode!=='fixed'" label="同步单价"><SyncSameMonthPrices compact v-if="editorVisible" :project-id="editor.rootId" :order-id="editor.id" :source-order-no="editor.orderNo" :client-id="editor.clientId" :version="treeVersion" :month="editor.billingMonth" :disabled="saving||!canSyncEditorPrices||!!localTarget" :prepare="prepareEditorSync" @synced="onSameMonthSynced" /></el-form-item>
          </div>
</template></CustomerTranslationPriceEditor>


          <section class="finance-settlement-section">
            <div class="finance-settlement-heading"><h4>{{editor.pricingMode==='fixed'?'固定收费':'总价与说明'}}</h4><BillingTaxModeField v-model="editor.billingTaxMode" :order="editor" :disabled="saving||!!editor.fixedPricingFrom" /></div>
            <div class="finance-settlement-row" :class="{'finance-settlement-row--fixed':editor.pricingMode==='fixed'}">
            <div class="finance-settlement-grid" :class="{'finance-settlement-grid--fixed':editor.pricingMode==='fixed'}">
              <el-form-item v-if="editor.pricingMode==='fixed'" label="货币"><el-select v-model="editor.currency" :disabled="!!editor.fixedPricingFrom"><el-option v-for="currency in ['CNY','USD','HKD','EUR','GBP','JPY']" :key="currency" :value="currency" /></el-select></el-form-item>
              <el-form-item :label="editor.pricingMode==='fixed'?'不含税固定收费':'不含税总价'" prop="adjustedTotal" :rules="[{validator:(_rule,_value,callback)=>callback(!editor.fixedPricingFrom&&editor.pricingMode==='fixed'&&!isClearedFinanceForm(editor)&&!hasFixedFeeAmount(editor)?new Error('请填写不含税或含税固定收费'):undefined),trigger:'change'}]"><template #label><span class="finance-total-heading" :class="{'finance-total-heading--filled':hasTotalAmount('excl')}">{{editor.pricingMode==='fixed'?'不含税固定收费':'不含税总价'}}<small>{{editor.pricingMode==='fixed'?editor.currency:calculatedCurrency('excl')}}</small></span></template><div class="finance-total-line"><div v-if="editor.pricingMode!=='fixed'" class="finance-calculated-amount"><small>自动计算</small><ReadonlyField :class="{'finance-amount-filled':Object.keys(calculatedTotals.excl.totals).length>0}" :model-value="calculatedTotal('excl')" source="auto" /></div><div class="finance-adjusted-amount"><small v-if="editor.pricingMode!=='fixed'">调整金额</small><el-input-number v-model="editor.adjustedTotal" :class="{'finance-amount-filled':editor.adjustedTotal!=null&&editor.adjustedTotal!==''}" :disabled="!!editor.fixedPricingFrom || editor.pricingMode!=='fixed' && new Set((editor.prices||[]).map(row=>row.currency)).size>1" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入不含税固定收费':'选填'" /></div></div></el-form-item>
              <el-form-item :label="editor.pricingMode==='fixed'?'含税固定收费':'含税总价'"><template #label><span class="finance-total-heading" :class="{'finance-total-heading--filled':hasTotalAmount('incl')}">{{editor.pricingMode==='fixed'?'含税固定收费':'含税总价'}}<small>{{editor.pricingMode==='fixed'?editor.currency:calculatedCurrency('incl')}}</small></span></template><div class="finance-total-line"><div v-if="editor.pricingMode!=='fixed'" class="finance-calculated-amount"><small>自动计算</small><ReadonlyField :class="{'finance-amount-filled':Object.keys(calculatedTotals.incl.totals).length>0}" :model-value="calculatedTotal('incl')" source="auto" /></div><div class="finance-adjusted-amount"><small v-if="editor.pricingMode!=='fixed'">调整金额</small><el-input-number v-model="editor.adjustedTotalInclTax" :disabled="!!editor.fixedPricingFrom" :class="{'finance-amount-filled':editor.adjustedTotalInclTax!=null&&editor.adjustedTotalInclTax!==''}" :min="0" :precision="2" :controls="false" :placeholder="editor.pricingMode==='fixed'?'请输入含税固定收费':'选填'" /></div></div></el-form-item>
            </div>
            <div class="finance-notes-grid"><el-form-item label="内部说明"><el-input v-model="editor.explanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item><el-form-item label="客户说明"><el-input v-model="editor.customerExplanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item></div>
            </div>
          </section>

          </section>
          <PaymentRegistrationFields :draft-totals="editor.id===editor.rootId||localTarget?paymentDraftTotals(editor,calculatedTotals):null" v-model="editor" :project-id="editor.rootId" prefix="paymentConfirmation" :can-confirm="canManageHr() && !localTarget && !!editor.paymentVersion" :confirm-disabled="editorDirty || saving" @confirm-payment="confirmPayment"><template #actions><el-button :disabled="!editor.rootId||saving" @click="openLinkedPayment">打开发票、查账与追账</el-button></template></PaymentRegistrationFields>
          <p v-if="!editor.rootId" class="finance-help">保存项目后可打开完整付款情况。</p>
        </AppForm>

        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        </template></CustomerFinanceModuleTabs>
      </div>
      <template #footer><el-button v-if="canWrite&&financeModule==='translation'&&!editor.fixedPricingFrom" type="danger" plain :disabled="saving||editorLoading" @click="clearAllFinance">清空</el-button><el-button :disabled="saving" @click="closeEditor()">取消</el-button><el-button v-if="financeModule==='translation'" :type="editorDirty?'primary':'default'" :disabled="editorLoading||!!editor.fixedPricingFrom" :loading="saving" @click="save()">保存</el-button></template>
    </DraggableFormDialog>
    <CustomerReferencePriceDialog v-if="editorVisible" ref="referencePickerRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" :matrix="editor.wordCountMatrix" :language-pair="editor.languagePair" :refresh-project="rebaseEditorAfterLibrary" />
    <CustomerRateSyncPreview v-if="editorVisible" ref="rateSyncPreviewRef" :client-id="editor.clientId" :client-name="editor.clientShortName" :prices="editor.prices" :matrix="editor.wordCountMatrix" :refresh-project="rebaseEditorAfterLibrary" />
    <SubOrderStructureDialog v-model="structureVisible" :project-id="structureProjectId" :selected-order-no="structureOrderNo" />
    <DraggableFormDialog v-model="historyVisible" append-to-body class="customer-finance-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" :title="`财务修改记录 · ${historyOrder?.orderNo||''}`"><TranslationFinanceHistory v-if="historyVisible&&historyOrder" :project-id="historyOrder.rootId" :order-id="historyOrder.id" /><template #footer><el-button @click="historyVisible=false">关闭</el-button></template></DraggableFormDialog>
  </el-card>
</template>

<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import CustomerStatementPaper from '@/components/common/CustomerStatementPaper.vue'
import {previewStatementProjects} from '@/api/customerStatements'
import {calculateTaxOrderPriceTree} from '@/utils/translationQuantityBasis'
import CustomerFinanceModuleTabs from '@/components/common/CustomerFinanceModuleTabs.vue'
import RevenueStatisticsDialog from '@/components/common/RevenueStatisticsDialog.vue'
import ProjectPaymentDialog from '@/components/common/ProjectPaymentDialog.vue'
import ProjectInvoiceDialog from '@/components/common/ProjectInvoiceDialog.vue'
import TranslationOrderDetailPopover from '@/components/common/TranslationOrderDetailPopover.vue'
import CustomerFinanceTableCell from '@/components/common/CustomerFinanceTableCell.vue'
import {getProject} from '@/api/projects'
import BillingTaxModeField from '@/components/common/BillingTaxModeField.vue'
import {requestPricingModeSwitch} from '@/utils/pricingModeSwitch'
import {billingTaxChoices,effectiveBillingTaxMode,hasFixedFeeAmount} from '@/utils/billingTaxMode'
import {saveCustomerFinanceTable} from '@/api/translationCustomerFinance'
import {useFinanceTableEditing} from '@/composables/useFinanceTableEditing'
import {financeClientDisplayOffset,financeDisplayIndexes,indexFinanceClientOrders,sliceFinanceClientOrders} from '@/utils/financeClientOrderPagination'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { getWordCountMatrixListSummary } from '@/utils/wordCountMatrix'
import PaymentRegistrationFields from '@/components/common/PaymentRegistrationFields.vue'
import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '@/utils/paymentDetails'
import {paymentStatusLabel,paymentStatusFilterOptions,fullPaymentMismatchOption,paymentConfirmationForm,paymentConfirmationPayload,paymentChangeEvent,notifyPaymentChanged,connectPaymentSync} from '@/utils/paymentConfirmation'
import {paymentDraftTotals} from '@/utils/paymentDraftTotals'
import {clearFinanceForm,isClearedFinanceForm} from '@/utils/clearFinanceForm'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import TranslationDocumentRequirements from '@/components/common/TranslationDocumentRequirements.vue'
import {notifyStatementCustomerSync} from '@/utils/confirmStatementRequirement'
import {documentNotesForm,invoiceRequirement} from '@/utils/documentRequirements'
import CustomerStatementDialog from '@/components/common/CustomerStatementDialog.vue'
import {taxPriceForm,taxPriceSummary} from '@/utils/taxPrices'
import {copySavedValue} from '@/utils/savedDataMerge'
import { computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import SubOrderStructureDialog from './components/SubOrderStructureDialog.vue'
import { getCustomerTranslationRates, getCustomerFinanceProject, getCustomerFinancePage, saveCustomerFinanceProject, confirmProjectPayment, setProjectStatementRequired } from '@/api/translationCustomerFinance'
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
import CustomerRateSyncPreview from '@/components/common/CustomerRateSyncPreview.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CustomerPriceFields from './components/CustomerPriceFields.vue'
import CustomerTranslationPriceEditor from '@/components/common/CustomerTranslationPriceEditor.vue'
import TranslationFinanceHistory from '@/components/common/TranslationFinanceHistory.vue'
import {orderStatementMonth} from '@/utils/statementRequirementMonth'
import {customerStatementContext} from '@/utils/customerStatementContext'
import CustomerFinanceAggregateSummary from '@/components/common/CustomerFinanceAggregateSummary.vue'
import CustomerStatementRequiredToggle from '@/components/common/CustomerStatementRequiredToggle.vue'
import CustomerTranslationRates from '@/components/common/CustomerTranslationRates.vue'
import CustomerReferencePriceDialog from '@/components/common/CustomerReferencePriceDialog.vue'
import {priceMatch,expectedOrderPrices,replaceMatchedReference,sameCustomerRatePrice,fillCustomerReferencePrice} from '@/utils/customerRateMatching'
import SyncSameMonthPrices from '@/components/common/SyncSameMonthPrices.vue'
import {calculateOrderPriceTree,resolveRateQuantity} from '@/utils/translationQuantityBasis'
import {newCustomerRate,ratePayload,referenceDraft,defaultRateMetric} from '@/utils/customerTranslationRates'

const columns = [
  {key:'orderNo',label:'订单号',width:124},{key:'projectName',label:'项目名称',width:240},
  {key:'clientShortName',label:'客户简称',width:105},{key:'projectStatus',label:'项目状态',width:110},
  {key:'languagePair',label:'翻译方向',width:136},{key:'wordCount',label:'字数统计',width:96},
  {key:'pricingMode',label:'计价方式',width:110},{key:'billingMonth',label:'账单月份',width:96},{key:'unitPrice',label:'单价',width:160},{key:'totalPrice',label:'不含税总价',width:120},{key:'totalInclTax',label:'含税总价',width:120},
  {key:'statementRequired',label:'对账单',width:100},{key:'explanation',label:'说明',width:300},{key:'paymentStatus',label:'付款状态',width:175},
]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('translation-customer-finance',columns,columns.map(item=>item.key),{legacyDefaultKeys:[columns.filter(item=>item.key!=='paymentStatus').map(item=>item.key),columns.filter(item=>!['statementRequired','paymentStatus'].includes(item.key)).map(item=>item.key)]})
const tableFields=['pricingMode','billingMonth','unitPrice','totalPrice','totalInclTax','explanation']
const visibleColumns=computed(()=>columns.filter(item=>props.statementClientView?!['languagePair','wordCount','billingMonth'].includes(item.key):isVisible(item.key)))
const fixedStorageKey=`finance-fixed-columns:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const fixedColumns=ref((()=>{try{return JSON.parse(localStorage.getItem(fixedStorageKey)||'[]').filter(key=>['orderNo','projectName'].includes(key))}catch{return []}})())
function toggleFixedColumn(key){fixedColumns.value=fixedColumns.value.includes(key)?fixedColumns.value.filter(value=>value!==key):[...fixedColumns.value,key];localStorage.setItem(fixedStorageKey,JSON.stringify(fixedColumns.value))}

const statuses=getProjectStatusOptions('translation'),canWrite=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const emit=defineEmits(['saved','document-requirements-saved'])
const props=defineProps({clientId:{type:[String,Number],default:''},clientIds:{type:Array,default:()=>[]},statementPreview:Function,editorOnly:Boolean,clientScope:Boolean,statementClientView:Boolean,requireStatementForSelection:Boolean,previewMode:String,previewMonths:Array,initialMonth:String,managerQuery:{type:Object,default:()=>({})}})
const statementTableRef=ref(),statementSelected=ref([]),projectPreview=ref(null),previewLoading=ref(false)
function canSelectStatementProject(row){return !row.fixedPricingFrom&&(!props.requireStatementForSelection||row.statementRequired===true)}
async function statementSelection(){
  if(!await tableEditing.flush())throw new Error('请先处理未保存的内容')
  const selectedIds = new Set(statementSelected.value.map(row=>row.id))
  if(selectedIds.size && !props.requireStatementForSelection)return [...selectedIds]
  const requiredFilter = props.requireStatementForSelection ? {statement_required:true} : {}
  const ids=new Set()
  const months=props.previewMonths?.length?props.previewMonths:[filters.month]
  for(const month of months){let skip=0;while(true){const data=await getCustomerFinancePage({...financeParams(),...requiredFilter,billing_month:month||undefined,skip,limit:100});for(const row of data.items||[])ids.add(row.id);skip+=100;if(skip>=data.total||!data.items?.length)break}}
  return [...ids].filter(id=>!selectedIds.size||selectedIds.has(id))
}
async function previewProjects(){
  previewLoading.value=true
  try{const order_ids=await statementSelection();projectPreview.value=props.statementPreview?await props.statementPreview(order_ids):await previewStatementProjects({client_id:props.clientId,month:filters.month,months:props.previewMonths,mode:props.previewMode||'children',order_ids})}
  catch(e){ElMessage.error(getLocalizedErrorMessage(e,'对账单预览失败'))}
  finally{previewLoading.value=false}
}
const financeModule=ref('translation')
const financePaymentSource=`finance-editor-${Math.random().toString(36).slice(2)}`
const paymentContextId=ref('')
const revenueVisible=ref(false),paymentVisible=ref(false),quotationVisible=ref(false),statementVisible=ref(false),statementContext=ref(null)
const invoiceVisible=ref(false),invoiceContext=ref({})
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
  if(row.fixedPricingFrom)return
  if(command==='price')return openEditor(row)
  if(command==='statement')return openRowStatement(row)
  if(command==='invoice')return openRowInvoice(row)
}
function openRowInvoice(row){invoiceContext.value={projectId:row.rootId||row.id,orderId:row.id};invoiceVisible.value=true}
function openEditorInvoice(){invoiceContext.value={projectId:editor.value.rootId,orderId:localTarget.value?undefined:editor.value.id,preview:{orderNo:editor.value.orderNo,clientName:editor.value.clientShortName,required:invoiceRequirement(editor.value),totals:Object.fromEntries(paymentDraftTotals(editor.value,calculatedTotals.value).filter(item=>item.key.startsWith('billing:')).map(item=>[item.currency,item.amount])),note:editor.value.documentNotes?.invoice||''}};invoiceVisible.value=true}
function onInvoiceSaved(result){if(editor.value.rootId===result.projectId&&editor.value.paymentVersion===result.previousPaymentVersion)editor.value.paymentVersion=result.paymentVersion;emit('saved');if(!props.editorOnly)void load()}
function openRowStatement(row){
  const context=customerStatementContext(row)
  if(!context){ElMessage.warning('请先确认客户及账单月份');return}
  statementContext.value=context
  statementVisible.value=true
  if(row.statementRequired===false){
    ElMessage.warning(`${row.orderNo} 已标为「无需对账单」。如需纳入，请在客户项目的对账单列重新确认。`)
  }
}
const filters=reactive({clientOrderCount:'',keyword:'',projectStatus:[],paymentStatus:'',statementRequired:'',pricingMode:'',client:'',month:props.initialMonth||'',manager:'',missingWordCount:false,missingUnitPrice:false,missingTotal:''}),rows=ref([]),subtotals=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),advancedVisible=ref(false)
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
const headerFilterDefinitions={
  paymentStatus:{key:'paymentStatus',label:'付款状态',type:'select',multiple:false,options:[...paymentStatusFilterOptions,fullPaymentMismatchOption]},
  statementRequired:{key:'statementRequired',label:'对账单',type:'select',multiple:false,options:[{value:'required',label:'需'},{value:'not_required',label:'不需'}]},
  projectStatus:{key:'projectStatus',label:'项目状态',type:'select',options:statuses},
  pricingMode:{key:'pricingMode',label:'计价方式',type:'select',multiple:false,options:[{value:'metric',label:'工作量'},{value:'fixed',label:'固定收费'},{value:'aggregate',label:'子订单汇总'}]},
}
const tableEditing=useFinanceTableEditing(onTablePriceSaved)
watch(rows,values=>tableEditing.syncRows(values),{flush:'sync'})
const clientGroups=ref([]),groupOrderTotal=ref(0),collapsedClients=ref([]),childPagination=ref(false)
const orderDisplayOffset = ref(0)
const clientOrderPageSize=10,clientOrderPages=ref({})
const clientOrderGroups=computed(()=>{
  const rootsByClient=new Map()
  for(const row of rows.value){
    const roots=rootsByClient.get(row.clientGroupKey)||[]
    roots.push(row)
    rootsByClient.set(row.clientGroupKey,roots)
  }
  return clientGroups.value.map(group=>({...group,...indexFinanceClientOrders(rootsByClient.get(group.key)||[])}))
})
const tableRows=computed(()=>{
  if(filters.clientOrderCount!=='multiple')return rows.value
  return clientOrderGroups.value.map(group=>{
    const pageCount=Math.ceil(group.total/clientOrderPageSize)
    const currentPage=Math.min(clientOrderPages.value[group.key]||1,pageCount||1)
    const collapsed=collapsedClients.value.includes(group.key)
    return {id:'client-group:'+group.key,_clientGroup:true,groupKey:group.key,clientName:group.name,
      orderTotal:group.total,pageCount,currentPage,collapsed,
      displayOffset:collapsed?0:financeClientDisplayOffset(group.orders,currentPage,clientOrderPageSize),
      children:collapsed?[]:sliceFinanceClientOrders(group.orders,currentPage,clientOrderPageSize)}
  })
})
const displayIndexes = computed(() => {
  if(filters.clientOrderCount!=='multiple') return financeDisplayIndexes(tableRows.value, orderDisplayOffset.value)
  const indexes = new Map()
  for(const group of tableRows.value) financeDisplayIndexes(group.children, group.displayOffset, indexes)
  return indexes
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
function applyManager(){managerScope.value=managerDraftScope.value==='name'&&!managerDraftIds.value.length?'all':managerDraftScope.value;managerIds.value=managerScope.value==='name'?[...managerDraftIds.value]:[];filters.manager='';managerPickerVisible.value=false;search()}
const advancedCount=computed(()=>Number(filters.projectStatus.length>0)+Number(!!filters.client.trim())+Number(filters.missingWordCount)+Number(filters.missingUnitPrice)+Number(!!filters.missingTotal))
function clearAdvanced(){filters.projectStatus=[];filters.client='';filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';search()}
let timer,controller,sequence=0,disposed=false
function financeParams(){return {include_payment_status:true,payment_status:filters.paymentStatus||undefined,statement_required:filters.statementRequired==='required'?true:filters.statementRequired==='not_required'?false:undefined,pricing_mode:filters.pricingMode||undefined,client_order_count:filters.clientOrderCount||undefined,client_id:props.statementClientView?undefined:props.clientId||undefined,client_ids:props.statementClientView&&props.clientId?[props.clientId]:props.clientIds.length?props.clientIds:undefined,keyword:filters.keyword.trim()||undefined,project_statuses:filters.projectStatus.length?filters.projectStatus:undefined,client:filters.client.trim()||undefined,billing_month:filters.month||undefined,...activeManagerQuery.value,...(props.statementClientView?props.managerQuery:{}),missing_word_count:filters.missingWordCount||undefined,missing_unit_price:filters.missingUnitPrice||undefined,missing_total:filters.missingTotal||undefined}}
async function load(options={}){
  if(editorLoading.value)return
  if(!options?.fromTable&&!await tableEditing.flush()){
    // The row editor keeps drafts by order ID while the main list is filtered or paginated.
    if(props.statementClientView)return false
  }
  const current=++sequence;controller?.abort();controller=new AbortController();if(!options?.fromTable)loading.value=true;error.value=''
  try{
    const params=financeParams()
    const data=await getCustomerFinancePage({...params,paginate_children:!props.statementClientView&&filters.clientOrderCount!=='multiple',skip:(page.value-1)*10,limit:10},{signal:controller.signal})
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
function setBillingMonth(month){
  filters.month=month||''
  search()
}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function queueFilterSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!String(value||'').trim())search();else timer=setTimeout(search,400)}
function resetSearch(){filters.clientOrderCount='';collapsedClients.value=[];filters.missingWordCount=false;filters.missingUnitPrice=false;filters.missingTotal='';filters.keyword='';filters.projectStatus=[];filters.paymentStatus='';filters.statementRequired='';filters.pricingMode='';filters.client='';filters.month='';filters.manager='';managerIds.value=[];managerScope.value=props.clientScope?'all':'self';search()}
const formatAmounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'-'
const languageDirections=value=>String(value||'').split('；').map(direction=>direction.trim()).filter(Boolean)
function cell(row,key){
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
const editorDocumentProject=computed(()=>({...editor.value,id:editor.value.rootId,orderNo:editor.value.documentOrderNo||editor.value.orderNo,clientShortName:editor.value.documentClientShortName||editor.value.clientShortName}))
function openEditorStatement(){const context=customerStatementContext(editorDocumentProject.value);if(!context)return ElMessage.warning('请先选择或保存客户，并确认订单号所属月份');statementContext.value=context;statementVisible.value=true}
function documentDraft(root){return {quotationRequired:!!root.quotationRequired,statementRequired:root.statementRequired!==false,statementUpdatedAt:root.updatedAt,quotationDraft:copySavedValue(root.quotationDraft||null),statementRequiredDirty:false,quotationDraftDirty:false,documentNotes:documentNotesForm(root.documentNotes),documentNotesDirty:false,documentOrderNo:root.orderNo,documentClientShortName:root.clientShortName,clientManager:root.clientManager}}
async function saveEditorStatementRequirement(value,confirmation){
  if(saving.value)return
  saving.value=true
  const draft=editor.value
  try{
    const saved=await setProjectStatementRequired(draft.rootId,{
      statement_required:value,
      expected_statement_required:draft.statementRequired,
      expected_updated_at:draft.statementUpdatedAt||null,
      statement_sync:confirmation.scope,
      statement_customer_sync:confirmation.customerScope,
    })
    editor.value.statementRequired=saved.statementRequired
    editor.value.statementUpdatedAt=saved.updatedAt
    const baseline=JSON.parse(original.value)
    baseline[11]=saved.statementRequired
    original.value=JSON.stringify(baseline)
    if(documentParent.value?.id===draft.rootId)documentParent.value.statementRequired=saved.statementRequired
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{
      detail:{projectId:draft.rootId,syncScope:confirmation.scope||confirmation.customerScope},
    }))
    notifyStatementCustomerSync(confirmation.customerScope)
    await rebaseEditorAfterLibrary().catch(error=>{
      saveError.value=getLocalizedErrorMessage(error,'对账单需求已保存，请重新打开价格与付款读取最新数据')
    })
    emit('saved',saved)
    ElMessage.success(confirmation.customerScope?'已保存并同步客户管理':'是否需对账单已保存')
  }finally{
    saving.value=false
  }
}
function documentPayload(){return {quotation_required:editor.value.quotationRequired,statement_required:editor.value.statementRequiredDirty?editor.value.statementRequired:undefined,statement_sync:editor.value.statementRequiredDirty?editor.value.statementSync:undefined,statement_customer_sync:editor.value.statementRequiredDirty?editor.value.statementCustomerSync:undefined,quotation_draft:editor.value.quotationDraftDirty?editor.value.quotationDraft:undefined,document_notes:editor.value.documentNotesDirty?editor.value.documentNotes:undefined,documents_only:!!(editor.value.priceAggregate||editor.value.fixedPricingFrom)}}
function applyDocumentDraft(persisted){
  const parent=documentParent.value||localPaymentParent.value
  const value={id:editor.value.rootId,quotationRequired:editor.value.quotationRequired,statementRequired:editor.value.statementRequired,statementRequiredChanged:editor.value.statementRequiredDirty,quotationDraft:editor.value.quotationDraft,quotationDraftChanged:editor.value.quotationDraftDirty,documentNotes:documentNotesForm(editor.value.documentNotes),documentNotesChanged:editor.value.documentNotesDirty,persisted}
  if(parent){parent.quotationRequired=value.quotationRequired;if(value.statementRequiredChanged){parent.statementRequired=value.statementRequired;parent.statementRequiredExplicit=true}if(value.quotationDraftChanged)parent.quotationDraft=value.quotationDraft;if(value.documentNotesChanged)parent.documentNotes=value.documentNotes}
  emit('document-requirements-saved',value)
}
const originalPaymentConfirmation=ref(''),originalPaymentDetails=ref('[]')
const editorVisible=ref(false),editorLoading=ref(false),saving=ref(false),saveError=ref(''),editor=ref({}),formRef=ref(),editorBody=ref()
const invoiceReview = ref(false)
watch(editorVisible, visible => { if (!visible) invoiceReview.value = false })
function locateInvoiceRequirement() {
  if (invoiceReview.value) scrollFormTarget(editorBody.value?.querySelector('[data-field-key="invoiceRequired"]'), editorBody.value)
}
const siblingOrders = ref(null)
const switchingSibling = ref(false)
const siblingNavigationDisabled = computed(() => switchingSibling.value || editorLoading.value || saving.value || pricingModeSwitching.value || syncPreviewPending.value || !!editor.value.fixedPricingFrom)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const original=ref(''), pricingModeOnlySignature=ref(null)
let pricingModeBeforeSwitch=null
let treeVersion='',libraryVersion=''
const referencePrices=ref([]),updateLibrary=ref(false),referencePickerRef=ref()
const historyVisible=ref(false),historyOrder=ref(null)
const getWordCountSummary=row=>getWordCountMatrixListSummary(row.wordCountMatrix||{},{source:row.wordCountMatrixSource})
const paymentConfirmationDirty=computed(()=>JSON.stringify(paymentConfirmationInput(editor.value.paymentConfirmation))!==JSON.stringify(paymentConfirmationInput(JSON.parse(originalPaymentConfirmation.value||'null'))))
const paymentDetailsDirty=computed(()=>paymentDetailsSignature(editor.value.paymentDraft)!==originalPaymentDetails.value)
const originalPrices=ref([])
const rateSyncPreviewRef=ref(),syncPreviewPending=ref(false)
const editorDirty=computed(()=>editorVisible.value&&!editorLoading.value&&!!original.value&&editorSignature()!==original.value)
const calculatedTotals=computed(()=>calculateTaxOrderPriceTree(editor.value,originalPrices.value))
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
async function onTablePriceSaved(result){
  const item=result?.item
  if(item){
    syncSavedFinanceRows(item)
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
function editorSignature(){return JSON.stringify([editor.value.pricingMode,editor.value.currency,(editor.value.prices||[]).map(ratePayload),editor.value.adjustedTotal,editor.value.adjustedTotalInclTax,editor.value.explanation,editor.value.billingMonth,updateLibrary.value,paymentConfirmationInput(editor.value.paymentConfirmation),editor.value.customerExplanation||'',editor.value.quotationRequired,editor.value.statementRequired,editor.value.quotationDraft,editor.value.statementRequiredDirty,editor.value.quotationDraftDirty,editor.value.billingTaxMode||null,paymentDetailsPayload(editor.value.paymentDraft),editor.value.documentNotes,editor.value.documentNotesDirty,editor.value.statementSync||null,editor.value.statementCustomerSync||null])}
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
    draft.adjustedTotal=undefined
    const client=draft.clientShortName||draft.clientName||'当前客户'
    const order=draft.orderNo?`订单 ${draft.orderNo}`:'当前订单'
    ElMessage.info(`已将客户管理中${client}的笔译报价带入${order}，保存后生效`)
  }catch(e){ElMessage.warning(e.message)}
}
let editorSequence=0,editorReadSequence=0
function findFinanceOrder(order, id, siblings = null, index = -1){
  if(order.id === id) return {order, siblings, index}
  const children = order.children || []
  for(const [childIndex, child] of children.entries()){
    const match = findFinanceOrder(child, id, children, childIndex)
    if(match) return match
  }
  return null
}

function updateSiblingOrders({siblings, index}, offset = 0){
  siblingOrders.value = siblings && {
    previous: siblings[index + offset - 1],
    next: siblings[index + offset + 1],
  }
}

async function openSibling(offset){
  if(siblingNavigationDisabled.value)return
  switchingSibling.value = true
  try{
    await openEditor(editor.value, offset)
  }finally{
    switchingSibling.value = false
  }
}

async function openEditor(row, siblingOffset = 0, reviewInvoice = false){
  if(!canWrite||row.fixedPricingFrom||editorLoading.value||saving.value)return
  if(!await tableEditing.flush())return ElMessage.warning('有单元格尚未保存，请先处理提示')
  if(siblingOffset){
    if(!await confirmEditorDiscard('切换同级子订单'))return
  }else if(editorVisible.value&&!await guardEditor())return
  const current=++editorSequence
  clearTimeout(timer);controller?.abort();sequence++;loading.value=false
  editorLoading.value=true
  try{
    const data=await getCustomerFinanceProject(row.rootId)
    if(disposed||current!==editorSequence)return
    const match = findFinanceOrder(data.item, row.id)
    if(!match)throw new Error('订单已变化，请刷新')
    const selected = siblingOffset ? match.siblings?.[match.index + siblingOffset] : match.order
    if(!selected){
      updateSiblingOrders(match)
      return ElMessage.warning('该方向已没有同级子订单')
    }
    if(selected.fixedPricingFrom)return ElMessage.warning(`随上级订单 ${selected.fixedPricingFrom} 固定收费，请在上级订单操作`)
    financeModule.value='translation'
    paymentContextId.value=row.rootId
    localTarget.value=null;localPaymentParent.value=null;linkedQuotationVisible.value=false
    if(!siblingOffset){projectFormTarget.value=null;documentParent.value=null}
    updateSiblingOrders(match, siblingOffset)
    originalPrices.value=copySavedValue(selected.prices||[])
    editor.value={...copySavedValue(selected),...documentDraft(data.item),clientId:data.item.clientId,clientShortName:data.item.clientShortName,paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation),paymentDraft:paymentDetailsForm(data.payment?.payments),paymentVersion:data.payment?.version||'',prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),billingMonth:orderStatementMonth(selected.orderNo)||selected.billingMonth||null}
    referencePrices.value=data.referencePrices?.items||[];libraryVersion=data.referencePrices?.version||'';updateLibrary.value=false
    if(!editor.value.prices.length){
      // 空单价代表尚未填写或已清空，客户参考价必须由用户明确采用。
      editor.value.clearedAll=true
    }
    treeVersion=data.version;saveError.value='';pricingModeBeforeSwitch=null;pricingModeOnlySignature.value=null;original.value='';clearFieldSearch()
    invoiceReview.value = reviewInvoice
    editorVisible.value=true
    await nextTick()
    original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft)
    if(siblingOffset)editorBody.value?.closest('.el-dialog__body')?.scrollTo({top:0})
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
  const modeOnly=pricingModeOnlySignature.value===currentSignature
  if(preserveDraft&&selected.pricingMode!==before[0]&&[0,1,2,3,4,15].some(index=>JSON.stringify(signature[index])!==JSON.stringify(before[index]))){
    throw new Error('计价方式已在另一处修改，当前价格草稿已保留，请核对后重新打开')
  }
  updateSiblingOrders(match)
  const fresh={...copySavedValue(selected),...documentDraft(data.item),clientId:data.item.clientId,clientShortName:data.item.clientShortName,prices:(selected.prices||[]).map(price=>({...price,taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?undefined:Number(price.amount),unitSize:Number(price.unitSize||1)})),adjustedTotal:selected.adjustedTotal==null?undefined:Number(selected.adjustedTotal),adjustedTotalInclTax:selected.adjustedTotalInclTax==null?undefined:Number(selected.adjustedTotalInclTax),paymentConfirmation:paymentConfirmationForm(data.item.paymentConfirmation),paymentDraft:paymentDetailsForm(data.payment?.payments),paymentVersion:data.payment?.version||''}
  if(preserveDraft&&draft.clearedAll)fresh.clearedAll=true
  editor.value=fresh;updateLibrary.value=false;await nextTick();original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(fresh.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(fresh.paymentDraft)
  originalPrices.value=copySavedValue(selected.prices||[]);treeVersion=data.version;referencePrices.value=data.referencePrices?.items||[];libraryVersion=data.referencePrices?.version||''
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
  if(JSON.stringify(signature[15])!==JSON.stringify(before[15]))fresh.billingTaxMode=draft.billingTaxMode
  for(const [field,index] of [['quotationRequired',10],['statementRequired',11],['quotationDraft',12],['statementRequiredDirty',13],['quotationDraftDirty',14]]){if(JSON.stringify(signature[index])!==JSON.stringify(before[index]))fresh[field]=draft[field]}
  if(JSON.stringify(signature[17])!==JSON.stringify(before[17])){fresh.documentNotes=draft.documentNotes;fresh.documentNotesDirty=draft.documentNotesDirty}
  if(draft.statementRequiredDirty){fresh.statementSync=draft.statementSync;fresh.statementCustomerSync=draft.statementCustomerSync}
  editor.value={...fresh}
  pricingModeOnlySignature.value=modeOnly?editorSignature():null
}
const canSyncEditorPrices=computed(()=>!!editor.value.prices?.length&&editor.value.prices.every(row=>row.languagePair&&row.currency&&Number(row.unitSize||1)>0&&resolveRateQuantity(editor.value.wordCountMatrix,row.metric).metric&&(row.taxPrices?.unitPriceExclTax!=null||row.taxPrices?.unitPriceInclTax!=null)))
async function prepareEditorSync(){await rebaseEditorAfterLibrary();if(!canSyncEditorPrices.value){ElMessage.warning('请填写语种方向、币种、明确计量单位及至少一个单价');return false}return {order_id:editor.value.id,version:treeVersion,billing_month:editor.value.billingMonth,prices:editor.value.prices.map(ratePayload)}}

async function openAggregateOrder(rootId,id){
  const find=node=>node.id===id?node:(node.children||[]).map(find).find(Boolean)
  let target=rows.value.map(find).find(Boolean)
  if(!target){const data=await getCustomerFinanceProject(rootId);target=find(data.item)}
  if(target)await openEditor(target)
}
async function confirmEditorDiscard(title){
  if(!editorDirty.value)return true
  try{
    await ElMessageBox.confirm('放弃后，本次对计价方式、价格和付款信息的修改均不会保存。',title,{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})
    return true
  }catch{return false}
}
async function closeEditor(done){
  if(saving.value||editorLoading.value||switchingSibling.value||!await confirmEditorDiscard('关闭编辑'))return
  pricingModeBeforeSwitch=null
  pricingModeOnlySignature.value=null
  if(typeof done==='function')done();else editorVisible.value=false
}
async function clearAllFinance(){
  try{await ElMessageBox.confirm('将清空当前窗口可填写的单价、金额、内部说明、客户说明、单据需求及付款信息。订单号、关联项目、字数统计和下级汇总信息保留。保存后生效，原数据保留在修改记录中。是否继续？','清空价格与付款',{type:'warning',confirmButtonText:'确认清空',cancelButtonText:'取消',closeOnClickModal:false})}catch{return}
  editor.value=clearFinanceForm(editor.value,newCustomerRate)
  updateLibrary.value=false;saveError.value='';formRef.value?.clearValidate()
}
let automaticRateCheck
async function offerPriceSync(row){
  if(!canWriteClients||!canWrite||!editor.value.clientId||!editor.value.billingMonth||!canSyncEditorPrices.value||localTarget.value||saving.value||syncPreviewPending.value)return
  const draft=editor.value,signature=JSON.stringify(ratePayload(row))
  const request=getCustomerTranslationRates(draft.clientId).catch(()=>null)
  automaticRateCheck=request
  const library=await request
  if(automaticRateCheck!==request)return
  automaticRateCheck=null
  if(!library?.ready||!editorVisible.value||editor.value!==draft||saving.value||switchingSibling.value||syncPreviewPending.value||
    !draft.prices.includes(row)||JSON.stringify(ratePayload(row))!==signature||!canSyncEditorPrices.value)return
  if(library.items.some(reference=>priceMatch(reference,row,draft.wordCountMatrix).matched&&sameCustomerRatePrice(reference,row)))return

  syncPreviewPending.value=true
  let confirmed
  try{
    confirmed=await rateSyncPreviewRef.value.confirm(library)
  }finally{
    syncPreviewPending.value=false
  }
  if(confirmed&&editorVisible.value)await save(true,confirmed)
}
async function save(syncToClient=false,confirmedLibrary=null){
  if(!syncToClient&&automaticRateCheck){
    const draft=editor.value
    await automaticRateCheck
    if(!editorVisible.value||editor.value!==draft)return
  }
  if(saving.value||!canWrite||editor.value.fixedPricingFrom)return
  if(!syncToClient&&syncPreviewPending.value)return
  const activeForm=formRef.value
  if((syncToClient||localTarget.value||pricingModeOnlySignature.value!==editorSignature())&&!await activeForm?.validate().catch(()=>false))return
  const signature=editorSignature()
  const modeOnly=!syncToClient&&!localTarget.value&&pricingModeOnlySignature.value===signature
  const paymentChanged=paymentConfirmationDirty.value||paymentDetailsDirty.value
  let paymentOnly=false
  if(!syncToClient&&!localTarget.value&&paymentChanged&&original.value){
    const saved=JSON.parse(original.value)
    // These two positions in editorSignature represent the payment confirmation and details.
    paymentOnly=JSON.parse(signature).every((value,index)=>
      index===8||index===16||JSON.stringify(value)===JSON.stringify(saved[index]))
  }
  if(!modeOnly&&!paymentOnly&&!editor.value.priceAggregate&&editor.value.pricingMode!=='fixed'&&!editor.value.prices.length&&!isClearedFinanceForm(editor.value))return ElMessage.warning('请至少填写一条语种单价')
  if(!modeOnly&&!paymentOnly&&!editor.value.fixedPricingFrom&&!editor.value.priceAggregate&&editor.value.pricingMode==='fixed'&&editor.value.adjustedTotal==null&&editor.value.adjustedTotalInclTax==null&&!isClearedFinanceForm(editor.value))return ElMessage.warning('请填写固定收费金额')
  if(localTarget.value){saving.value=true;try{await saveLocalFinance()}catch(e){saveError.value=getLocalizedErrorMessage(e,'付款保存失败，当前输入已保留')}finally{saving.value=false}return}
  if(syncToClient){
    if(syncPreviewPending.value)return
    let confirmed=confirmedLibrary
    if(!confirmed){
      syncPreviewPending.value=true
      try{confirmed=await rateSyncPreviewRef.value.confirm()}
      finally{syncPreviewPending.value=false}
    }
    if(!confirmed)return
    libraryVersion=confirmed.version
  }
  saving.value=true;saveError.value=''
  try{
    const draft=editor.value
    const mode=draft.pricingMode||'metric'
    const orderMode=draft.children?.length&&mode!==JSON.parse(original.value)[0]?mode:undefined
    const cleared=isClearedFinanceForm(draft)
    const paymentPayload={
      version:treeVersion,order_id:draft.id,
      payment_draft:paymentDetailsDirty.value?paymentDetailsPayload(draft.paymentDraft):undefined,
      payment_version:paymentDetailsDirty.value?draft.paymentVersion:undefined,
      payment_confirmation:paymentChanged?paymentConfirmationPayload(draft.paymentConfirmation):undefined,
    }
    const savedFinance=modeOnly
      ?await saveCustomerFinanceTable(draft.rootId,{version:treeVersion,order_id:draft.id,pricing_mode:mode})
      :await saveCustomerFinanceProject(draft.rootId,paymentOnly?{...paymentPayload,documents_only:true}:{
        ...documentPayload(),
        ...paymentPayload,
        order_pricing_mode:orderMode,clear_finance:cleared,
        ...(!draft.priceAggregate&&!draft.fixedPricingFrom?{billing_tax_mode:billingTaxChoices(draft).length>1?effectiveBillingTaxMode(draft):null}:{}),
        pricing_mode:draft.priceAggregate?'metric':mode,currency:draft.currency||'CNY',
        prices:draft.priceAggregate||mode==='fixed'||cleared?null:draft.prices.map(ratePayload),
        update_library:syncToClient,sync_confirmed:syncToClient,library_version:libraryVersion,
        adjusted_total:draft.adjustedTotal??null,adjusted_total_incl_tax:draft.adjustedTotalInclTax??null,
        explanation:draft.explanation||'',customer_explanation:draft.customerExplanation||'',billing_month:draft.billingMonth||null,
      })
    syncSavedFinanceRows(savedFinance.item)
    if(draft.statementRequiredDirty)notifyStatementCustomerSync(draft.statementCustomerSync)
    await updateProjectFormFinance(savedFinance.item.paymentConfirmation)
    if(!paymentOnly)applyDocumentDraft(true)
    if(draft.statementRequiredDirty)window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{projectId:draft.rootId}}))
    if(syncToClient){
      await rebaseEditorAfterLibrary(savedFinance,{preserveDraft:false})
      window.dispatchEvent(new CustomEvent('translation-finance-changed',{detail:{clientId:draft.clientId,source:financePaymentSource}}))
      const client=draft.clientShortName||draft.clientName||'当前客户'
      ElMessage.success(`已将订单 ${draft.orderNo} 的单价同步至客户管理中${client}的笔译报价`)
    }else{
      draft.paymentConfirmation=paymentConfirmationForm(savedFinance.item.paymentConfirmation)
      draft.paymentDraft=paymentDetailsForm(savedFinance.payment?.payments)
      draft.paymentVersion=savedFinance.payment?.version||''
      original.value=editorSignature()
      originalPaymentConfirmation.value=JSON.stringify(draft.paymentConfirmation)
      originalPaymentDetails.value=paymentDetailsSignature(draft.paymentDraft)
      pricingModeOnlySignature.value=null
      editorVisible.value=false
      ElMessage.success('价格与付款已保存')
    }
    notifyPaymentChanged(draft.rootId,editor.value.paymentConfirmation,financePaymentSource)
    emit('saved')
    await load({fromTable:true})
  }
  catch(e){saveError.value=getLocalizedErrorMessage(e,'保存失败，请检查收费明细；如项目已被其他人修改，请重新打开后编辑')}
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
  const payload={version:data.version,order_id:owner.id,customer_explanation:draft.customerExplanation,...(!owner.priceAggregate?{billing_tax_mode:draft.billingTaxMode||null}:{})}
  if(!owner.priceAggregate&&draft.pricingMode!=='fixed'&&draft.prices.length)payload.prices=draft.prices.map((row,index)=>ratePayload({...row,id:owner.prices?.[index]?.id||null}))
  await saveCustomerFinanceTable(rootId,payload)
  if(draft.statementSync||draft.statementCustomerSync){
    const latest=await getCustomerFinanceProject(rootId)
    await saveCustomerFinanceProject(rootId,{
      version:latest.version,order_id:rootId,documents_only:true,
      statement_required:draft.statementRequired,statement_sync:draft.statementSync,statement_customer_sync:draft.statementCustomerSync,
    })
    window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{projectId:rootId}}))
    notifyStatementCustomerSync(draft.statementCustomerSync)
  }
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
  editor.value.statementSync=pendingFormFinance.get(target)?.statementSync||null
  editor.value.statementCustomerSync=pendingFormFinance.get(target)?.statementCustomerSync||null
  originalPrices.value=JSON.parse(JSON.stringify(editor.value.prices));referencePrices.value=[];saveError.value='';pricingModeOnlySignature.value=null;original.value='';clearFieldSearch();editorVisible.value=true;await nextTick();original.value=editorSignature();originalPaymentConfirmation.value=JSON.stringify(editor.value.paymentConfirmation);originalPaymentDetails.value=paymentDetailsSignature(editor.value.paymentDraft)
  if(parent.clientId){try{const data=await getCustomerTranslationRates(parent.clientId);if(editorVisible.value&&localTarget.value===target){
      referencePrices.value=data.items||[]
      for(const price of editor.value.prices)fillCustomerReferencePrice(price,referencePrices.value,editor.value.wordCountMatrix)
    }}catch(e){saveError.value=getLocalizedErrorMessage(e,'客户参考价加载失败')}}
}
async function saveLocalFinance(){
  if(editor.value.rootId&&(paymentDetailsDirty.value||paymentConfirmationDirty.value)){
    const fresh=await getCustomerFinanceProject(editor.value.rootId)
    const saved=await saveCustomerFinanceProject(editor.value.rootId,{version:fresh.version,order_id:editor.value.rootId,documents_only:true,payment_draft:paymentDetailsDirty.value?paymentDetailsPayload(editor.value.paymentDraft):undefined,payment_version:editor.value.paymentVersion,payment_confirmation:paymentConfirmationPayload(editor.value.paymentConfirmation)})
    editor.value.paymentConfirmation=paymentConfirmationForm(saved.item.paymentConfirmation)
    editor.value.paymentDraft=paymentDetailsForm(saved.payment?.payments);editor.value.paymentVersion=saved.payment?.version||''
    notifyPaymentChanged(editor.value.rootId,editor.value.paymentConfirmation,financePaymentSource)
  }
  pendingFormFinance.set(localTarget.value,{prices:copySavedValue(editor.value.prices),customerExplanation:editor.value.customerExplanation||'',pricingMode:editor.value.pricingMode,billingTaxMode:billingTaxChoices(editor.value).length>1?effectiveBillingTaxMode(editor.value):null,statementSync:editor.value.statementSync,statementCustomerSync:editor.value.statementCustomerSync,statementRequired:editor.value.statementRequired})
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
function openPaymentManagement(){paymentVisible.value=true}
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
  emit('saved')
}
watch(()=>[filters.projectStatus,props.initialMonth,props.previewMonths,props.previewMode,JSON.stringify(props.managerQuery)],()=>{projectPreview.value=null},{deep:true})
watch(rows,()=>{projectPreview.value=null})
watch(()=>props.clientIds.join(','),()=>{if(props.statementClientView)search()})
defineExpose({openForForm,persistForForm,statementSelection,reloadProjects:load})

watch(()=>props.clientId,search)
watch(()=>[props.initialMonth,JSON.stringify(props.managerQuery)],()=>{if(props.statementClientView){filters.month=props.initialMonth||'';search()}})
onMounted(()=>{if(props.clientId||props.clientIds.length)void load()})
onActivated(()=>{if(props.editorOnly)return;managerScope.value=props.clientScope?'all':'self';managerIds.value=[];managerDraftScope.value='self';managerDraftIds.value=[];filters.manager='';managerPickerVisible.value=false;page.value=1;subtotalPage.value=1;void load()})
function refreshStatementStatus(event){
  if(event?.detail?.source===financePaymentSource)return
  if(!props.editorOnly)void load({fromTable:true})
  const {projectId,clientId}=event?.detail||{}
  if(!editorVisible.value||saving.value||localTarget.value||!original.value)return
  if(clientId&&editor.value.clientId!==clientId)return
  if(projectId&&editor.value.rootId!==projectId&&!event.detail?.syncScope)return
  void rebaseEditorAfterLibrary().catch(error=>{
    saveError.value=getLocalizedErrorMessage(error,'项目财务刷新失败，当前填写已保留')
  })
}
function onCustomerStatementPreferenceSaved(event){
  if(!event.detail?.fromProject)refreshStatementStatus(event)
}
function refreshWordCounts(event){
  const {entityType,entityId}=event.detail||{}
  refreshStatementStatus({detail:{projectId:entityType==='project'?entityId:undefined}})
}
onMounted(()=>window.addEventListener('translation-word-count-saved',refreshWordCounts))
onBeforeUnmount(()=>window.removeEventListener('translation-word-count-saved',refreshWordCounts))
onMounted(()=>{connectPaymentSync();window.addEventListener('customer-statement-preference-saved',onCustomerStatementPreferenceSaved);window.addEventListener('translation-statements-changed',refreshStatementStatus);window.addEventListener('translation-finance-changed',refreshStatementStatus);window.addEventListener(paymentChangeEvent,onPaymentChanged)})
onDeactivated(()=>{editorSequence++;editorLoading.value=false;revenueVisible.value=false;paymentVisible.value=false;invoiceVisible.value=false;quotationVisible.value=false;statementVisible.value=false;rateSyncPreviewRef.value?.cancel();managerPickerVisible.value=false;historyVisible.value=false;clearTimeout(timer);sequence++;controller?.abort();loading.value=false})
async function guardEditor(){if(!await tableEditing.flush())return false;if(!editorVisible.value)return true;if(saving.value)return false;await closeEditor();return !editorVisible.value}
onBeforeRouteLeave(guardEditor)
onBeforeRouteUpdate((to,from)=>to.query.section!==from.query.section?guardEditor():true)
onBeforeUnmount(()=>{window.removeEventListener('customer-statement-preference-saved',onCustomerStatementPreferenceSaved);window.removeEventListener('translation-statements-changed',refreshStatementStatus);window.removeEventListener('translation-finance-changed',refreshStatementStatus);window.removeEventListener(paymentChangeEvent,onPaymentChanged);disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
useProjectStatusSync('translation',rows,{enabled:()=>!props.editorOnly,onChanged:()=>{if(!loading.value&&!editorLoading.value)void load({fromTable:true})}})
</script>

<style scoped>
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
.finance-pricing-region{margin:16px 0;padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.finance-pricing-region-title{font-size:14px;font-weight:700;margin:0 0 12px}.finance-pricing-region .finance-pricing-config{padding:0 0 16px;margin-bottom:16px;border:0;border-bottom:1px solid var(--el-border-color-lighter);border-radius:0}
.finance-editor-heading :deep(.dialog-field-search-header__heading){flex:1 1 auto;min-width:0}
.finance-editor-heading :deep(.dialog-field-search-header__extra){flex:1 1 180px;min-width:0}
.finance-editor-project-name{display:block;user-select:text;cursor:text;overflow-wrap:anywhere;font-size:14px;line-height:1.5;color:var(--el-text-color-regular)}
.finance-editor-manager{display:block;user-select:text;cursor:text;overflow-wrap:anywhere;font-size:13px;color:var(--el-text-color-secondary)}
.finance-sibling-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.finance-sibling-actions :deep(.el-button + .el-button){margin-left:0}
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
