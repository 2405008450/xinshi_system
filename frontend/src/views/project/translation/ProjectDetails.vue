<template>
  <el-card class="compact-list-card">
    <template #header>
      <div class="card-header">
        <span>项目详情</span>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
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

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="项目名称">
        <el-input v-model="searchForm.projectName" placeholder="请输入项目名称" clearable @input="handleTextSearch" @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="客户简称">
        <el-input v-model="searchForm.clientShortName" placeholder="请输入客户简称" clearable @input="handleTextSearch" @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.projectStatus" placeholder="请选择状态" clearable style="width: 160px" @change="handleSearch">
          <el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="advanced-filter-popover">
          <template #reference><el-button>高级筛选{{ advancedFilterCount ? `（${advancedFilterCount}）` : '' }}</el-button></template>
          <div class="advanced-filter-content">
            <el-form :model="searchForm" label-width="90px">
              <el-row :gutter="16">
                <el-col :span="12"><el-form-item label="订单号"><el-input v-model="searchForm.orderNo" clearable @input="handleTextSearch" @keyup.enter="handleSearch" /></el-form-item></el-col>
              </el-row>
            </el-form>
            <div class="advanced-filter-footer"><el-button link @click="clearAdvancedFilters">清空高级条件</el-button><el-button type="primary" @click="advancedVisible = false">关闭</el-button></div>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

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
              <el-button v-if="hasMoreSubOrders(row)" type="primary" link @click="goToSubOrderManagement(row)">进入子订单管理页</el-button>
            </div>
            <el-table :data="getVisibleSubOrders(row)" border>
              <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
              <el-table-column prop="subProjectName" label="子项目名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="languagePair" label="翻译方向" min-width="120" />
              <el-table-column label="字数统计" width="132" min-width="120">
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
              <el-table-column label="译员安排" min-width="180" show-overflow-tooltip>
                <template #default="{ row: subRow }">{{ formatAssignedTranslators(subRow.assignedTranslators, subRow.translatorName) }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" min-width="120">
                <template #default="{ row: subRow }">
                  <el-tag :type="getStatusType(subRow.status)">{{ getStatusLabel(subRow.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="详情" width="100" fixed="right">
                <template #default="{ row: subRow }">
                  <BusinessDetailPopover :row="subRow" title="子订单详情" :items="subOrderDetailItems" :status-label="getStatusLabel" :status-type="getStatusType" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="88" fixed="right" align="center">
                <template #default="{ row: subRow }">
                  <TableActionButton v-if="canWriteProjects" action="edit" @click="openProjectEditorForSubOrder(row, subRow)" />
                  <TableActionButton v-if="canWriteProjects" action="delete" @click="handleDeleteSubOrder(subRow)" />
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
        :show-overflow-tooltip="column.showOverflowTooltip !== false"
      >
        <template #header>
          <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
          <span v-else>{{ column.label }}</span>
        </template>
        <template #default="{ row }">
          <div v-if="column.key === 'orderNo'" class="order-no-actions">
            <BusinessDetailPopover :row="row" title="项目详情" :items="projectDetailItems" :status-label="getStatusLabel" :status-type="getStatusType">
              <template #reference>
                <el-button type="primary" link class="order-no-link business-clickable-cell" :title="`${row.orderNo}（点击查看详情）`" @click.stop>
                  {{ row.orderNo }}
                </el-button>
              </template>
            </BusinessDetailPopover>
            <PathActionButtons v-if="canReadProjectFiles" @open="openOriginalPath(row)" @copy="copyOriginalPath(row)" />
          </div>
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
          <div
            v-else-if="column.key === 'customerDeadlineTime'"
            class="deadline-cell"
            :title="formatDateTime(row.customerDeadlineTime)"
          >
            <span class="deadline-cell__time">{{ formatDateTime(row.customerDeadlineTime) }}</span>
            <el-tag
              v-if="getDeadlineDisplay(row).label"
              :type="getDeadlineDisplay(row).type"
              size="small"
              effect="light"
              class="deadline-cell__tag"
            >
              {{ getDeadlineDisplay(row).label }}
            </el-tag>
          </div>
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
      <el-table-column v-if="!deleteMode" label="操作" width="170" fixed="right" align="center">
        <template #default="{ row }">
          <div v-if="canWriteProjects" class="action-buttons">
            <el-button link type="primary" @click="startResourceRequest(row)">发起需求</el-button>
            <TableActionButton action="edit" @click="handleEdit(row)" />
          </div>
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
      v-model="dialogVisible"
      class="project-editor-dialog"
      width="min(1160px, calc(100vw - 32px))"
      top="4vh"
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
        <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
          <el-tabs v-model="projectDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
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
                  <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态" prop="projectStatus" data-field-key="projectStatus"><el-select v-model="form.projectStatus" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" :disabled="item.value === 'pending_confirmation'" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="项目名称" data-field-key="projectName">
                      <div class="auto-name-field">
                        <GeneratedProjectNameInput
                          v-model="form.projectName"
                          placeholder="可手工填写，或根据客户简称和日期自动生成"
                          @manual-input="handleProjectNameInput"
                          @regenerate="regenerateProjectName"
                        />
                        <div class="auto-name-field__hint">按“客户简称-当前日期”自动生成，存在子订单时追加批次；也可手动修改。</div>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="标题前缀">
                      <el-input v-model="form.subjectPrefix" maxlength="50" show-word-limit clearable placeholder="可选，例如：紧急、请优先处理" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24">
                    <el-form-item label="邮件主题预览" data-field-key="emailSubjectPreview">
                      <div class="subject-preview-field">
                        <el-input v-model="form.emailSubjectPreview" type="textarea" :rows="2" />
                        <div class="subject-preview-toolbar">
                          <span>按“标题前缀、订单号、客户简称、负责人联系方式、客户单号/标识、项目名称”顺序生成</span>
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
                  <el-col :xs="24" :md="12"><el-form-item label="来源咨询 ID"><el-input v-model="form.consultationId" readonly placeholder="手工新增项目无来源咨询" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="客户简称" data-field-key="clientShortName">
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
                  <el-col :xs="24" :md="12"><el-form-item label="客户编号" data-field-key="clientCode"><el-input v-model="form.clientCode" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户单号" data-field-key="customerOrderNo"><el-input v-model="form.customerOrderNo" placeholder="客户公司内部用于记录该外包项目的单号" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户负责人"><el-input v-model="form.clientManager" readonly placeholder="选择客户后从客户表自动带出" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="负责人联系方式"><el-input v-model="form.managerContact" readonly placeholder="选择客户后从客户表自动带出" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="服务内容" data-field-key="serviceContent">
                      <el-select
                        v-model="form.serviceContent"
                        filterable
                        allow-create
                        default-first-option
                        clearable
                        placeholder="可选择翻译、排版，或直接输入自定义内容"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="item in serviceContentOptions"
                          :key="item"
                          :label="item"
                          :value="item"
                        />
                      </el-select>
                    </el-form-item>
                  </el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型" data-field-key="fileTypeSecondary"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向" data-field-key="languagePair"><LanguagePairSelect v-model="form.languagePair" /></el-form-item></el-col>
                      </el-row>
                      <el-row :gutter="16">
                        <el-col :xs="24">
                          <el-form-item label="字数与预估" data-field-key="wordCountSummary">
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
                      <el-input :model-value="formatAssignedTranslators(form.assignedTranslators, form.translatorName)" readonly placeholder="由“稿件安排”模块统一维护" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户接单时间" data-field-key="customerReceptionTime"><el-date-picker v-model="form.customerReceptionTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间" data-field-key="customerDeadlineTime"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间" data-field-key="sentToClientTime"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="PM确认人" data-field-key="pmConfirmedBy"><el-select v-model="form.pmConfirmedBy" filterable clearable placeholder="请选择PM确认人" style="width: 100%"><el-option v-for="manager in projectManagerOptions" :key="manager.id" :label="manager.full_name || manager.username" :value="manager.id" /></el-select></el-form-item></el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="大项目经理确认"><el-input v-model="form.majorProjectManagerConfirmation" readonly placeholder="由“稿件安排”的确认安排操作自动记录" /></el-form-item></el-col>
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
                    <el-button v-if="canWriteProjects" @click="openBatchDialog">批量新增子订单</el-button>
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

                <el-table :data="getVisibleSubOrders({ subOrders: currentProjectSubOrders })" border>
                  <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
                  <el-table-column prop="subProjectName" label="子项目名称" min-width="180" show-overflow-tooltip />
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
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="canWriteProjects" :loading="submitLoading" @click="handleSubmit(true)">保存并发送邮件</el-button>
        <el-button v-if="canWriteProjects" type="primary" :loading="submitLoading" @click="handleSubmit(false)">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="subOrderDialogVisible" :title="subOrderDialogTitle" width="1040px" top="6vh" @closed="resetSubOrderForm">
      <div class="editor-body">
        <el-form ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="120px">
          <el-tabs v-model="subOrderDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="母订单号"><el-input :model-value="form.orderNo" disabled /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="子订单号"><el-input v-model="subOrderForm.subOrderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
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
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
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
                  <el-col :xs="24"><el-form-item label="已分配译员"><el-input :model-value="formatAssignedTranslators(subOrderForm.assignedTranslators, subOrderForm.translatorName)" readonly placeholder="请在“稿件安排”模块中分配译员" /></el-form-item></el-col>
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
        </el-form>
      </div>
      <template #footer>
        <el-button @click="subOrderDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitSubOrder">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="批量新增子订单" width="860px" @closed="resetBatchForm">
      <el-form ref="batchFormRef" :model="batchForm" :rules="batchRules" label-width="140px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="生成数量" prop="count"><el-input-number v-model="batchForm.count" :min="1" :max="50" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="起始序号"><el-input-number v-model="batchForm.startIndex" :min="1" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="子项目名前缀"><el-input v-model="batchForm.subProjectNamePrefix" placeholder="留空则按 母项目名称-子订单01 自动生成" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">批量公共字段</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="batchForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="优先级"><el-select v-model="batchForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文本类型"><el-input v-model="batchForm.fileTypeSecondary" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="batchForm.languagePair" :show-hint="false" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="字数摘要">
              <div class="word-count-summary">
                <span>{{ formatWordCountSummary(batchForm) }}</span>
                <WordCountMatrixPopover v-model="batchForm.wordCountMatrix" title="批量子订单字数统计">
                  <template #reference><el-button type="primary" link>字数统计</el-button></template>
                </WordCountMatrixPopover>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="batchForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="batchForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="batchForm.translatorId" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24">
            <el-alert title="我司、客户及译员预估数据统一在“字数统计”中按计量口径维护。" type="info" :closable="false" />
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchCreateSubOrders">批量创建</el-button>
      </template>
    </el-dialog>

    <BusinessMailComposer
      v-model="mailComposerVisible"
      project-type="translation"
      :project-id="mailProjectId"
      :consultation-id="mailConsultationId"
    />

  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CaretBottom, Check, MagicStick } from '@element-plus/icons-vue'
import { getProjects, getProjectCount, getProject, createProject, updateProject, deleteProject, getNextOrderNo } from '@/api/projects'
import { getProjectFilesByProject } from '@/api/projectFiles'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'
import { getProjectManagerCandidatesAPI, getProjectRoleCandidatesAPI } from '@/api/workflow'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ProjectFilesTab from './components/ProjectFilesTab.vue'
import { hasPermission } from '@/utils/permission'
import { buildAutoProjectName, isAutoProjectName } from '@/utils/projectNaming'
import { fetchProjectClientSuggestions } from '@/utils/projectClientAutocomplete'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import BusinessMailComposer from '@/components/common/BusinessMailComposer.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import GeneratedProjectNameInput from '@/components/common/GeneratedProjectNameInput.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { createEmptyWordCountMatrix, formatWordCountMatrix, getWordCountMatrixListSummary } from '@/utils/wordCountMatrix'
import { getLanguagePairSummary } from '@/utils/languagePair'
import { notifyEmailSubjectGenerated } from '@/utils/emailSubject'
import { launchOpenPath } from '@/utils/openPath'

const SUB_ORDER_PREVIEW_LIMIT = 10
const canWriteProjects = hasPermission('projects:write')
const canReadProjectFiles = hasPermission('project_files:read')
const mailComposerVisible = ref(false)
const mailProjectId = ref('')
const mailConsultationId = ref('')
const router = useRouter()
const route = useRoute()
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
const serviceContentOptions = ['翻译', '排版']
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
  '非项目工作',
]
const subOrderProgressFieldConfigs = [
  ...progressFieldConfigs,
  { key: 'reviewProgress', label: '审核进度（旧字段）' }
]
const progressFieldSet = new Set(subOrderProgressFieldConfigs.map((item) => item.key))
const progressMarks = { 0: '0%', 50: '50%', 100: '100%' }
const projectDetailItems = [
  { label: '订单号', key: 'orderNo' },
  { label: '项目名称', key: 'projectName' },
  { label: '邮件主题预览', key: 'emailSubjectPreview', span: 2 },
  { label: '服务内容', key: 'serviceContent', span: 2 },
  { label: '任务类型', key: 'taskType' },
  { label: '来源咨询 ID', key: 'consultationId' },
  { label: '客户简称', key: 'clientShortName' },
  { label: '客户编号', key: 'clientCode' },
  { label: '客户单号', key: 'customerOrderNo' },
  { label: '项目经理', key: 'projectManagerName' },
  { label: '项目专员', key: 'projectSpecialistName' },
  { label: '项目助理', key: 'projectAssistantName' },
  { label: '排版专员', key: 'layoutSpecialistName' },
  { label: '客户负责人', key: 'clientManager' },
  { label: '负责人联系方式', key: 'managerContact' },
  { label: '状态', key: 'projectStatus', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '翻译文本领域一级', key: 'projectFileTranslationDomainLevel1' },
  { label: '翻译文本领域二级', key: 'projectFileTranslationDomainLevel2' },
  { label: '文件类型一级', key: 'projectFileTypeLevel1' },
  { label: '文件类型二级', key: 'projectFileTypeLevel2' },
  { label: '文件格式', key: 'projectFileFormat' },
  { label: '文件属性一级', key: 'projectFileAttributeLevel1' },
  { label: '文件属性二级', key: 'projectFileAttributeLevel2' },
  { label: '文件属性三级', key: 'projectFileAttributeLevel3' },
  { label: '文件难度', key: 'projectFileDifficulty' },
  { label: '合同类型', key: 'projectContractType' },
  { label: '合同状态', key: 'projectContractStatus' },
  { label: '需提供报价单', key: 'quotationRequired', formatter: (value) => value ? '是' : '否' },
  { label: '报价单状态', key: 'quotationStatus' },
  { label: '报价单路径', key: 'quotationPath', span: 2 },
  { label: '客户专业要求', key: 'customerRequirementProfessional', span: 2 },
  { label: '客户特殊要求', key: 'customerRequirementSpecial', span: 2 },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数与预估', key: 'wordCountMatrix', span: 2, formatter: (value) => formatWordCountMatrix(value) },
  { label: '客户接单时间', key: 'customerReceptionTime' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: 'PM确认人 ID', key: 'pmConfirmedBy' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '大项目经理确认', key: 'majorProjectManagerConfirmation' },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
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
const createEmptyProjectForm = () => ({ id: '', orderNo: '', projectName: '', subjectPrefix: '', emailSubjectPreview: '', serviceContent: '', taskType: '', consultationId: '', clientId: '', subClientId: '', clientShortName: '', clientCode: '', customerOrderNo: '', clientManager: '', managerContact: '', fileTypeSecondary: '', projectContractType: '', projectContractStatus: '', quotationRequired: false, quotationStatus: '', quotationPath: '', customerRequirementProfessional: '', customerRequirementSpecial: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), projectStatus: 'confirmed', projectManagerId: '', projectManagerName: '', projectSpecialistId: '', projectAssistantId: '', layoutSpecialistId: '', customerReceptionTime: '', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', pmConfirmedBy: '', majorProjectManagerConfirmation: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', translatorDeliveryProgress: 0, preReviewQcProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, referenceFilePathOne: '' })
const createEmptySubOrderForm = () => ({ id: '', parentProjectId: '', subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', status: 'pending_confirmation', translatorDeliveryProgress: 0, preReviewQcProgress: 0, reviewProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '', remarks: '' })
const createBatchForm = () => ({ count: 1, startIndex: 1, subProjectNamePrefix: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCountMatrix: createEmptyWordCountMatrix(), customerDeadlineTime: '', sentToClientTime: '', translatorId: '', status: 'pending_confirmation' })
const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const subOrderDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const dialogTitle = ref('新增项目')
const subOrderDialogTitle = ref('新增子订单')
const formRef = ref(null)
const editorBodyRef = ref(null)
const fieldSearchRef = ref(null)
const fieldSearchKeyword = ref('')
const subOrderFormRef = ref(null)
const batchFormRef = ref(null)
const projectTableRef = ref(null)
const projectFilesTabRef = ref(null)
const tableData = ref([])
const projectStatusSavingIds = ref(new Set())
const expandedProjectIds = ref(new Set())
const expandedProjectRowKeys = computed(() => [...expandedProjectIds.value])
const currentProjectSubOrders = ref([])
const projectManagerOptions = ref([])
const projectRoleCandidateOptions = reactive(Object.fromEntries(projectRoleFieldConfigs.map((role) => [role.roleCode, []])))
const projectRoleOptionsLoading = ref(false)
const projectRoleOptionsLoaded = ref(false)
const projectNameManuallyEdited = ref(false)
const pagination = reactive({ page: 1, limit: 10, total: 0 })
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
const searchForm = reactive({ projectName: '', orderNo: '', clientShortName: '', projectStatus: '' })
const advancedVisible = ref(false)
const advancedFilterCount = computed(() => searchForm.orderNo ? 1 : 0)
const tableColumnOverrides = {
  orderNo: { width: PROJECT_LIST_COLUMN_WIDTHS.orderNo, minWidth: PROJECT_LIST_COLUMN_WIDTHS.orderNo, showOverflowTooltip: false, clickHint: '点击订单号查看笔译项目详情' },
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
  customerDeadlineTime: { width: 115, minWidth: 110, showOverflowTooltip: false },
  sentToClientTime: { minWidth: 150 },
  clientFeedback: { minWidth: 240 },
  majorProjectManagerConfirmation: { minWidth: 160 },
  assignedTranslators: { width: 100, minWidth: 96, showOverflowTooltip: false },
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
const tableColumns = projectDetailItems.map((item) => ({
  ...item,
  minWidth: 140,
  showOverflowTooltip: true,
  ...(tableColumnOverrides[item.key] || {}),
}))
const { selectedKeys: visibleColumnKeys, isVisible: isColumnVisible, reset: resetColumns } = useTableColumns(
  'translation-details-v4', tableColumns,
  ['orderNo', 'projectName', 'clientShortName', 'projectManagerName', 'assignedTranslators', 'projectStatus', 'languagePair', 'wordCountMatrix', 'customerDeadlineTime']
)
const visibleTableColumns = computed(() => tableColumns.filter((column) => isColumnVisible(column.key)))
const form = reactive(createEmptyProjectForm())
const subOrderForm = reactive(createEmptySubOrderForm())
const batchForm = reactive(createBatchForm())
const rules = { projectStatus: [{ required: true, message: '请选择状态', trigger: 'change' }] }
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const batchRules = { count: [{ required: true, message: '请输入生成数量', trigger: 'change' }] }
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
const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong'
const BUSINESS_TIME_OFFSET = '+08:00'
const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS
const nowTick = ref(Date.now())
const deliveredStatuses = new Set(['sent_to_client', 'client_feedback', 'feedback_sent_to_client'])
const endedStatuses = new Set(['cancelled', 'partially_cancelled'])

const parseBusinessDateTime = (value) => {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : new Date(value.getTime())
  const text = String(value).trim()
  const timezoneSuffixPattern = /(Z|[+-]\d{2}:?\d{2})$/i
  const normalized = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(text) && !timezoneSuffixPattern.test(text)
    ? `${text.replace(' ', 'T')}${BUSINESS_TIME_OFFSET}`
    : text
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}
const getBusinessDateParts = (value) => {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return { year: Number(values.year), month: Number(values.month), day: Number(values.day) }
}
const toDateKey = ({ year, month, day }) => `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
const shiftDateKey = (parts, days) => {
  const shifted = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + days))
  return toDateKey({ year: shifted.getUTCFullYear(), month: shifted.getUTCMonth() + 1, day: shifted.getUTCDate() })
}
const formatDateTime = (value) => {
  if (!value) return '-'
  const date = parseBusinessDateTime(value)
  return date
    ? new Intl.DateTimeFormat('zh-CN', { timeZone: BUSINESS_TIME_ZONE, dateStyle: 'medium', timeStyle: 'short' }).format(date)
    : String(value)
}
const formatRemainingDuration = (milliseconds, rounding = 'ceil') => {
  const duration = Math.abs(milliseconds)
  const roundValue = rounding === 'floor' ? Math.floor : Math.ceil
  if (duration < HOUR_MS) return `${Math.max(1, roundValue(duration / MINUTE_MS))} 分钟`
  if (duration < DAY_MS) return `${Math.max(1, roundValue(duration / HOUR_MS))} 小时`
  return `${Math.max(1, roundValue(duration / DAY_MS))} 天`
}
const getDeadlineDisplay = (row) => {
  const deadline = parseBusinessDateTime(row?.customerDeadlineTime)
  if (!deadline) return { label: '', type: 'info' }
  const status = normalizeStatus(row?.projectStatus)
  if (deliveredStatuses.has(status)) return { label: '已交付', type: 'success' }
  if (endedStatuses.has(status)) return { label: '已结束', type: 'info' }

  const difference = deadline.getTime() - nowTick.value
  if (Math.abs(difference) < MINUTE_MS) return { label: '现在截止', type: 'warning' }
  if (difference < 0) return { label: `已逾期 ${formatRemainingDuration(difference, 'floor')}`, type: 'danger' }

  const todayParts = getBusinessDateParts(nowTick.value)
  const deadlineParts = getBusinessDateParts(deadline)
  let prefix = ''
  if (todayParts && deadlineParts) {
    const deadlineKey = toDateKey(deadlineParts)
    if (deadlineKey === toDateKey(todayParts)) prefix = '今天截止 · '
    else if (deadlineKey === shiftDateKey(todayParts, 1)) prefix = '明天截止 · '
  }
  return {
    label: `${prefix}剩 ${formatRemainingDuration(difference)}`,
    type: prefix ? 'warning' : 'info',
  }
}
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
  form.projectName = buildAutoProjectName(form.clientShortName, currentProjectSubOrders.value.length)
}
const handleProjectNameInput = () => {
  projectNameManuallyEdited.value = true
}
const regenerateProjectName = () => {
  const generatedName = buildAutoProjectName(form.clientShortName, currentProjectSubOrders.value.length)
  if (!generatedName) return ElMessage.warning('请先选择或填写客户简称')
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
const isProjectExpanded = (row) => expandedProjectIds.value.has(row.id)
const handleProjectExpandChange = (_row, expandedRows) => {
  expandedProjectIds.value = new Set(expandedRows.map((item) => item.id))
}
const toggleProjectExpansion = (row) => {
  if (!getSubOrderCount(row)) return
  projectTableRef.value?.toggleRowExpansion(row, !isProjectExpanded(row))
}
const hasMoreSubOrders = (row) => getSubOrderCount(row) > SUB_ORDER_PREVIEW_LIMIT
const getVisibleSubOrders = (row) => (Array.isArray(row?.subOrders) ? row.subOrders.slice(0, SUB_ORDER_PREVIEW_LIMIT) : [])
const applyPagination = () => { fetchData() }
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
  delete result.managerContact
  delete result.subjectPrefix
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
      target[key] = values[key] ?? defaults[key]
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
  project_name: searchForm.projectName.trim() || undefined,
  order_no: searchForm.orderNo.trim() || undefined,
  client_short_name: searchForm.clientShortName.trim() || undefined,
  project_status: searchForm.projectStatus || undefined
})
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
      sort: 'unfinished_first_order_no_desc',
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const [response, countResponse] = await Promise.all([
      getProjects(params, { signal: requestController.signal }),
      getProjectCount(buildFilterParams(), { signal: requestController.signal })
    ])
    if (sequence !== requestSequence) return
    tableData.value = (Array.isArray(response) ? response : []).map(normalizeProject)
    pagination.total = countResponse?.total || tableData.value.length
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || sequence !== requestSequence) return
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || error.message || 'Failed to load projects')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
const projectRowClass = ({ row }) => String(row.id) === highlightedProjectId.value ? 'workbench-target-row' : ''
const focusRouteProject = async () => {
  const projectId = String(route.query.projectId || '')
  if (!projectId) return
  try {
    const detail = await getProject(projectId)
    highlightedProjectId.value = projectId
    searchForm.orderNo = detail.orderNo || detail.order_no || ''
    pagination.page = 1
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '定位笔译项目失败')
  }
}
const refreshProjectSubOrders = async (projectId) => {
  if (!projectId) return
  const response = await getSubOrdersByProject(projectId)
  const normalized = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
  currentProjectSubOrders.value = normalized
  tableData.value = tableData.value.map((item) => item.id === projectId ? { ...item, subOrders: normalized } : item)
  if (form.id === projectId) syncProjectName()
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
    ElMessage.error(error?.detail || error?.message || '加载项目角色候选人失败')
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

const getOriginalPath = async (row) => {
  if (!row?.id) return ''
  const files = await getProjectFilesByProject(row.id, { skip: 0, limit: 1 })
  return Array.isArray(files) ? String(files[0]?.storage_path || '').trim() : ''
}
const openOriginalPath = async (row) => {
  try {
    const path = await getOriginalPath(row)
    if (!path) {
      ElMessage.warning('该订单暂无原文路径')
      return
    }
    launchOpenPath(path)
  } catch (error) {
    ElMessage.error(error.detail || error.message || '获取原文路径失败')
  }
}
const copyOriginalPath = async (row) => {
  try {
    const path = await getOriginalPath(row)
    if (!path) {
      ElMessage.warning('该订单暂无原文路径')
      return
    }
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch (error) {
    ElMessage.error(error.detail || error.message || '复制失败，请稍后重试')
  }
}

const handleTextSearch = (value) => {
  clearTimeout(searchTimer)
  if (!value) return handleSearch()
  searchTimer = setTimeout(handleSearch, 400)
}
const handleSearch = () => { exitDeleteMode(); clearTimeout(searchTimer); pagination.page = 1; fetchData() }
const resetSearch = () => { searchForm.projectName = ''; searchForm.orderNo = ''; searchForm.clientShortName = ''; searchForm.projectStatus = ''; handleSearch() }
const clearAdvancedFilters = () => { searchForm.orderNo = ''; handleSearch() }
const clearSearch = () => {
  searchForm.projectName = ''
  searchForm.orderNo = ''
  searchForm.clientShortName = ''
  searchForm.projectStatus = ''
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
const resetBatchForm = () => { Object.assign(batchForm, createBatchForm()); batchFormRef.value?.clearValidate() }
const generateOrderNo = async () => { try { return await getNextOrderNo() } catch { const now = new Date(); return `TP-${String(now.getFullYear()).slice(-2)}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${String(Math.floor(Math.random() * 999) + 1).padStart(3, '0')}` } }
const goToSubOrderManagement = (project) => {
  const projectId = project.id || form.id
  if (!projectId) return
  router.push({ name: 'TranslationSubOrderManagement', params: { projectId }, query: { orderNo: project.orderNo || form.orderNo || '', projectName: project.projectName || form.projectName || '' } })
}
const handleAdd = async () => {
  dialogTitle.value = '新增项目'
  resetProjectForm()
  currentProjectSubOrders.value = []
  await Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
  form.orderNo = await generateOrderNo()
  dialogVisible.value = true
  await nextTick()
  projectFilesTabRef.value?.resetPathGroup()
}
const handleEdit = async (row) => {
  dialogTitle.value = '编辑项目详情'
  clearFieldSearch()
  await Promise.all([loadProjectManagerOptions(), loadProjectRoleOptions()])
  assignReactive(form, createEmptyProjectForm, row)
  currentProjectSubOrders.value = Array.isArray(row.subOrders) ? [...row.subOrders] : []
  projectNameManuallyEdited.value = Boolean(form.projectName) && !isAutoProjectName(form.projectName, form.clientShortName)
  syncProjectName()
  projectDialogTab.value = 'basic'
  projectBasicExpandedSections.value = ['project', 'business', 'execution']
  dialogVisible.value = true
  if (row.id) {
    try {
      await refreshProjectSubOrders(row.id)
    } catch (error) {
      ElMessage.error(error.detail || error.message || '加载子订单失败')
    }
  }
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
    if (searchForm.projectStatus && searchForm.projectStatus !== updated.projectStatus) {
      await fetchData()
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.detail || error?.message || '项目状态更新失败')
  } finally {
    setProjectStatusSaving(row.id, false)
  }
}
const handleSubmit = async (sendAfterSave = false) => {
  if (!formRef.value || submitLoading.value) return
  syncProjectName()
  const valid = await formRef.value.validate().catch((invalidFields) => {
    if (invalidFields?.projectStatus) {
      projectDialogTab.value = 'basic'
      if (!projectBasicExpandedSections.value.includes('execution')) {
        projectBasicExpandedSections.value = [...projectBasicExpandedSections.value, 'execution']
      }
    }
    return false
  })
  if (!valid) return

  const pathGroupValid = await projectFilesTabRef.value?.validatePathGroup()
  if (pathGroupValid === false) {
    projectDialogTab.value = 'files'
    return
  }

  submitLoading.value = true
  let projectSaved = false
  try {
    const payload = cleanPayload({ ...form })
    const isCreate = dialogTitle.value === '新增项目'
    let savedProject
    if (isCreate) {
      savedProject = await createProject(payload)
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
        ? `项目已保存，但路径组保存失败：${error.detail || error.message || '请重新进入项目补充保存'}`
        : (error.detail || error.message || '保存失败')
    )
  } finally {
    submitLoading.value = false
  }
}
const onProjectDialogClosed = () => { resetProjectForm(); resetSubOrderForm(); resetBatchForm(); currentProjectSubOrders.value = [] }
const createSubOrderDefaultsFromProject = () => ({ fileTypeSecondary: form.fileTypeSecondary, languagePair: form.languagePair, priority: form.priority, wordCountMatrix: JSON.parse(JSON.stringify(form.wordCountMatrix)), customerDeadlineTime: form.customerDeadlineTime, sentToClientTime: form.sentToClientTime, translatorId: form.translatorId, translatorAssignmentTime: form.translatorAssignmentTime, status: form.projectStatus || 'pending_confirmation', translatorDeliveryProgress: form.translatorDeliveryProgress, preReviewQcProgress: form.preReviewQcProgress, review1Progress: form.review1Progress, review2Progress: form.review2Progress, postReviewQcProgress: form.postReviewQcProgress, layoutProgress: form.layoutProgress, consolidationProgress: form.consolidationProgress, clientFeedback: form.clientFeedback })
const openCreateSubOrderDialog = () => { resetSubOrderForm(); subOrderDialogTitle.value = '新增子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...createSubOrderDefaultsFromProject(), parentProjectId: form.id }); subOrderDialogVisible.value = true }
const handleEditSubOrder = (row) => { resetSubOrderForm(); subOrderDialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...row, parentProjectId: row.parentProjectId || form.id }); subOrderDialogVisible.value = true }
const openProjectEditorForSubOrder = async (projectRow, subOrderRow) => { await handleEdit(projectRow); await nextTick(); handleEditSubOrder(subOrderRow) }
const buildSubOrderPayload = (source) => {
  return cleanPayload({ parentProjectId: form.id, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCountMatrix: source.wordCountMatrix, customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', status: source.status || 'pending', translatorDeliveryProgress: source.translatorDeliveryProgress ?? 0, preReviewQcProgress: source.preReviewQcProgress ?? 0, reviewProgress: source.reviewProgress ?? 0, review1Progress: source.review1Progress ?? 0, review2Progress: source.review2Progress ?? 0, postReviewQcProgress: source.postReviewQcProgress ?? 0, layoutProgress: source.layoutProgress ?? 0, consolidationProgress: source.consolidationProgress ?? 0, networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
}
const handleSubmitSubOrder = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildSubOrderPayload(subOrderForm); if (subOrderDialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } subOrderDialogVisible.value = false; await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '子订单保存失败') } }
const handleDeleteSubOrder = async (row) => { try { await ElMessageBox.confirm(`确认删除子订单 ${row.subOrderNo} 吗？`, '提示', { type: 'warning' }); await deleteSubOrder(row.id); ElMessage.success('子订单删除成功'); if (form.id && row.parentProjectId === form.id) await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '子订单删除失败') } }
const openBatchDialog = () => { resetBatchForm(); Object.assign(batchForm, { ...createBatchForm(), ...createSubOrderDefaultsFromProject(), subProjectNamePrefix: form.projectName ? `${form.projectName}-子订单` : '' }); batchDialogVisible.value = true }
const createBatchSubProjectName = (index) => { const prefix = batchForm.subProjectNamePrefix || (form.projectName ? `${form.projectName}-子订单` : '子订单'); return `${prefix}${String(index).padStart(2, '0')}` }
const handleBatchCreateSubOrders = async () => { if (!batchFormRef.value) return; const valid = await batchFormRef.value.validate().catch(() => false); if (!valid) return; try { for (let offset = 0; offset < batchForm.count; offset += 1) { const sequence = batchForm.startIndex + offset; const payload = buildSubOrderPayload({ ...batchForm, subProjectName: createBatchSubProjectName(sequence), remarks: '' }); await createSubOrder(payload) } batchDialogVisible.value = false; ElMessage.success(`已批量创建 ${batchForm.count} 条子订单`); await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '批量新增失败') } }
let clockTimer = null
onMounted(async () => {
  await fetchData()
  await focusRouteProject()
  clockTimer = window.setInterval(() => { nowTick.value = Date.now() }, MINUTE_MS)
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  clearFieldSearchHighlight()
  if (clockTimer) window.clearInterval(clockTimer)
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
.order-no-actions { display: flex; align-items: center; gap: 6px; }
.order-no-actions :deep(.el-popover__reference-wrapper) { flex: 1; min-width: 0; }
.order-no-link { display: block; width: 100%; height: auto; min-width: 0; padding: 0; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.action-buttons { display: inline-flex; align-items: center; justify-content: center; flex-wrap: nowrap; white-space: nowrap; }
.status-switch-tag.el-tag { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; max-width: 100%; cursor: pointer; user-select: none; vertical-align: middle; transition: opacity 0.15s ease; }
.status-switch-tag :deep(.el-tag__content) { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; white-space: nowrap; line-height: 1; }
.status-switch-text { line-height: 1; }
.status-switch-caret { width: 10px; height: 10px; flex-shrink: 0; margin: 0; font-size: 10px; }
.status-switch-tag:hover { opacity: 0.85; }
.status-switch-tag.is-updating { pointer-events: none; opacity: 0.55; }
.status-option-row { display: inline-flex; align-items: center; gap: 8px; width: 100%; }
.status-current-icon { color: var(--el-color-primary); }
.deadline-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 0; padding: 2px 0; }
.deadline-cell__time { max-width: 100%; overflow: hidden; font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.deadline-cell__tag { max-width: 100%; }
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
:global(.project-editor-dialog) { display: flex; flex-direction: column; max-height: 92vh; overflow: hidden; }
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
.editor-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.form-section { padding: 4px 2px 12px; }
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
.sub-order-panel { padding: 12px 24px 20px; background: #fafafa; }
.sub-order-panel__header { margin-bottom: 12px; }
.sub-order-alert { margin-bottom: 12px; }
.el-alert { margin-top: 16px; }
.project-table :deep(.project-expand-column) { padding: 0 !important; border-right: 0 !important; }
.project-table :deep(.project-expand-column .cell) { display: none; padding: 0; }
.index-cell { display: inline-flex; flex-direction: column; align-items: center; justify-content: center; min-height: 40px; line-height: 20px; }

@media (max-width: 768px) {
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
