<template>
  <el-card class="compact-list-card">
    <template #header>
      <div class="card-header">
        <span>笔译项目管理</span>
        <div class="header-actions">
          <el-button v-if="!deleteMode" :icon="Download" @click="openExportDialog">导出 Excel</el-button>
          <TableColumnSettings
            v-model="visibleColumnKeys"
            v-model:secondary-model-value="visibleSubOrderColumnKeys"
            title="笔译项目字段"
            secondary-title="子订单字段"
            secondary-hint="子订单号作为详情入口固定显示；操作列固定保留。"
            :columns="tableColumns"
            :secondary-columns="subOrderTableColumns"
            :column-count="2"
            :secondary-column-count="2"
            @reset="resetColumns"
            @reset-secondary="resetSubOrderColumns"
          />
          <BatchDeleteToolbar
            v-if="canWriteProjects"
            :active="deleteMode"
            :selected-count="selectedRows.length"
            :loading="deleting"
            @enter="enterDeleteMode"
            @exit="exitDeleteMode"
            @confirm="confirmBatchDelete"
          />
          <el-button v-if="canWriteProjects && !deleteMode" type="primary" @click="handleAdd">新增项目</el-button>
        </div>
      </div>
    </template>

    <AppForm :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input v-model="searchForm.keyword" placeholder="母/子订单号、项目名称、客户名称或客户单号" clearable style="width: 340px" @input="handleTextSearch" @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.projectStatus" multiple collapse-tags :max-collapse-tags="1" placeholder="请选择状态" clearable style="width: 180px" @change="handleSearch">
          <el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedFilterCount" popper-class="translation-advanced-filter-popover" @clear="clearAdvancedFilters" @reset="resetSearch">
          <CompactFilterGrid
            :fields="translationAdvancedFilterFields"
            :model="searchForm"
            @update="updateConfiguredFilter"
            @text-input="handleConfiguredTextInput"
            @change="handleSearch"
            @enter="handleSearch"
          />
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>

    <el-table
      ref="projectTableRef"
      class="project-table project-detail-list-table"
      :data="tableData"
      v-loading="loading"
      row-key="id"
      :row-class-name="projectRowClass"
      border
      :expand-row-keys="expandedProjectRowKeys"
      @expand-change="handleProjectExpandChange"
      @selection-change="handleDeleteSelectionChange"
    >
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column
        type="expand"
        width="1"
        class-name="project-expand-column"
        label-class-name="project-expand-column"
      >
        <template #default="{ row }">
          <div class="sub-order-panel">
            <div class="sub-order-panel__header">
              <div class="sub-order-panel__meta">
                <span>子订单列表</span>
                <el-tag size="small" type="info">共 {{ getSubOrderCount(row) }} 条</el-tag>
                <el-tag v-if="hasMoreSubOrders(row)" size="small" type="warning">当前仅显示前 {{ SUB_ORDER_PREVIEW_LIMIT }} 条</el-tag>
              </div>
              <div class="sub-order-panel__actions">
                <el-button v-if="canWriteProjects" type="primary" link @click="openBatchDialog(row)">批量新增子订单</el-button>
                <el-button v-if="hasMoreSubOrders(row)" type="primary" link @click="goToSubOrderManagement(row)">进入子订单管理页</el-button>
              </div>
            </div>
            <el-table class="sub-order-table" :data="getVisibleSubOrders(row)" border>
              <el-table-column label="子订单号" min-width="180">
                <template #header><ClickableColumnHeader label="子订单号" hint="点击子订单号查看详情" /></template>
                <template #default="{ row: subRow }">
                  <BusinessDetailPopover :row="subRow" title="子订单详情" :items="subOrderDetailItems" :status-label="getStatusLabel" :status-type="getStatusType">
                    <template #reference>
                      <el-button type="primary" link class="sub-order-no-link business-clickable-cell" :title="`${subRow.subOrderNo}（点击查看详情）`" @click.stop>
                        {{ subRow.subOrderNo || '-' }}
                      </el-button>
                    </template>
                  </BusinessDetailPopover>
                </template>
              </el-table-column>
              <el-table-column v-if="isSubOrderColumnVisible('subProjectName')" min-width="220">
                <template #header>
                  <div class="sub-order-name-header">
                    <span>子项目名称</span>
                    <el-button
                      v-if="canWriteProjects"
                      type="primary"
                      link
                      size="small"
                      :icon="Check"
                      :loading="expandedInlineSaving"
                      :disabled="getExpandedInlinePendingCount(row.id) === 0"
                      title="保存全部子项目名称"
                      @click="saveAllInlineNames('expanded', row.id)"
                    >保存全部{{ getExpandedInlinePendingCount(row.id) ? `（${getExpandedInlinePendingCount(row.id)}）` : '' }}</el-button>
                  </div>
                </template>
                <template #default="{ row: subRow }">
                  <InlineSubProjectName
                    :sub-order-id="subRow.id"
                    :model-value="subRow.subProjectName"
                    :editable="canWriteProjects"
                    @pending-change="handleInlinePendingChange('expanded', subRow, $event)"
                    @saved="handleInlineSubOrderSaved(subRow, $event, 'expanded')"
                  />
                </template>
              </el-table-column>
              <el-table-column v-if="isSubOrderColumnVisible('languagePair')" prop="languagePair" label="翻译方向" min-width="120" />
              <el-table-column v-if="isSubOrderColumnVisible('wordCountMatrix')" label="字数统计" width="132" min-width="120">
                <template #header><ClickableColumnHeader label="字数统计" hint="点击查看子订单字数统计" /></template>
                <template #default="{ row: subRow }">
                  <div class="word-count-list-cell">
                    <WordCountMatrixPopover v-model="subRow.wordCountMatrix" entity-type="suborder" :entity-id="subRow.id" title="子订单字数统计" @saved="fetchData">
                      <template #reference>
                        <el-button
                          type="primary"
                          link
                          class="word-count-compact-link business-clickable-cell"
                          :title="getWordCountListSummary(subRow).title"
                        >
                          <span class="compact-cell-value">
                            <span class="compact-cell-value__primary">{{ getWordCountListSummary(subRow).primary }}</span>
                            <span
                              v-if="getWordCountListSummary(subRow).extraCount"
                              class="compact-cell-value__count"
                            >+{{ getWordCountListSummary(subRow).extraCount }}</span>
                          </span>
                        </el-button>
                      </template>
                    </WordCountMatrixPopover>
                  </div>
                </template>
              </el-table-column>
              <el-table-column v-if="isSubOrderColumnVisible('assignedTranslators')" label="译员安排" min-width="180" show-overflow-tooltip>
                <template #default="{ row: subRow }">{{ formatAssignedTranslators(subRow.assignedTranslators, subRow.translatorName) }}</template>
              </el-table-column>
              <el-table-column v-if="isSubOrderColumnVisible('translatorReturnTime')" label="译员回稿时间" min-width="190">
                <template #header><ClickableColumnHeader label="译员回稿时间" hint="点击回稿时间编辑译员任务完成情况及价格" /></template>
                <template #default="{ row: subRow }">
                  <TranslatorCompletionPopover
                    :translators="subRow.assignedTranslators"
                    :status="subRow.status"
                    :editable="canWriteProjects"
                    :save="(completions) => saveSubOrderTranslatorCompletions(subRow, completions)"
                  />
                </template>
              </el-table-column>
              <el-table-column v-if="isSubOrderColumnVisible('status')" prop="status" label="状态" min-width="120">
                <template #default="{ row: subRow }">
                  <el-tag :type="getStatusType(subRow.status)">{{ getStatusLabel(subRow.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="88" fixed="right" align="center">
                <template #default="{ row: subRow }">
                  <PrimaryEditButton v-if="canWriteProjects" @click="openSubOrderEditorFromList(row, subRow)" />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="序号" :width="PROJECT_LIST_COLUMN_WIDTHS.index" align="center">
        <template #default="{ row, $index }">
          <div class="index-cell">
            <span>{{ $index + 1 }}</span>
            <TableExpandButton
              v-if="getSubOrderCount(row)"
              :expanded="isProjectExpanded(row)"
              expand-label="展开子订单"
              collapse-label="收起子订单"
              @click="toggleProjectExpansion(row)"
            />
          </div>
        </template>
      </el-table-column>
      <el-table-column
        v-for="column in visibleTableColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :min-width="column.minWidth"
        :show-overflow-tooltip="column.key !== 'projectName' && column.showOverflowTooltip !== false"
        :class-name="getSortColumnClass(column.key)"
        :label-class-name="getSortColumnClass(column.key)"
      >
        <template #header>
          <div class="project-column-header">
            <ConfiguredColumnHeaderFilter
              v-if="headerFilterDefinition(column.key)"
              :definition="headerFilterDefinition(column.key)"
              :model-value="searchForm[headerFilterDefinition(column.key).key]"
              @update:model-value="searchForm[headerFilterDefinition(column.key).key] = $event"
              @text-input="handleConfiguredTextInput"
              @change="handleSearch"
              @enter="handleSearch"
              @clear="handleSearch"
            >
              <template #label>
                <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
                <span v-else>{{ column.label }}</span>
              </template>
            </ConfiguredColumnHeaderFilter>
            <template v-else>
              <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
              <span v-else>{{ column.label }}</span>
            </template>
            <button
              v-if="getTimeSortMode(column.key)"
              type="button"
              class="time-column-sort-trigger"
              :class="{ 'is-active': isTimeSortActive(column.key) }"
              :aria-label="getTimeSortTitle(column)"
              :aria-pressed="isTimeSortActive(column.key)"
              :title="getTimeSortTitle(column)"
              @click.stop="toggleTimeSort(column.key)"
            >
              <el-icon><SortUp /></el-icon>
            </button>
          </div>
        </template>
        <template #default="{ row }">
          <div v-if="column.key === 'orderNo'" class="order-no-actions">
            <BusinessDetailPopover
              :row="row"
              title="项目详情"
              :items="projectDetailItems"
              :status-label="getStatusLabel"
              :status-type="getStatusType"
              :editable="canWriteProjects && !deleteMode"
              :save-field="(field, value) => saveProjectTextField(row, field, value)"
              @conflict="fetchData"
            >
              <template #reference>
                <el-button type="primary" link class="order-no-link business-clickable-cell" :title="`${row.orderNo}（点击查看详情）`" @click.stop>
                  {{ row.orderNo }}
                </el-button>
              </template>
            </BusinessDetailPopover>
            <PathActionButtons v-if="canReadProjectFiles" @open="openOriginalPath(row)" @copy="copyOriginalPath(row)" />
          </div>
          <InlineTextField
            v-else-if="column.key === 'projectName'"
            :model-value="row.projectName"
            :editable="canWriteProjects && !deleteMode"
            label="项目名称"
            required
            :maxlength="255"
            :save-field="(value) => saveProjectTextField(row, 'projectName', value)"
            @conflict="fetchData"
          />
          <el-dropdown
            v-else-if="column.key === 'projectStatus' && canWriteProjects"
            trigger="click"
            :disabled="projectStatusSavingIds.has(row.id)"
            @command="(command) => changeProjectStatus(row, command)"
          >
            <el-tag
              :type="getStatusType(row.projectStatus)"
              size="small"
              class="status-switch-tag"
              :class="{ 'is-updating': projectStatusSavingIds.has(row.id) }"
            >
              <span class="status-switch-text">{{ getStatusLabel(row.projectStatus) }}</span>
              <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
            </el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="item in projectStatusOptions"
                  :key="item.value"
                  :command="item.value"
                  :disabled="item.value === normalizeStatus(row.projectStatus) || item.value === 'pending_confirmation' || projectStatusSavingIds.has(row.id)"
                >
                  <span class="status-option-row">
                    <el-tag :type="getStatusType(item.value)" size="small" effect="plain" class="status-option-tag">{{ item.label }}</el-tag>
                    <el-icon v-if="item.value === normalizeStatus(row.projectStatus)" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tag v-else-if="column.key === 'projectStatus'" :type="getStatusType(row.projectStatus)">
            {{ getStatusLabel(row.projectStatus) }}
          </el-tag>
          <DeadlineHintCell
            v-else-if="column.key === 'customerDeadlineTime'"
            :deadline="row.customerDeadlineTime"
            :status="row.projectStatus"
          />
          <TranslatorCompletionPopover
            v-else-if="column.key === 'translatorReturnTime'"
            :translators="row.assignedTranslators"
            :status="row.projectStatus"
            :editable="canWriteProjects && !deleteMode"
            :save="(completions) => saveProjectTranslatorCompletions(row, completions)"
          />
          <div
            v-else-if="column.key === 'languagePair'"
            class="compact-cell-value"
            :title="row.languagePair || '-'"
          >
            <span class="compact-cell-value__primary">{{ getLanguagePairSummary(row.languagePair).primary }}</span>
            <span v-if="getLanguagePairSummary(row.languagePair).extraCount" class="compact-cell-value__count">
              +{{ getLanguagePairSummary(row.languagePair).extraCount }}
            </span>
          </div>
          <div
            v-else-if="column.key === 'assignedTranslators'"
            class="compact-cell-value"
            :title="formatAssignedTranslators(row.assignedTranslators, row.translatorName)"
          >
            <span class="compact-cell-value__primary">{{ getAssignedTranslatorSummary(row).primary }}</span>
            <span v-if="getAssignedTranslatorSummary(row).extraCount" class="compact-cell-value__count">
              +{{ getAssignedTranslatorSummary(row).extraCount }}
            </span>
          </div>
          <div v-else-if="column.key === 'wordCountMatrix'" class="word-count-list-cell">
            <WordCountMatrixPopover v-model="row.wordCountMatrix" entity-type="project" :entity-id="row.id" title="项目字数统计" @saved="fetchData">
              <template #reference>
                <el-button type="primary" link class="word-count-compact-link business-clickable-cell" :title="getWordCountListSummary(row).title">
                  <span class="compact-cell-value">
                    <span class="compact-cell-value__primary">{{ getWordCountListSummary(row).primary }}</span>
                    <span v-if="getWordCountListSummary(row).extraCount" class="compact-cell-value__count">
                      +{{ getWordCountListSummary(row).extraCount }}
                    </span>
                  </span>
                </el-button>
              </template>
            </WordCountMatrixPopover>
          </div>
          <span v-else>{{ formatTableColumnValue(row, column) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" :width="PROJECT_LIST_COLUMN_WIDTHS.actions" fixed="right" align="center">
        <template #default="{ row }">
          <ProjectListRowActions
            v-if="canWriteProjects"
            :start-request-label="resourceRequestActionLabel(row.id)"
            @edit="handleEdit(row)"
            @start-request="startResourceRequest(row)"
          />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      style="margin-top: 20px"
      @size-change="applyPagination"
      @current-change="applyPagination"
    />

    <el-dialog
      v-model="exportDialogVisible"
      title="导出笔译项目"
      width="min(520px, calc(100vw - 32px))"
      top="12vh"
      :close-on-click-modal="!exporting"
      :close-on-press-escape="!exporting"
      :show-close="!exporting"
      @closed="resetExportForm"
    >
      <AppForm
        ref="exportFormRef"
        :model="exportForm"
        :rules="exportRules"
        label-width="110px"
        @submit.prevent
      >
        <el-form-item label="时间口径" prop="timeField">
          <el-select v-model="exportForm.timeField" style="width: 100%">
            <el-option
              v-for="item in TRANSLATION_EXPORT_TIME_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围" prop="dateRange">
          <el-date-picker
            v-model="exportForm.dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            unlink-panels
            style="width: 100%"
          />
        </el-form-item>
        <el-alert
          title="将继承当前关键词和高级筛选，并导出命中母订单下的全部子订单。"
          type="info"
          :closable="false"
          show-icon
        />
      </AppForm>
      <template #footer>
        <el-button :disabled="exporting" @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="handleExport">导出</el-button>
      </template>
    </el-dialog>

    <DraggableFormDialog
      v-model="dialogVisible"
      class="project-editor-dialog"
      width="min(1160px, calc(100vw - 32px))"
      top="5vh"
      @closed="onProjectDialogClosed"
    >
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          v-model="fieldSearchKeyword"
          :title="dialogTitle"
          :fetch-suggestions="fetchFieldSuggestions"
          @select="locateProjectField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="editorBodyRef" class="editor-body">
        <AppForm ref="formRef" :model="form" :rules="rules" label-width="120px">
          <el-tabs v-model="projectDialogTab" class="editor-tabs project-editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <div class="project-key-fields">
                  <div class="project-key-fields__header">
                    <div>
                      <h3>关键必填信息</h3>
                      <p>请优先完成以下内容，再补充其余项目资料。</p>
                    </div>
                    <el-tag type="danger" effect="plain">7 项必填</el-tag>
                  </div>
                  <el-row :gutter="16">
                    <el-col :xs="24">
                      <el-form-item label="项目名称" prop="projectName" data-field-key="projectName">
                        <div class="auto-name-field">
                          <GeneratedProjectNameInput
                            v-model="form.projectName"
                            placeholder="可手工填写，或根据客户、方向和交稿时间自动生成"
                            @manual-input="handleProjectNameInput"
                            @regenerate="regenerateProjectName"
                          />
                          <div class="auto-name-field__hint">按“客户简称，翻译方向简称，月日时回稿”自动生成，例如“广州学在华留学咨询，法译中，9月1日16点回稿”；存在子订单时追加批次，也可手动修改。</div>
                        </div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="16">
                    <el-col :xs="24" :md="12">
                      <el-form-item label="客户简称" prop="clientShortName" data-field-key="clientShortName">
                        <div class="client-autocomplete-field">
                          <el-autocomplete
                            v-model="form.clientShortName"
                            :fetch-suggestions="fetchClientSuggestions"
                            value-key="client_short_name"
                            placeholder="选择已有客户，或直接输入新客户简称"
                            clearable
                            :debounce="300"
                            :trigger-on-focus="true"
                            style="width: 100%"
                            @select="handleClientSelect"
                            @input="handleClientShortNameInput"
                            @clear="clearSelectedClient"
                          >
                            <template #default="{ item }">
                              <div class="client-suggestion">
                                <span>
                                  {{ item.client_short_name }}
                                  <el-tag v-if="item.sub_client_id" size="small" type="warning">子客户</el-tag>
                                </span>
                                <span class="client-suggestion__meta">{{ item.client_code }} · {{ item.client_name }}{{ item.parent_client_short_name ? ` · 归属 ${item.parent_client_short_name}` : '' }}</span>
                              </div>
                            </template>
                          </el-autocomplete>
                          <div class="client-autocomplete-hint">没有匹配客户时，保存项目会自动新增一条待完善的客户信息。</div>
                        </div>
                      </el-form-item>
                    </el-col>
                    <el-col :xs="24" :md="12">
                      <el-form-item label="翻译方向" prop="languagePair" data-field-key="languagePair">
                        <LanguagePairSelect v-model="form.languagePair" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="16">
                    <el-col :xs="24">
                      <el-form-item label="字数与预估" prop="wordCountMatrix" data-field-key="wordCountSummary">
                        <div class="word-count-summary">
                          <span>{{ formatWordCountSummary(form) }}</span>
                          <WordCountMatrixPopover
                            v-model="form.wordCountMatrix"
                            entity-type="project"
                            :entity-id="form.id"
                            title="项目字数统计"
                            @saved="handleProjectWordCountSaved"
                          >
                            <template #reference><el-button type="primary" link>展开字数统计</el-button></template>
                          </WordCountMatrixPopover>
                        </div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="16">
                    <el-col :xs="24" :md="12"><el-form-item label="客户接单时间" prop="customerReceptionTime" data-field-key="customerReceptionTime"><el-date-picker v-model="form.customerReceptionTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                    <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间" prop="customerDeadlineTime" data-field-key="customerDeadlineTime"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                  </el-row>
                </div>
                <el-collapse v-model="projectBasicExpandedSections" class="project-basic-collapse">
                  <el-collapse-item name="project">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目与客户</span>
                        <span class="project-basic-collapse__hint">订单、项目名称、客户及服务信息</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="订单号"><ReadonlyField :model-value="form.orderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态" prop="projectStatus" data-field-key="projectStatus"><el-select v-model="form.projectStatus" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" :disabled="item.value === 'pending_confirmation'" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="标题前缀">
                      <el-select
                        v-model="form.subjectPrefix"
                        filterable
                        allow-create
                        default-first-option
                        clearable
                        placeholder="可直接选择常用前缀，也可自行输入"
                        style="width: 100%"
                      >
                        <el-option v-for="item in COMMON_SUBJECT_PREFIX_OPTIONS" :key="item" :label="item" :value="item" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24">
                    <el-form-item label="邮件主题预览" data-field-key="emailSubjectPreview">
                      <div class="subject-preview-field">
                        <el-input v-model="form.emailSubjectPreview" type="textarea" :rows="2" />
                        <div class="subject-preview-toolbar">
                          <span>按“标题前缀、订单号、客户简称、客户经理联系方式、客户单号/标识、项目名称”顺序生成</span>
                          <el-button class="soft-action-button" :icon="MagicStick" @click="generateEmailSubject">生成邮件主题</el-button>
                        </div>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="任务类型" data-field-key="taskType">
                      <el-select
                        v-model="form.taskType"
                        filterable
                        allow-create
                        clearable
                        placeholder="成交项目自动取自咨询类型，也可手工补录"
                        style="width: 100%"
                      >
                        <el-option v-for="item in taskTypeOptions" :key="item" :label="item" :value="item" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="来源咨询 ID"><ReadonlyField :model-value="form.consultationId" source="auto" placeholder="手工新增项目无来源咨询" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户编号" data-field-key="clientCode"><ReadonlyField :model-value="form.clientCode" source="auto" :placeholder="form.clientId ? '选择客户后自动带出' : '保存后自动生成'" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户单号" data-field-key="customerOrderNo"><el-input v-model="form.customerOrderNo" placeholder="客户公司内部用于记录该外包项目的单号" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户经理"><ReadonlyField :model-value="form.clientManager" source="auto" placeholder="选择客户后自动带出" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col v-if="showManagerContactInput" :xs="24" :md="12">
                    <el-form-item label="客户经理联系方式" label-width="140px">
                      <el-input
                        v-model="form.managerContact"
                        maxlength="100"
                        clearable
                        placeholder="请输入客户经理联系方式"
                      />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="服务内容" prop="serviceContent" data-field-key="serviceContent">
                      <div class="service-content-field">
                        <el-select
                          v-model="serviceContentSelection"
                          filterable
                          allow-create
                          default-first-option
                          clearable
                          placeholder="请选择服务内容"
                        >
                          <el-option
                            v-for="item in serviceContentOptions"
                            :key="item"
                            :label="item"
                            :value="item"
                          />
                        </el-select>
                        <el-input
                          v-if="customServiceContentOption"
                          v-model="serviceContentCustomText"
                          clearable
                          maxlength="200"
                          :placeholder="`请补充${customServiceContentOption}的具体内容`"
                        />
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型" data-field-key="fileTypeSecondary"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
                      </el-row>
                    </div>
                  </el-collapse-item>

                  <el-collapse-item name="business">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目商务信息</span>
                        <span class="project-basic-collapse__hint">合同、报价单及客户要求</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="合同类型" data-field-key="projectContractType">
                      <el-input v-model="form.projectContractType" clearable placeholder="请输入项目合同类型" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="合同状态" data-field-key="projectContractStatus">
                      <el-input v-model="form.projectContractStatus" clearable placeholder="请输入项目合同状态" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="需提供报价单" data-field-key="quotationRequired">
                  <el-checkbox v-model="form.quotationRequired">需要提供项目报价单</el-checkbox>
                </el-form-item>
                <el-row v-if="form.quotationRequired" :gutter="16">
                  <el-col :xs="24" :md="8">
                    <el-form-item label="报价单状态" data-field-key="quotationStatus">
                      <el-input v-model="form.quotationStatus" clearable placeholder="请输入状态" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="16">
                    <el-form-item label="报价单路径" data-field-key="quotationPath">
                      <el-input v-model="form.quotationPath" clearable placeholder="如 \\win-server\项目报价单" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="客户专业要求" data-field-key="customerRequirementProfessional">
                  <el-input v-model="form.customerRequirementProfessional" type="textarea" :rows="2" placeholder="请输入客户专业要求" />
                </el-form-item>
                      <el-form-item label="客户特殊要求" data-field-key="customerRequirementSpecial">
                  <el-input v-model="form.customerRequirementSpecial" type="textarea" :rows="2" placeholder="请输入客户特殊要求" />
                      </el-form-item>
                    </div>
                  </el-collapse-item>

                  <el-collapse-item name="execution">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目执行信息</span>
                        <span class="project-basic-collapse__hint">负责人、优先级、时间及确认信息</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级" data-field-key="priority"><el-select v-model="form.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="项目经理" data-field-key="projectManagerId">
                      <el-select
                        v-model="form.projectManagerId"
                        filterable
                        clearable
                        placeholder="绑定管理层主负责人"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="manager in projectManagerOptions"
                          :key="manager.id"
                          :label="manager.is_on_leave ? `${manager.full_name || manager.username}（${manager.assignment_disabled_reason || '请假中'}）` : (manager.full_name || manager.username)"
                          :value="manager.id"
                          :disabled="manager.is_on_leave && manager.id !== form.projectManagerId"
                        />
                      </el-select>
                      <div class="auto-name-field__hint">管理层主负责人，与当前流程处理人相互独立。</div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col
                    v-for="role in projectRoleFieldConfigs"
                    :key="role.roleCode"
                    :xs="24"
                    :md="8"
                  >
                    <el-form-item :label="role.label" :data-field-key="role.fieldKey">
                      <el-select
                        v-model="form[role.formKey]"
                        filterable
                        clearable
                        :placeholder="`未绑定时进入${role.label}角色池`"
                        style="width: 100%"
                        :loading="projectRoleOptionsLoading"
                      >
                        <el-option
                          v-for="user in projectRoleCandidateOptions[role.roleCode] || []"
                          :key="user.id"
                          :label="user.is_on_leave ? `${user.full_name || user.username}（${user.assignment_disabled_reason || '请假中'}）` : (user.full_name || user.username)"
                          :value="user.id"
                          :disabled="user.is_on_leave && String(user.id) !== String(form[role.formKey])"
                        />
                      </el-select>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="客户反馈" data-field-key="clientFeedback"><el-input v-model="form.clientFeedback" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="已分配译员">
                      <ReadonlyField :model-value="formatAssignedTranslators(form.assignedTranslators, form.translatorName)" source="auto" placeholder="由“稿件安排”模块统一维护" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="译员回稿时间">
                      <ReadonlyField :model-value="formatTranslatorReturnTimes(form.assignedTranslators)" source="auto" placeholder="由“稿件安排”的全稿预定时间自动带出" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间" data-field-key="sentToClientTime"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="PM确认人" data-field-key="pmConfirmedBy"><el-select v-model="form.pmConfirmedBy" filterable clearable placeholder="请选择PM确认人" style="width: 100%"><el-option v-for="manager in projectManagerOptions" :key="manager.id" :label="manager.full_name || manager.username" :value="manager.id" /></el-select></el-form-item></el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="大项目经理确认"><ReadonlyField :model-value="form.majorProjectManagerConfirmation" source="auto" placeholder="由“稿件安排”的确认安排操作自动记录" /></el-form-item></el-col>
                      </el-row>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in progressFieldConfigs" :key="item.key" class="progress-card" :data-field-key="item.key">
                  <div class="progress-card__header">
                    <span>{{ item.label }}</span>
                    <strong>{{ formatProgressDisplay(form[item.key]) }}</strong>
                  </div>
                  <el-slider
                    v-model="form[item.key]"
                    :min="0"
                    :max="100"
                    :marks="progressMarks"
                    show-input
                    input-size="small"
                  />
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="子订单" name="suborders">
              <template v-if="form.id">
                <div class="section-header">
                  <div class="section-title">子订单管理</div>
                  <div class="section-actions">
                    <el-button v-if="canWriteProjects" type="primary" @click="openCreateSubOrderDialog">新增子订单</el-button>
                    <el-button v-if="canWriteProjects" @click="openBatchDialog(form, 'quantity')">按数量批量新增</el-button>
                    <el-button v-if="canWriteProjects" @click="openBatchDialog(form, 'filenames')">导入文件名</el-button>
                    <el-button v-if="hasMoreSubOrders({ subOrders: currentProjectSubOrders })" @click="goToSubOrderManagement(form)">查看全部子订单</el-button>
                  </div>
                </div>

                <el-alert
                  v-if="hasMoreSubOrders({ subOrders: currentProjectSubOrders })"
                  title="当前仅展示前 10 条子订单，更多数据请进入独立子订单管理页查看和操作。"
                  type="warning"
                  :closable="false"
                  show-icon
                  class="sub-order-alert"
                />

                <el-table class="sub-order-table" :data="getVisibleSubOrders({ subOrders: currentProjectSubOrders })" border>
                  <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
                  <el-table-column min-width="220">
                    <template #header>
                      <div class="sub-order-name-header">
                        <span>子项目名称</span>
                        <el-button
                          v-if="canWriteProjects"
                          type="primary"
                          link
                          size="small"
                          :icon="Check"
                          :loading="editorInlineSaving"
                          :disabled="editorInlinePendingCount === 0"
                          title="保存全部子项目名称"
                          @click="saveAllInlineNames('editor')"
                        >保存全部{{ editorInlinePendingCount ? `（${editorInlinePendingCount}）` : '' }}</el-button>
                      </div>
                    </template>
                    <template #default="{ row }">
                      <InlineSubProjectName
                        :sub-order-id="row.id"
                        :model-value="row.subProjectName"
                        :editable="canWriteProjects"
                        @pending-change="handleInlinePendingChange('editor', row, $event)"
                        @saved="handleInlineSubOrderSaved(row, $event, 'editor')"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="languagePair" label="翻译方向" min-width="120" />
                  <el-table-column label="字数统计" width="132" min-width="120">
                    <template #header><ClickableColumnHeader label="字数统计" hint="点击查看子订单字数统计" /></template>
                    <template #default="{ row }">
                      <div class="word-count-list-cell">
                        <WordCountMatrixPopover v-model="row.wordCountMatrix" entity-type="suborder" :entity-id="row.id" title="子订单字数统计" @saved="fetchData">
                          <template #reference>
                            <el-button type="primary" link class="word-count-compact-link business-clickable-cell" :title="getWordCountListSummary(row).title">
                              <span class="compact-cell-value">
                                <span class="compact-cell-value__primary">{{ getWordCountListSummary(row).primary }}</span>
                                <span v-if="getWordCountListSummary(row).extraCount" class="compact-cell-value__count">
                                  +{{ getWordCountListSummary(row).extraCount }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </WordCountMatrixPopover>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" min-width="120">
                    <template #default="{ row }">
                      <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="详情" width="100" fixed="right">
                    <template #default="{ row }">
                      <BusinessDetailPopover :row="row" title="子订单详情" :items="subOrderDetailItems" :status-label="getStatusLabel" :status-type="getStatusType" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="{ row }">
                      <TableActionButton v-if="canWriteProjects" action="edit" @click="handleEditSubOrder(row)" />
                      <TableActionButton v-if="canWriteProjects" action="delete" @click="handleDeleteSubOrder(row)" />
                    </template>
                  </el-table-column>
                </el-table>
              </template>
              <el-alert v-else title="请先保存母订单，再在此 Tab 中新增或批量新增子订单。" type="info" :closable="false" show-icon />
            </el-tab-pane>

            <el-tab-pane v-if="canReadProjectFiles" label="项目文件" name="files">
              <ProjectFilesTab
                ref="projectFilesTabRef"
                :project-id="form.id"
                :order-no="form.orderNo"
                entity-type="project"
                :active="projectDialogTab === 'files'"
                :show-save-action="false"
                :allow-draft="true"
                v-model:reference-file-path-one="form.referenceFilePathOne"
                @status-change="handleProjectFileStatusChange"
              />
            </el-tab-pane>
          </el-tabs>
        </AppForm>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="canWriteProjects" :loading="submitLoading" @click="handleSubmit(true)">保存并发送邮件</el-button>
        <el-button v-if="canWriteProjects" type="primary" :loading="submitLoading" @click="handleSubmit(false)">保存</el-button>
      </template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="subOrderDialogVisible" class="suborder-editor-dialog" :title="subOrderDialogTitle" width="min(1040px, calc(100vw - 32px))" top="5vh" @closed="resetSubOrderForm">
      <div class="editor-body">
        <AppForm ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="120px">
          <el-tabs v-model="subOrderDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="母订单号"><ReadonlyField :model-value="form.orderNo" source="auto" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="子订单号"><ReadonlyField :model-value="subOrderForm.subOrderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="子项目名称" prop="subProjectName"><el-input v-model="subOrderForm.subProjectName" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态"><el-select v-model="subOrderForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="subOrderForm.fileTypeSecondary" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="subOrderForm.languagePair" :show-hint="false" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="subOrderForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="客户反馈"><el-input v-model="subOrderForm.clientFeedback" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="备注"><el-input v-model="subOrderForm.remarks" type="textarea" :rows="3" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="分配与预估" name="assignment">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="已分配译员"><ReadonlyField :model-value="formatAssignedTranslators(subOrderForm.assignedTranslators, subOrderForm.translatorName)" source="auto" placeholder="请在“稿件安排”模块中分配译员" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="译员回稿时间"><ReadonlyField :model-value="formatTranslatorReturnTimes(subOrderForm.assignedTranslators)" source="auto" placeholder="由“稿件安排”的全稿预定时间自动带出" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-alert title="新的译员分配统一由“稿件安排”维护；历史单译员字段仅用于兼容旧数据。" type="info" :closable="false" show-icon /></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="字数与预估">
                      <div class="word-count-summary">
                        <span>{{ formatWordCountSummary(subOrderForm) }}</span>
                        <WordCountMatrixPopover
                          v-model="subOrderForm.wordCountMatrix"
                          entity-type="suborder"
                          :entity-id="subOrderForm.id"
                          title="子订单字数统计"
                          @saved="handleSubOrderWordCountSaved"
                        >
                          <template #reference><el-button type="primary" link>展开字数统计</el-button></template>
                        </WordCountMatrixPopover>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="网络文件路径"><el-input v-model="subOrderForm.networkFilePath" type="textarea" :rows="3" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in subOrderProgressFieldConfigs" :key="item.key" class="progress-card">
                  <div class="progress-card__header">
                    <span>{{ item.label }}</span>
                    <strong>{{ formatProgressDisplay(subOrderForm[item.key]) }}</strong>
                  </div>
                  <el-slider
                    v-model="subOrderForm[item.key]"
                    :min="0"
                    :max="100"
                    :marks="progressMarks"
                    show-input
                    input-size="small"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </AppForm>
      </div>
      <template #footer>
        <el-button @click="subOrderDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitSubOrder">保存</el-button>
      </template>
    </DraggableFormDialog>

    <SubOrderBatchCreateDialog
      v-model="batchDialogVisible"
      :project="batchTargetProject"
      :existing-names="batchExistingNames"
      :initial-mode="batchDialogMode"
      @created="handleBatchCreated"
    />

    <BusinessMailComposer
      v-model="mailComposerVisible"
      project-type="translation"
      :project-id="mailProjectId"
      :consultation-id="mailConsultationId"
    />

  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CaretBottom, Check, Download, MagicStick, SortUp } from '@element-plus/icons-vue'
import { getProjectPage, getProject, createProject, updateProject, updateProjectTextField, deleteProject, getNextOrderNo, exportTranslationProjects } from '@/api/projects'
import { getProjectFilesByProject } from '@/api/projectFiles'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'
import { getProjectManagerCandidatesAPI, getProjectRoleCandidatesAPI } from '@/api/workflow'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ProjectFilesTab from './components/ProjectFilesTab.vue'
import InlineSubProjectName from './components/InlineSubProjectName.vue'
import SubOrderBatchCreateDialog from './components/SubOrderBatchCreateDialog.vue'
import { hasPermission } from '@/utils/permission'
import { buildAutoProjectName, isAutoProjectName } from '@/utils/projectNaming'
import { fetchProjectClientSuggestions } from '@/utils/projectClientAutocomplete'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import InlineTextField from '@/components/common/InlineTextField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import BusinessMailComposer from '@/components/common/BusinessMailComposer.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import GeneratedProjectNameInput from '@/components/common/GeneratedProjectNameInput.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import TranslatorCompletionPopover from './components/TranslatorCompletionPopover.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useFormDraft } from '@/composables/useFormDraft'
import { useResourceRequestStatuses } from '@/composables/useResourceRequestStatuses'
import { createEmptyWordCountMatrix, formatWordCountMatrix, getWordCountMatrixListSummary } from '@/utils/wordCountMatrix'
import { getLanguagePairSummary } from '@/utils/languagePair'
import { COMMON_SUBJECT_PREFIX_OPTIONS, notifyEmailSubjectGenerated, extractSubjectPrefix } from '@/utils/emailSubject'
import { copyTextToClipboard } from '@/utils/clipboard'
import { launchOpenPath } from '@/utils/openPath'
import { resolvePreferredProjectPath } from '@/utils/projectPath'
import { createIdempotencyKey } from '@/utils/idempotency'
import {
  formatBusinessDateTime as formatDateTime,
  isTranslatorReturnTerminalStatus,
  parseBusinessDateTime,
} from '@/utils/deadlineDisplay'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'
import {
  DEFAULT_TRANSLATION_PROJECT_SORT,
  TRANSLATION_PROJECT_TIME_SORT_MODES,
  getTranslationProjectTimeSortMode,
  getTranslationProjectTimeSortTitle,
  isTranslationProjectTimeSortActive,
  nextTranslationProjectTimeSortMode,
} from '@/utils/translationProjectTimeSort'
import {
  DEFAULT_TRANSLATION_EXPORT_TIME_FIELD,
  TRANSLATION_EXPORT_TIME_OPTIONS,
  buildTranslationExportFilename,
  buildTranslationExportParams,
} from '@/utils/translationProjectExport'

const SUB_ORDER_PREVIEW_LIMIT = 10
const canWriteProjects = hasPermission('projects:write')
const canReadProjectFiles = hasPermission('project_files:read')
const mailComposerVisible = ref(false)
const mailProjectId = ref('')
const mailConsultationId = ref('')
const router = useRouter()
const route = useRoute()
const { load: loadResourceRequestStatuses, actionLabel: resourceRequestActionLabel } = useResourceRequestStatuses('translation')
const startResourceRequest = (row) => router.push({ name: 'ResourceRequests', query: { sourceType: 'translation', sourceProjectId: row.id } })
const highlightedProjectId = ref('')
const projectDialogTab = ref('basic')
const projectBasicExpandedSections = ref(['project', 'business', 'execution'])
const subOrderDialogTab = ref('basic')
const projectStatusOptions = [
  { label: '待确认', value: 'pending_confirmation' },
  { label: '已确认', value: 'confirmed' },
  { label: '已整理', value: 'organized' },
  { label: '已排译员', value: 'translator_assigned' },
  { label: '已发译员', value: 'sent_to_translator' },
  { label: '译员发回', value: 'translator_returned' },
  { label: '已专检', value: 'special_checked' },
  { label: '已排版', value: 'typeset' },
  { label: '已专检排版', value: 'special_checked_typeset' },
  { label: '已审核', value: 'reviewed' },
  { label: '已发客户', value: 'sent_to_client' },
  { label: '客户反馈', value: 'client_feedback' },
  { label: '反馈后发客户', value: 'feedback_sent_to_client' },
  { label: '已取消', value: 'cancelled' },
  { label: '已部分取消', value: 'partially_cancelled' },
  { label: '已暂停', value: 'paused' }
]
const priorityOptions = ['低', '中', '高', '紧急']
const serviceContentOptions = [
  '翻译',
  'Word排版',
  'PPT排版',
  'InDesign排版',
  'CorelDRAW排版',
  'Illustrator排版',
  'CAD排版',
  '翻译+InDesign排版',
  '翻译+CorelDRAW排版',
  '翻译+Illustrator排版',
  '翻译+CAD排版',
  '其他排版',
  '翻译+其他排版',
]
const customServiceContentOptions = ['其他排版', '翻译+其他排版']
const projectRoleFieldConfigs = [
  { roleCode: 'project_specialist', label: '项目专员', formKey: 'projectSpecialistId', fieldKey: 'projectSpecialistId' },
  { roleCode: 'project_assistant', label: '项目助理', formKey: 'projectAssistantId', fieldKey: 'projectAssistantId' },
  { roleCode: 'layout_specialist', label: '排版专员', formKey: 'layoutSpecialistId', fieldKey: 'layoutSpecialistId' }
]
const progressFieldConfigs = [
  { key: 'translatorDeliveryProgress', label: '译员交付进度' },
  { key: 'preReviewQcProgress', label: '审校前 QC' },
  { key: 'review1Progress', label: '审校 1' },
  { key: 'review2Progress', label: '审校 2' },
  { key: 'postReviewQcProgress', label: '审校后 QC' },
  { key: 'layoutProgress', label: '排版进度' },
  { key: 'consolidationProgress', label: '整合进度' }
]
const basicProjectFieldSearchItems = [
  { key: 'projectName', label: '项目名称', aliases: ['项目名'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'emailSubjectPreview', label: '邮件主题预览', aliases: ['邮件标题'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'taskType', label: '任务类型', aliases: ['项目类型', '咨询类型'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'clientShortName', label: '客户简称', aliases: ['客户名称', '客户'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'clientCode', label: '客户编号', aliases: ['客户编码'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'customerOrderNo', label: '客户单号', aliases: ['客户订单号'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'serviceContent', label: '服务内容', aliases: ['服务'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'fileTypeSecondary', label: '文本类型', aliases: ['文件类型'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'languagePair', label: '翻译方向', aliases: ['语言对', '语言方向'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'wordCountSummary', label: '字数与预估', aliases: ['字数摘要', '客户提供字数', '内部核算字数', '统计口径', '预计译员字数'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'projectContractType', label: '合同类型', aliases: ['项目合同类型'], section: 'business', sectionLabel: '项目商务信息' },
  { key: 'projectContractStatus', label: '合同状态', aliases: ['项目合同状态'], section: 'business', sectionLabel: '项目商务信息' },
  { key: 'quotationRequired', label: '需提供报价单', aliases: ['报价单', '是否需要报价'], section: 'business', sectionLabel: '项目商务信息' },
  { key: 'quotationStatus', label: '报价单状态', aliases: ['报价状态'], section: 'business', sectionLabel: '项目商务信息', requires: 'quotationRequired' },
  { key: 'quotationPath', label: '报价单路径', aliases: ['报价文件', '报价路径'], section: 'business', sectionLabel: '项目商务信息', requires: 'quotationRequired' },
  { key: 'customerRequirementProfessional', label: '客户专业要求', aliases: ['专业要求'], section: 'business', sectionLabel: '项目商务信息' },
  { key: 'customerRequirementSpecial', label: '客户特殊要求', aliases: ['特殊要求'], section: 'business', sectionLabel: '项目商务信息' },
  { key: 'priority', label: '优先级', aliases: ['紧急程度'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'projectStatus', label: '状态', aliases: ['项目状态', '业务状态'], section: 'project', sectionLabel: '项目与客户' },
  { key: 'projectManagerId', label: '项目经理', aliases: ['负责人', '项目负责人'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'projectSpecialistId', label: '项目专员', aliases: ['项目专员负责人'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'projectAssistantId', label: '项目助理', aliases: ['项目助理负责人'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'layoutSpecialistId', label: '排版专员', aliases: ['排版负责人'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'clientFeedback', label: '客户反馈', aliases: ['反馈'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'customerReceptionTime', label: '客户接单时间', aliases: ['接单时间'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'customerDeadlineTime', label: '客户交稿时间', aliases: ['交稿时间', '截止时间'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'sentToClientTime', label: '发客户时间', aliases: ['发送客户时间'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'translatorReturnTime', label: '译员回稿时间', aliases: ['全稿预定时间', '译员交稿全稿预定时间'], section: 'execution', sectionLabel: '项目执行信息' },
  { key: 'pmConfirmedBy', label: 'PM确认人 ID', aliases: ['PM确认人', '确认人'], section: 'execution', sectionLabel: '项目执行信息' },
].map((item) => ({ ...item, tab: 'basic', tabLabel: '基础信息', location: `基础信息 · ${item.sectionLabel}` }))
const progressFieldSearchItems = progressFieldConfigs.map((item) => ({
  ...item,
  aliases: [item.label.replaceAll(' ', '')],
  tab: 'progress',
  tabLabel: '进度跟踪',
  location: '进度跟踪',
}))
const projectFieldSearchItems = [
  ...basicProjectFieldSearchItems,
  ...progressFieldSearchItems,
]
const taskTypeOptions = [
  '笔译项目',
  '口译项目',
  '招聘项目',
  '标注项目',
  '配音项目',
  '字幕项目',
  '公证项目',
  '认证项目',
  '其他项目',
]
const subOrderProgressFieldConfigs = [
  ...progressFieldConfigs,
  { key: 'reviewProgress', label: '审核进度（旧字段）' }
]
const progressFieldSet = new Set(subOrderProgressFieldConfigs.map((item) => item.key))
const progressMarks = { 0: '0%', 50: '50%', 100: '100%' }
const projectDetailItems = [
  { label: '订单号', key: 'orderNo' },
  { label: '项目名称', key: 'projectName', editable: true, required: true, maxlength: 255 },
  { label: '邮件主题预览', key: 'emailSubjectPreview', span: 2, editable: true, multiline: true },
  { label: '服务内容', key: 'serviceContent', span: 2, editable: true, maxlength: 255 },
  { label: '任务类型', key: 'taskType', editable: true, maxlength: 50 },
  { label: '来源咨询 ID', key: 'consultationId' },
  { label: '客户简称', key: 'clientShortName' },
  { label: '客户编号', key: 'clientCode' },
  { label: '客户单号', key: 'customerOrderNo', editable: true, maxlength: 100 },
  { label: '项目经理', key: 'projectManagerName' },
  { label: '项目专员', key: 'projectSpecialistName' },
  { label: '项目助理', key: 'projectAssistantName' },
  { label: '排版专员', key: 'layoutSpecialistName' },
  { label: '客户经理', key: 'clientManager' },
  { label: '客户经理联系方式', key: 'managerContact' },
  { label: '状态', key: 'projectStatus', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary', editable: true, maxlength: 100 },
  { label: '翻译文本领域一级', key: 'projectFileTranslationDomainLevel1' },
  { label: '翻译文本领域二级', key: 'projectFileTranslationDomainLevel2' },
  { label: '文件类型一级', key: 'projectFileTypeLevel1' },
  { label: '文件类型二级', key: 'projectFileTypeLevel2' },
  { label: '文件格式', key: 'projectFileFormat' },
  { label: '文件属性一级', key: 'projectFileAttributeLevel1' },
  { label: '文件属性二级', key: 'projectFileAttributeLevel2' },
  { label: '文件属性三级', key: 'projectFileAttributeLevel3' },
  { label: '文件难度', key: 'projectFileDifficulty' },
  { label: '合同类型', key: 'projectContractType', editable: true, maxlength: 100 },
  { label: '合同状态', key: 'projectContractStatus', editable: true, maxlength: 100 },
  { label: '需提供报价单', key: 'quotationRequired', formatter: (value) => value ? '是' : '否' },
  { label: '报价单状态', key: 'quotationStatus', editable: true, maxlength: 100 },
  { label: '报价单路径', key: 'quotationPath', span: 2, editable: true, multiline: true },
  { label: '客户专业要求', key: 'customerRequirementProfessional', span: 2, editable: true, multiline: true },
  { label: '客户特殊要求', key: 'customerRequirementSpecial', span: 2, editable: true, multiline: true },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数与预估', key: 'wordCountMatrix', span: 2, formatter: (value) => formatWordCountMatrix(value) },
  { label: '客户接单时间', key: 'customerReceptionTime' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: 'PM确认人 ID', key: 'pmConfirmedBy' },
  { label: '客户反馈', key: 'clientFeedback', span: 2, editable: true, multiline: true },
  { label: '大项目经理确认', key: 'majorProjectManagerConfirmation' },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
  { label: '译员回稿时间', key: 'translatorReturnTime', span: 2, formatter: (_value, row) => formatTranslatorReturnTimes(row.assignedTranslators), clickHint: '点击回稿时间编辑译员任务完成情况及价格' },
  { label: '译员任务完成情况', key: 'translatorCompletionRemarks', span: 2, formatter: (_value, row) => formatTranslatorCompletionRemarks(row.assignedTranslators) },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前 QC', key: 'preReviewQcProgress' },
  { label: '审校 1', key: 'review1Progress' },
  { label: '审校 2', key: 'review2Progress' },
  { label: '审校后 QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const subOrderDetailItems = [
  { label: '子订单号', key: 'subOrderNo' },
  { label: '子项目名称', key: 'subProjectName' },
  { label: '状态', key: 'status', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数与预估', key: 'wordCountMatrix', span: 2, formatter: (value) => formatWordCountMatrix(value) },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
  { label: '译员回稿时间', key: 'translatorReturnTime', span: 2, formatter: (_value, row) => formatTranslatorReturnTimes(row.assignedTranslators) },
  { label: '译员任务完成情况', key: 'translatorCompletionRemarks', span: 2, formatter: (_value, row) => formatTranslatorCompletionRemarks(row.assignedTranslators) },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前 QC', key: 'preReviewQcProgress' },
  { label: '审核进度（旧字段）', key: 'reviewProgress' },
  { label: '审校 1', key: 'review1Progress' },
  { label: '审校 2', key: 'review2Progress' },
  { label: '审校后 QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '备注', key: 'remarks', span: 2 },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const createEmptyProjectForm = () => ({ id: '', orderNo: '', projectName: '', subjectPrefix: '', emailSubjectPreview: '', serviceContent: '', taskType: '笔译项目', consultationId: '', clientId: '', subClientId: '', clientShortName: '', clientCode: '', customerOrderNo: '', clientManager: '', managerContact: '', fileTypeSecondary: '', projectContractType: '', projectContractStatus: '', quotationRequired: false, quotationStatus: '', quotationPath: '', customerRequirementProfessional: '', customerRequirementSpecial: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), projectStatus: 'confirmed', projectManagerId: '', projectManagerName: '', projectSpecialistId: '', projectAssistantId: '', layoutSpecialistId: '', customerReceptionTime: '', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', pmConfirmedBy: '', majorProjectManagerConfirmation: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', translatorDeliveryProgress: 0, preReviewQcProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, referenceFilePathOne: '' })
const createEmptySubOrderForm = () => ({ id: '', parentProjectId: '', subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', status: 'pending_confirmation', translatorDeliveryProgress: 0, preReviewQcProgress: 0, reviewProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '', remarks: '' })
const loading = ref(false)
const submitLoading = ref(false)
const exporting = ref(false)
const exportDialogVisible = ref(false)
const exportFormRef = ref(null)
const exportForm = reactive({
  timeField: DEFAULT_TRANSLATION_EXPORT_TIME_FIELD,
  dateRange: [],
})
const exportRules = {
  timeField: [{ required: true, message: '请选择时间口径', trigger: 'change' }],
  dateRange: [{ type: 'array', required: true, len: 2, message: '请选择完整的时间范围', trigger: 'change' }],
}
let submitLocked = false
const projectCreateIdempotencyKey = ref('')
const dialogVisible = ref(false)
const subOrderDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const batchDialogMode = ref('quantity')
const batchTargetProject = ref({})
const batchTargetSubOrders = ref([])
const expandedInlineChanges = ref(new Map())
const editorInlineChanges = ref(new Map())
const expandedInlineSaving = ref(false)
const editorInlineSaving = ref(false)
const dialogTitle = ref('新增项目')
const subOrderDialogTitle = ref('新增子订单')
const formRef = ref(null)
const editorBodyRef = ref(null)
const fieldSearchRef = ref(null)
const fieldSearchKeyword = ref('')
const subOrderFormRef = ref(null)
const projectTableRef = ref(null)
const projectFilesTabRef = ref(null)
const tableData = ref([])
const projectStatusSavingIds = ref(new Set())
const expandedProjectIds = ref([])
const shouldInitializeProjectExpansion = ref(true)
const expandedProjectRowKeys = computed(() => expandedProjectIds.value)
const currentProjectSubOrders = ref([])
const batchExistingNames = computed(() => batchTargetSubOrders.value.map((item) => item.subProjectName).filter(Boolean))
const getExpandedInlinePendingCount = (projectId) => [...expandedInlineChanges.value.values()]
  .filter((change) => String(change.row?.parentProjectId) === String(projectId))
  .length
const editorInlinePendingCount = computed(() => editorInlineChanges.value.size)
const projectManagerOptions = ref([])
const projectRoleCandidateOptions = reactive(Object.fromEntries(projectRoleFieldConfigs.map((role) => [role.roleCode, []])))
const projectRoleOptionsLoading = ref(false)
const projectRoleOptionsLoaded = ref(false)
const projectNameManuallyEdited = ref(false)
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const DEFAULT_SORT_MODE = DEFAULT_TRANSLATION_PROJECT_SORT
const sortMode = ref(DEFAULT_SORT_MODE)
const TIME_SORT_MODES = TRANSLATION_PROJECT_TIME_SORT_MODES
const {
  deleteMode,
  deleting,
  selectedRows,
  enterDeleteMode,
  exitDeleteMode,
  handleDeleteSelectionChange,
  confirmBatchDelete,
} = useBatchDelete({
  rows: tableData,
  tableRef: projectTableRef,
  pagination,
  deleteRow: (row) => deleteProject(row.id),
  getLabel: (row) => row.orderNo || row.projectName,
  reload: () => fetchData(),
  entityName: '笔译项目',
})
const searchForm = reactive({
  keyword: '', projectStatus: '', taskType: '', serviceContent: '', priority: '',
  projectManagerId: '', customerDeadlineRange: [], createdRange: [],
})
const advancedVisible = ref(false)
const translationFilterFields = [
  { key: 'orderNo', label: '订单号', type: 'text' },
  { key: 'projectName', label: '项目名称', type: 'text' },
  { key: 'serviceContent', label: '服务内容', type: 'select', options: serviceContentOptions },
  { key: 'taskType', label: '任务类型', type: 'select', options: taskTypeOptions },
  { key: 'clientShortName', label: '客户简称', type: 'text' },
  { key: 'clientCode', label: '客户编号', type: 'text' },
  { key: 'customerOrderNo', label: '客户单号', type: 'text' },
  { key: 'projectManagerId', label: '项目经理', type: 'select', options: () => projectManagerOptions.value.map((item) => ({ label: item.full_name || item.username, value: item.id })) },
  { key: 'projectSpecialistName', label: '项目专员', type: 'text' },
  { key: 'projectAssistantName', label: '项目助理', type: 'text' },
  { key: 'layoutSpecialistName', label: '排版专员', type: 'text' },
  { key: 'clientManager', label: '客户经理', type: 'text' },
  { key: 'managerContact', label: '客户经理联系方式', type: 'text' },
  { key: 'projectStatus', label: '状态', type: 'select', options: projectStatusOptions },
  { key: 'fileTypeSecondary', label: '文本类型', type: 'text' },
  { key: 'projectFileTranslationDomainLevel1', label: '翻译文本领域一级', type: 'text' },
  { key: 'projectFileTranslationDomainLevel2', label: '翻译文本领域二级', type: 'text' },
  { key: 'projectFileTypeLevel1', label: '文件类型一级', type: 'text' },
  { key: 'projectFileTypeLevel2', label: '文件类型二级', type: 'text' },
  { key: 'projectFileFormat', label: '文件格式', type: 'text' },
  { key: 'projectFileAttributeLevel1', label: '文件属性一级', type: 'text' },
  { key: 'projectFileAttributeLevel2', label: '文件属性二级', type: 'text' },
  { key: 'projectFileAttributeLevel3', label: '文件属性三级', type: 'text' },
  { key: 'projectFileDifficulty', label: '文件难度', type: 'text' },
  { key: 'projectContractType', label: '合同类型', type: 'text' },
  { key: 'projectContractStatus', label: '合同状态', type: 'text' },
  { key: 'quotationRequired', label: '需提供报价单', type: 'boolean' },
  { key: 'quotationStatus', label: '报价单状态', type: 'text' },
  { key: 'customerRequirementProfessional', label: '客户专业要求', type: 'text' },
  { key: 'customerRequirementSpecial', label: '客户特殊要求', type: 'text' },
  { key: 'languagePair', label: '翻译方向', type: 'text' },
  { key: 'priority', label: '优先级', type: 'select', options: priorityOptions },
  { key: 'wordCountDimension', apiKey: 'word_count_dimension', label: '字数统计口径', type: 'select', options: [{value:'company',label:'我司'},{value:'customer',label:'客户'},{value:'translator_estimate',label:'译员预估'}] },
  { key: 'wordCountMetricType', apiKey: 'word_count_metric_type', label: '字数统计指标', type: 'select', options: [{value:'words',label:'字数'},{value:'characters_no_spaces',label:'字符数（不计空格）'},{value:'cjk_chars_korean_words',label:'中文字符和朝鲜语单词'},{value:'foreign_words',label:'外文字数'},{value:'documents',label:'份数'},{value:'pages',label:'页数'}] },
  { key: 'wordCountMatrix', apiKey: 'word_count', label: '字数与预估', type: 'number-range', wide: true, min: 0 },
  { key: 'customerReceptionTime', label: '客户接单时间', type: 'date-range', wide: true },
  { key: 'customerDeadlineTime', label: '客户交稿时间', type: 'date-range', wide: true },
  { key: 'translatorReturnTime', label: '译员回稿时间', type: 'date-range', wide: true },
  { key: 'sentToClientTime', label: '发客户时间', type: 'date-range', wide: true },
  { key: 'pmConfirmedBy', label: 'PM确认人', type: 'select', options: () => projectManagerOptions.value.map((item) => ({ label: item.full_name || item.username, value: item.id })) },
  { key: 'majorProjectManagerConfirmation', label: '大项目经理确认', type: 'text' },
  { key: 'assignedTranslators', apiKey: 'translator_name', label: '已分配译员', type: 'text' },
  { key: 'translatorAssignmentTime', label: '译员分配时间', type: 'date-range', wide: true },
  ...progressFieldConfigs.map((item) => ({ ...item, type: 'number-range', wide: true, min: 0, max: 100 })),
  { key: 'clientFeedback', label: '客户反馈', type: 'text' },
  { key: 'createdAt', label: '创建时间', type: 'date-range', wide: true },
  { key: 'updatedAt', label: '更新时间', type: 'date-range', wide: true },
]
Object.assign(searchForm, createFilterModel(translationFilterFields), { keyword: '' })
const translationAdvancedFilterFields = translationFilterFields.filter((item) => item.key !== 'projectStatus')
const advancedFilterCount = computed(() => countActiveFilters(searchForm, translationAdvancedFilterFields))
const translationDefaultFilterKeys = new Set(['orderNo', 'projectName', 'clientShortName', 'projectManagerName', 'assignedTranslators', 'projectStatus', 'languagePair', 'wordCountMatrix', 'customerDeadlineTime', 'translatorReturnTime'])
const translationHeaderFieldMap = { projectManagerName: 'projectManagerId' }
const headerFilterDefinition = (columnKey) => {
  if (!translationDefaultFilterKeys.has(columnKey)) return null
  const fieldKey = translationHeaderFieldMap[columnKey] || columnKey
  return translationFilterFields.find((item) => item.key === fieldKey) || null
}
const tableColumnOverrides = {
  orderNo: { width: PROJECT_LIST_COLUMN_WIDTHS.orderNo, minWidth: PROJECT_LIST_COLUMN_WIDTHS.orderNo, showOverflowTooltip: false, clickHint: '点击订单号查看笔译项目管理' },
  projectName: { minWidth: PROJECT_LIST_COLUMN_WIDTHS.projectName },
  serviceContent: { minWidth: 96 },
  taskType: { minWidth: 110 },
  clientShortName: { minWidth: PROJECT_LIST_COLUMN_WIDTHS.clientShortName },
  clientCode: { minWidth: 100 },
  customerOrderNo: { minWidth: 120 },
  projectManagerName: { minWidth: 90 },
  clientManager: { minWidth: 110 },
  managerContact: { minWidth: 150 },
  projectStatus: { minWidth: PROJECT_LIST_COLUMN_WIDTHS.projectStatus, showOverflowTooltip: false },
  fileTypeSecondary: { minWidth: 110 },
  projectFileTranslationDomainLevel1: { minWidth: 180 },
  projectFileTranslationDomainLevel2: { minWidth: 180 },
  projectFileTypeLevel1: { minWidth: 180 },
  projectFileTypeLevel2: { minWidth: 180 },
  projectFileFormat: { minWidth: 100 },
  projectFileAttributeLevel1: { minWidth: 200 },
  projectFileAttributeLevel2: { minWidth: 200 },
  projectFileAttributeLevel3: { minWidth: 200 },
  projectFileDifficulty: { minWidth: 96 },
  projectContractType: { minWidth: 180 },
  projectContractStatus: { minWidth: 140 },
  quotationRequired: { minWidth: 200 },
  quotationStatus: { minWidth: 140 },
  quotationPath: { minWidth: 240 },
  customerRequirementProfessional: { minWidth: 240 },
  customerRequirementSpecial: { minWidth: 240 },
  languagePair: { width: 110, minWidth: 100, showOverflowTooltip: false },
  priority: { minWidth: 80 },
  wordCountMatrix: { label: '字数统计', width: 110, minWidth: 100, showOverflowTooltip: false, clickHint: '点击查看项目字数统计' },
  customerReceptionTime: { minWidth: 150 },
  customerDeadlineTime: { width: 170, minWidth: 160, showOverflowTooltip: false },
  sentToClientTime: { minWidth: 150 },
  clientFeedback: { minWidth: 240 },
  majorProjectManagerConfirmation: { minWidth: 160 },
  assignedTranslators: { width: 100, minWidth: 96, showOverflowTooltip: false },
  translatorReturnTime: { minWidth: 190 },
  translatorAssignmentTime: { minWidth: 150 },
  translatorDeliveryProgress: { minWidth: 110 },
  preReviewQcProgress: { minWidth: 96 },
  review1Progress: { minWidth: 84 },
  review2Progress: { minWidth: 84 },
  postReviewQcProgress: { minWidth: 96 },
  layoutProgress: { minWidth: 90 },
  consolidationProgress: { minWidth: 90 },
  createdBy: { minWidth: 280 },
  createdAt: { minWidth: 150 },
  updatedAt: { minWidth: 150 },
}
const tableColumns = projectDetailItems.filter((item) => item.key !== 'translatorCompletionRemarks').map((item) => ({
  ...item,
  minWidth: 140,
  showOverflowTooltip: true,
  ...(tableColumnOverrides[item.key] || {}),
}))
const subOrderTableColumns = [
  { key: 'subProjectName', label: '子项目名称' },
  { key: 'languagePair', label: '翻译方向' },
  { key: 'wordCountMatrix', label: '字数统计' },
  { key: 'assignedTranslators', label: '译员安排' },
  { key: 'translatorReturnTime', label: '译员回稿时间' },
  { key: 'status', label: '状态' },
]
const legacySubOrderDefaultColumnKeys = subOrderTableColumns.map((column) => column.key)
const subOrderDefaultColumnKeys = legacySubOrderDefaultColumnKeys.filter((key) => key !== 'assignedTranslators')
const legacyTranslationDefaultColumnKeys = ['orderNo', 'projectName', 'clientShortName', 'projectManagerName', 'assignedTranslators', 'projectStatus', 'languagePair', 'wordCountMatrix', 'customerDeadlineTime']
const legacyTranslationDefaultColumnKeysWithReturnTime = [...legacyTranslationDefaultColumnKeys]
legacyTranslationDefaultColumnKeysWithReturnTime.splice(5, 0, 'translatorReturnTime')
const translationDefaultColumnKeys = legacyTranslationDefaultColumnKeysWithReturnTime.filter((key) => key !== 'assignedTranslators')
const { selectedKeys: visibleColumnKeys, isVisible: isColumnVisible, reset: resetColumns } = useTableColumns(
  'translation-details-v4',
  tableColumns,
  translationDefaultColumnKeys,
  { legacyDefaultKeys: [legacyTranslationDefaultColumnKeys, legacyTranslationDefaultColumnKeysWithReturnTime] }
)
const {
  selectedKeys: visibleSubOrderColumnKeys,
  isVisible: isSubOrderColumnVisible,
  reset: resetSubOrderColumns,
} = useTableColumns(
  'translation-details-sub-orders-v1',
  subOrderTableColumns,
  subOrderDefaultColumnKeys,
  { legacyDefaultKeys: [legacySubOrderDefaultColumnKeys] },
)
const visibleTableColumns = computed(() => tableColumns.filter((column) => isColumnVisible(column.key)))
watch(visibleColumnKeys, (keys) => {
  const activeColumnKey = Object.keys(TIME_SORT_MODES)
    .find((key) => TIME_SORT_MODES[key] === sortMode.value)
  if (activeColumnKey && !keys.includes(activeColumnKey)) {
    sortMode.value = DEFAULT_SORT_MODE
    handleSortChange()
  }
})
const form = reactive(createEmptyProjectForm())
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({
  namespace: 'translation-project',
  form,
  createDefault: createEmptyProjectForm,
  formRef,
  applyDraft: (draft) => {
    assignReactive(form, createEmptyProjectForm, draft)
    form.subjectPrefix = extractSubjectPrefix(form.emailSubjectPreview, form)
    projectNameManuallyEdited.value = Boolean(draft.projectName)
  },
})
const customServiceContentOption = computed(() => customServiceContentOptions.find((option) => (
  form.serviceContent === option
  || form.serviceContent?.startsWith(`${option}：`)
  || form.serviceContent?.startsWith(`${option}:`)
)) || '')
const serviceContentSelection = computed({
  get: () => customServiceContentOption.value || form.serviceContent,
  set: (value) => { form.serviceContent = value || '' },
})
const serviceContentCustomText = computed({
  get: () => {
    const option = customServiceContentOption.value
    if (!option || form.serviceContent === option) return ''
    return form.serviceContent.slice(option.length).replace(/^[：:]\s*/, '')
  },
  set: (value) => {
    const option = customServiceContentOption.value
    if (!option) return
    form.serviceContent = value ? `${option}：${value}` : option
  },
})
const showManagerContactInput = computed(() => !form.clientId && Boolean(form.clientShortName?.trim()))
const subOrderForm = reactive(createEmptySubOrderForm())
const requiredTextValidator = (message) => (_rule, value, callback) => {
  if (!String(value || '').trim()) return callback(new Error(message))
  callback()
}
const validateWordCountMatrix = (_rule, value, callback) => {
  const hasWordCount = Object.values(value || {}).some((dimension) => (
    Object.values(dimension || {}).some((item) => (
      item !== null && item !== undefined && item !== '' && Number.isFinite(Number(item))
    ))
  ))
  if (!hasWordCount) return callback(new Error('请至少填写一项字数或预估数据'))
  callback()
}
const rules = {
  projectName: [{ validator: requiredTextValidator('请输入项目名称'), trigger: ['blur', 'change'] }],
  clientShortName: [{ validator: requiredTextValidator('请选择或输入客户简称'), trigger: ['blur', 'change'] }],
  serviceContent: [{ validator: requiredTextValidator('请选择或输入服务内容'), trigger: ['blur', 'change'] }],
  languagePair: [{ validator: requiredTextValidator('请选择翻译方向'), trigger: 'change' }],
  wordCountMatrix: [{ validator: validateWordCountMatrix, trigger: 'change' }],
  customerReceptionTime: [{ required: true, message: '请选择客户接单时间', trigger: 'change' }],
  customerDeadlineTime: [{ required: true, message: '请选择客户交稿时间', trigger: 'change' }],
  projectStatus: [{ required: true, message: '请选择状态', trigger: 'change' }],
}
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const NULLABLE_FIELDS = ['emailSubjectPreview', 'serviceContent', 'taskType', 'consultationId', 'clientId', 'subClientId', 'projectManagerId', 'customerOrderNo', 'customerReceptionTime', 'customerDeadlineTime', 'sentToClientTime', 'pmConfirmedBy', 'translatorId', 'translatorAssignmentTime', 'clientFeedback', 'referenceFilePathOne', 'fileTypeSecondary', 'projectContractType', 'projectContractStatus', 'quotationStatus', 'quotationPath', 'customerRequirementProfessional', 'customerRequirementSpecial', 'languagePair', 'priority', 'remarks', 'subProjectName']
const legacyStatusMap = {
  pending: 'pending_confirmation',
  in_progress: 'confirmed',
  completed: 'sent_to_client',
  terminated: 'cancelled'
}
const normalizeStatus = (status) => legacyStatusMap[status] || status
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === normalizeStatus(status))?.label || status || '-'
const getStatusType = (status) => ({
  pending_confirmation: 'info',
  confirmed: 'primary',
  organized: 'primary',
  translator_assigned: 'warning',
  sent_to_translator: 'warning',
  translator_returned: 'primary',
  special_checked: 'primary',
  typeset: 'primary',
  special_checked_typeset: 'primary',
  reviewed: 'success',
  sent_to_client: 'success',
  client_feedback: 'success',
  feedback_sent_to_client: 'success',
  cancelled: 'danger',
  partially_cancelled: 'danger',
  paused: 'warning'
}[normalizeStatus(status)] || 'info')

function formatWordCountSummary(target = {}) {
  return formatWordCountMatrix(target.wordCountMatrix)
}
function getWordCountListSummary(target = {}) {
  return getWordCountMatrixListSummary(target.wordCountMatrix, {
    translators: target.assignedTranslators || target.assigned_translators || []
  })
}
const toLocalWordCountMatrix = (saved = {}) => ({
  company: saved.company || {},
  customer: saved.customer || {},
  translatorEstimate: saved.translator_estimate || saved.translatorEstimate || {},
})
const handleProjectWordCountSaved = async (saved) => {
  form.wordCountMatrix = toLocalWordCountMatrix(saved)
  formRef.value?.clearValidate('wordCountMatrix')
  await fetchData()
}
const handleSubOrderWordCountSaved = async (saved) => {
  subOrderForm.wordCountMatrix = toLocalWordCountMatrix(saved)
  if (form.id) await refreshProjectSubOrders(form.id)
  await fetchData()
}
const formatAssignedTranslators = (items, legacyName = '') => {
  if (Array.isArray(items) && items.length) {
    return items
      .map((item) => {
        const name = item.translatorName || item.translator_name || ''
        const scope = item.translationScope || item.translation_scope || ''
        return scope ? `${name}（${scope}）` : name
      })
      .filter(Boolean)
      .join('、')
  }
  return legacyName || '-'
}
const formatTranslatorReturnTimes = (items) => {
  if (!Array.isArray(items) || !items.length) return '-'
  const values = items
    .map((item) => {
      const time = item.translatorReturnTime || item.translator_return_time
      if (!time) return ''
      const name = item.translatorName || item.translator_name || '译员'
      return `${name}：${formatDateTime(time)}`
    })
    .filter(Boolean)
  return values.length ? values.join('；') : '-'
}
const formatTranslatorCompletionRemarks = (items) => {
  if (!Array.isArray(items) || !items.length) return '-'
  const values = items
    .map((item) => {
      const remarks = item.completionRemarks || item.completion_remarks
      if (!remarks) return ''
      const name = item.translatorName || item.translator_name || '译员'
      return `${name}：${remarks}`
    })
    .filter(Boolean)
  return values.length ? values.join('；') : '-'
}
const getTranslatorReturnDeadlineItems = (items) => (
  Array.isArray(items)
    ? items.map((item, index) => ({
        key: item.arrangementId || item.arrangement_id || item.translatorId || item.translator_id || index,
        name: item.translatorName || item.translator_name || '译员',
        time: item.translatorReturnTime || item.translator_return_time || '',
      })).filter((item) => item.time)
    : []
)
const getAssignedTranslatorNames = (items, legacyName = '') => {
  if (Array.isArray(items) && items.length) {
    return items
      .map((item) => item.translatorName || item.translator_name || '')
      .filter(Boolean)
  }
  return legacyName ? [legacyName] : []
}
const getAssignedTranslatorSummary = (row) => {
  const names = getAssignedTranslatorNames(row.assignedTranslators, row.translatorName)
  return {
    primary: names[0] || '-',
    extraCount: Math.max(0, names.length - 1),
  }
}
const pad = (value) => String(value).padStart(2, '0')
const syncProjectName = ({ force = false } = {}) => {
  if (projectNameManuallyEdited.value && !force) return
  form.projectName = buildAutoProjectName(
    form.clientShortName,
    currentProjectSubOrders.value.length,
    new Date(),
    form.languagePair,
    form.customerDeadlineTime
  )
}
const handleProjectNameInput = () => {
  projectNameManuallyEdited.value = true
}
const regenerateProjectName = () => {
  const missing = []
  if (!String(form.clientShortName || '').trim()) missing.push('客户简称')
  if (!String(form.languagePair || '').trim()) missing.push('翻译方向')
  if (!form.customerDeadlineTime) missing.push('客户交稿时间')
  if (missing.length) return ElMessage.warning(`请先填写：${missing.join('、')}`)
  const generatedName = buildAutoProjectName(
    form.clientShortName,
    currentProjectSubOrders.value.length,
    new Date(),
    form.languagePair,
    form.customerDeadlineTime
  )
  projectNameManuallyEdited.value = false
  form.projectName = generatedName
  ElMessage.success('项目名称已重新生成，仍可手工修改')
}
const generateEmailSubject = () => notifyEmailSubjectGenerated(form, ElMessage)
const clampProgress = (value) => Math.max(0, Math.min(100, Number(value) || 0))
const parseProgressValue = (value) => {
  if (value === null || value === undefined || value === '') return 0
  if (typeof value === 'number') return clampProgress(value)
  const matched = String(value).match(/-?\d+/)
  return clampProgress(matched ? Number(matched[0]) : 0)
}
const normalizeProgressValue = (value) => `${clampProgress(value)}%`
const formatProgressDisplay = (value) => `${clampProgress(value)}%`
const tableDateFieldKeys = new Set([
  'customerReceptionTime',
  'customerDeadlineTime',
  'sentToClientTime',
  'translatorAssignmentTime',
  'createdAt',
  'updatedAt',
])
const tableProgressFieldKeys = new Set(progressFieldConfigs.map((item) => item.key))
const formatTableColumnValue = (row, column) => {
  if (column.key === 'wordCountMatrix') return formatWordCountSummary(row)
  if (typeof column.formatter === 'function') return column.formatter(row[column.key], row)
  const value = row[column.key]
  if (tableDateFieldKeys.has(column.key)) return formatDateTime(value)
  if (tableProgressFieldKeys.has(column.key)) return formatProgressDisplay(value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.join('、') : '-'
  return value === null || value === undefined || value === '' ? '-' : value
}
const getProjectRoleAssigneeName = (project, roleCode) => {
  const assignments = Array.isArray(project?.roleAssignments) ? project.roleAssignments : []
  const assignment = assignments.find((item) => (item.roleCode || item.role_code) === roleCode)
  return assignment?.assigneeName || assignment?.assignee_name || '角色池'
}
const normalizeProject = (project) => ({
  ...project,
  projectSpecialistName: getProjectRoleAssigneeName(project, 'project_specialist'),
  projectAssistantName: getProjectRoleAssigneeName(project, 'project_assistant'),
  layoutSpecialistName: getProjectRoleAssigneeName(project, 'layout_specialist'),
  subOrders: Array.isArray(project.subOrders) ? [...project.subOrders].sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
})
const getSubOrderCount = (row) => Array.isArray(row?.subOrders) ? row.subOrders.length : 0
const clearProjectExpansion = () => {
  expandedProjectIds.value = []
  shouldInitializeProjectExpansion.value = true
  expandedInlineChanges.value = new Map()
}
const isProjectExpanded = (row) => expandedProjectIds.value.some((id) => String(id) === String(row.id))
const handleProjectExpandChange = (row, expandedRows) => {
  const isExpanded = expandedRows.some((item) => String(item.id) === String(row.id))
  expandedProjectIds.value = expandedRows
    .filter((item) => getSubOrderCount(item))
    .map((item) => item.id)
  if (!isExpanded) {
    expandedInlineChanges.value = new Map(
      [...expandedInlineChanges.value].filter(([, change]) => (
        String(change.row?.parentProjectId) !== String(row.id)
      ))
    )
  }
}
const toggleProjectExpansion = (row) => {
  if (!getSubOrderCount(row)) return
  projectTableRef.value?.toggleRowExpansion(row, !isProjectExpanded(row))
}
const hasMoreSubOrders = (row) => getSubOrderCount(row) > SUB_ORDER_PREVIEW_LIMIT
const getEarliestTranslatorReturnTime = (row) => {
  const timestamps = getTranslatorReturnDeadlineItems(row?.assignedTranslators)
    .map((item) => parseBusinessDateTime(item.time)?.getTime())
    .filter(Number.isFinite)
  return timestamps.length ? Math.min(...timestamps) : Number.POSITIVE_INFINITY
}
const getSubOrderReturnSortRank = (row) => {
  if (isTranslatorReturnTerminalStatus(row?.status)) return 2
  return Number.isFinite(getEarliestTranslatorReturnTime(row)) ? 0 : 1
}
const compareSubOrdersByTranslatorReturn = (left, right) => {
  const rankDifference = getSubOrderReturnSortRank(left) - getSubOrderReturnSortRank(right)
  if (rankDifference) return rankDifference
  const deadlineDifference = getEarliestTranslatorReturnTime(left) - getEarliestTranslatorReturnTime(right)
  if (Number.isFinite(deadlineDifference) && deadlineDifference) return deadlineDifference
  return String(left?.subOrderNo || '').localeCompare(String(right?.subOrderNo || ''))
}
const getVisibleSubOrders = (row) => (Array.isArray(row?.subOrders)
  ? [...row.subOrders].sort(compareSubOrdersByTranslatorReturn).slice(0, SUB_ORDER_PREVIEW_LIMIT)
  : [])
const applyPagination = () => { clearProjectExpansion(); fetchData() }
const cleanPayload = (payload) => {
  const result = { ...payload }
  result.roleAssignments = projectRoleFieldConfigs.map((role) => ({
    roleCode: role.roleCode,
    assigneeId: result[role.formKey] || null
  }))
  projectRoleFieldConfigs.forEach((role) => delete result[role.formKey])
  NULLABLE_FIELDS.forEach((key) => {
    if (result[key] === '') result[key] = null
  })
  progressFieldSet.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(result, key)) {
      result[key] = normalizeProgressValue(result[key])
    }
  })
  delete result.translatorName
  delete result.assignedTranslators
  delete result.clientManager
  result.managerContact = result.managerContact?.trim() || null
  delete result.subjectPrefix
  delete result.createdAt
  result.expectedUpdatedAt = result.updatedAt || null
  delete result.updatedAt
  delete result.projectManagerName
  result.quotationRequired = Boolean(result.quotationRequired)
  if (!result.quotationRequired) {
    result.quotationStatus = null
    result.quotationPath = null
  }
  return result
}
const assignReactive = (target, defaultsFactory, values = {}) => {
  const defaults = defaultsFactory()
  Object.keys(defaults).forEach((key) => {
    if (progressFieldSet.has(key)) {
      target[key] = parseProgressValue(values[key] ?? defaults[key])
    } else if (key === 'projectStatus' || key === 'status') {
      target[key] = normalizeStatus(values[key] ?? defaults[key])
    } else {
      target[key] = key === 'assignedTranslators' && Array.isArray(values[key])
        ? values[key].map((item) => ({ ...item }))
        : (values[key] ?? defaults[key])
    }
  })
  if (Object.prototype.hasOwnProperty.call(defaults, 'projectSpecialistId')) {
    const assignments = Array.isArray(values.roleAssignments) ? values.roleAssignments : []
    const byCode = Object.fromEntries(assignments.map((item) => [
      item.roleCode || item.role_code,
      item.assigneeId || item.assignee_id || ''
    ]))
    projectRoleFieldConfigs.forEach((role) => {
      target[role.formKey] = byCode[role.roleCode] || ''
    })
  }
}
const buildFilterParams = () => ({
  keyword: searchForm.keyword.trim() || undefined,
  field_filters: serializeFieldFilters(searchForm, translationFilterFields),
})
const resetExportForm = () => {
  exportForm.timeField = DEFAULT_TRANSLATION_EXPORT_TIME_FIELD
  exportForm.dateRange = []
  exportFormRef.value?.clearValidate()
}
const openExportDialog = () => {
  resetExportForm()
  exportDialogVisible.value = true
}
const handleExport = async () => {
  if (!exportFormRef.value || exporting.value) return
  const valid = await exportFormRef.value.validate().catch(() => false)
  if (!valid) return
  exporting.value = true
  try {
    const params = buildTranslationExportParams(buildFilterParams(), exportForm, sortMode.value)
    const blob = await exportTranslationProjects(params)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = buildTranslationExportFilename(exportForm.timeField, exportForm.dateRange)
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    exportDialogVisible.value = false
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '导出笔译项目失败'))
  } finally {
    exporting.value = false
  }
}
let searchTimer = null
let requestController = null
let requestSequence = 0
const fetchData = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const params = {
      ...buildFilterParams(),
      sort: sortMode.value,
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const response = await getProjectPage(params, { signal: requestController.signal })
    if (sequence !== requestSequence) return
    tableData.value = (Array.isArray(response?.items) ? response.items : []).map(normalizeProject)
    const expandableProjectIds = tableData.value
      .filter((item) => getSubOrderCount(item))
      .map((item) => item.id)
    if (shouldInitializeProjectExpansion.value) {
      expandedProjectIds.value = expandableProjectIds
      shouldInitializeProjectExpansion.value = false
    } else {
      const validProjectIds = new Set(expandableProjectIds.map(String))
      expandedProjectIds.value = expandedProjectIds.value.filter((id) => validProjectIds.has(String(id)))
    }
    pagination.total = response?.total || 0
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || sequence !== requestSequence) return
    ElMessage.error(getLocalizedErrorMessage(error, '网络异常，项目列表未刷新，请检查网络后重试'))
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
const hasActiveListFilters = () => Object.values(searchForm).some((value) => (
  Array.isArray(value) ? value.length > 0 : Boolean(String(value || '').trim())
))
const saveProjectTextField = async (row, field, value) => {
  const updated = normalizeProject(await updateProjectTextField(row.id, field, value, row.updatedAt))
  Object.assign(row, updated)
  if (hasActiveListFilters()) void fetchData()
  return updated
}
const projectRowClass = ({ row }) => String(row.id) === highlightedProjectId.value ? 'workbench-target-row' : ''
const focusRouteProject = async (editorReady = Promise.resolve()) => {
  const projectId = String(route.query.projectId || '')
  if (!projectId) return
  try {
    const detail = await getProject(projectId)
    highlightedProjectId.value = projectId
    searchForm.keyword = detail.orderNo || detail.order_no || ''
    pagination.page = 1
    const listPromise = fetchData()
    if (route.query.openEditor === '1') {
      await editorReady
      await handleEdit(detail, true)
      const query = { ...route.query }
      delete query.openEditor
      await router.replace({ query })
    }
    await Promise.all([listPromise, editorReady])
  } catch (error) {
    ElMessage.error(error.detail || '定位笔译项目失败')
  }
}
const refreshProjectSubOrders = async (projectId) => {
  if (!projectId) return
  const response = await getSubOrdersByProject(projectId)
  const normalized = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
  if (String(form.id) === String(projectId)) currentProjectSubOrders.value = normalized
  tableData.value = tableData.value.map((item) => String(item.id) === String(projectId) ? { ...item, subOrders: normalized } : item)
  if (String(form.id) === String(projectId)) syncProjectName()
}

const loadProjectManagerOptions = async () => {
  if (projectManagerOptions.value.length) return
  try {
    projectManagerOptions.value = await getProjectManagerCandidatesAPI({ include_current: true })
  } catch {
    projectManagerOptions.value = []
  }
}

const loadProjectRoleOptions = async () => {
  if (projectRoleOptionsLoaded.value || projectRoleOptionsLoading.value) return
  projectRoleOptionsLoading.value = true
  try {
    const results = await Promise.all(
      projectRoleFieldConfigs.map((role) => getProjectRoleCandidatesAPI(role.roleCode))
    )
    projectRoleFieldConfigs.forEach((role, index) => {
      projectRoleCandidateOptions[role.roleCode] = Array.isArray(results[index]) ? results[index] : []
    })
    projectRoleOptionsLoaded.value = true
  } catch (error) {
    projectRoleOptionsLoaded.value = false
    ElMessage.error(getLocalizedErrorMessage(error, '加载项目角色候选人失败'))
  } finally {
    projectRoleOptionsLoading.value = false
  }
}

const fetchClientSuggestions = fetchProjectClientSuggestions
const handleClientSelect = (client) => {
  form.clientId = client.parent_client_id || client.id || ''
  form.subClientId = client.sub_client_id || ''
  form.clientShortName = client.client_short_name || ''
  form.clientCode = client.client_code || ''
  form.clientManager = client.client_manager || ''
  form.managerContact = client.manager_contact || ''
  projectNameManuallyEdited.value = false
  syncProjectName({ force: true })
}
const handleClientShortNameInput = () => {
  form.clientId = ''
  form.subClientId = ''
  form.clientCode = ''
  form.clientManager = ''
  form.managerContact = ''
  form.projectName = ''
  projectNameManuallyEdited.value = false
}
const clearSelectedClient = () => {
  form.clientId = ''
  form.subClientId = ''
  form.clientShortName = ''
  form.clientCode = ''
  form.clientManager = ''
  form.managerContact = ''
  form.projectName = ''
  projectNameManuallyEdited.value = false
}

const getPreferredProjectPath = async (row) => {
  if (!row?.id) return null
  const files = await getProjectFilesByProject(row.id, { skip: 0, limit: 1 })
  const projectFile = Array.isArray(files) && files.length ? files[0] : {}
  return resolvePreferredProjectPath(projectFile, row)
}
const openOriginalPath = async (row) => {
  try {
    const resolvedPath = await getPreferredProjectPath(row)
    if (!resolvedPath) {
      ElMessage.warning('该订单暂无可用文件路径')
      return
    }
    if (!launchOpenPath(resolvedPath.path)) {
      ElMessage.error('该路径不在企业允许的网络目录中，已阻止打开')
    }
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '获取文件路径失败'))
  }
}
const copyOriginalPath = async (row) => {
  try {
    const resolvedPath = await getPreferredProjectPath(row)
    if (!resolvedPath) {
      ElMessage.warning('该订单暂无可用文件路径')
      return
    }
    const copied = await copyTextToClipboard(resolvedPath.path)
    if (!copied) {
      ElMessage.error('复制失败，请手工复制')
      return
    }
    ElMessage.success(`${resolvedPath.source}已复制`)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '复制失败，请稍后重试'))
  }
}

const handleTextSearch = (value) => {
  clearTimeout(searchTimer)
  if (!value) return handleSearch()
  searchTimer = setTimeout(handleSearch, 400)
}
const handleSearch = () => { exitDeleteMode(); clearProjectExpansion(); clearTimeout(searchTimer); pagination.page = 1; fetchData() }
const handleSortChange = () => { exitDeleteMode(); clearProjectExpansion(); pagination.page = 1; fetchData() }
const getTimeSortMode = getTranslationProjectTimeSortMode
const isTimeSortActive = (columnKey) => isTranslationProjectTimeSortActive(sortMode.value, columnKey)
const getTimeSortTitle = (column) => getTranslationProjectTimeSortTitle(sortMode.value, column.key, column.label)
const toggleTimeSort = (columnKey) => {
  if (!getTimeSortMode(columnKey)) return
  sortMode.value = nextTranslationProjectTimeSortMode(sortMode.value, columnKey)
  handleSortChange()
}
const getSortColumnClass = (columnKey) => {
  if (sortMode.value === 'translator_return_time_asc' && columnKey === 'translatorReturnTime') return 'is-active-sort-column'
  if (sortMode.value === 'customer_deadline_time_asc' && columnKey === 'customerDeadlineTime') return 'is-active-sort-column'
  return ''
}
const updateConfiguredFilter = (key, value) => { searchForm[key] = value }
const handleConfiguredTextInput = (value) => handleTextSearch(value)
const resetSearch = () => { searchForm.keyword = ''; sortMode.value = DEFAULT_SORT_MODE; resetFilterModel(searchForm, translationFilterFields); handleSearch() }
const clearAdvancedFilters = () => { resetFilterModel(searchForm, translationAdvancedFilterFields); handleSearch() }
const clearSearch = () => {
  searchForm.keyword = ''
  resetFilterModel(searchForm, translationFilterFields)
}
let highlightedFieldElement = null
let fieldHighlightTimer = null
const normalizeFieldSearchText = (value) => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')
const getFieldSearchScore = (item, keyword) => {
  const label = normalizeFieldSearchText(item.label)
  const aliases = (item.aliases || []).map(normalizeFieldSearchText)
  if (label === keyword) return 0
  if (aliases.some((value) => value === keyword)) return 1
  if (label.startsWith(keyword)) return 2
  if (aliases.some((value) => value.startsWith(keyword))) return 3
  if (label.includes(keyword)) return 4
  if (aliases.some((value) => value.includes(keyword))) return 5
  return Number.POSITIVE_INFINITY
}
const fetchFieldSuggestions = (queryString, callback) => {
  const keyword = normalizeFieldSearchText(queryString)
  if (!keyword) {
    callback([])
    return
  }
  const matches = projectFieldSearchItems
    .map((item, index) => ({ item, index, score: getFieldSearchScore(item, keyword) }))
    .filter(({ score }) => Number.isFinite(score))
    .sort((left, right) => left.score - right.score || left.index - right.index)
    .map(({ item }) => item)
  callback(matches)
}
const clearFieldSearchHighlight = () => {
  if (fieldHighlightTimer) window.clearTimeout(fieldHighlightTimer)
  fieldHighlightTimer = null
  highlightedFieldElement?.classList.remove('is-field-search-highlight')
  highlightedFieldElement = null
}
const clearFieldSearch = () => {
  fieldSearchKeyword.value = ''
  clearFieldSearchHighlight()
}
const waitForFieldLayout = (delay = 0) => new Promise((resolve) => {
  window.setTimeout(() => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve))
  }, delay)
})
const focusLocatedField = (target) => {
  const focusTarget = target.querySelector([
    'input:not([disabled])',
    'textarea:not([disabled])',
    'button:not([disabled])',
    '[role="slider"]',
    '[tabindex]:not([tabindex="-1"])',
  ].join(', '))
  if (!focusTarget || typeof focusTarget.focus !== 'function') return
  try {
    focusTarget.focus({ preventScroll: true })
  } catch {
    focusTarget.focus()
  }
}
const locateProjectField = async (selectedItem) => {
  if (!selectedItem?.key) return
  const requiresUnavailableField = selectedItem.requires && !form[selectedItem.requires]
  const targetItem = requiresUnavailableField
    ? projectFieldSearchItems.find((item) => item.key === selectedItem.requires)
    : selectedItem
  if (!targetItem) return

  fieldSearchRef.value?.blur?.()
  projectDialogTab.value = targetItem.tab
  const shouldExpandSection = targetItem.section && !projectBasicExpandedSections.value.includes(targetItem.section)
  if (shouldExpandSection) {
    projectBasicExpandedSections.value = [...projectBasicExpandedSections.value, targetItem.section]
  }

  await nextTick()
  await waitForFieldLayout(shouldExpandSection ? 320 : 0)
  const target = editorBodyRef.value?.querySelector(`[data-field-key="${targetItem.key}"]`)
  if (!target) {
    ElMessage.warning(`暂时无法定位“${selectedItem.label}”`)
    return
  }

  clearFieldSearchHighlight()
  const editorBody = editorBodyRef.value
  const bodyRect = editorBody.getBoundingClientRect()
  const targetRect = target.getBoundingClientRect()
  const targetScrollTop = editorBody.scrollTop + targetRect.top - bodyRect.top
    - Math.max(0, (editorBody.clientHeight - targetRect.height) / 2)
  editorBody.scrollTo({ top: Math.max(0, targetScrollTop), behavior: 'smooth' })
  target.classList.add('is-field-search-highlight')
  highlightedFieldElement = target
  focusLocatedField(target)
  fieldHighlightTimer = window.setTimeout(clearFieldSearchHighlight, 1500)

  if (requiresUnavailableField) {
    ElMessage.info(`请先启用“${targetItem.label}”，再编辑“${selectedItem.label}”`)
  }
}
const resetProjectForm = () => {
  assignReactive(form, createEmptyProjectForm)
  projectNameManuallyEdited.value = false
  projectDialogTab.value = 'basic'
  projectBasicExpandedSections.value = ['project', 'business', 'execution']
  editorBodyRef.value?.scrollTo({ top: 0 })
  clearFieldSearch()
}
const resetSubOrderForm = () => { assignReactive(subOrderForm, createEmptySubOrderForm); subOrderFormRef.value?.clearValidate(); subOrderDialogTab.value = 'basic' }
const generateOrderNo = async () => { try { return await getNextOrderNo() } catch { const now = new Date(); return `TP-${String(now.getFullYear()).slice(-2)}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${String(Math.floor(Math.random() * 999) + 1).padStart(3, '0')}` } }
const goToSubOrderManagement = (project) => {
  const projectId = project.id || form.id
  if (!projectId) return
  router.push({ name: 'TranslationSubOrderManagement', params: { projectId }, query: { orderNo: project.orderNo || form.orderNo || '', projectName: project.projectName || form.projectName || '' } })
}
const handleAdd = async () => {
  dialogTitle.value = '新增项目'
  resetProjectForm()
  projectCreateIdempotencyKey.value = createIdempotencyKey()
  currentProjectSubOrders.value = []
  await Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
  form.orderNo = await generateOrderNo()
  dialogVisible.value = true
  await nextTick()
  editorBodyRef.value?.scrollTo({ top: 0, behavior: 'auto' })
  projectFilesTabRef.value?.resetPathGroup()
  await beginDraft('create')
}
const handleEdit = async (row, editorOptionsReady = false) => {
  dialogTitle.value = '编辑项目详情'
  clearFieldSearch()
  if (!editorOptionsReady) await Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
  assignReactive(form, createEmptyProjectForm, row)
  if (!String(form.taskType || '').trim()) form.taskType = '笔译项目'
  form.subjectPrefix = extractSubjectPrefix(form.emailSubjectPreview, form)
  currentProjectSubOrders.value = Array.isArray(row.subOrders) ? [...row.subOrders] : []
  projectNameManuallyEdited.value = Boolean(form.projectName) && !isAutoProjectName(form.projectName, form.clientShortName)
  syncProjectName()
  projectDialogTab.value = 'basic'
  projectBasicExpandedSections.value = ['project', 'business', 'execution']
  dialogVisible.value = true
  await nextTick()
  editorBodyRef.value?.scrollTo({ top: 0, behavior: 'auto' })
  if (row.id) {
    try {
      await refreshProjectSubOrders(row.id)
    } catch (error) {
      ElMessage.error(getLocalizedErrorMessage(error, '加载子订单失败'))
    }
  }
  await beginDraft(`edit:${row.id}`)
}
const handleProjectFileStatusChange = (status) => {
  if (!status) return
  form.projectStatus = normalizeStatus(status)
  const row = tableData.value.find((item) => item.id === form.id)
  if (row) row.projectStatus = form.projectStatus
}
const setProjectStatusSaving = (id, saving) => {
  const next = new Set(projectStatusSavingIds.value)
  if (saving) next.add(id)
  else next.delete(id)
  projectStatusSavingIds.value = next
}
const changeProjectStatus = async (row, value) => {
  const previousStatus = normalizeStatus(row.projectStatus)
  const nextStatus = normalizeStatus(value)
  if (!nextStatus || nextStatus === previousStatus) return

  setProjectStatusSaving(row.id, true)
  try {
    const updated = normalizeProject(await updateProject(row.id, { projectStatus: nextStatus }))
    Object.assign(row, updated)
    ElMessage.success('项目状态已更新')
    if (searchForm.projectStatus?.length && !searchForm.projectStatus.includes(updated.projectStatus)) {
      await fetchData()
    }
  } catch (error) {
    ElMessage.error(error?.detail || '项目状态更新失败')
  } finally {
    setProjectStatusSaving(row.id, false)
  }
}
const handleSubmit = async (sendAfterSave = false) => {
  if (!formRef.value || submitLocked) return
  submitLocked = true
  syncProjectName()
  const valid = await formRef.value.validate().catch((invalidFields) => {
    if (invalidFields?.projectStatus) {
      projectDialogTab.value = 'basic'
      if (!projectBasicExpandedSections.value.includes('project')) {
        projectBasicExpandedSections.value = [...projectBasicExpandedSections.value, 'project']
      }
    }
    return false
  })
  if (!valid) {
    await nextTick()
    editorBodyRef.value?.querySelector('.is-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    submitLocked = false
    return
  }

  const pathGroupValid = await projectFilesTabRef.value?.validatePathGroup()
  if (pathGroupValid === false) {
    projectDialogTab.value = 'files'
    submitLocked = false
    return
  }

  submitLoading.value = true
  let projectSaved = false
  try {
    const payload = cleanPayload({ ...form })
    const isCreate = dialogTitle.value === '新增项目'
    let savedProject
    if (isCreate) {
      savedProject = await createProject(payload, projectCreateIdempotencyKey.value)
      // 新项目按创建时间倒序展示；回到第一页并清除可能隐藏新项目的旧筛选条件。
      pagination.page = 1
      clearSearch()
    } else {
      savedProject = await updateProject(payload.id, payload)
    }
    projectSaved = true

    const savedPathGroup = await projectFilesTabRef.value?.savePathGroup({
      projectId: savedProject?.id || payload.id,
      orderNo: savedProject?.orderNo || form.orderNo,
      silent: true,
    })

    ElMessage.success(
      savedPathGroup
        ? (isCreate ? '项目及路径组创建成功' : '项目及路径组更新成功')
        : (isCreate ? '项目创建成功' : '项目更新成功')
    )
    clearDraft()
    dialogVisible.value = false
    if (sendAfterSave) {
      mailProjectId.value = savedProject?.id || payload.id
      mailConsultationId.value = savedProject?.consultationId || payload.consultationId || ''
      mailComposerVisible.value = true
    }

    try {
      await fetchData()
    } catch {
      // fetchData 内部已处理错误；保存结果不应被误报为失败。
    }
  } catch (error) {
    ElMessage.error(
      projectSaved
        ? `项目已保存，但路径组保存失败：${getLocalizedErrorMessage(error, '请重新进入项目补充保存')}`
        : getLocalizedErrorMessage(error, '保存失败')
    )
  } finally {
    submitLoading.value = false
    submitLocked = false
  }
}
const onProjectDialogClosed = () => { pauseDraft(); resetProjectForm(); resetSubOrderForm(); editorInlineChanges.value = new Map(); currentProjectSubOrders.value = [] }
const createSubOrderDefaultsFromProject = () => ({ fileTypeSecondary: form.fileTypeSecondary, languagePair: form.languagePair, priority: form.priority, wordCountMatrix: JSON.parse(JSON.stringify(form.wordCountMatrix)), customerDeadlineTime: form.customerDeadlineTime, sentToClientTime: form.sentToClientTime, translatorId: form.translatorId, translatorAssignmentTime: form.translatorAssignmentTime, status: form.projectStatus || 'pending_confirmation', translatorDeliveryProgress: form.translatorDeliveryProgress, preReviewQcProgress: form.preReviewQcProgress, review1Progress: form.review1Progress, review2Progress: form.review2Progress, postReviewQcProgress: form.postReviewQcProgress, layoutProgress: form.layoutProgress, consolidationProgress: form.consolidationProgress, clientFeedback: form.clientFeedback })
const openCreateSubOrderDialog = () => { resetSubOrderForm(); subOrderDialogTitle.value = '新增子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...createSubOrderDefaultsFromProject(), parentProjectId: form.id }); subOrderDialogVisible.value = true }
const handleEditSubOrder = (row) => { resetSubOrderForm(); subOrderDialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...row, parentProjectId: row.parentProjectId || form.id }); subOrderDialogVisible.value = true }
const openSubOrderEditorFromList = (projectRow, subOrderRow) => {
  // 子订单弹窗仍需母订单上下文，但不应因此打开母订单编辑弹窗。
  assignReactive(form, createEmptyProjectForm, projectRow)
  handleEditSubOrder(subOrderRow)
}
const saveProjectTranslatorCompletions = async (row, completions) => {
  const updated = normalizeProject(await updateProject(row.id, {
    assignedTranslatorCompletions: completions,
    expectedUpdatedAt: row.updatedAt || null,
  }))
  Object.assign(row, updated)
  if (String(form.id) === String(row.id)) assignReactive(form, createEmptyProjectForm, updated)
  return updated
}
const saveSubOrderTranslatorCompletions = async (row, completions) => {
  const updated = await updateSubOrder(row.id, { assignedTranslatorCompletions: completions })
  handleInlineSubOrderSaved(row, updated)
  if (String(subOrderForm.id) === String(row.id)) assignReactive(subOrderForm, createEmptySubOrderForm, updated)
  return updated
}
const buildSubOrderPayload = (source) => {
  return cleanPayload({ parentProjectId: form.id, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCountMatrix: source.wordCountMatrix, customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', assignedTranslators: source.assignedTranslators || [], translatorAssignmentTime: source.translatorAssignmentTime || '', status: source.status || 'pending', translatorDeliveryProgress: source.translatorDeliveryProgress ?? 0, preReviewQcProgress: source.preReviewQcProgress ?? 0, reviewProgress: source.reviewProgress ?? 0, review1Progress: source.review1Progress ?? 0, review2Progress: source.review2Progress ?? 0, postReviewQcProgress: source.postReviewQcProgress ?? 0, layoutProgress: source.layoutProgress ?? 0, consolidationProgress: source.consolidationProgress ?? 0, networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
}
const handleSubmitSubOrder = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildSubOrderPayload(subOrderForm); if (subOrderDialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } subOrderDialogVisible.value = false; await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '子订单保存失败')) } }
const handleDeleteSubOrder = async (row) => { try { await ElMessageBox.confirm(`确认删除子订单 ${row.subOrderNo} 吗？`, '提示', { type: 'warning' }); await deleteSubOrder(row.id); ElMessage.success('子订单删除成功'); if (form.id && row.parentProjectId === form.id) await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(getLocalizedErrorMessage(error, '子订单删除失败')) } }
const openBatchDialog = (project, mode = 'quantity') => {
  const target = project?.id ? project : form
  if (!target?.id) return
  batchTargetProject.value = { ...target }
  batchTargetSubOrders.value = String(target.id) === String(form.id) && currentProjectSubOrders.value.length
    ? [...currentProjectSubOrders.value]
    : [...(target.subOrders || [])]
  batchDialogMode.value = mode
  batchDialogVisible.value = true
}
const handleBatchCreated = async () => {
  const projectId = batchTargetProject.value?.id
  if (!projectId) return
  await refreshProjectSubOrders(projectId)
}
const getInlineChangeRefs = (scope) => scope === 'editor'
  ? { changes: editorInlineChanges, saving: editorInlineSaving }
  : { changes: expandedInlineChanges, saving: expandedInlineSaving }
const handleInlinePendingChange = (scope, row, change) => {
  const { changes } = getInlineChangeRefs(scope)
  const next = new Map(changes.value)
  if (change.pending) next.set(String(change.id), { row, name: change.name, valid: change.valid })
  else next.delete(String(change.id))
  changes.value = next
}
const handleInlineSubOrderSaved = (row, updated, scope) => {
  if (scope) {
    const { changes } = getInlineChangeRefs(scope)
    const next = new Map(changes.value)
    next.delete(String(updated.id))
    changes.value = next
  }
  Object.assign(row, updated)
  currentProjectSubOrders.value = currentProjectSubOrders.value.map((item) => String(item.id) === String(updated.id) ? { ...item, ...updated } : item)
  tableData.value = tableData.value.map((project) => ({
    ...project,
    subOrders: Array.isArray(project.subOrders)
      ? project.subOrders.map((item) => String(item.id) === String(updated.id) ? { ...item, ...updated } : item)
      : project.subOrders,
  }))
}
const saveAllInlineNames = async (scope, projectId = null) => {
  const { changes, saving } = getInlineChangeRefs(scope)
  const pending = [...changes.value.values()].filter((change) => (
    scope !== 'expanded' || String(change.row?.parentProjectId) === String(projectId)
  ))
  if (!pending.length || saving.value) return
  if (pending.some((item) => !item.valid)) {
    ElMessage.warning('请先补全所有子项目名称，再保存全部')
    return
  }
  saving.value = true
  try {
    const results = await Promise.allSettled(
      pending.map(async (item) => ({ item, updated: await updateSubOrder(item.row.id, { subProjectName: item.name }) }))
    )
    const remaining = new Map(changes.value)
    let successCount = 0
    results.forEach((result) => {
      if (result.status !== 'fulfilled') return
      successCount += 1
      remaining.delete(String(result.value.updated.id))
      handleInlineSubOrderSaved(result.value.item.row, result.value.updated)
    })
    changes.value = remaining
    const failedCount = results.length - successCount
    if (failedCount) ElMessage.warning(`已保存 ${successCount} 条，${failedCount} 条保存失败，请重试`)
    else ElMessage.success(`已保存 ${successCount} 条子项目名称`)
  } finally {
    saving.value = false
  }
}
onMounted(async () => {
  if (route.query.projectId) {
    const editorReady = route.query.openEditor === '1'
      ? Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
      : Promise.resolve()
    await Promise.all([focusRouteProject(editorReady), loadResourceRequestStatuses()])
    return
  }
  await Promise.all([fetchData(), loadProjectManagerOptions(), loadResourceRequestStatuses()])
})
watch(
  () => [route.query.projectId, route.query.openEditor],
  ([projectId, openEditor], [previousProjectId, previousOpenEditor]) => {
    if (projectId && (projectId !== previousProjectId || (openEditor === '1' && previousOpenEditor !== '1'))) {
      const editorReady = openEditor === '1'
        ? Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
        : Promise.resolve()
      void focusRouteProject(editorReady)
    }
  }
)
watch(
  () => [form.languagePair, form.customerDeadlineTime],
  () => syncProjectName()
)
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  clearFieldSearchHighlight()
  requestController?.abort()
})
</script>

<style scoped>
:deep(.workbench-target-row > td.el-table__cell) { background: var(--el-color-primary-light-9) !important; }
.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 6px 10px;
  margin-bottom: 8px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}
.search-form :deep(.el-form-item) { margin: 0; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.advanced-filter-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced-filter-footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); }
:global(.advanced-filter-popover) { max-width: calc(100vw - 32px) !important; }
.card-header,
.section-header,
.sub-order-panel__header { display: flex; align-items: center; justify-content: space-between; }
.sub-order-panel__meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sub-order-panel__actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sub-order-name-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.sub-order-name-header :deep(.el-button) { flex: none; padding: 0 2px; font-weight: 400; }
.order-no-actions { display: flex; align-items: center; gap: 6px; }
.order-no-actions :deep(.el-popover__reference-wrapper) { flex: 1; min-width: 0; }
.order-no-link,
.sub-order-no-link { display: block; width: 100%; height: auto; min-width: 0; padding: 0; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.status-switch-tag.el-tag { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; max-width: 100%; cursor: pointer; user-select: none; vertical-align: middle; transition: opacity 0.15s ease; }
.status-switch-tag :deep(.el-tag__content) { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; white-space: nowrap; line-height: 1; }
.status-switch-text { line-height: 1; }
.status-switch-caret { width: 10px; height: 10px; flex-shrink: 0; margin: 0; font-size: 10px; }
.status-switch-tag:hover { opacity: 0.85; }
.status-switch-tag.is-updating { pointer-events: none; opacity: 0.55; }
.status-option-row { display: inline-flex; align-items: center; gap: 8px; width: 100%; }
.status-current-icon { color: var(--el-color-primary); }
.compact-cell-value { display: flex; align-items: center; min-width: 0; gap: 5px; white-space: nowrap; }
.compact-cell-value__primary { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.compact-cell-value__count { flex-shrink: 0; padding: 0 5px; border-radius: 8px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 12px; line-height: 18px; }
.client-suggestion { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.client-suggestion__meta { color: var(--el-text-color-secondary); font-size: 12px; }
.client-autocomplete-field { width: 100%; }
.client-autocomplete-hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.auto-name-field { width: 100%; }
.auto-name-field__hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.subject-preview-field { width: 100%; min-width: 0; }
.subject-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.subject-preview-toolbar .el-button { flex: none; }
.soft-action-button { --el-button-bg-color: var(--el-color-primary-light-9); --el-button-border-color: var(--el-color-primary-light-7); --el-button-text-color: var(--el-color-primary-dark-2); --el-button-hover-bg-color: var(--el-color-primary-light-8); --el-button-hover-border-color: var(--el-color-primary-light-5); --el-button-hover-text-color: var(--el-color-primary); flex: none; font-weight: 500; }
.word-count-summary { width: 100%; min-height: 32px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 10px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-fill-color-lighter); color: var(--el-text-color-regular); }
.word-count-list-cell { display: flex; align-items: center; min-width: 0; }
.word-count-compact-link { max-width: 100%; height: auto; padding: 0; }
.word-count-compact-link :deep(.compact-cell-value) { max-width: 100%; }
.word-count-compact-link :deep(.compact-cell-value__primary) { color: inherit; }
:global(.project-editor-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.suborder-editor-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.suborder-editor-dialog .el-dialog__header),
:global(.suborder-editor-dialog .el-dialog__footer) { flex: 0 0 auto; }
:global(.suborder-editor-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.suborder-editor-dialog .el-dialog__footer) { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -3px 10px rgb(0 0 0 / 4%); }
:global(.project-editor-dialog .el-dialog__header),
:global(.project-editor-dialog .el-dialog__footer) { flex: 0 0 auto; }
:global(.project-editor-dialog .el-dialog__body) { display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; }
:global(.is-field-search-highlight) {
  outline: 2px solid var(--el-color-warning);
  outline-offset: 3px;
  border-radius: 6px;
  background: var(--el-color-warning-light-8);
  box-shadow: 0 0 0 6px rgb(230 162 60 / 18%);
  animation: project-field-search-pulse 0.75s ease-in-out 2;
  transition: background-color 0.2s ease, outline-color 0.2s ease, box-shadow 0.2s ease;
}
@keyframes project-field-search-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgb(230 162 60 / 16%); }
  50% { box-shadow: 0 0 0 9px rgb(230 162 60 / 30%); }
}
@media (prefers-reduced-motion: reduce) {
  :global(.is-field-search-highlight) { animation: none; }
}
.editor-body { flex: 1; min-height: 0; overflow-y: auto; padding: 4px 4px 0 0; scroll-behavior: smooth; }
.project-editor-tabs > :deep(.el-tabs__header) {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--el-bg-color);
  box-shadow: 0 6px 10px -10px rgb(0 0 0 / 35%);
}
.editor-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.form-section { padding: 4px 2px 12px; }
.service-content-field { display: flex; width: 100%; gap: 12px; }
.service-content-field > .el-select { flex: 0 0 min(360px, 45%); }
.service-content-field > .el-input { flex: 1; min-width: 0; }
.project-key-fields { margin-bottom: 16px; padding: 18px 16px 4px; border: 1px solid var(--el-color-primary-light-7); border-radius: 10px; background: var(--el-color-primary-light-9); }
.project-key-fields__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.project-key-fields__header h3 { margin: 0; color: var(--el-text-color-primary); font-size: 16px; line-height: 1.5; }
.project-key-fields__header p { margin: 3px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.project-basic-collapse__title { display: flex; align-items: center; min-width: 0; gap: 12px; color: var(--el-text-color-primary); font-weight: 600; }
.project-basic-collapse__hint { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.project-basic-collapse__body { padding: 16px 12px 0; }
.project-basic-collapse :deep(.el-collapse-item__header) { height: 48px; padding: 0 12px; background: var(--el-fill-color-lighter); }
.project-basic-collapse :deep(.el-collapse-item__content) { padding-bottom: 8px; }
.progress-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.progress-card { padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: var(--radius-lg); background: var(--color-surface); }
.progress-card__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-size: 14px; }
.section-title { margin: 12px 0; font-size: 15px; font-weight: 600; }
.section-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.sub-order-panel {
  padding: 12px 24px 20px;
  border-top: 1px solid #dce5e2;
  border-bottom: 1px solid #dce5e2;
  background: #f6f8f7;
}
.sub-order-panel__header { margin-bottom: 12px; }
.sub-order-table { --el-table-border-color: #dce5e2; --el-table-row-hover-bg-color: #edf3f1; }
.sub-order-table :deep(.el-table__header-wrapper th.el-table__cell) { background: #eef3f1; }
.sub-order-table :deep(.el-table__body tr > td.el-table__cell) { background: #f8faf9; }
.sub-order-table :deep(.el-table__body tr:nth-child(even) > td.el-table__cell) { background: #f5f8f7; }
.sub-order-table :deep(.el-table__body tr:hover > td.el-table__cell) { background: #edf3f1 !important; }
.sub-order-alert { margin-bottom: 12px; }
.el-alert { margin-top: 16px; }
.project-table :deep(.project-expand-column) { padding: 0 !important; border-right: 0 !important; }
.project-table :deep(.project-expand-column .cell) { display: none; padding: 0; }
.project-table :deep(th.is-active-sort-column) {
  background: var(--el-color-primary-light-9) !important;
  color: var(--el-color-primary);
}
.project-table :deep(td.is-active-sort-column) { background: rgb(64 158 255 / 4%); }
.project-column-header { display: inline-flex; align-items: center; max-width: 100%; gap: 4px; }
.time-column-sort-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font-size: 13px;
}
.time-column-sort-trigger:hover { background: var(--el-fill-color); color: var(--el-color-primary); }
.time-column-sort-trigger.is-active {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 0 0 2px #bfdbfe;
}
.time-column-sort-trigger.is-active:hover { background: #1d4ed8; color: #fff; }
.index-cell { display: inline-flex; flex-direction: column; align-items: center; justify-content: center; min-height: 40px; line-height: 20px; }

@media (max-width: 768px) {
  .service-content-field { flex-direction: column; }
  .service-content-field > .el-select { flex-basis: auto; width: 100%; }

  .search-form :deep(.el-form-item),
  .search-form :deep(.el-form-item__content),
  .search-form :deep(.el-input),
  .search-form :deep(.el-select) {
    width: 100%;
  }

  .search-form :deep(.el-form-item:last-child) {
    margin-left: 0;
  }
}

</style>
