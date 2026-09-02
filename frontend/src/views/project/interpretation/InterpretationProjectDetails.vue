<template>
  <el-card class="interpretation-card compact-list-card">
    <template #header>
      <div class="card-header">
        <span>口译项目管理</span>
        <div class="header-actions">
          <TableColumnSettings
            v-model="visibleColumnKeys"
            :columns="tableColumns"
            :column-count="2"
            hint="序号和操作列固定显示；订单号属于可配置业务字段。"
            @reset="resetColumns"
          />
          <BatchDeleteToolbar
            v-if="canWrite"
            :active="deleteMode"
            :selected-count="selectedRows.length"
            :loading="deleting"
            @enter="enterDeleteMode"
            @exit="exitDeleteMode"
            @confirm="confirmBatchDelete"
          />
          <el-button v-if="canWrite && !deleteMode" type="primary" @click="handleAdd">新增口译项目</el-button>
        </div>
      </div>
    </template>

    <AppForm :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input
          v-model="searchForm.keyword"
          placeholder="订单号、项目名称、客户名称或客户单号"
          clearable
          style="width: 300px"
          @input="handleTextSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="项目状态">
        <el-select v-model="searchForm.projectStatus" multiple collapse-tags :max-collapse-tags="1" clearable placeholder="全部" style="width: 180px" @change="handleSearch">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <AdvancedFilterPopover
          v-model:visible="advancedVisible"
          :count="advancedCount"
          popper-class="interpretation-advanced-popover"
          @clear="clearAdvanced"
          @reset="resetSearch"
        >
          <CompactFilterGrid
            :fields="interpretationAdvancedFilterFields"
            :model="searchForm"
            @update="updateConfiguredFilter"
            @text-input="handleConfiguredTextInput"
            @change="handleSearch"
            @enter="handleSearch"
          />
          <AppForm v-if="false" label-position="top">
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="项目类型">
                    <el-select v-model="searchForm.projectType" clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="预定日期">
                    <el-date-picker
                      v-model="searchForm.scheduledDateRange"
                      type="daterange"
                      value-format="YYYY-MM-DD"
                      range-separator="至"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      @change="handleSearch"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="译员">
                    <el-select v-model="searchForm.translatorId" filterable clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in translators" :key="item.id" :label="translatorOptionLabel(item)" :value="item.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="客户/子客户">
                    <el-select v-model="searchForm.clientSelection" filterable clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in filterClientOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="语言">
                    <el-select v-model="searchForm.languageId" filterable clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in languages" :key="item.id" :label="item.label" :value="item.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
          </AppForm>
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>

    <el-table ref="projectTableRef" :data="tableData" v-loading="loading" row-key="id" :row-class-name="projectRowClass" border class="interpretation-table project-detail-list-table" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="index" label="序号" :width="PROJECT_LIST_COLUMN_WIDTHS.index" align="center" fixed="left" />
      <el-table-column v-if="isVisible('orderNo')" label="订单号" :width="PROJECT_LIST_COLUMN_WIDTHS.orderNo" fixed="left">
        <template #header>
          <ConfiguredColumnHeaderFilter :definition="headerFilterDefinition('orderNo')" :model-value="searchForm.orderNo" @update:model-value="searchForm.orderNo = $event" @text-input="handleConfiguredTextInput" @change="handleSearch" @enter="handleSearch" @clear="handleSearch">
            <template #label><ClickableColumnHeader label="订单号" hint="点击订单号查看口译项目管理" /></template>
          </ConfiguredColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <div class="order-cell">
            <el-popover
              trigger="click"
              placement="left"
              :width="760"
              title="口译项目管理"
              popper-class="interpretation-detail-popover"
              @show="loadDetail(row.id)"
              @hide="cancelInlineDetailEdit"
            >
              <template #reference>
                <el-button type="primary" link class="order-no-link business-clickable-cell" :title="row.orderNo" @click.stop>{{ row.orderNo }}</el-button>
              </template>
              <div class="detail-content" v-loading="detailLoadingId === row.id">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="订单号">{{ textValue(detailRow(row).orderNo) }}</el-descriptions-item>
                  <el-descriptions-item label="项目状态">{{ statusLabel(detailRow(row).projectStatus) }}</el-descriptions-item>
                  <el-descriptions-item label="项目名称" :span="2"><InlineTextField :model-value="detailRow(row).projectName" :editable="canWrite && !deleteMode" label="项目名称" :maxlength="500" :save-field="(value) => saveDetailTextField(row, 'projectName', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="内部协作角色" :span="2">{{ internalRolesText(detailRow(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="具体任务" :span="2"><InlineTextField :model-value="detailRow(row).taskDescription" :editable="canWrite && !deleteMode" label="具体任务" multiline :save-field="(value) => saveDetailTextField(row, 'taskDescription', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(detailRow(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="客户简称">{{ textValue(detailRow(row).clientShortName) }}</el-descriptions-item>
                  <el-descriptions-item label="客户编号">{{ textValue(detailRow(row).clientCode) }}</el-descriptions-item>
                  <el-descriptions-item label="客户全称">{{ textValue(detailRow(row).clientFullName) }}</el-descriptions-item>
                  <el-descriptions-item label="客户领域">{{ textValue(detailRow(row).clientDomain) }}</el-descriptions-item>
                  <el-descriptions-item label="现客户经理">{{ textValue(detailRow(row).currentClientManager) }}</el-descriptions-item>
                  <el-descriptions-item label="客户经理联系方式">{{ textValue(detailRow(row).managerContact) }}</el-descriptions-item>
                  <el-descriptions-item label="子客户/联系人"><InlineTextField :model-value="detailRow(row).contactName" :display-value="detailRow(row).contactName || detailRow(row).subClientContact" :editable="canWrite && !deleteMode" label="子客户/联系人" :maxlength="255" :save-field="(value) => saveDetailTextField(row, 'contactName', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户单号/项目标识" :span="2"><InlineTextField :model-value="detailRow(row).customerOrderNo" :editable="canWrite && !deleteMode" label="客户单号/项目标识" :maxlength="150" :save-field="(value) => saveDetailTextField(row, 'customerOrderNo', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="项目时间" :span="2">{{ timeRangesText(detailRow(row).timeRanges) }}</el-descriptions-item>
                  <el-descriptions-item label="项目地点" :span="2">{{ arrayText(detailRow(row).locations, '、') }}</el-descriptions-item>
                  <el-descriptions-item label="口译方向" :span="2">{{ textValue(detailRow(row).languageDirectionsDisplay) }}</el-descriptions-item>
                  <el-descriptions-item label="客户预算" :span="2"><InlineTextField :model-value="detailRow(row).customerBudget" :editable="canWrite && !deleteMode" label="客户预算" multiline :maxlength="500" :save-field="(value) => saveDetailTextField(row, 'customerBudget', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户咨询时间">{{ formatDateTime(detailRow(row).customerConsultationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="客户确认时间">{{ formatDateTime(detailRow(row).customerConfirmationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="口译领域" :span="2"><InlineTextField :model-value="detailRow(row).interpretationDomain" :editable="canWrite && !deleteMode" label="口译领域" multiline :save-field="(value) => saveDetailTextField(row, 'interpretationDomain', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="口译内容" :span="2"><InlineTextField :model-value="detailRow(row).interpretationContent" :editable="canWrite && !deleteMode" label="口译内容" multiline :save-field="(value) => saveDetailTextField(row, 'interpretationContent', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="总需求人数">{{ textValue(detailRow(row).requiredInterpreterCount) }}</el-descriptions-item>
                  <el-descriptions-item label="译员性别">{{ textValue(detailRow(row).requiredInterpreterGender) }}</el-descriptions-item>
                  <el-descriptions-item label="口译水平">{{ textValue(detailRow(row).requiredInterpretationLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="特殊要求"><InlineTextField :model-value="detailRow(row).interpreterSpecialRequirements" :editable="canWrite && !deleteMode" label="特殊要求" multiline :save-field="(value) => saveDetailTextField(row, 'interpreterSpecialRequirements', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="译员身高"><InlineTextField :model-value="detailRow(row).interpreterHeightRequirement" :editable="canWrite && !deleteMode" label="译员身高" :maxlength="100" :save-field="(value) => saveDetailTextField(row, 'interpreterHeightRequirement', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="译员相貌"><InlineTextField :model-value="detailRow(row).interpreterAppearanceRequirement" :editable="canWrite && !deleteMode" label="译员相貌" :maxlength="255" :save-field="(value) => saveDetailTextField(row, 'interpreterAppearanceRequirement', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="着装要求" :span="2"><InlineTextField :model-value="detailRow(row).interpreterDressRequirement" :editable="canWrite && !deleteMode" label="着装要求" :maxlength="255" multiline :save-field="(value) => saveDetailTextField(row, 'interpreterDressRequirement', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="译员安排" :span="2">{{ textValue(detailRow(row).assignedInterpretersDisplay) }}</el-descriptions-item>
                  <el-descriptions-item label="译员编号" :span="2">{{ textValue(detailRow(row).translatorCodes) }}</el-descriptions-item>
                  <el-descriptions-item label="项目文件路径" :span="2"><InlineTextField :model-value="detailRow(row).filePath" :editable="canWrite && !deleteMode" label="项目文件路径" multiline :save-field="(value) => saveDetailTextField(row, 'filePath', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="报价单路径" :span="2"><InlineTextField :model-value="detailRow(row).quotationPath" :editable="canWrite && !deleteMode" label="报价单路径" multiline :save-field="(value) => saveDetailTextField(row, 'quotationPath', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="合同路径" :span="2"><InlineTextField :model-value="detailRow(row).contractPath" :editable="canWrite && !deleteMode" label="合同路径" multiline :save-field="(value) => saveDetailTextField(row, 'contractPath', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户对信实评价">{{ textValue(detailRow(row).clientRating) }}</el-descriptions-item>
                  <el-descriptions-item label="评价备注"><InlineTextField :model-value="detailRow(row).clientRatingNote" :editable="canWrite && !deleteMode" label="评价备注" multiline :save-field="(value) => saveDetailTextField(row, 'clientRatingNote', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户对译员评价" :span="2">
                    {{ interpreterRatingsText(detailRow(row).interpreterAssignments) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="发圈请求" :span="2"><InlineTextField :model-value="detailRow(row).socialPostRequest" :editable="canWrite && !deleteMode" label="发圈请求" multiline :save-field="(value) => saveDetailTextField(row, 'socialPostRequest', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="资源请求" :span="2"><InlineTextField :model-value="detailRow(row).resourceRequest" :editable="canWrite && !deleteMode" label="资源请求" multiline :save-field="(value) => saveDetailTextField(row, 'resourceRequest', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="来源咨询 ID" :span="2">{{ textValue(detailRow(row).consultationId) }}</el-descriptions-item>
                  <el-descriptions-item label="创建时间">{{ formatDateTime(detailRow(row).createdAt) }}</el-descriptions-item>
                  <el-descriptions-item label="更新时间">{{ formatDateTime(detailRow(row).updatedAt) }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="2">
                    <InlineTextField :model-value="detailRow(row).remarks" :editable="canWrite && !deleteMode" label="备注" multiline :save-field="(value) => saveDetailTextField(row, 'remarks', value)" @conflict="loadDetail(row.id, true)" />
                  </el-descriptions-item>
                  <el-descriptions-item label="邮件主题预览" :span="2"><InlineTextField :model-value="detailRow(row).emailSubjectPreview" :editable="canWrite && !deleteMode" label="邮件主题预览" multiline :save-field="(value) => saveDetailTextField(row, 'emailSubjectPreview', value)" @conflict="loadDetail(row.id, true)" /></el-descriptions-item>
                </el-descriptions>
              </div>
            </el-popover>
            <PathActionButtons @open="openProjectPath(row)" @copy="copyProjectPath(row)" />
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
        :show-overflow-tooltip="!['projectName', 'projectStatus'].includes(column.key)"
      >
        <template #header>
          <ConfiguredColumnHeaderFilter v-if="headerFilterDefinition(column.key)" :definition="headerFilterDefinition(column.key)" :model-value="searchForm[headerFilterDefinition(column.key).key]" @update:model-value="searchForm[headerFilterDefinition(column.key).key] = $event" @text-input="handleConfiguredTextInput" @change="handleSearch" @enter="handleSearch" @clear="handleSearch">
            <template #label><ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" /><span v-else>{{ column.label }}</span></template>
          </ConfiguredColumnHeaderFilter>
          <template v-else><ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" /><span v-else>{{ column.label }}</span></template>
        </template>
        <template #default="{ row }">
          <el-dropdown
            v-if="column.key === 'projectStatus' && canWrite"
            trigger="click"
            :disabled="projectStatusSavingIds.has(row.id)"
            @command="(command) => changeProjectStatus(row, command)"
          >
            <el-tag
              :type="statusType(row.projectStatus)"
              size="small"
              class="status-switch-tag"
              :class="{ 'is-updating': projectStatusSavingIds.has(row.id) }"
            >
              <span class="status-switch-text">{{ statusLabel(row.projectStatus) }}</span>
              <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
            </el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="item in statusOptions"
                  :key="item.value"
                  :command="item.value"
                  :disabled="item.value === row.projectStatus || projectStatusSavingIds.has(row.id)"
                >
                  <span class="status-option-row">
                    <el-tag :type="statusType(item.value)" size="small" effect="plain">{{ item.label }}</el-tag>
                    <el-icon v-if="item.value === row.projectStatus" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tag v-else-if="column.key === 'projectStatus'" :type="statusType(row.projectStatus)" size="small">{{ statusLabel(row.projectStatus) }}</el-tag>
          <el-popover
            v-else-if="column.key === 'clientShortName' && row.clientShortName"
            trigger="click"
            placement="left"
            :width="420"
            title="客户关联信息"
            popper-class="interpretation-client-popover"
          >
            <template #reference>
              <el-button type="primary" link class="business-clickable-cell" @click.stop>{{ row.clientShortName }}</el-button>
            </template>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="子客户/联系人">{{ textValue(row.subClientContact) }}</el-descriptions-item>
              <el-descriptions-item label="客户单号/项目标识">{{ textValue(row.customerOrderNo) }}</el-descriptions-item>
            </el-descriptions>
          </el-popover>
          <el-popover
            v-else-if="column.key === 'assignedInterpretersDisplay'"
            trigger="click"
            placement="left"
            :width="760"
            title="译员安排详情"
            popper-class="interpretation-interpreter-popover"
            @show="loadDetail(row.id)"
          >
            <template #reference>
              <el-button type="primary" link class="business-clickable-cell" @click.stop>{{ row.assignedInterpretersDisplay || '查看要求' }}</el-button>
            </template>
            <div class="interpreter-detail-content" v-loading="detailLoadingId === row.id">
              <div class="interpreter-detail-section-title">常用要求</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="总需求人数">{{ textValue(detailRow(row).requiredInterpreterCount) }}</el-descriptions-item>
                <el-descriptions-item label="译员性别">{{ textValue(detailRow(row).requiredInterpreterGender) }}</el-descriptions-item>
                <el-descriptions-item label="口译水平">{{ textValue(detailRow(row).requiredInterpretationLevel) }}</el-descriptions-item>
                <el-descriptions-item label="特殊要求">{{ textValue(detailRow(row).interpreterSpecialRequirements) }}</el-descriptions-item>
              </el-descriptions>
              <div class="interpreter-detail-section-title">形象与着装要求</div>
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="译员身高">{{ textValue(detailRow(row).interpreterHeightRequirement) }}</el-descriptions-item>
                <el-descriptions-item label="译员相貌">{{ textValue(detailRow(row).interpreterAppearanceRequirement) }}</el-descriptions-item>
                <el-descriptions-item label="着装要求">{{ textValue(detailRow(row).interpreterDressRequirement) }}</el-descriptions-item>
              </el-descriptions>
              <div class="interpreter-detail-section-title">
                已安排译员（{{ detailRow(row).interpreterAssignments?.length || 0 }} 人）
              </div>
              <template v-if="detailRow(row).interpreterAssignments?.length">
                <el-descriptions
                  v-for="person in detailRow(row).interpreterAssignments"
                  :key="person.id"
                  :title="person.translatorName"
                  :column="2"
                  border
                  size="small"
                  class="translator-profile"
                >
                  <el-descriptions-item label="译员编号">{{ textValue(person.translatorCode) }}</el-descriptions-item>
                  <el-descriptions-item label="口译水平">{{ textValue(person.translatorInterpretationLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="性别">{{ textValue(person.translatorGender) }}</el-descriptions-item>
                  <el-descriptions-item label="身高">{{ textValue(person.translatorHeight) }}</el-descriptions-item>
                  <el-descriptions-item label="相貌">{{ textValue(person.translatorAppearance) }}</el-descriptions-item>
                  <el-descriptions-item label="语种">{{ textValue(person.translatorLanguages) }}</el-descriptions-item>
                  <el-descriptions-item label="翻译类型">{{ textValue(person.translatorTranslationType) }}</el-descriptions-item>
                  <el-descriptions-item label="方向">{{ textValue(person.translatorDirection) }}</el-descriptions-item>
                  <el-descriptions-item label="简历路径" :span="2">{{ textValue(person.translatorResumePath) }}</el-descriptions-item>
                  <el-descriptions-item label="客户评价" :span="2">{{ ratingText(person.customerRating, person.evaluationNote) }}</el-descriptions-item>
                </el-descriptions>
              </template>
              <el-empty v-else description="暂未安排译员" :image-size="64" />
            </div>
          </el-popover>
          <InlineTextField
            v-else-if="column.key === 'projectName'"
            :model-value="row.projectName"
            :editable="canWrite && !deleteMode"
            label="项目名称"
            :maxlength="500"
            :save-field="(value) => saveDetailTextField(row, 'projectName', value)"
            @conflict="fetchData"
          />
          <span v-else>{{ tableCellText(row, column.key) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" :width="PROJECT_LIST_COLUMN_WIDTHS.actions" fixed="right" align="center">
        <template #default="{ row }">
          <ProjectListRowActions
            v-if="canWrite"
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
      class="pagination"
      @size-change="fetchData"
      @current-change="fetchData"
    />

    <DraggableFormDialog
      v-model="dialogVisible"
      class="interpretation-editor-dialog"
      width="min(1080px, calc(100vw - 32px))"
      top="5vh"
      @closed="onEditorClosed"
    >
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          v-model="fieldSearchKeyword"
          :title="dialogTitle"
          :fetch-suggestions="fetchFieldSuggestions"
          @select="locateDialogField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="dialogBodyRef" class="editor-body">
        <AppForm ref="formRef" :model="form" :rules="rules" label-width="120px">
          <section class="form-section interpretation-key-fields">
            <div class="interpretation-key-fields__header">
              <div><h3>关键必填信息</h3><p>请优先完成以下内容，再补充其余项目资料。</p></div>
              <el-tag type="danger" effect="plain">8 项必填</el-tag>
            </div>
            <el-row :gutter="16">
              <el-col :xs="24">
                <el-form-item label="项目名称" prop="projectName">
                  <GeneratedProjectNameInput
                    v-model="form.projectName"
                    placeholder="可手工填写，或根据时间、地点、方向和类型生成"
                    :loading="nameLoading"
                    @manual-input="handleProjectNameInput"
                    @regenerate="generateProjectName"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="项目类型" prop="projectTypes">
                  <el-select v-model="form.projectTypes" multiple clearable collapse-tags collapse-tags-tooltip style="width: 100%">
                    <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="客户简称" prop="clientShortName" data-field-key="clientShortName">
                  <div class="client-autocomplete-field">
                    <el-autocomplete
                      v-model="form.clientShortName"
                      :fetch-suggestions="fetchClientSuggestions"
                      value-key="client_short_name"
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
                          <span>{{ item.client_short_name }} <el-tag v-if="item.sub_client_id" size="small" type="warning">子客户</el-tag></span>
                          <span class="client-suggestion__meta">{{ item.client_code }} · {{ item.client_name }}{{ item.parent_client_short_name ? ` · 归属 ${item.parent_client_short_name}` : '' }}</span>
                        </div>
                      </template>
                    </el-autocomplete>
                    <div class="client-autocomplete-hint">没有匹配客户时，保存项目会自动新增一条待完善的客户信息。</div>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="具体任务" prop="taskDescription">
              <el-input v-model="form.taskDescription" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" placeholder="请输入具体任务，可填写详细的工作内容和要求" resize="vertical" />
            </el-form-item>
            <div class="section-title-row"><h3>预定时间</h3><el-button type="primary" plain @click="addTimeRange">增加时间段</el-button></div>
            <div v-for="(item, index) in form.timeRanges" :key="index" class="repeat-card">
              <div class="repeat-title">时间段 {{ index + 1 }}<el-button v-if="form.timeRanges.length > 1" link type="danger" @click="form.timeRanges.splice(index, 1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="12"><el-form-item label="预定开始" :prop="`timeRanges.${index}.scheduledStart`" :rules="requiredScheduledStartRule"><el-date-picker v-model="item.scheduledStart" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="预定结束" :prop="`timeRanges.${index}.scheduledEnd`" :rules="requiredScheduledEndRule"><el-date-picker v-model="item.scheduledEnd" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="实际开始"><el-date-picker v-model="item.actualStart" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" clearable format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="实际结束"><el-date-picker v-model="item.actualEnd" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" clearable format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
              </el-row>
            </div>
            <el-form-item label="地点" prop="locations" class="composite-required-item">
              <div class="location-panel">
                <div class="location-panel__header">
                  <div><h4>项目地点</h4><div class="location-panel__hint">默认保留 1 个地点，最多可添加 {{ MAX_LOCATIONS }} 个</div></div>
                  <el-button type="primary" plain :icon="Plus" :disabled="form.locations.length >= MAX_LOCATIONS" @click="addLocation">增加地点</el-button>
                </div>
                <el-row :gutter="12" class="location-list">
                  <el-col v-for="(location, index) in form.locations" :key="index" :xs="24" :md="12">
                    <div class="location-item">
                      <div class="location-item__header"><span>地点 {{ index + 1 }}</span><el-button v-if="form.locations.length > 1" link type="danger" @click="removeLocation(index)">删除</el-button></div>
                      <el-input v-model="form.locations[index]" :aria-label="`项目地点 ${index + 1}`" placeholder="请输入项目地点" clearable />
                    </div>
                  </el-col>
                </el-row>
              </div>
            </el-form-item>
            <el-form-item label="口译方向" prop="languageDirections" class="composite-required-item">
              <InterpretationDirectionEditor
                v-model="form.languageDirections"
                :languages="selectableLanguages"
                :required-total="directionRequiredTotal"
                @manage-languages="openLanguageManager"
                @create-language="addLanguage"
              />
            </el-form-item>
          </section>

          <section class="form-section">
            <h3>基础与客户</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><ReadonlyField :model-value="form.orderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="项目状态" prop="projectStatus">
                  <el-select v-model="form.projectStatus" style="width: 100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="客户预算"><el-input v-model="form.customerBudget" placeholder="可填写金额、计价单位及差旅说明" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><ReadonlyField :model-value="form.currentClientManager" source="auto" placeholder="选择客户后自动带出" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="客户全称"><ReadonlyField :model-value="form.clientFullName" :source="form.clientId ? 'auto' : 'editable'" :placeholder="form.clientId ? '选择客户后自动带出' : '新客户可补充全称'" @update:model-value="form.clientFullName = $event" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户编号"><ReadonlyField :model-value="form.clientCode" :source="form.clientId ? 'auto' : 'editable'" :placeholder="form.clientId ? '选择客户后自动带出' : '新客户不填则自动生成'" @update:model-value="form.clientCode = $event" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户领域"><ReadonlyField :model-value="form.clientDomain" source="auto" placeholder="选择客户后自动带出" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="联系人"><el-input v-model="form.contactName" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户单号/标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
              <el-col v-if="showManagerContactInput" :xs="24" :md="8"><el-form-item label="客户经理联系方式"><el-input v-model="form.managerContact" maxlength="100" clearable placeholder="请输入客户经理联系方式" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户咨询时间"><el-date-picker v-model="form.customerConsultationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户确认时间"><el-date-picker v-model="form.customerConfirmationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
            </el-row>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>译员安排与评价</h3></div>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="译员性别"><el-select v-model="form.requiredInterpreterGender" clearable placeholder="不限" style="width: 100%"><el-option label="不限" value="不限" /><el-option label="男" value="男" /><el-option label="女" value="女" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="口译水平"><el-select v-model="form.requiredInterpretationLevel" clearable placeholder="请选择" style="width: 100%"><el-option label="初级" value="初级" /><el-option label="中级" value="中级" /><el-option label="高级" value="高级" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="特殊要求"><el-input v-model="form.interpreterSpecialRequirements" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <div class="interpreter-requirement-group">
              <div class="requirement-group-title">形象与着装要求</div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="8"><el-form-item label="译员身高"><el-input v-model="form.interpreterHeightRequirement" /></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="译员相貌"><el-input v-model="form.interpreterAppearanceRequirement" /></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="着装要求"><el-input v-model="form.interpreterDressRequirement" /></el-form-item></el-col>
              </el-row>
            </div>
            <div v-for="(item, index) in form.interpreterAssignments" :key="index" class="repeat-card">
              <div class="repeat-title">译员 {{ index + 1 }}<el-button link type="danger" @click="form.interpreterAssignments.splice(index, 1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="12"><el-form-item label="译员"><el-select v-model="item.translatorId" filterable style="width: 100%"><el-option v-for="person in translators" :key="person.id" :label="translatorOptionLabel(person)" :value="person.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户评价"><el-select v-model="item.customerRating" clearable style="width: 100%"><el-option v-for="rating in ratingOptions" :key="rating.value" :label="rating.label" :value="rating.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24"><el-form-item label="评价备注"><el-input v-model="item.evaluationNote" type="textarea" :rows="2" /></el-form-item></el-col>
              </el-row>
            </div>
            <el-button class="interpreter-add-button" :icon="Plus" @click="addInterpreter">增加译员</el-button>
          </section>

          <section class="form-section">
            <h3>扩展信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="口译领域"><el-input v-model="form.interpretationDomain" type="textarea" :rows="2" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="口译内容"><el-input v-model="form.interpretationContent" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="项目文件路径"><PathInput v-model="form.filePath" @open="openPathValue(form.filePath)" @copy="copyPathValue(form.filePath)" /></el-form-item>
            <el-form-item label="报价单路径"><PathInput v-model="form.quotationPath" @open="openPathValue(form.quotationPath)" @copy="copyPathValue(form.quotationPath)" /></el-form-item>
            <el-form-item label="合同路径"><PathInput v-model="form.contractPath" @open="openPathValue(form.contractPath)" @copy="copyPathValue(form.contractPath)" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户对信实评价"><el-select v-model="form.clientRating" clearable style="width: 100%"><el-option v-for="rating in ratingOptions" :key="rating.value" :label="rating.label" :value="rating.value" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="评价备注"><el-input v-model="form.clientRatingNote" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="发圈请求"><el-input v-model="form.socialPostRequest" type="textarea" :rows="2" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="资源请求"><el-input v-model="form.resourceRequest" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="备注" class="remarks-form-item"><el-input v-model="form.remarks" type="textarea" :rows="5" /></el-form-item>
            <el-form-item label="标题前缀">
              <el-input v-model="form.subjectPrefix" maxlength="50" show-word-limit clearable placeholder="可选，例如：紧急、请优先处理" />
            </el-form-item>
            <el-form-item label="邮件主题预览">
              <div class="subject-preview-field">
                <el-input v-model="form.emailSubjectPreview" type="textarea" :rows="3" />
                <div class="subject-preview-toolbar">
                  <span>按“标题前缀、订单号、客户简称、客户经理联系方式、客户单号/标识、项目名称”顺序生成</span>
                  <el-button class="soft-action-button" :icon="MagicStick" @click="generateEmailSubject">生成邮件主题</el-button>
                </div>
              </div>
            </el-form-item>
          </section>
          <InternalProjectRolesForm v-model="form.roleAssignments" />
        </AppForm>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :loading="submitLoading" @click="handleSubmit(true)">保存并发送邮件</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit(false)">保存</el-button>
      </template>
    </DraggableFormDialog>

    <el-dialog
      v-model="languageManagerVisible"
      title="管理口译语种"
      class="language-manager-dialog"
      width="min(760px, calc(100vw - 32px))"
      top="8vh"
      append-to-body
    >
      <div class="language-manager-hint">
        系统预置语种只读；自定义语种可以重命名或停用。停用不会影响历史项目，但不会再出现在新项目的可选项中。
      </div>
      <el-table :data="languages" v-loading="languageManagerLoading" border max-height="480">
        <el-table-column prop="label" label="语种名称" min-width="220">
          <template #default="{ row }">
            <span>{{ row.label }}</span>
            <el-tag v-if="row.isCustom" size="small" type="warning" class="language-type-tag">新</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110" align="center">
          <template #default="{ row }">{{ row.isCustom ? '用户新增' : '系统预置' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }"><el-tag :type="row.isActive === false ? 'info' : 'success'">{{ row.isActive === false ? '已停用' : '启用中' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <template v-if="row.isCustom">
              <el-button link type="primary" @click="renameLanguage(row)">重命名</el-button>
              <el-button v-if="row.isActive !== false" link type="danger" @click="toggleLanguage(row, false)">停用</el-button>
              <el-button v-else link type="success" @click="toggleLanguage(row, true)">重新启用</el-button>
            </template>
            <span v-else class="readonly-language">只读</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="languageManagerVisible = false">关闭</el-button></template>
    </el-dialog>
    <BusinessMailComposer
      v-model="mailComposerVisible"
      project-type="interpretation"
      :project-id="mailProjectId"
      :consultation-id="mailConsultationId"
    />
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CaretBottom, Check, MagicStick, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as projectApi from '@/api/interpretationProjects'
import * as clientApi from '@/api/clients'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { getProjectTalentOptions } from '@/api/talents'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import GeneratedProjectNameInput from '@/components/common/GeneratedProjectNameInput.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import PathInput from '@/components/common/PathInput.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import BusinessMailComposer from '@/components/common/BusinessMailComposer.vue'
import InternalProjectRolesForm from '@/components/common/InternalProjectRolesForm.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import InlineTextField from '@/components/common/InlineTextField.vue'
import InterpretationDirectionEditor from './components/InterpretationDirectionEditor.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useTableColumns } from '@/composables/useTableColumns'
import { useFormDraft } from '@/composables/useFormDraft'
import { useResourceRequestStatuses } from '@/composables/useResourceRequestStatuses'
import { notifyEmailSubjectGenerated, extractSubjectPrefix } from '@/utils/emailSubject'
import { hasPermission } from '@/utils/permission'
import { fetchProjectClientSuggestions } from '@/utils/projectClientAutocomplete'
import { launchOpenPath } from '@/utils/openPath'
import { createIdempotencyKey } from '@/utils/idempotency'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'

const canWrite = hasPermission('projects:write')
const mailComposerVisible = ref(false)
const mailProjectId = ref('')
const mailConsultationId = ref('')
const loading = ref(true)
const submitLoading = ref(false)
let submitLocked = false
const projectCreateIdempotencyKey = ref('')
const projectStatusSavingIds = ref(new Set())
const nameLoading = ref(false)
const nameManuallyEdited = ref(false)
const dialogVisible = ref(false)
const languageManagerVisible = ref(false)
const languageManagerLoading = ref(false)
const dialogTitle = ref('新增口译项目')
const formRef = ref(null)
const route = useRoute()
const router = useRouter()
const { load: loadResourceRequestStatuses, actionLabel: resourceRequestActionLabel } = useResourceRequestStatuses('interpretation')
const startResourceRequest = (row) => {
  if (!row.languageDirectionCountsComplete) {
    ElMessage.warning('该项目的语言方向人数尚未补齐，请先编辑项目后再发起需求')
    return
  }
  router.push({ name: 'ResourceRequests', query: { sourceType: 'interpretation', sourceProjectId: row.id } })
}
const highlightedProjectId = ref('')
const dialogBodyRef = ref(null)
const {
  fieldSearchRef,
  fieldSearchKeyword,
  fetchFieldSuggestions,
  locateDialogField,
  clearFieldSearch,
} = useDialogFieldSearch(dialogBodyRef)
const tableData = ref([])
const projectTableRef = ref(null)
const clients = ref([])
const translators = ref([])
const languages = ref([])
const filterClientOptions = computed(() => clients.value.flatMap((client) => [
  { value: `client:${client.id}`, label: client.client_short_name || client.client_name },
  ...((client.sub_clients || []).map((sub) => ({
    value: `sub:${sub.id}`,
    label: `${client.client_short_name || client.client_name} / ${sub.client_short_name || sub.client_name}`,
  }))),
]))
const detailCache = reactive({})
const detailLoadingId = ref(null)
const advancedVisible = ref(false)
let searchTimer = null
let autoNameTimer = null
let requestController = null
let requestId = 0
let namePreviewRequestId = 0

const projectTypeOptions = [
  { value: 'onsite', label: '现场口译' },
  { value: 'booth', label: '展会摊位口译' },
  { value: 'exhibition_escort', label: '展会陪同口译' },
  { value: 'escort', label: '陪同口译' },
  { value: 'small_business_meeting', label: '小型商务会议口译' },
  { value: 'small_non_business_meeting', label: '小型（非商务）会议口译' },
  { value: 'consecutive', label: '会议交传口译' },
  { value: 'simultaneous', label: '会议同传口译' },
  { value: 'online_meeting', label: '线上会议口译' },
  { value: 'online_simultaneous', label: '线上同传口译' },
]
const projectTypeMap = Object.fromEntries(projectTypeOptions.map((item) => [item.value, item.label]))
const statusOptions = [
  { value: 'initial_follow_up', label: '初步跟进中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'cancelled', label: '已取消' },
  { value: 'partially_cancelled', label: '已部分取消' },
  { value: 'ended', label: '已结束' },
  { value: 'settled', label: '已结款' },
]
const statusMap = Object.fromEntries(statusOptions.map((item) => [item.value, item.label]))
const ratingOptions = [
  { value: 'very_satisfied', label: '非常满意' },
  { value: 'satisfied', label: '满意' },
  { value: 'basically_satisfied', label: '基本满意' },
  { value: 'dissatisfied', label: '不满意' },
  { value: 'very_dissatisfied', label: '非常不满意' },
]
const ratingMap = Object.fromEntries(ratingOptions.map((item) => [item.value, item.label]))

const tableColumns = [
  { key: 'orderNo', label: '订单号', width: PROJECT_LIST_COLUMN_WIDTHS.orderNo },
  { key: 'projectName', label: '项目名称', minWidth: PROJECT_LIST_COLUMN_WIDTHS.projectName },
  { key: 'projectTypes', label: '项目类型', minWidth: 150 },
  { key: 'taskDescription', label: '具体任务', minWidth: PROJECT_LIST_COLUMN_WIDTHS.longText },
  { key: 'currentClientManager', label: '现客户经理', width: 92 },
  { key: 'projectStatus', label: '项目状态', width: PROJECT_LIST_COLUMN_WIDTHS.projectStatus },
  { key: 'clientShortName', label: '客户简称', width: PROJECT_LIST_COLUMN_WIDTHS.clientShortName, clickHint: '点击客户简称查看关联信息' },
  { key: 'clientCode', label: '客户编号', width: 100 },
  { key: 'clientFullName', label: '客户全称', minWidth: 150 },
  { key: 'clientDomain', label: '客户领域', minWidth: 120 },
  { key: 'managerContact', label: '客户经理联系方式', minWidth: 150 },
  { key: 'subClientContact', label: '子客户/联系人', minWidth: 125 },
  { key: 'customerOrderNo', label: '客户单号/项目标识', minWidth: 140 },
  { key: 'timeRanges', label: '项目时间', minWidth: 200 },
  { key: 'locations', label: '项目地点', minWidth: 140 },
  { key: 'languageDirectionsDisplay', label: '口译方向', minWidth: PROJECT_LIST_COLUMN_WIDTHS.languageDirection },
  { key: 'customerBudget', label: '客户预算', minWidth: 120 },
  { key: 'customerConsultationTime', label: '客户咨询时间', minWidth: 150 },
  { key: 'customerConfirmationTime', label: '客户确认时间', minWidth: 150 },
  { key: 'interpretationDomain', label: '口译领域', minWidth: 120 },
  { key: 'interpretationContent', label: '口译内容', minWidth: 160 },
  { key: 'requiredInterpreterCount', label: '总需求人数', width: 105 },
  { key: 'requiredInterpreterGender', label: '译员性别', width: 90 },
  { key: 'requiredInterpretationLevel', label: '口译水平', width: 90 },
  { key: 'interpreterSpecialRequirements', label: '特殊要求', minWidth: 140 },
  { key: 'interpreterHeightRequirement', label: '译员身高', minWidth: 110 },
  { key: 'interpreterAppearanceRequirement', label: '译员相貌', minWidth: 110 },
  { key: 'interpreterDressRequirement', label: '着装要求', minWidth: 120 },
  { key: 'assignedInterpretersDisplay', label: '译员安排', minWidth: 140, clickHint: '点击查看译员要求与安排详情' },
  { key: 'translatorCodes', label: '译员编号', minWidth: 110 },
  { key: 'filePath', label: '项目文件路径', minWidth: 180 },
  { key: 'quotationPath', label: '报价单路径', minWidth: 180 },
  { key: 'contractPath', label: '合同路径', minWidth: 180 },
  { key: 'clientRating', label: '客户对信实评价', minWidth: 130 },
  { key: 'clientRatingNote', label: '评价备注', minWidth: 160 },
  { key: 'interpreterAssignments', label: '客户对译员评价', minWidth: 180 },
  { key: 'remarks', label: '备注', minWidth: 180 },
  { key: 'emailSubjectPreview', label: '邮件主题预览', minWidth: 200 },
  { key: 'socialPostRequest', label: '发圈请求', minWidth: 150 },
  { key: 'resourceRequest', label: '资源请求', minWidth: 150 },
  { key: 'createdAt', label: '创建时间', minWidth: 150 },
  { key: 'updatedAt', label: '更新时间', minWidth: 150 },
]
const defaultColumns = [
  'orderNo', 'projectName', 'taskDescription', 'currentClientManager', 'projectStatus', 'clientShortName',
  'languageDirectionsDisplay', 'customerBudget', 'assignedInterpretersDisplay',
]
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns(
  'interpretation-details-v5', tableColumns, defaultColumns
)
const visibleTableColumns = computed(() => tableColumns.filter((item) => item.key !== 'orderNo' && isVisible(item.key)))

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
  deleteRow: (row) => projectApi.deleteInterpretationProject(row.id),
  getLabel: (row) => row.orderNo || row.projectName,
  reload: () => fetchData(),
  onDeleted: (row) => { delete detailCache[row.id] },
  entityName: '口译项目',
})
const searchForm = reactive({
  keyword: '', projectStatus: '', projectType: '', scheduledDateRange: [], translatorId: '', clientSelection: '', languageId: '',
})
const interpretationFilterFields = [
  { key: 'orderNo', label: '订单号', type: 'text' },
  { key: 'projectName', label: '项目名称', type: 'text' },
  { key: 'projectTypes', label: '项目类型', type: 'select', options: projectTypeOptions },
  { key: 'taskDescription', label: '具体任务', type: 'text' },
  { key: 'currentClientManager', label: '现客户经理', type: 'text' },
  { key: 'projectStatus', label: '项目状态', type: 'select', options: statusOptions },
  { key: 'clientShortName', label: '客户简称', type: 'text' },
  { key: 'clientCode', label: '客户编号', type: 'text' },
  { key: 'clientFullName', label: '客户全称', type: 'text' },
  { key: 'clientDomain', label: '客户领域', type: 'text' },
  { key: 'managerContact', label: '经理联系方式', type: 'text' },
  { key: 'contactName', label: '联系人', type: 'text' },
  { key: 'customerOrderNo', label: '客户单号', type: 'text' },
  { key: 'scheduledDateRange', apiKey: 'scheduled_date', label: '预定日期', type: 'date-range', wide: true },
  { key: 'locations', label: '口译地点', type: 'text' },
  { key: 'languageDirectionsDisplay', apiKey: 'language_id', label: '口译方向', type: 'select', options: () => languages.value.map((item) => ({ label: item.label, value: item.id })) },
  { key: 'customerBudget', label: '客户预算', type: 'text' },
  { key: 'customerConsultationTime', label: '客户咨询时间', type: 'date-range', wide: true },
  { key: 'customerConfirmationTime', label: '客户确认时间', type: 'date-range', wide: true },
  { key: 'interpretationDomain', label: '口译领域', type: 'text' },
  { key: 'interpretationContent', label: '口译内容', type: 'text' },
  { key: 'requiredInterpreterCount', label: '总需求人数', type: 'number-range', wide: true, min: 0 },
  { key: 'requiredInterpreterGender', label: '译员性别要求', type: 'text' },
  { key: 'requiredInterpretationLevel', label: '口译级别要求', type: 'text' },
  { key: 'interpreterSpecialRequirements', label: '译员特殊要求', type: 'text' },
  { key: 'interpreterHeightRequirement', label: '身高要求', type: 'text' },
  { key: 'interpreterAppearanceRequirement', label: '形象要求', type: 'text' },
  { key: 'interpreterDressRequirement', label: '着装要求', type: 'text' },
  { key: 'assignedInterpretersDisplay', apiKey: 'translator_id', label: '译员安排', type: 'select', options: () => translators.value.map((item) => ({ label: translatorOptionLabel(item), value: item.id })) },
  { key: 'clientRating', label: '客户评分', type: 'select', options: ratingOptions },
  { key: 'clientRatingNote', label: '评分说明', type: 'text' },
  { key: 'remarks', label: '备注', type: 'text' },
  { key: 'createdAt', label: '创建时间', type: 'date-range', wide: true },
  { key: 'updatedAt', label: '更新时间', type: 'date-range', wide: true },
]
Object.assign(searchForm, createFilterModel(interpretationFilterFields), { keyword: '' })
const interpretationAdvancedFilterFields = interpretationFilterFields.filter((item) => item.key !== 'projectStatus')
const advancedCount = computed(() => countActiveFilters(searchForm, interpretationAdvancedFilterFields))
const headerFilterDefinition = (key) => {
  if (!defaultColumns.includes(key)) return null
  return interpretationFilterFields.find((item) => item.key === key) || null
}

const MAX_LOCATIONS = 4
const emptyTimeRange = () => ({ scheduledStart: '', scheduledEnd: '', actualStart: '', actualEnd: '' })
const emptyLanguageDirection = () => ({ languageIds: ['', ''], requiredCount: null })
const defaultForm = () => ({
  id: '', orderNo: '', projectName: '', projectTypes: [], taskDescription: '',
  clientId: '', subClientId: '', clientShortName: '', clientFullName: '', clientCode: '',
  clientDomain: '', currentClientManager: '', managerContact: '', contactName: '', customerOrderNo: '', projectStatus: 'initial_follow_up',
  locations: [''], customerBudget: '', customerConsultationTime: '', customerConfirmationTime: '',
  requiredInterpreterGender: '', requiredInterpretationLevel: '',
  interpreterSpecialRequirements: '', interpreterHeightRequirement: '',
  interpreterAppearanceRequirement: '', interpreterDressRequirement: '',
  interpretationDomain: '', interpretationContent: '', filePath: '', quotationPath: '', contractPath: '',
  clientRating: '', clientRatingNote: '', remarks: '', subjectPrefix: '', emailSubjectPreview: '', socialPostRequest: '', resourceRequest: '',
  timeRanges: [emptyTimeRange()], languageDirections: [emptyLanguageDirection()], interpreterAssignments: [], roleAssignments: [],
})
const form = reactive(defaultForm())
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({
  namespace: 'interpretation-project',
  form,
  createDefault: defaultForm,
  formRef,
  applyDraft: (draft) => {
    Object.assign(form, defaultForm(), draft)
    nameManuallyEdited.value = Boolean(draft.projectName)
  },
})
const showManagerContactInput = computed(() => (
  !form.clientId
  && Boolean(form.clientShortName?.trim() || form.clientFullName?.trim())
))
const directionRequiredTotal = computed(() => form.languageDirections.reduce(
  (total, item) => total + (Number.isInteger(item.requiredCount) && item.requiredCount > 0 ? item.requiredCount : 0),
  0,
))
const requiredTextValidator = (message) => (_rule, value, callback) => {
  if (!String(value || '').trim()) return callback(new Error(message))
  callback()
}
const validateLocations = (_rule, value, callback) => {
  if (!(value || []).some((item) => String(item || '').trim())) return callback(new Error('请至少填写一个地点'))
  callback()
}
const validateLanguageDirections = (_rule, value, callback) => {
  const directions = value || []
  if (!directions.length) return callback(new Error('请至少添加一个口译方向'))
  if (directions.some((item) => item.languageIds.length < 2 || item.languageIds.length > 5 || item.languageIds.some((id) => !id))) return callback(new Error('每个口译方向必须完整选择 2 至 5 个语种'))
  if (directions.some((item) => !Number.isInteger(item.requiredCount) || item.requiredCount < 1)) return callback(new Error('请填写每个口译方向的需求人数'))
  callback()
}
const requiredScheduledStartRule = [{ required: true, message: '请选择预定开始时间', trigger: 'change' }]
const requiredScheduledEndRule = [{ required: true, message: '请选择预定结束时间', trigger: 'change' }]
const rules = {
  projectName: [{ validator: requiredTextValidator('请输入项目名称'), trigger: ['blur', 'change'] }],
  projectTypes: [{ type: 'array', required: true, min: 1, message: '请至少选择一个项目类型', trigger: 'change' }],
  taskDescription: [{ validator: requiredTextValidator('请输入具体任务'), trigger: ['blur', 'change'] }],
  clientShortName: [{ validator: requiredTextValidator('请选择或输入客户简称'), trigger: ['blur', 'change'] }],
  locations: [{ validator: validateLocations, trigger: 'change' }],
  languageDirections: [{ validator: validateLanguageDirections, trigger: 'change' }],
  projectStatus: [{ required: true, message: '请选择项目状态', trigger: 'change' }],
}

const selectedLanguageIds = computed(() => new Set(
  form.languageDirections.flatMap((item) => item.languageIds).filter(Boolean)
))
const selectableLanguages = computed(() => languages.value.filter(
  (item) => item.isActive !== false || selectedLanguageIds.value.has(item.id)
))

const statusLabel = (value) => statusMap[value] || value || '-'
const statusType = (value) => ({ initial_follow_up: 'warning', in_progress: 'primary', cancelled: 'danger', partially_cancelled: 'warning', ended: 'success', settled: 'success' }[value] || 'info')
const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const internalRolesText = (row) => {
  const labels = { project_manager: '项目经理', project_specialist: '项目专员', project_assistant: '项目助理' }
  return (row.roleAssignments || []).map((item) => `${labels[item.roleCode] || item.roleName}：${item.assigneeName || '未分配'}`).join('；') || '-'
}
const arrayText = (value, separator = '；') => Array.isArray(value) && value.length ? value.join(separator) : '-'
const formatRange = (item) => {
  const scheduled = `${formatDateTime(item.scheduledStart)} 至 ${formatDateTime(item.scheduledEnd)}`
  const actual = item.actualStart || item.actualEnd ? `；实际 ${formatDateTime(item.actualStart)} 至 ${formatDateTime(item.actualEnd)}` : ''
  return `${scheduled}${actual}`
}
const timeRangesText = (items) => Array.isArray(items) && items.length ? items.map(formatRange).join('；') : '-'
const projectTypesText = (row) => Array.isArray(row.projectTypes) && row.projectTypes.length ? row.projectTypes.map((value) => projectTypeMap[value] || value).join('；') : '-'
const ratingText = (rating, note) => [ratingMap[rating] || rating, note].filter(Boolean).join('：') || '-'
const interpreterRatingsText = (items) => Array.isArray(items) && items.length
  ? items.map((item) => `${item.translatorName}：${ratingText(item.customerRating, item.evaluationNote)}`).join('；')
  : '-'
const tableCellText = (row, key) => {
  if (key === 'projectTypes') return projectTypesText(row)
  if (key === 'timeRanges') return timeRangesText(row.timeRanges)
  if (key === 'locations') return arrayText(row.locations, '、')
  if (key === 'customerConsultationTime' || key === 'customerConfirmationTime' || key === 'createdAt' || key === 'updatedAt') {
    return formatDateTime(row[key])
  }
  if (key === 'clientRating') return ratingText(row.clientRating, null)
  if (key === 'interpreterAssignments') return interpreterRatingsText(row.interpreterAssignments)
  return textValue(row[key])
}
const translatorOptionLabel = (item) => {
  const name = item.fullName || item.translator_name || item.translatorName
  const code = item.resourceCode || item.translator_code || item.translatorCode
  const level = item.interpretation_level || item.interpretationLevel || item.translatorInterpretationLevel
  return `${name || item.id}${code ? `（${code}）` : ''}${level ? ` · ${level}` : ''}${item.isHistorical ? ' · 已安排' : ''}`
}

const buildFilters = () => {
  return {
    keyword: searchForm.keyword.trim() || undefined,
    field_filters: serializeFieldFilters(searchForm, interpretationFilterFields),
  }
}
const fetchData = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const currentId = ++requestId
  loading.value = true
  const filters = buildFilters()
  try {
    const [rows, count] = await Promise.all([
      projectApi.getInterpretationProjects({ skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit, ...filters }, { signal: requestController.signal }),
      projectApi.getInterpretationProjectCount(filters, { signal: requestController.signal }),
    ])
    if (currentId !== requestId) return
    tableData.value = Array.isArray(rows) ? rows : []
    pagination.total = count?.total || 0
  } catch (error) {
    if (currentId !== requestId || error?.code === 'ERR_CANCELED') return
    ElMessage.error(error.detail || '网络异常，口译项目列表未刷新，请检查网络后重试')
  } finally {
    if (currentId === requestId) loading.value = false
  }
}
const handleSearch = () => { exitDeleteMode(); clearTimeout(searchTimer); pagination.page = 1; fetchData() }
const handleTextSearch = (value) => {
  clearTimeout(searchTimer)
  if (!value?.trim()) return handleSearch()
  searchTimer = setTimeout(handleSearch, 400)
}
const updateConfiguredFilter = (key, value) => { searchForm[key] = value }
const handleConfiguredTextInput = (value) => handleTextSearch(value)
const resetSearch = () => { searchForm.keyword = ''; resetFilterModel(searchForm, interpretationFilterFields); handleSearch() }
const clearAdvanced = () => { resetFilterModel(searchForm, interpretationAdvancedFilterFields); handleSearch() }

const loadReferenceData = async () => {
  const [clientRows, translatorRows, languageRows] = await Promise.allSettled([
    clientApi.getClients({ skip: 0, limit: 500, frequent_first: true }),
    getProjectTalentOptions('interpretation'),
    projectApi.getInterpretationLanguages({ include_inactive: true }),
  ])
  clients.value = clientRows.status === 'fulfilled' && Array.isArray(clientRows.value) ? clientRows.value : []
  translators.value = translatorRows.status === 'fulfilled' && Array.isArray(translatorRows.value) ? translatorRows.value : []
  languages.value = languageRows.status === 'fulfilled' && Array.isArray(languageRows.value) ? languageRows.value : []
}
const loadDetail = async (id, force = false) => {
  if (!id) return null
  if (!force && detailCache[id]) return detailCache[id]
  detailLoadingId.value = id
  try {
    const detail = await projectApi.getInterpretationProject(id)
    detailCache[id] = detail
    return detail
  } catch (error) {
    ElMessage.error(error.detail || '加载项目详情失败')
    return null
  } finally {
    detailLoadingId.value = null
  }
}
const detailRow = (row) => detailCache[row.id] || row
const cancelInlineDetailEdit = () => window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
const saveDetailTextField = async (row, field, value) => {
  const current = detailRow(row)
  const updated = await projectApi.updateInterpretationProjectTextField(row.id, field, value, current.updatedAt)
  detailCache[row.id] = updated
  Object.assign(row, updated)
  if (Object.values(buildFilters()).some(Boolean)) void fetchData()
  return updated
}
const projectRowClass = ({ row }) => String(row.id) === highlightedProjectId.value ? 'workbench-target-row' : ''
const focusRouteProject = async (editorReady = Promise.resolve()) => {
  const projectId = String(route.query.projectId || '')
  if (!projectId) return
  const detail = await loadDetail(projectId)
  if (!detail) return
  highlightedProjectId.value = projectId
  searchForm.keyword = detail.orderNo || ''
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
}

const fetchClientSuggestions = fetchProjectClientSuggestions
const handleClientSelect = (client) => {
  form.clientId = client.parent_client_id || client.id || ''
  form.subClientId = client.sub_client_id || ''
  form.clientShortName = client.client_short_name || ''
  form.clientFullName = client.client_name || ''
  form.clientCode = client.client_code || ''
  form.clientDomain = client.client_domain || ''
  form.currentClientManager = client.client_manager || ''
  form.managerContact = client.manager_contact || ''
}
const handleClientShortNameInput = () => {
  const hadSelectedClient = Boolean(form.clientId || form.subClientId)
  form.clientId = ''
  form.subClientId = ''
  form.clientCode = ''
  form.clientDomain = ''
  form.currentClientManager = ''
  form.managerContact = ''
  if (hadSelectedClient) form.clientFullName = ''
}
const clearSelectedClient = () => {
  form.clientId = ''
  form.subClientId = ''
  form.clientShortName = ''
  form.clientFullName = ''
  form.clientCode = ''
  form.clientDomain = ''
  form.currentClientManager = ''
  form.managerContact = ''
}
const addTimeRange = () => form.timeRanges.push(emptyTimeRange())
const addLocation = () => {
  if (form.locations.length < MAX_LOCATIONS) form.locations.push('')
}
const removeLocation = (index) => {
  if (form.locations.length > 1) form.locations.splice(index, 1)
}
const addInterpreter = () => form.interpreterAssignments.push({ translatorId: '', customerRating: '', evaluationNote: '' })
const sortLanguages = () => languages.value.sort((a, b) => (
  Number(a.isActive === false) - Number(b.isActive === false)
  || Number(a.isCustom) - Number(b.isCustom)
  || a.label.localeCompare(b.label, 'zh-CN')
))
const replaceLanguage = (updated) => {
  const index = languages.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) languages.value.splice(index, 1, updated)
  else languages.value.push(updated)
  sortLanguages()
}
const openLanguageManager = async () => {
  languageManagerVisible.value = true
  languageManagerLoading.value = true
  try {
    languages.value = await projectApi.getInterpretationLanguages({ include_inactive: true })
    sortLanguages()
  } catch (error) {
    ElMessage.error(error.detail || '加载语种目录失败')
  } finally {
    languageManagerLoading.value = false
  }
}
const addLanguage = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要新增的语种或方言名称', '新增口译语种', {
      inputPlaceholder: '例如：粤语', inputValidator: (text) => !!text?.trim() || '语种名称不能为空',
    })
    const created = await projectApi.createInterpretationLanguage(value.trim())
    replaceLanguage(created)
    ElMessage.success('语种已新增')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || '新增语种失败')
  }
}
const renameLanguage = async (language) => {
  try {
    const { value } = await ElMessageBox.prompt('修改后，所有引用该语种的项目都会显示新名称。', '重命名语种', {
      inputValue: language.label,
      inputPlaceholder: '请输入语种或方言名称',
      inputValidator: (text) => !!text?.trim() || '语种名称不能为空',
      confirmButtonText: '保存',
    })
    const updated = await projectApi.updateInterpretationLanguage(language.id, { label: value.trim() })
    replaceLanguage(updated)
    ElMessage.success('语种名称已更新')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || '修改语种失败')
  }
}
const toggleLanguage = async (language, isActive) => {
  try {
    if (!isActive) {
      await ElMessageBox.confirm(
        `停用“${language.label}”后，新项目将无法选择该语种，历史项目不受影响。确定继续吗？`,
        '停用语种',
        { type: 'warning', confirmButtonText: '确定停用' }
      )
    }
    const updated = await projectApi.updateInterpretationLanguage(language.id, { isActive })
    replaceLanguage(updated)
    ElMessage.success(isActive ? '语种已重新启用' : '语种已停用')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || '更新语种状态失败')
  }
}

const normalizedNestedPayload = () => ({
  timeRanges: form.timeRanges.filter((item) => item.scheduledStart || item.scheduledEnd).map((item) => ({
    scheduledStart: item.scheduledStart,
    scheduledEnd: item.scheduledEnd,
    actualStart: item.actualStart || null,
    actualEnd: item.actualEnd || null,
  })),
  languageDirections: form.languageDirections.filter((item) => item.languageIds.some(Boolean) || item.requiredCount).map((item) => ({
    languageIds: item.languageIds,
    requiredCount: item.requiredCount,
  })),
  interpreterAssignments: form.interpreterAssignments.filter((item) => item.translatorId).map((item) => ({
    translatorId: item.translatorId,
    customerRating: item.customerRating || null,
    evaluationNote: item.evaluationNote?.trim() || null,
  })),
})
const validateNested = (nested) => {
  if (form.timeRanges.some((item) => (item.scheduledStart || item.scheduledEnd) && (!item.scheduledStart || !item.scheduledEnd))) throw new Error('每个时间段必须同时填写预定开始和预定结束')
  if (nested.timeRanges.some((item) => new Date(item.scheduledEnd) < new Date(item.scheduledStart))) throw new Error('预定结束时间不能早于预定开始时间')
  if (form.languageDirections.some((item) => (item.languageIds.some(Boolean) || item.requiredCount) && (item.languageIds.length < 2 || item.languageIds.length > 5 || item.languageIds.some((id) => !id)))) throw new Error('每个口译方向必须完整选择 2 至 5 个语种')
  if (nested.languageDirections.some((item) => !Number.isInteger(item.requiredCount) || item.requiredCount < 1)) throw new Error('每个口译方向都必须填写大于等于 1 的需求人数')
  if (nested.languageDirections.some((item) => new Set(item.languageIds).size !== item.languageIds.length)) throw new Error('同一口译方向内的语种不能重复')
  const directionKeys = nested.languageDirections.map((item) => [...item.languageIds].sort().join(':'))
  if (new Set(directionKeys).size !== directionKeys.length) throw new Error('同一双向口译方向不能重复')
  const translatorIds = nested.interpreterAssignments.map((item) => item.translatorId)
  if (new Set(translatorIds).size !== translatorIds.length) throw new Error('同一译员不能重复安排')
}
const projectNamePayload = () => {
  const nested = normalizedNestedPayload()
  return {
    projectTypes: form.projectTypes,
    locations: form.locations.filter((item) => item?.trim()).map((item) => item.trim()),
    timeRanges: nested.timeRanges,
    languageDirections: nested.languageDirections,
  }
}
const hasCompleteProjectNameSource = (payload) => (
  payload.projectTypes.length > 0
  && payload.locations.length > 0
  && payload.timeRanges.length > 0
  && payload.languageDirections.length > 0
  && payload.timeRanges.every((item) => item.scheduledStart && item.scheduledEnd)
  && payload.languageDirections.every((item) => item.languageIds.length >= 2 && item.languageIds.every(Boolean))
)
const previewProjectName = async ({ automatic = false } = {}) => {
  const payload = projectNamePayload()
  if (automatic && !hasCompleteProjectNameSource(payload)) return
  const currentRequestId = ++namePreviewRequestId
  if (!automatic) nameLoading.value = true
  try {
    const result = await projectApi.previewInterpretationProjectName(payload)
    if (currentRequestId !== namePreviewRequestId || (automatic && nameManuallyEdited.value)) return
    form.projectName = result.projectName
    nameManuallyEdited.value = false
    if (!automatic) ElMessage.success('项目名称已重新生成，仍可手工修改')
  } catch (error) {
    if (!automatic) ElMessage.warning(getLocalizedErrorMessage(error, '无法生成项目名称'))
  } finally {
    if (!automatic) nameLoading.value = false
  }
}
const generateProjectName = () => previewProjectName()
const generateEmailSubject = () => notifyEmailSubjectGenerated(form, ElMessage)
const handleProjectNameInput = () => {
  nameManuallyEdited.value = true
  namePreviewRequestId += 1
}

const buildPayload = () => {
  const nested = normalizedNestedPayload()
  validateNested(nested)
  return {
    projectName: form.projectName?.trim() || null,
    projectTypes: form.projectTypes,
    taskDescription: form.taskDescription?.trim() || null,
    clientId: form.clientId || null,
    subClientId: form.subClientId || null,
    clientName: form.clientFullName?.trim() || null,
    clientShortName: form.clientShortName?.trim() || null,
    clientCode: form.clientCode?.trim() || null,
    managerContact: form.managerContact?.trim() || null,
    contactName: form.contactName?.trim() || null,
    customerOrderNo: form.customerOrderNo?.trim() || null,
    projectStatus: form.projectStatus,
    locations: form.locations.filter((item) => item?.trim()).map((item) => item.trim()),
    customerBudget: form.customerBudget?.trim() || null,
    requiredInterpreterGender: form.requiredInterpreterGender || null,
    requiredInterpretationLevel: form.requiredInterpretationLevel || null,
    interpreterSpecialRequirements: form.interpreterSpecialRequirements?.trim() || null,
    interpreterHeightRequirement: form.interpreterHeightRequirement?.trim() || null,
    interpreterAppearanceRequirement: form.interpreterAppearanceRequirement?.trim() || null,
    interpreterDressRequirement: form.interpreterDressRequirement?.trim() || null,
    customerConsultationTime: form.customerConsultationTime || null,
    customerConfirmationTime: form.customerConfirmationTime || null,
    interpretationDomain: form.interpretationDomain?.trim() || null,
    interpretationContent: form.interpretationContent?.trim() || null,
    filePath: form.filePath?.trim() || null,
    quotationPath: form.quotationPath?.trim() || null,
    contractPath: form.contractPath?.trim() || null,
    clientRating: form.clientRating || null,
    clientRatingNote: form.clientRatingNote?.trim() || null,
    remarks: form.remarks?.trim() || null,
    emailSubjectPreview: form.emailSubjectPreview?.trim() || null,
    expectedUpdatedAt: form.updatedAt || null,
    socialPostRequest: form.socialPostRequest?.trim() || null,
    resourceRequest: form.resourceRequest?.trim() || null,
    roleAssignments: form.roleAssignments,
    ...nested,
  }
}
const assignForm = (detail) => {
  const client = clients.value.find((item) => item.id === detail.clientId)
  const knownTranslatorIds = new Set(translators.value.map((item) => item.id))
  for (const item of detail.interpreterAssignments || []) {
    if (!knownTranslatorIds.has(item.translatorId)) {
      translators.value.push({
        id: item.translatorId,
        fullName: item.translatorName,
        resourceCode: item.translatorCode,
        interpretationLevel: item.translatorInterpretationLevel,
        isHistorical: true,
      })
      knownTranslatorIds.add(item.translatorId)
    }
  }
  Object.assign(form, defaultForm(), {
    ...detail,
    projectName: detail.projectName || '',
    clientId: detail.clientId || '', subClientId: detail.subClientId || '',
    clientShortName: detail.clientShortName || '', clientFullName: detail.clientFullName || '', clientCode: detail.clientCode || '',
    clientDomain: detail.clientDomain || '',
    currentClientManager: detail.currentClientManager || '',
    managerContact: detail.managerContact || client?.manager_contact || '',
    requiredInterpreterGender: detail.requiredInterpreterGender || '',
    requiredInterpretationLevel: detail.requiredInterpretationLevel || '',
    interpreterSpecialRequirements: detail.interpreterSpecialRequirements || '',
    interpreterHeightRequirement: detail.interpreterHeightRequirement || '',
    interpreterAppearanceRequirement: detail.interpreterAppearanceRequirement || '',
    interpreterDressRequirement: detail.interpreterDressRequirement || '',
    locations: detail.locations?.length ? detail.locations.slice(0, MAX_LOCATIONS) : [''],
    customerConsultationTime: detail.customerConsultationTime || '', customerConfirmationTime: detail.customerConfirmationTime || '',
    timeRanges: detail.timeRanges?.length ? detail.timeRanges.map((item) => ({ scheduledStart: item.scheduledStart, scheduledEnd: item.scheduledEnd, actualStart: item.actualStart || '', actualEnd: item.actualEnd || '' })) : [emptyTimeRange()],
    languageDirections: detail.languageDirections?.length
      ? detail.languageDirections.map((item) => ({ languageIds: item.languageIds?.length ? item.languageIds : [item.sourceLanguageId, item.targetLanguageId], requiredCount: item.requiredCount ?? null }))
      : [emptyLanguageDirection()],
    interpreterAssignments: (detail.interpreterAssignments || []).map((item) => ({ translatorId: item.translatorId, customerRating: item.customerRating || '', evaluationNote: item.evaluationNote || '' })),
    roleAssignments: detail.roleAssignments || [],
  })
  form.subjectPrefix = extractSubjectPrefix(detail.emailSubjectPreview, form)
  nameManuallyEdited.value = Boolean(detail.projectName)
}
const resetEditorScroll = async () => { await nextTick(); dialogBodyRef.value?.parentElement?.scrollTo({ top: 0, behavior: 'auto' }) }
const handleAdd = async () => { dialogTitle.value = '新增口译项目'; resetForm(); projectCreateIdempotencyKey.value = createIdempotencyKey(); dialogVisible.value = true; await resetEditorScroll(); await beginDraft('create') }
const handleEdit = async (row, useProvidedDetail = false) => {
  const detail = useProvidedDetail ? row : await loadDetail(row.id, true)
  if (!detail) return
  dialogTitle.value = `编辑口译项目 · ${detail.orderNo}`
  assignForm(detail)
  dialogVisible.value = true
  await resetEditorScroll()
  await beginDraft(`edit:${detail.id}`)
}
const handleSubmit = async (sendAfterSave = false) => {
  if (submitLocked) return
  submitLocked = true
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    await nextTick()
    dialogBodyRef.value?.querySelector('.is-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    submitLocked = false
    return
  }
  submitLoading.value = true
  try {
    const payload = buildPayload()
    const saved = form.id
      ? await projectApi.updateInterpretationProject(form.id, payload)
      : await projectApi.createInterpretationProject(payload, projectCreateIdempotencyKey.value)
    if (form.id) delete detailCache[form.id]
    if (saved?.id) detailCache[saved.id] = saved
    ElMessage.success(form.id ? '口译项目已更新' : '口译项目已创建')
    clearDraft()
    dialogVisible.value = false
    if (sendAfterSave) {
      mailProjectId.value = saved?.id || form.id
      mailConsultationId.value = saved?.consultationId || form.consultationId || ''
      mailComposerVisible.value = true
    }
    await fetchData()
  } catch (error) {
    const message = getLocalizedErrorMessage(error, '保存失败')
    ElMessage.error(message)
    if (message.includes('时间')) dialogBodyRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    submitLoading.value = false
    submitLocked = false
  }
}
const setProjectStatusSaving = (id, saving) => {
  const next = new Set(projectStatusSavingIds.value)
  if (saving) next.add(id)
  else next.delete(id)
  projectStatusSavingIds.value = next
}
const changeProjectStatus = async (row, value) => {
  if (!value || value === row.projectStatus) return
  setProjectStatusSaving(row.id, true)
  try {
    const updated = await projectApi.updateInterpretationProjectStatus(row.id, value)
    Object.assign(row, updated)
    detailCache[row.id] = updated
    ElMessage.success('项目状态已更新')
    if (searchForm.projectStatus?.length && !searchForm.projectStatus.includes(updated.projectStatus)) await fetchData()
  } catch (error) {
    ElMessage.error(error?.detail || '项目状态更新失败')
  } finally {
    setProjectStatusSaving(row.id, false)
  }
}
const resetForm = () => { Object.assign(form, defaultForm()); nameManuallyEdited.value = false; formRef.value?.clearValidate(); clearFieldSearch() }
const onEditorClosed = () => { pauseDraft(); resetForm() }

watch(
  () => [form.projectTypes, form.locations, form.timeRanges, form.languageDirections],
  () => {
    clearTimeout(autoNameTimer)
    if (nameManuallyEdited.value || !dialogVisible.value) return
    autoNameTimer = setTimeout(() => previewProjectName({ automatic: true }), 400)
  },
  { deep: true },
)

const openPathValue = (path) => {
  if (!path?.trim()) return ElMessage.warning('暂无可打开的路径')
  if (!launchOpenPath(path.trim())) ElMessage.error('该路径不在企业允许的网络目录中，已阻止打开')
}
const copyPathValue = async (path) => {
  if (!path?.trim()) return ElMessage.warning('暂无可复制的路径')
  try { await navigator.clipboard.writeText(path.trim()); ElMessage.success('路径已复制') } catch { ElMessage.error('复制失败，请手工复制') }
}
const projectPath = async (row) => (await loadDetail(row.id))?.filePath || ''
const openProjectPath = async (row) => openPathValue(await projectPath(row))
const copyProjectPath = async (row) => copyPathValue(await projectPath(row))

onMounted(async () => {
  const editorReady = Promise.all([loadReferenceData(), loadResourceRequestStatuses()])
  if (route.query.projectId) {
    await focusRouteProject(editorReady)
    return
  }
  await editorReady
  await fetchData()
})
watch(
  () => [route.query.projectId, route.query.openEditor],
  ([projectId, openEditor], [previousProjectId, previousOpenEditor]) => {
    if (projectId && (projectId !== previousProjectId || (openEditor === '1' && previousOpenEditor !== '1'))) {
      void focusRouteProject()
    }
  }
)
onBeforeUnmount(() => { clearTimeout(searchTimer); clearTimeout(autoNameTimer); requestController?.abort() })
</script>

<style scoped>
:deep(.workbench-target-row > td.el-table__cell) { background: var(--el-color-primary-light-9) !important; }
.client-autocomplete-field { width: 100%; }
.client-autocomplete-hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.client-suggestion { display: flex; flex-direction: column; min-width: 0; padding: 4px 0; line-height: 1.45; }
.client-suggestion__meta { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.card-header, .header-actions, .advanced-header, .section-title-row, .repeat-title, .order-cell { display: flex; align-items: center; }
.card-header, .advanced-header, .section-title-row, .repeat-title { justify-content: space-between; }
.header-actions { display: flex; gap: 8px; }
.search-form { margin-bottom: 4px; }
.filter-count { display: inline-flex; min-width: 18px; height: 18px; margin-left: 5px; padding: 0 5px; align-items: center; justify-content: center; border-radius: 9px; color: #fff; background: var(--el-color-primary); font-size: 11px; }
.advanced-panel { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced-header { margin-bottom: 12px; font-weight: 600; }
.pagination { margin-top: 20px; }
.order-cell { min-width: 0; gap: 4px; }
.order-cell :deep(.el-popover__reference-wrapper) { flex: 1; min-width: 0; }
.order-cell :deep(.path-action-buttons) { width: 40px; min-width: 40px; }
.order-cell :deep(.path-action-buttons .el-button) { width: 19px; height: 22px; }
.order-no-link { display: block; width: 100%; height: auto; min-width: 0; padding: 0; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.editor-body { min-height: 0; }
.form-section { margin-bottom: 18px; padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-fill-color-blank); }
.form-section h3 { margin: 0 0 16px; font-size: 16px; }
.form-section h4 { margin: 0; font-size: 15px; }
.interpretation-key-fields { border-color: var(--el-color-primary-light-7); background: var(--el-color-primary-light-9); }
.interpretation-key-fields__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.interpretation-key-fields__header h3 { margin-bottom: 0; }
.interpretation-key-fields__header p { margin: 3px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.composite-required-item :deep(.el-form-item__content), .direction-panel { width: 100%; }
.composite-required-item .location-panel { width: 100%; margin-top: 0; }
.section-title-row { margin-bottom: 12px; }
.section-title-row h3 { margin-bottom: 0; }
.repeat-card { margin-bottom: 12px; padding: 12px 12px 0; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-light); }
.location-panel { margin: 4px 0 18px; padding: 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-fill-color-light); }
.location-panel__header, .location-item__header { display: flex; align-items: center; justify-content: space-between; }
.location-panel__header { gap: 16px; margin-bottom: 12px; }
.location-panel__hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.location-list { margin-bottom: -12px; }
.location-list .el-col { margin-bottom: 12px; }
.location-item { height: 100%; padding: 10px 12px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-blank); }
.location-item__header { min-height: 28px; margin-bottom: 6px; color: var(--el-text-color-regular); font-size: 13px; font-weight: 600; }
.interpreter-requirement-group { margin: 4px 0 16px; padding: 14px 14px 0; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-light); }
.requirement-group-title { margin-bottom: 12px; color: var(--el-text-color-regular); font-weight: 600; }
.repeat-title { margin-bottom: 8px; color: var(--el-text-color-regular); font-weight: 600; }
.project-name-cell { display: block; white-space: normal; overflow-wrap: anywhere; line-height: 1.5; }
.status-switch-tag.el-tag { display: inline-flex; min-width: 92px; max-width: 100%; align-items: center; justify-content: center; gap: 4px; flex-wrap: nowrap; cursor: pointer; user-select: none; vertical-align: middle; transition: opacity .15s ease; }
.status-switch-tag :deep(.el-tag__content) { display: inline-flex; width: 100%; align-items: center; justify-content: center; gap: 4px; flex-wrap: nowrap; white-space: nowrap; line-height: 1; }
.status-switch-text { line-height: 1; }
.status-switch-caret { width: 10px; height: 10px; flex-shrink: 0; margin: 0; font-size: 10px; }
.status-switch-tag:hover { opacity: .85; }
.status-switch-tag.is-updating { pointer-events: none; opacity: .55; }
.status-option-row { display: inline-flex; width: 100%; align-items: center; gap: 8px; }
.status-current-icon { color: var(--el-color-primary); }
.soft-action-button { --el-button-bg-color: var(--el-color-primary-light-9); --el-button-border-color: var(--el-color-primary-light-7); --el-button-text-color: var(--el-color-primary-dark-2); --el-button-hover-bg-color: var(--el-color-primary-light-8); --el-button-hover-border-color: var(--el-color-primary-light-5); --el-button-hover-text-color: var(--el-color-primary); flex: none; font-weight: 500; }
.subject-preview-field { width: 100%; min-width: 0; }
.subject-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.subject-preview-toolbar .el-button { flex: none; }
.interpreter-add-button { width: 100%; margin-top: 4px; border-style: dashed; color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.interpreter-add-button:hover { border-style: dashed; background: var(--el-color-primary-light-8); }
.new-language-tag { float: right; margin-left: 8px; }
.language-type-tag { margin-left: 8px; }
.language-manager-hint { margin-bottom: 14px; padding: 10px 12px; border-radius: 6px; color: var(--el-text-color-regular); background: var(--el-fill-color-light); line-height: 1.6; }
.readonly-language { color: var(--el-text-color-secondary); }
.remarks-form-item :deep(textarea) { min-height: 120px; }
:deep(.path-input) { display: flex; width: 100%; gap: 8px; }
:deep(.path-input .el-input) { flex: 1; }
</style>

<style>
.interpretation-advanced-popover, .interpretation-detail-popover, .interpretation-client-popover, .interpretation-interpreter-popover { max-width: calc(100vw - 32px) !important; }
.interpretation-client-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-interpreter-popover .interpreter-detail-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.interpretation-interpreter-popover .interpreter-detail-section-title { margin: 14px 0 8px; color: var(--el-text-color-primary); font-weight: 600; }
.interpretation-interpreter-popover .interpreter-detail-section-title:first-child { margin-top: 0; }
.interpretation-interpreter-popover .translator-profile { margin-bottom: 12px; }
.interpretation-interpreter-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-detail-popover .detail-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.interpretation-detail-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-detail-popover .remarks-detail { min-height: 88px; white-space: pre-wrap; }
.interpretation-editor-dialog { display: flex; max-height: 90vh; flex-direction: column; overflow: hidden; }
.interpretation-editor-dialog .el-dialog__header,
.interpretation-editor-dialog .el-dialog__footer { flex: 0 0 auto; }
.interpretation-editor-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; padding-top: 12px; }
.interpretation-editor-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -3px 10px rgba(0, 0, 0, 0.04); }
.language-manager-dialog { display: flex; max-height: 84vh; flex-direction: column; overflow: hidden; }
.language-manager-dialog .el-dialog__header,
.language-manager-dialog .el-dialog__footer { flex: 0 0 auto; }
.language-manager-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
@media (max-width: 768px) {
  .interpretation-card .search-form .el-form-item { display: flex; width: 100%; margin-right: 0; }
  .interpretation-card .search-form .el-input, .interpretation-card .search-form .el-select { width: 100% !important; }
  .location-panel__header { align-items: flex-start; flex-direction: column; }
  .location-panel__header .el-button { width: 100%; }
}
</style>
