<template>
  <el-card class="compact-list-card">
    <template #header>
      <div class="card-header">
        <span>招聘项目详情</span>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite && !deleteMode" type="primary" @click="openAdd">新增招聘项目</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键字"><el-input v-model="searchForm.keyword" clearable placeholder="项目、客户、职位或属地" @input="handleTextSearch" @keyup.enter="handleSearch" /></el-form-item>
      <el-form-item label="项目状态"><el-select v-model="searchForm.projectStatus" clearable placeholder="全部" style="width: 180px" @change="handleSearch"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button><el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" width="min(760px, calc(100vw - 32px))" popper-class="recruitment-advanced-filter-popover">
          <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
          <div class="advanced-content">
            <el-form :model="searchForm" label-width="110px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><el-select v-model="searchForm.clientManagerId" clearable filterable style="width:100%" @change="handleSearch"><el-option v-for="user in activeUsers" :key="user.id" :label="userLabel(user)" :value="user.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="履职日期范围"><el-date-picker v-model="searchForm.employmentRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户/子客户"><el-select v-model="searchForm.clientSelection" clearable filterable style="width:100%" @change="handleSearch"><el-option v-for="item in clientOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="外语/翻译方向"><el-select v-model="searchForm.languageId" clearable filterable style="width:100%" @change="handleSearch"><el-option v-for="item in languages" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="拟入职日期范围"><el-date-picker v-model="searchForm.targetOnboardRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="创建时间范围"><el-date-picker v-model="searchForm.createdRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" @change="handleSearch" /></el-form-item></el-col>
              </el-row>
            </el-form>
            <div class="advanced-footer"><el-button link @click="clearAdvanced">清空高级条件</el-button><el-button type="primary" @click="advancedVisible=false">关闭</el-button></div>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table ref="projectTableRef" :data="rows" v-loading="loading" :row-class-name="projectRowClass" border row-key="id" class="recruitment-list-table project-detail-list-table" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column label="序号" :width="PROJECT_LIST_COLUMN_WIDTHS.index" align="center"><template #default="{ $index }">{{ (pagination.page - 1) * pagination.limit + $index + 1 }}</template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="column.tooltip !== false">
        <template #header>
          <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
          <span v-else>{{ column.label }}</span>
        </template>
        <template #default="{ row }">
          <div v-if="column.key === 'orderNo'" class="order-cell">
            <BusinessDetailPopover :row="row" title="招聘项目详情" :items="detailItems" :status-label="statusLabel" :status-type="statusType">
              <template #reference><el-button type="primary" link class="order-no-link business-clickable-cell" :title="row.orderNo" @click.stop>{{ row.orderNo }}</el-button></template>
            </BusinessDetailPopover>
            <PathActionButtons @open="openPath(row.projectPath)" @copy="copyPath(row.projectPath)" />
          </div>
          <el-button v-else-if="column.key === 'projectName'" type="primary" link class="wrap-link business-clickable-cell" @click="openProgress(row)">{{ row.projectName || '待生成' }}</el-button>
          <el-popover v-else-if="column.key === 'jobDescription'" trigger="click" placement="left" :width="560">
            <template #reference><el-button type="primary" link class="description-preview business-clickable-cell">{{ row.jobDescription || '-' }}</el-button></template>
            <div class="long-text-detail">{{ row.jobDescription || '-' }}</div>
          </el-popover>
          <el-popover v-else-if="column.key === 'clientShortName'" trigger="click" placement="left" :width="420">
            <template #reference><el-button type="primary" link class="business-clickable-cell">{{ row.clientShortName || '-' }}</el-button></template>
            <el-descriptions title="客户关联信息" :column="1" border size="small">
              <el-descriptions-item label="子客户/联系人">{{ displayValue(row.contactName) }}</el-descriptions-item>
              <el-descriptions-item label="客户单号/项目标识">{{ displayValue(row.customerOrderNo) }}</el-descriptions-item>
            </el-descriptions>
          </el-popover>
          <el-dropdown
            v-else-if="column.key === 'projectStatus' && canWrite"
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
                    <el-tag :type="statusType(item.value)" size="small" effect="plain" class="status-option-tag">{{ item.label }}</el-tag>
                    <el-icon v-if="item.value === row.projectStatus" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tag v-else-if="column.key === 'projectStatus'" :type="statusType(row.projectStatus)">{{ statusLabel(row.projectStatus) }}</el-tag>
          <el-button v-else-if="column.key === 'candidateCount'" type="primary" link class="business-clickable-cell candidate-count-link" @click="openCandidates(row)">
            <span>{{ row.candidateCount || 0 }} 人</span><el-icon><ArrowRight /></el-icon>
          </el-button>
          <span v-else-if="column.key === 'headcount'">{{ headcountText(row) }}</span>
          <span v-else-if="column.key === 'languageSummary'">{{ languageText(row) }}</span>
          <span v-else-if="column.key === 'employmentPeriod'" class="employment-period-text">{{ periodText(row) }}</span>
          <span v-else-if="column.key === 'targetOnboard'">{{ row.targetOnboardType === 'anytime' ? '随时' : formatDate(row.targetOnboardDate) }}</span>
          <span v-else-if="column.key === 'serviceFee'">{{ feeText(row) }}</span>
          <span v-else-if="dateTimeColumnKeys.has(column.key)">{{ formatDateTime(row[column.key]) }}</span>
          <span v-else>{{ displayValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" width="170" fixed="right" align="center"><template #default="{ row }"><div v-if="canWrite" class="action-buttons"><el-button link type="primary" @click="startResourceRequest(row)">发起需求</el-button><TableActionButton action="edit" @click="openEdit(row)" /></div></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @current-change="fetchData" @size-change="handleSizeChange" />

    <el-dialog v-model="editorVisible" width="min(1000px, calc(100vw - 32px))" top="5vh" class="recruitment-editor" @closed="resetForm">
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          v-model="fieldSearchKeyword"
          :title="editorTitle"
          subtitle="集中维护职位、客户、招聘要求和项目资料"
          :fetch-suggestions="fetchFieldSuggestions"
          @select="locateDialogField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="editorBodyRef" class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="140px" class="recruitment-form">
          <div class="form-section"><h3>项目与职位</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><ReadonlyField :model-value="form.orderNo" source="auto" placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="项目状态" prop="projectStatus"><el-select v-model="form.projectStatus" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16"><el-col :span="24"><el-form-item label="项目名称"><GeneratedProjectNameInput v-model="form.projectName" placeholder="可手工填写，或根据招聘信息自动生成" :loading="nameLoading" @manual-input="handleProjectNameInput" @regenerate="generateName" /></el-form-item></el-col></el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="职位名称/类型" prop="positionTitle"><el-input v-model="form.positionTitle" placeholder="例如：法语翻译、海外销售" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="招聘人数" prop="headcountMin"><div class="number-range"><el-input-number v-model="form.headcountMin" :min="0" :controls="false" placeholder="最低人数" /><span class="range-separator">—</span><el-input-number v-model="form.headcountMax" :min="form.headcountMin || 0" :controls="false" placeholder="最高人数" /><span class="range-unit">人</span></div></el-form-item></el-col>
            </el-row>
            <el-form-item label="职位描述">
              <div class="job-description-editor">
                <el-input v-model="form.jobDescription" type="textarea" :autosize="{ minRows: 7, maxRows: 14 }" placeholder="填写岗位职责、任职要求和补充说明" />
                <div class="job-description-toolbar">
                  <span>{{ (form.jobDescription || '').length }} 字符，支持粘贴较长的职位说明</span>
                  <el-button class="soft-action-button" :icon="FullScreen" @click="jobDescriptionEditorVisible=true">大窗编辑</el-button>
                </div>
              </div>
            </el-form-item>
          </div>

          <div class="form-section"><h3>客户信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="客户简称" data-field-key="clientShortName">
                  <div class="client-autocomplete-field">
                    <el-autocomplete v-model="form.clientShortName" :fetch-suggestions="fetchClientSuggestions" value-key="client_short_name" placeholder="选择已有客户，或直接输入新客户简称" clearable :debounce="300" :trigger-on-focus="true" style="width:100%" @select="handleClientSelect" @input="handleClientShortNameInput" @clear="clearSelectedClient">
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
              <el-col :xs="24" :md="12"><el-form-item label="子客户/联系人"><el-input v-model="form.contactName" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户编号"><ReadonlyField v-model="form.clientCode" :source="form.clientId ? 'auto' : 'editable'" :placeholder="form.clientId ? '选择客户后自动带出' : '新客户不填则自动生成'" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户全称"><ReadonlyField v-model="form.clientName" :source="form.clientId ? 'auto' : 'editable'" :placeholder="form.clientId ? '选择客户后自动带出' : '新客户可补充全称'" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户领域"><ReadonlyField :model-value="form.clientDomain" source="auto" placeholder="选择客户后自动带出" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户单号/项目标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="负责人联系方式"><ReadonlyField :model-value="form.managerContact" source="auto" placeholder="选择客户后自动带出" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><el-select v-model="form.clientManagerId" filterable clearable style="width:100%"><el-option v-for="user in managerUserOptions" :key="user.id" :label="userOptionLabel(user)" :value="user.id" :disabled="!user.is_active" /></el-select></el-form-item></el-col>
            </el-row>
          </div>

          <div class="form-section"><h3>招聘要求</h3>
            <el-form-item label="外语/翻译方向"><RecruitmentLanguageDirections v-model="form.languageDirections" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="拟履职周期" prop="employmentRange"><el-date-picker v-model="form.employmentRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="任职工作属地" prop="workLocation"><el-input v-model="form.workLocation" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="拟入职时间"><el-radio-group v-model="form.targetOnboardType"><el-radio value="date">具体日期</el-radio><el-radio value="anytime">随时</el-radio></el-radio-group></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="拟入职日期"><el-date-picker v-model="form.targetOnboardDate" value-format="YYYY-MM-DD" :disabled="form.targetOnboardType==='anytime'" style="width:100%" /></el-form-item></el-col>
            </el-row>
          </div>

          <div class="form-section"><h3>服务费用与扩展信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="服务费用"><el-select v-model="form.serviceFeeType" clearable placeholder="选择计费方式" style="width:100%"><el-option label="固定金额" value="fixed" /><el-option label="年薪比例" value="annual_salary_rate" /><el-option label="其他" value="other" /></el-select></el-form-item></el-col>
              <el-col v-if="form.serviceFeeType==='fixed'" :xs="24" :md="16"><el-form-item label="币种/金额" prop="serviceFeeAmount"><div class="money-field"><el-select v-model="form.serviceFeeCurrency"><el-option label="人民币" value="CNY" /><el-option label="美元" value="USD" /><el-option label="港币" value="HKD" /></el-select><el-input-number v-model="form.serviceFeeAmount" :min="0" :precision="2" :controls="false" placeholder="请输入金额" /></div></el-form-item></el-col>
              <el-col v-if="form.serviceFeeType==='annual_salary_rate'" :xs="24" :md="16"><el-form-item label="年薪比例" prop="serviceFeeRate"><el-input-number v-model="form.serviceFeeRate" :min="0" :max="100" :precision="2" :controls="false" placeholder="请输入比例" /><span class="suffix">%</span></el-form-item></el-col>
            </el-row>
            <el-form-item label="费用说明"><el-input v-model="form.serviceFeeNote" /></el-form-item>
            <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="客户咨询时间"><el-date-picker v-model="form.customerConsultationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="客户确认时间"><el-date-picker v-model="form.customerConfirmationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
            <el-form-item label="项目路径"><PathInput v-model="form.projectPath" @open="openPath(form.projectPath)" @copy="copyPath(form.projectPath)" /></el-form-item>
            <el-form-item label="报价单路径"><PathInput v-model="form.quotationPath" @open="openPath(form.quotationPath)" @copy="copyPath(form.quotationPath)" /></el-form-item>
            <el-form-item label="合同路径"><PathInput v-model="form.contractPath" @open="openPath(form.contractPath)" @copy="copyPath(form.contractPath)" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="3" /></el-form-item>
            <el-form-item label="标题前缀">
              <el-input v-model="form.subjectPrefix" maxlength="50" show-word-limit clearable placeholder="可选，例如：紧急、请优先处理" />
            </el-form-item>
            <el-form-item label="邮件主题预览">
              <div class="subject-preview-field">
                <el-input v-model="form.emailSubjectPreview" type="textarea" :rows="2" />
                <div class="subject-preview-toolbar">
                  <span>按“标题前缀、订单号、客户简称、负责人联系方式、客户单号/标识、项目名称”顺序生成</span>
                  <el-button class="soft-action-button" :icon="MagicStick" @click="generateEmailSubject">生成邮件主题</el-button>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="发圈请求"><el-input v-model="form.socialPostRequest" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="资源请求"><el-input v-model="form.resourceRequest" type="textarea" :rows="2" /></el-form-item>
          </div>

          <InternalProjectRolesForm v-model="form.roleAssignments" />

          <div v-if="form.id" class="form-section candidate-section">
            <div class="section-heading">
              <h3>简历人选管理</h3>
              <div class="candidate-heading-actions">
                <span>共 {{ candidateRows.length }} 人</span>
                <el-button class="soft-action-button" :icon="Plus" size="small" @click="openCandidateEditor()">新增候选人</el-button>
              </div>
            </div>
            <RecruitmentCandidateTable
              :rows="candidateRows" :loading="candidateLoading" :can-write="canWrite" :resume-sources="resumeSources"
              layout="cards"
              @edit="openCandidateEditor" @delete="removeCandidate" @refresh="loadCandidates"
              @row-updated="replaceCandidate" @source-created="addResumeSource"
            />
          </div>
        </el-form>
      </div>
      <template #footer><div class="editor-footer"><el-button @click="editorVisible=false">取消</el-button><el-button :loading="saving" @click="saveProject(true)">保存并发送邮件</el-button><el-button type="primary" :loading="saving" @click="saveProject(false)">保存</el-button></div></template>
    </el-dialog>

    <el-dialog v-model="jobDescriptionEditorVisible" title="编辑职位描述" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body class="job-description-dialog">
      <div class="job-description-dialog__body">
        <p>可在此集中编辑岗位职责、任职要求及其他补充说明，内容会实时同步到项目表单。</p>
        <el-input v-model="form.jobDescription" class="job-description-large-input" type="textarea" :rows="22" placeholder="填写岗位职责、任职要求和补充说明" />
        <div class="job-description-count">{{ (form.jobDescription || '').length }} 字符</div>
      </div>
      <template #footer><el-button type="primary" @click="jobDescriptionEditorVisible=false">完成</el-button></template>
    </el-dialog>

    <el-dialog v-model="progressVisible" :title="`${activeProject?.projectName || activeProject?.orderNo || ''} 项目进度表`" width="min(760px, calc(100vw - 32px))">
      <div class="inline-create progress-create" v-if="canWrite">
        <el-date-picker v-model="progressOccurredAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择发生时间" />
        <el-input v-model="progressNote" placeholder="补充进度说明" @keyup.enter="addProgress" />
        <el-button type="primary" :loading="progressSaving" @click="addProgress">添加记录</el-button>
      </div>
      <el-timeline v-loading="progressLoading"><el-timeline-item v-for="item in progressRows" :key="item.id" :timestamp="formatDateTime(item.occurredAt)" :type="item.isSystem ? 'primary' : 'success'" placement="top"><el-card shadow="never"><div v-if="item.fromStatus || item.toStatus"><b>{{ item.fromStatus ? statusLabel(item.fromStatus) : '创建项目' }}</b><span> → </span><b>{{ item.toStatus ? statusLabel(item.toStatus) : '补充记录' }}</b></div><div class="progress-note">{{ item.note || '-' }}</div><small>{{ item.operatorName || '系统' }} · {{ item.isSystem ? '系统记录' : '人工记录' }}</small></el-card></el-timeline-item></el-timeline>
    </el-dialog>

    <el-dialog v-model="candidateVisible" :title="`${activeProject?.projectName || activeProject?.orderNo || ''} 简历人选跟进情况表`" width="min(980px, calc(100vw - 32px))" top="5vh" append-to-body class="candidate-list-dialog">
      <div class="candidate-toolbar"><span>共 {{ candidateRows.length }} 人</span><el-button v-if="canWrite" type="primary" @click="openCandidateEditor()">新增候选人</el-button></div>
      <RecruitmentCandidateTable
        :rows="candidateRows" :loading="candidateLoading" :can-write="canWrite" :resume-sources="resumeSources"
        layout="cards"
        @edit="openCandidateEditor" @delete="removeCandidate" @refresh="loadCandidates"
        @row-updated="replaceCandidate" @source-created="addResumeSource"
      />
    </el-dialog>

    <el-dialog v-model="candidateEditorVisible" :title="candidateForm.id ? '编辑候选人' : '新增候选人'" width="min(760px, calc(100vw - 32px))" top="5vh" append-to-body class="candidate-editor-dialog">
      <div class="candidate-editor-body"><el-form ref="candidateFormRef" :model="candidateForm" :rules="candidateRules" label-width="110px">
        <el-form-item label="复用人才档案"><el-select v-model="candidateForm.personId" filterable clearable placeholder="可选择人才库已有人员" style="width:100%" @change="handleCandidatePersonChange"><el-option v-for="person in talentOptions" :key="person.id" :label="`${person.fullName}${person.resourceCode ? `（${person.resourceCode}）` : ''}`" :value="person.id" /></el-select></el-form-item>
        <el-form-item label="候选人姓名" prop="candidateName"><el-input v-model="candidateForm.candidateName" /></el-form-item>
        <el-form-item label="简历路径"><el-input v-model="candidateForm.resumePath" /></el-form-item>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="简历来源"><el-select v-model="candidateForm.resumeSourceId" filterable clearable style="width:100%"><el-option v-for="source in resumeSources" :key="source.id" :label="source.label" :value="source.id" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="入职日期"><el-date-picker v-model="candidateForm.actualOnboardDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col></el-row>
        <div v-for="(interview, index) in candidateForm.interviews" :key="interview.localKey" class="candidate-interview-editor">
          <div class="candidate-interview-editor__heading">
            <span>{{ candidateInterviewLabel(interview.roundNo) }}日期与详情</span>
            <el-button v-if="index > 0 && index === candidateForm.interviews.length - 1" link type="danger" @click="removeLastCandidateInterview">移除本轮</el-button>
          </div>
          <el-form-item :label="`${candidateInterviewLabel(interview.roundNo)}日期`"><el-date-picker v-model="interview.interviewDate" value-format="YYYY-MM-DD" clearable style="width:100%" /></el-form-item>
          <el-form-item :label="`${candidateInterviewLabel(interview.roundNo)}详情`"><el-input v-model="interview.details" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" :placeholder="`填写${candidateInterviewLabel(interview.roundNo)}反馈、结论及后续安排`" /></el-form-item>
        </div>
        <div class="candidate-interview-actions"><el-button type="primary" plain @click="addCandidateInterview">增加下一轮面试</el-button></div>
        <el-collapse><el-collapse-item title="更多信息" name="legacy">
          <el-form-item label="当前阶段"><el-select v-model="candidateForm.stage" style="width:100%"><el-option v-for="item in candidateStageOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="联系方式"><el-input v-model="candidateForm.contactInfo" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="跟进人"><el-select v-model="candidateForm.ownerId" filterable clearable style="width:100%"><el-option v-for="user in activeUsers" :key="user.id" :label="userLabel(user)" :value="user.id" /></el-select></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="推荐时间"><el-date-picker v-model="candidateForm.recommendedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="原面试时间"><el-date-picker v-model="candidateForm.interviewAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="Offer时间"><el-date-picker v-model="candidateForm.offerAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="下次跟进"><el-date-picker v-model="candidateForm.nextFollowUpAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
          <el-form-item label="计划入职"><el-date-picker v-model="candidateForm.plannedOnboardDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="candidateForm.remarks" type="textarea" :rows="3" /></el-form-item>
        </el-collapse-item></el-collapse>
      </el-form></div>
      <template #footer><el-button @click="candidateEditorVisible=false">取消</el-button><el-button type="primary" :loading="candidateSaving" @click="saveCandidate">保存</el-button></template>
    </el-dialog>
    <BusinessMailComposer
      v-model="mailComposerVisible"
      project-type="recruitment"
      :project-id="mailProjectId"
      :consultation-id="mailConsultationId"
    />
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, CaretBottom, Check, FullScreen, MagicStick, Plus } from '@element-plus/icons-vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import InternalProjectRolesForm from '@/components/common/InternalProjectRolesForm.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import GeneratedProjectNameInput from '@/components/common/GeneratedProjectNameInput.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import PathInput from '@/components/common/PathInput.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useTableColumns } from '@/composables/useTableColumns'
import { notifyEmailSubjectGenerated, extractSubjectPrefix } from '@/utils/emailSubject'
import { hasPermission } from '@/utils/permission'
import { fetchProjectClientSuggestions } from '@/utils/projectClientAutocomplete'
import { launchOpenPath } from '@/utils/openPath'
import { getClients } from '@/api/clients'
import { getUsers } from '@/api/users'
import { getRecruitmentTalents } from '@/api/talents'
import { getProjectLanguages } from '@/api/projectLanguages'
import {
  createRecruitmentCandidate, createRecruitmentProgress, createRecruitmentProject,
  deleteRecruitmentCandidate, deleteRecruitmentProject, getRecruitmentCandidates,
  getRecruitmentProgress, getRecruitmentProject, getRecruitmentProjectCount,
  getRecruitmentProjects, getRecruitmentResumeSources, patchRecruitmentProjectStatus, previewRecruitmentProjectName, updateRecruitmentCandidate,
  updateRecruitmentProject,
} from '@/api/recruitmentProjects'
import RecruitmentLanguageDirections from '@/components/common/LanguageDirectionsEditor.vue'
import RecruitmentCandidateTable from './recruitment/RecruitmentCandidateTable.vue'
import BusinessMailComposer from '@/components/common/BusinessMailComposer.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'

const canWrite = hasPermission('projects:write')
const route = useRoute()
const router = useRouter()
const startResourceRequest = (row) => router.push({ name: 'ResourceRequests', query: { sourceType: 'recruitment', sourceProjectId: row.id } })
const highlightedProjectId = ref('')
const mailComposerVisible = ref(false)
const mailProjectId = ref('')
const mailConsultationId = ref('')
const statusOptions = [
  ['pending_setup','新建待立项'],['sourcing','立项启动（寻访阶段）'],['recommending','简历推荐中'],['interviewing','面试进行中'],['offer_negotiation','Offer谈判阶段'],['pending_onboard','候选人待入职'],['probation','已入职保用期'],['closed','项目结案'],
].map(([value,label]) => ({ value,label }))
const candidateStageOptions = [['screening','待筛选'],['recommended','已推荐'],['interviewing','面试中'],['offer','Offer阶段'],['pending_onboard','待入职'],['onboarded','已入职'],['rejected','已淘汰']].map(([value,label]) => ({value,label}))
const statusLabel = (value) => statusOptions.find((item) => item.value === value)?.label || value || '-'
const statusType = (value) => ({ pending_setup:'info', sourcing:'primary', recommending:'warning', interviewing:'warning', offer_negotiation:'warning', pending_onboard:'primary', probation:'success', closed:'success' }[value] || 'info')
const candidateStageLabel = (value) => candidateStageOptions.find((item) => item.value === value)?.label || value || '-'

// 顺序严格对应业务字段清单；序号、操作是结构列，不参与字段设置。
const tableColumns = [
  {key:'orderNo',label:'订单号',width:PROJECT_LIST_COLUMN_WIDTHS.orderNo,tooltip:false,clickHint:'点击订单号查看项目详情'},
  {key:'projectName',label:'项目名称',minWidth:PROJECT_LIST_COLUMN_WIDTHS.projectName,tooltip:false,clickHint:'点击项目名称查看项目进度'},
  {key:'jobDescription',label:'职位描述',width:PROJECT_LIST_COLUMN_WIDTHS.longText,tooltip:false,clickHint:'点击职位描述查看完整内容'},
  {key:'positionTitle',label:'职位名称/类型',width:118},
  {key:'headcount',label:'招聘人数',width:78},
  {key:'clientManagerName',label:'现客户经理',width:92},
  {key:'projectStatus',label:'项目状态',width:PROJECT_LIST_COLUMN_WIDTHS.projectStatus},
  {key:'clientShortName',label:'客户简称',minWidth:PROJECT_LIST_COLUMN_WIDTHS.clientShortName,clickHint:'点击客户简称查看关联信息'},
  {key:'clientCode',label:'客户编号',width:96},
  {key:'clientName',label:'客户全称',minWidth:135},
  {key:'clientDomain',label:'客户领域',width:110},
  {key:'contactName',label:'子客户/联系人',width:115},
  {key:'customerOrderNo',label:'客户单号/项目标识',width:135},
  {key:'languageSummary',label:'外语/翻译方向',minWidth:PROJECT_LIST_COLUMN_WIDTHS.languageDirection},
  {key:'targetOnboard',label:'拟入职日期',width:100},
  {key:'employmentPeriod',label:'拟履职周期',width:155},
  {key:'workLocation',label:'任职工作属地',minWidth:92},
  {key:'serviceFee',label:'服务费用',width:88},
  {key:'candidateCount',label:'简历人选数',width:95,clickHint:'点击人数查看候选人跟进情况'},
  {key:'customerConsultationTime',label:'客户咨询时间',width:140},
  {key:'customerConfirmationTime',label:'客户确认时间',width:140},
  {key:'quotationPath',label:'报价单路径',minWidth:155},
  {key:'contractPath',label:'合同路径',minWidth:155},
  {key:'projectPath',label:'项目路径',minWidth:155},
  {key:'remarks',label:'备注',minWidth:140},
  {key:'emailSubjectPreview',label:'邮件主题预览',minWidth:165},
  {key:'socialPostRequest',label:'发圈请求',minWidth:150},
  {key:'resourceRequest',label:'资源请求',minWidth:150},
  {key:'createdAt',label:'创建时间',width:140},
  {key:'updatedAt',label:'更新时间',width:140},
]
const defaultColumnKeys = [
  'orderNo','projectName','jobDescription','headcount','projectStatus','clientShortName',
  'languageSummary','targetOnboard','employmentPeriod','workLocation','candidateCount',
]
const dateTimeColumnKeys = new Set(['customerConsultationTime', 'customerConfirmationTime', 'createdAt', 'updatedAt'])
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns('recruitment-details-v5', tableColumns, defaultColumnKeys)
const visibleColumns = computed(() => tableColumns.filter((item) => isVisible(item.key)))
const summarizeDetail = (value, maxLength = 80) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text
}
const roleAssignmentName = (row, roleCode) => row.roleAssignments?.find((item) => item.roleCode === roleCode)?.assigneeName || '未分配'
const detailItems = [
  {label:'订单号',key:'orderNo'},
  {label:'项目名称',key:'projectName'},
  {label:'职位描述',key:'jobDescription',span:2,formatter:(value)=>summarizeDetail(value)},
  {label:'职位名称/类型',key:'positionTitle'},
  {label:'招聘人数',key:'headcount',formatter:(_value,row)=>headcountText(row)},
  {label:'现客户经理',key:'clientManagerName'},
  {label:'项目状态',key:'projectStatus',type:'status'},
  {label:'项目经理',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_manager')},
  {label:'项目专员',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_specialist')},
  {label:'项目助理',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_assistant')},
  {label:'客户简称',key:'clientShortName'},
  {label:'客户编号',key:'clientCode'},
  {label:'客户全称',key:'clientName'},
  {label:'客户领域',key:'clientDomain'},
  {label:'子客户/联系人',key:'contactName'},
  {label:'客户单号/项目标识',key:'customerOrderNo'},
  {label:'外语/翻译方向',key:'languageSummary',span:2,formatter:(_value,row)=>languageText(row)},
  {label:'拟入职日期',key:'targetOnboard',formatter:(_value,row)=>row.targetOnboardType==='anytime'?'随时':formatDate(row.targetOnboardDate)},
  {label:'拟履职周期',key:'employmentPeriod',formatter:(_value,row)=>periodText(row)},
  {label:'任职工作属地',key:'workLocation'},
  {label:'服务费用',key:'serviceFee',formatter:(_value,row)=>feeText(row)},
  {label:'简历人选数',key:'candidateCount',formatter:(value)=>`${value || 0} 人`},
  {label:'客户咨询时间',key:'customerConsultationTime'},
  {label:'客户确认时间',key:'customerConfirmationTime'},
  {label:'报价单路径',key:'quotationPath',span:2},
  {label:'合同路径',key:'contractPath',span:2},
  {label:'项目路径',key:'projectPath',span:2},
  {label:'备注',key:'remarks',span:2},
  {label:'邮件主题预览',key:'emailSubjectPreview',span:2},
  {label:'发圈请求',key:'socialPostRequest',span:2},
  {label:'资源请求',key:'resourceRequest',span:2},
  {label:'创建时间',key:'createdAt'},
  {label:'更新时间',key:'updatedAt'},
]

const rows = ref([]); const loading = ref(true); const users = ref([]); const clients = ref([]); const resumeSources = ref([]); const talentOptions = ref([]); const languages = ref([]); const projectTableRef = ref(null)
const activeUsers = computed(() => users.value.filter((item) => item.is_active !== false))
const managerUserOptions = computed(() => { const current = users.value.find((item) => item.id === form.clientManagerId); return current && !current.is_active ? [current, ...activeUsers.value] : activeUsers.value })
const userLabel = (user) => user.full_name || user.username
const userOptionLabel = (user) => `${userLabel(user)}${user.is_active === false ? '（已停用）' : ''}`
const clientDomainText = (item) => [item?.field_level1, item?.field_level2].filter(Boolean).join(' / ')
const clientOptions = computed(() => clients.value.flatMap((client) => [
  {
    value:`client:${client.id}`,label:client.client_short_name || client.client_name,
    clientId:client.id,subClientId:'',clientShortName:client.client_short_name || '',
    clientCode:client.client_code || '',clientName:client.client_name || '',
    clientDomain:clientDomainText(client),clientManager:client.client_manager || '',
    managerContact:client.manager_contact || '',
  },
  ...((client.sub_clients || []).map((sub) => ({
    value:`sub:${sub.id}`,label:`${client.client_short_name || client.client_name} / ${sub.client_short_name || sub.client_name}`,
    clientId:client.id,subClientId:sub.id,clientShortName:sub.client_short_name || '',
    clientCode:sub.sub_client_code || '',clientName:sub.client_name || '',
    clientDomain:clientDomainText(sub),clientManager:sub.client_manager || client.client_manager || '',
    managerContact:sub.manager_contact || client.manager_contact || '',
  }))),
]))

const pagination = reactive({page:1,limit:20,total:0})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:projectTableRef,pagination,deleteRow:(row)=>deleteRecruitmentProject(row.id),getLabel:(row)=>row.orderNo||row.projectName,reload:()=>fetchData(),entityName:'招聘项目'})
const searchForm = reactive({keyword:'',projectStatus:'',clientManagerId:'',employmentRange:[],clientSelection:'',languageId:'',targetOnboardRange:[],createdRange:[]})
const projectStatusSavingIds = ref(new Set())
const advancedVisible = ref(false)
const advancedCount = computed(() => [
  searchForm.clientManagerId,
  searchForm.employmentRange?.length === 2 ? 1 : '',
  searchForm.clientSelection,
  searchForm.languageId,
  searchForm.targetOnboardRange?.length === 2 ? 1 : '',
  searchForm.createdRange?.length === 2 ? 1 : '',
].filter(Boolean).length)
let searchTimer = null; let controller = null; let sequence = 0
const buildFilters = () => {
  const selection = searchForm.clientSelection || ''
  return {
    keyword: searchForm.keyword.trim() || undefined,
    project_status: searchForm.projectStatus || undefined,
    client_manager_id: searchForm.clientManagerId || undefined,
    employment_date_start: searchForm.employmentRange?.[0] || undefined,
    employment_date_end: searchForm.employmentRange?.[1] || undefined,
    client_id: selection.startsWith('client:') ? selection.slice(7) : undefined,
    sub_client_id: selection.startsWith('sub:') ? selection.slice(4) : undefined,
    language_id: searchForm.languageId || undefined,
    target_onboard_date_start: searchForm.targetOnboardRange?.[0] || undefined,
    target_onboard_date_end: searchForm.targetOnboardRange?.[1] || undefined,
    created_date_start: searchForm.createdRange?.[0] || undefined,
    created_date_end: searchForm.createdRange?.[1] || undefined,
  }
}
const fetchData = async () => { controller?.abort(); controller = new AbortController(); const current=++sequence; loading.value=true; try { const filters=buildFilters(); const [list,count]=await Promise.all([getRecruitmentProjects({skip:(pagination.page-1)*pagination.limit,limit:pagination.limit,...filters},{signal:controller.signal}),getRecruitmentProjectCount(filters,{signal:controller.signal})]); if(current!==sequence)return; rows.value=list||[]; pagination.total=count?.total||0 } catch(error){ if(error?.code!=='ERR_CANCELED'&&current===sequence) ElMessage.error(error?.response?.data?.detail||'网络异常，招聘项目列表未刷新，请检查网络后重试') } finally { if(current===sequence)loading.value=false } }
const projectRowClass=({row})=>String(row.id)===highlightedProjectId.value?'workbench-target-row':''
const focusRouteProject=async()=>{const projectId=String(route.query.projectId||'');if(!projectId)return;try{const detail=await getRecruitmentProject(projectId);highlightedProjectId.value=projectId;searchForm.keyword=detail.orderNo||'';pagination.page=1;await fetchData()}catch(error){ElMessage.error(error?.response?.data?.detail||'定位招聘项目失败')}}
const handleTextSearch = (value) => { clearTimeout(searchTimer); if(!value)return handleSearch(); searchTimer=setTimeout(handleSearch,400) }
const handleSearch = () => { exitDeleteMode(); clearTimeout(searchTimer); pagination.page=1; fetchData() }
const resetSearch = () => { Object.assign(searchForm,{keyword:'',projectStatus:'',clientManagerId:'',employmentRange:[],clientSelection:'',languageId:'',targetOnboardRange:[],createdRange:[]}); handleSearch() }
const clearAdvanced = () => { Object.assign(searchForm,{clientManagerId:'',employmentRange:[],clientSelection:'',languageId:'',targetOnboardRange:[],createdRange:[]}); handleSearch() }
const handleSizeChange = () => { pagination.page=1; fetchData() }

const emptyForm = () => ({id:'',orderNo:'',projectName:'',jobDescription:'',positionTitle:'',headcountMin:null,headcountMax:null,projectStatus:'pending_setup',clientId:'',subClientId:'',clientSelection:'',clientShortName:'',clientCode:'',clientName:'',clientDomain:'',contactName:'',customerOrderNo:'',clientManagerId:'',managerContact:'',targetOnboardType:'date',targetOnboardDate:'',employmentRange:[],workLocation:'',serviceFeeType:'',serviceFeeCurrency:'CNY',serviceFeeAmount:null,serviceFeeRate:null,serviceFeeNote:'',customerConsultationTime:'',customerConfirmationTime:'',projectPath:'',quotationPath:'',contractPath:'',remarks:'',subjectPrefix:'',emailSubjectPreview:'',socialPostRequest:'',resourceRequest:'',languageDirections:[],roleAssignments:[]})
const form = reactive(emptyForm()); const formRef=ref(); const editorBodyRef=ref(); const editorVisible=ref(false); const jobDescriptionEditorVisible=ref(false); const saving=ref(false); const nameLoading=ref(false); const nameManuallyEdited=ref(false); const editorTitle=computed(()=>form.id?'编辑招聘项目':'新增招聘项目')
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
let autoNameTimer=null; let namePreviewRequestId=0
const rules = { projectStatus:[{required:true,message:'请选择项目状态',trigger:'change'}], positionTitle:[{required:true,message:'请输入职位名称/类型',trigger:'blur'}], headcountMin:[{required:true,message:'请输入招聘人数',trigger:'change'}], employmentRange:[{required:true,message:'请选择拟履职周期',trigger:'change'}], workLocation:[{required:true,message:'请输入任职工作属地',trigger:'blur'}], serviceFeeAmount:[{trigger:'change',validator:(_rule,value,callback)=>form.serviceFeeType==='fixed'&&value==null?callback(new Error('固定金额服务费必须填写金额')):callback()}], serviceFeeRate:[{trigger:'change',validator:(_rule,value,callback)=>form.serviceFeeType==='annual_salary_rate'&&value==null?callback(new Error('年薪比例服务费必须填写比例')):callback()}] }
const resolveManagerByName = (name) => {
  const exact = activeUsers.value.filter((user) => userLabel(user) === String(name || '').trim())
  if (exact.length === 1) return exact[0].id
  const fallback = activeUsers.value.filter((user) => userLabel(user) === '欧阳靖琳')
  return fallback.length === 1 ? fallback[0].id : ''
}
const fetchClientSuggestions = fetchProjectClientSuggestions
const handleClientSelect = (item) => {
  Object.assign(form, {
    clientId:item?.parent_client_id||item?.id||'',subClientId:item?.sub_client_id||'',
    clientShortName:item?.client_short_name||'',clientCode:item?.client_code||'',
    clientName:item?.client_name||'',clientDomain:item?.client_domain||'',
    managerContact:item?.manager_contact||'',
    clientManagerId:item ? resolveManagerByName(item.client_manager) : '',
  })
}
const handleClientShortNameInput = () => {
  const hadSelectedClient=Boolean(form.clientId||form.subClientId)
  Object.assign(form,{clientId:'',subClientId:'',clientCode:'',clientDomain:'',managerContact:''})
  if(hadSelectedClient)form.clientName=''
  if(hadSelectedClient)form.clientManagerId=resolveManagerByName('')
}
const clearSelectedClient = () => {
  Object.assign(form,{clientId:'',subClientId:'',clientShortName:'',clientCode:'',clientName:'',clientDomain:'',managerContact:'',clientManagerId:resolveManagerByName('')})
}
const resetForm = () => { jobDescriptionEditorVisible.value=false; Object.assign(form,emptyForm()); nameManuallyEdited.value=false; namePreviewRequestId+=1; formRef.value?.clearValidate(); clearFieldSearch() }
const resetEditorScroll=async()=>{await nextTick();editorBodyRef.value?.scrollTo({top:0,behavior:'auto'})}
const openAdd = async () => { resetForm(); const defaultManager=activeUsers.value.filter((item)=>userLabel(item)==='欧阳靖琳'); if(defaultManager.length===1)form.clientManagerId=defaultManager[0].id; editorVisible.value=true; await resetEditorScroll() }
const openEdit = async (row) => { try { const item=await getRecruitmentProject(row.id); const clientSelection=item.subClientId?`sub:${item.subClientId}`:(item.clientId?`client:${item.clientId}`:''); const selectedClient=clientOptions.value.find((option)=>option.value===clientSelection); Object.assign(form,emptyForm(),item,{employmentRange:item.employmentStart&&item.employmentEnd?[item.employmentStart,item.employmentEnd]:[],clientSelection,managerContact:selectedClient?.managerContact||''}); form.subjectPrefix=extractSubjectPrefix(item.emailSubjectPreview,form); nameManuallyEdited.value=Boolean(item.projectName); activeProject.value=item; candidateRows.value=[]; editorVisible.value=true; await resetEditorScroll(); loadCandidates() } catch(error){ElMessage.error(error?.response?.data?.detail||'项目详情加载失败')} }
const clean = (value) => value===''?null:value
const buildPayload = () => ({projectName:clean(form.projectName),jobDescription:clean(form.jobDescription),positionTitle:clean(form.positionTitle),headcountMin:form.headcountMin,headcountMax:form.headcountMax??form.headcountMin,projectStatus:form.projectStatus,clientId:clean(form.clientId),subClientId:clean(form.subClientId),clientShortName:clean(form.clientShortName?.trim()),clientCode:clean(form.clientCode?.trim()),clientName:clean(form.clientName?.trim()),contactName:clean(form.contactName),customerOrderNo:clean(form.customerOrderNo),clientManagerId:clean(form.clientManagerId),targetOnboardType:form.targetOnboardType,targetOnboardDate:form.targetOnboardType==='anytime'?null:clean(form.targetOnboardDate),employmentStart:form.employmentRange?.[0]||null,employmentEnd:form.employmentRange?.[1]||null,workLocation:clean(form.workLocation),serviceFeeType:clean(form.serviceFeeType),serviceFeeCurrency:clean(form.serviceFeeCurrency),serviceFeeAmount:form.serviceFeeType==='fixed'?form.serviceFeeAmount:null,serviceFeeRate:form.serviceFeeType==='annual_salary_rate'?form.serviceFeeRate:null,serviceFeeNote:clean(form.serviceFeeNote),customerConsultationTime:clean(form.customerConsultationTime),customerConfirmationTime:clean(form.customerConfirmationTime),projectPath:clean(form.projectPath),quotationPath:clean(form.quotationPath),contractPath:clean(form.contractPath),remarks:clean(form.remarks),emailSubjectPreview:clean(form.emailSubjectPreview),expectedUpdatedAt:form.updatedAt||null,socialPostRequest:clean(form.socialPostRequest),resourceRequest:clean(form.resourceRequest),roleAssignments:form.roleAssignments,languageDirections:form.languageDirections.filter((item)=>item.sourceLanguageId).map((item)=>({...item,targetLanguageId:item.directionType==='translation'?item.targetLanguageId:null}))})
const projectNamePayload = () => ({
  employmentStart: form.employmentRange?.[0] || null,
  employmentEnd: form.employmentRange?.[1] || null,
  workLocation: form.workLocation?.trim() || null,
  positionTitle: form.positionTitle?.trim() || null,
  languageDirections: form.languageDirections
    .filter((item) => item.sourceLanguageId)
    .map((item) => ({ ...item, targetLanguageId: item.directionType === 'translation' ? item.targetLanguageId : null })),
})
const hasCompleteProjectNameSource = (payload) => (
  payload.employmentStart
  && payload.employmentEnd
  && payload.workLocation
  && payload.positionTitle
  && payload.languageDirections.length > 0
  && payload.languageDirections.every((item) => item.directionType !== 'translation' || item.targetLanguageId)
)
const previewProjectName = async ({ automatic = false } = {}) => {
  const payload = projectNamePayload()
  if (!hasCompleteProjectNameSource(payload)) {
    if (!automatic) ElMessage.warning('请先填写拟履职周期、工作属地、外语/翻译方向和职位名称')
    return
  }
  const currentRequestId = ++namePreviewRequestId
  if (!automatic) nameLoading.value = true
  try {
    const result = await previewRecruitmentProjectName(payload)
    if (currentRequestId !== namePreviewRequestId || (automatic && nameManuallyEdited.value)) return
    form.projectName = result.projectName
    nameManuallyEdited.value = false
    if (!automatic) ElMessage.success('项目名称已重新生成，仍可手工修改')
  } catch(error) {
    if (!automatic) ElMessage.error(error?.response?.data?.detail || '项目名称生成失败')
  } finally {
    if (!automatic) nameLoading.value = false
  }
}
const generateName = () => previewProjectName()
const handleProjectNameInput = () => { nameManuallyEdited.value=true; namePreviewRequestId+=1 }
const generateEmailSubject = () => {
  notifyEmailSubjectGenerated(form, ElMessage)
}
const saveProject = async (sendAfterSave=false) => { if(!formRef.value)return; const valid=await formRef.value.validate().catch(()=>false); if(!valid){ editorBodyRef.value?.querySelector('.is-error')?.scrollIntoView({behavior:'smooth',block:'center'}); return } saving.value=true; try { const payload=buildPayload(); const saved=form.id?await updateRecruitmentProject(form.id,payload):await createRecruitmentProject(payload); ElMessage.success(form.id?'招聘项目已更新':'招聘项目已创建'); editorVisible.value=false; if(sendAfterSave){mailProjectId.value=saved?.id||form.id;mailConsultationId.value=saved?.consultationId||form.consultationId||'';mailComposerVisible.value=true} fetchData() } catch(error){ElMessage.error(error?.response?.data?.detail||'保存失败')} finally{saving.value=false} }
const setProjectStatusSaving=(id,saving)=>{const next=new Set(projectStatusSavingIds.value);if(saving)next.add(id);else next.delete(id);projectStatusSavingIds.value=next}
const changeProjectStatus=async(row,value)=>{if(!value||value===row.projectStatus)return;setProjectStatusSaving(row.id,true);try{const updated=await patchRecruitmentProjectStatus(row.id,value);Object.assign(row,updated);ElMessage.success('项目状态已更新');if(searchForm.projectStatus&&searchForm.projectStatus!==updated.projectStatus)await fetchData()}catch(error){ElMessage.error(error?.response?.data?.detail||'项目状态更新失败')}finally{setProjectStatusSaving(row.id,false)}}

watch(
  () => [form.employmentRange, form.workLocation, form.positionTitle, form.languageDirections],
  () => {
    clearTimeout(autoNameTimer)
    if (nameManuallyEdited.value || !editorVisible.value) return
    autoNameTimer=setTimeout(() => previewProjectName({automatic:true}), 400)
  },
  {deep:true},
)

const currentLocalDateTime = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
const progressVisible=ref(false), progressLoading=ref(false), progressSaving=ref(false), progressRows=ref([]), progressNote=ref(''), progressOccurredAt=ref(currentLocalDateTime()), activeProject=ref(null)
const openProgress = async (row) => { activeProject.value=row; progressNote.value=''; progressOccurredAt.value=currentLocalDateTime(); progressVisible.value=true; progressLoading.value=true; try{progressRows.value=await getRecruitmentProgress(row.id)}catch{ElMessage.error('进度记录加载失败')}finally{progressLoading.value=false} }
const addProgress = async () => { if(!progressOccurredAt.value)return ElMessage.warning('请选择发生时间'); if(!progressNote.value.trim())return ElMessage.warning('请输入进度说明'); progressSaving.value=true; try{await createRecruitmentProgress(activeProject.value.id,{note:progressNote.value.trim(),occurredAt:progressOccurredAt.value}); progressNote.value=''; progressOccurredAt.value=currentLocalDateTime(); progressRows.value=await getRecruitmentProgress(activeProject.value.id)}catch(error){ElMessage.error(error?.response?.data?.detail||'添加失败')}finally{progressSaving.value=false} }

const candidateVisible=ref(false),candidateLoading=ref(false),candidateRows=ref([]),candidateEditorVisible=ref(false),candidateSaving=ref(false),candidateFormRef=ref()
let candidateInterviewKey=0
const emptyCandidateInterview=(roundNo)=>({localKey:`interview-${++candidateInterviewKey}`,roundNo,interviewDate:'',details:''})
const emptyCandidate=()=>({id:'',personId:'',candidateName:'',contactInfo:'',resumePath:'',resumeSourceId:'',stage:'screening',recommendedAt:'',interviewAt:'',offerAt:'',plannedOnboardDate:'',actualOnboardDate:'',interviews:[emptyCandidateInterview(1)],ownerId:'',nextFollowUpAt:'',remarks:''})
const candidateForm=reactive(emptyCandidate()); const candidateRules={candidateName:[{required:true,message:'请输入候选人姓名',trigger:'blur'}]}
const loadCandidates=async()=>{candidateLoading.value=true;try{candidateRows.value=await getRecruitmentCandidates(activeProject.value.id)}catch{ElMessage.error('候选人加载失败')}finally{candidateLoading.value=false}}
const openCandidates=async(row)=>{activeProject.value=row;candidateVisible.value=true;await loadCandidates()}
const normalizeCandidateInterviews=(row)=>{
  const values=(row?.interviews||[]).map((item,index)=>({...emptyCandidateInterview(index+1),...item,roundNo:index+1}))
  return values.length?values:[emptyCandidateInterview(1)]
}
const openCandidateEditor=(row=null)=>{Object.assign(candidateForm,emptyCandidate(),row||{}, {interviews:normalizeCandidateInterviews(row)});candidateEditorVisible.value=true}
const candidateInterviewLabel=(roundNo)=>roundNo<=10?`${['零','一','二','三','四','五','六','七','八','九','十'][roundNo]}面`:`第${roundNo}轮面试`
const addCandidateInterview=()=>candidateForm.interviews.push(emptyCandidateInterview(candidateForm.interviews.length+1))
const removeLastCandidateInterview=()=>{if(candidateForm.interviews.length>1)candidateForm.interviews.pop()}
const handleCandidatePersonChange=(id)=>{const person=talentOptions.value.find(item=>item.id===id);if(!person)return;candidateForm.candidateName=person.fullName||candidateForm.candidateName;candidateForm.contactInfo=[person.primaryPhone,person.primaryEmail].filter(Boolean).join(' / ')||candidateForm.contactInfo}
const candidatePayloadKeys=['personId','candidateName','contactInfo','resumePath','resumeSourceId','stage','recommendedAt','interviewAt','offerAt','plannedOnboardDate','actualOnboardDate','interviews','ownerId','nextFollowUpAt','remarks']
const candidatePayload=()=>Object.fromEntries(candidatePayloadKeys.map((key)=>[key,key==='interviews'?candidateForm.interviews.map((item,index)=>({roundNo:index+1,interviewDate:clean(item.interviewDate),details:clean(item.details)})):clean(candidateForm[key])]))
const saveCandidate=async()=>{const valid=await candidateFormRef.value?.validate().catch(()=>false);if(!valid)return;candidateSaving.value=true;try{if(candidateForm.id)await updateRecruitmentCandidate(candidateForm.id,candidatePayload());else{let payload=candidatePayload();try{await createRecruitmentCandidate(activeProject.value.id,payload)}catch(error){const detail=error.detail;if(detail?.code!=='duplicate_talent')throw error;const first=detail.duplicates?.[0];try{await ElMessageBox.confirm(`人才库中已有联系方式相同的“${first?.full_name||first?.fullName||'候选人'}”，是否复用该人才档案？`,'疑似重复人才',{confirmButtonText:'复用已有档案',cancelButtonText:'仍然新建',distinguishCancelAndClose:true,type:'warning'});payload.personId=first.id;await createRecruitmentCandidate(activeProject.value.id,payload)}catch(action){if(action==='cancel')await createRecruitmentCandidate(activeProject.value.id,{...payload,allowDuplicate:true});else throw action}}}candidateEditorVisible.value=false;await loadCandidates();await fetchData();ElMessage.success('候选人已保存')}catch(error){if(error!=='close')ElMessage.error(error?.detail?.message||error?.detail||error?.response?.data?.detail||'保存失败')}finally{candidateSaving.value=false}}
const removeCandidate=async(row)=>{try{await ElMessageBox.confirm(`确认删除候选人 ${row.candidateName} 吗？`,'提示',{type:'warning'});await deleteRecruitmentCandidate(row.id);await loadCandidates();await fetchData()}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error('删除失败')}}
const replaceCandidate=(updated)=>{const index=candidateRows.value.findIndex((item)=>item.id===updated.id);if(index>=0)candidateRows.value.splice(index,1,updated)}
const addResumeSource=(source)=>{if(!resumeSources.value.some((item)=>item.id===source.id))resumeSources.value.push(source);resumeSources.value.sort((a,b)=>Number(a.isCustom)-Number(b.isCustom)||a.label.localeCompare(b.label,'zh-CN'))}

const displayValue=(value)=>value===null||value===undefined||value===''?'-':value
const formatDate=(value)=>value?new Intl.DateTimeFormat('zh-CN').format(new Date(`${value}T00:00:00`)):'-'
const formatDateTime=(value)=>value?new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)):'-'
const headcountText=(row)=>row.headcountMin==null?'-':(row.headcountMax!=null&&row.headcountMax!==row.headcountMin?`${row.headcountMin}–${row.headcountMax}人`:`${row.headcountMin}人`)
const languageText=(row)=>(row.languageDirections||[]).map((item)=>item.label).join('；')||'-'
const fullPeriodText=(row)=>row.employmentStart&&row.employmentEnd?`${formatDate(row.employmentStart)}—${formatDate(row.employmentEnd)}`:'-'
const periodText=(row)=>fullPeriodText(row)
const feeText=(row)=>row.serviceFeeType==='fixed'?`${row.serviceFeeCurrency||'CNY'} ${row.serviceFeeAmount??'-'}`:row.serviceFeeType==='annual_salary_rate'?`年薪 ${row.serviceFeeRate??'-'}%`:row.serviceFeeType==='other'?(row.serviceFeeNote||'其他'):'-'
const openPath=(path)=>{if(!path?.trim())return ElMessage.warning('该项目暂无路径');if(!launchOpenPath(path.trim()))ElMessage.error('该路径不在企业允许的网络目录中，已阻止打开')}
const copyPath=async(path)=>{if(!path?.trim())return ElMessage.warning('该项目暂无路径');try{await navigator.clipboard.writeText(path.trim());ElMessage.success('路径已复制')}catch{ElMessage.error('复制失败，请手工复制')}}

onMounted(async()=>{const [userRows,clientRows,sourceRows,talents,languageRows]=await Promise.all([getUsers({skip:0,limit:500}),getClients({skip:0,limit:500}),getRecruitmentResumeSources(),getRecruitmentTalents({skip:0,limit:500}),getProjectLanguages()]).catch(()=>[[],[],[],[],[]]);users.value=userRows||[];clients.value=clientRows||[];resumeSources.value=sourceRows||[];talentOptions.value=talents||[];languages.value=languageRows||[];await fetchData();await focusRouteProject()})
onBeforeUnmount(()=>{clearTimeout(searchTimer);clearTimeout(autoNameTimer);controller?.abort()})
</script>

<style scoped>
:deep(.workbench-target-row > td.el-table__cell) { background: var(--el-color-primary-light-9) !important; }
.client-autocomplete-field{width:100%}.client-autocomplete-hint{margin-top:4px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.4}.client-suggestion{display:flex;flex-direction:column;min-width:0;padding:4px 0;line-height:1.45}.client-suggestion__meta{overflow:hidden;color:var(--el-text-color-secondary);font-size:12px;text-overflow:ellipsis;white-space:nowrap}
:global(.recruitment-advanced-filter-popover){max-width:calc(100vw - 32px)!important;max-height:calc(100vh - 32px);overflow:hidden}:global(.recruitment-advanced-filter-popover .advanced-content){max-height:calc(100vh - 64px);overflow-y:auto}
.card-header,.header-actions,.advanced-footer,.candidate-toolbar,.inline-create,.number-range,.money-field,.candidate-heading-actions{display:flex;align-items:center;gap:8px}.card-header,.candidate-toolbar{justify-content:space-between}.search-form{margin-bottom:8px}.pagination{margin-top:20px}.advanced-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-footer{justify-content:flex-end;border-top:1px solid var(--el-border-color-lighter);padding-top:10px}.order-cell{display:flex;align-items:center}.wrap-link{height:auto;min-height:32px;padding:5px 0;white-space:normal;text-align:left;line-height:1.45;align-items:flex-start}.description-preview{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.long-text-detail{max-height:560px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}.editor-body{overflow-y:auto}.section-heading{position:relative}.section-heading h3{padding-right:210px}.candidate-heading-actions{position:absolute;right:8px;top:6px}.number-range .el-input-number{width:130px}.money-field{width:100%;min-width:0}.money-field .el-select{width:120px;flex:none}.money-field .el-input-number{flex:1;min-width:140px}.suffix{margin-left:6px}.editor-footer{justify-content:flex-end}.inline-create{margin-bottom:18px}.inline-create .el-input{flex:1}.progress-create{padding:8px 0}.progress-create :deep(.el-date-editor){width:210px;flex:none}.progress-note{margin:8px 0;white-space:pre-wrap}.candidate-toolbar{margin-bottom:12px}
.wrap-link :deep(span){line-height:1.45}
.candidate-count-link{gap:2px}
.recruitment-list-table :deep(.el-table__cell){padding:6px 0}.recruitment-list-table :deep(.cell){padding-right:5px;padding-left:5px;line-height:1.35}.recruitment-list-table .wrap-link{min-height:26px;padding:2px 0}.recruitment-list-table .order-cell{gap:2px}
.recruitment-list-table .order-cell{min-width:0;gap:4px}.recruitment-list-table .order-cell :deep(.el-popover__reference-wrapper){flex:1;min-width:0}.recruitment-list-table .order-no-link{display:block;width:100%;height:auto;min-width:0;padding:0;overflow:hidden;text-align:left;text-overflow:ellipsis;white-space:nowrap}
.employment-period-text{font-size:12px;font-variant-numeric:tabular-nums;letter-spacing:-.1px;white-space:nowrap}
.action-buttons{display:inline-flex;align-items:center;justify-content:center;flex-wrap:nowrap;white-space:nowrap}
.status-switch-tag.el-tag{display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;max-width:100%;cursor:pointer;user-select:none;vertical-align:middle;transition:opacity .15s ease}.status-switch-tag :deep(.el-tag__content){display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;white-space:nowrap;line-height:1}.status-switch-text{line-height:1}.status-switch-caret{width:10px;height:10px;flex-shrink:0;margin:0;font-size:10px}.status-switch-tag:hover{opacity:.85}.status-switch-tag.is-updating{pointer-events:none;opacity:.55}.status-option-row{display:inline-flex;align-items:center;gap:8px;width:100%}.status-current-icon{color:var(--el-color-primary)}
.candidate-interview-editor{margin-bottom:14px;padding:14px 14px 2px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-extra-light)}.candidate-interview-editor__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;color:var(--el-text-color-primary);font-size:14px;font-weight:600}.candidate-interview-actions{display:flex;justify-content:center;margin:-2px 0 18px}
.job-description-editor{width:100%}.job-description-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px;color:var(--el-text-color-secondary);font-size:12px}.job-description-toolbar .el-button{flex:none}.job-description-dialog__body>p{margin:0 0 12px;color:var(--el-text-color-secondary);font-size:13px;line-height:1.6}.job-description-count{margin-top:8px;color:var(--el-text-color-secondary);font-size:12px;text-align:right}.job-description-large-input :deep(.el-textarea__inner){min-height:min(520px,calc(90vh - 210px));line-height:1.7;resize:none}
.subject-preview-field{width:100%;min-width:0}.subject-preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.5}.subject-preview-toolbar .el-button{flex:none}
:deep(.recruitment-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:deep(.recruitment-editor .el-dialog__header),:deep(.recruitment-editor .el-dialog__footer){flex:none}:deep(.recruitment-editor .el-dialog__body){display:flex;flex:1;min-height:0;overflow:hidden;padding-top:8px}:deep(.recruitment-editor .editor-body){flex:1;min-height:0}:deep(.recruitment-editor .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
:global(.job-description-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.job-description-dialog .el-dialog__header),:global(.job-description-dialog .el-dialog__footer){flex:none}:global(.job-description-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.job-description-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-bg-color)}
:global(.candidate-list-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.candidate-list-dialog .el-dialog__header){flex:none}:global(.candidate-list-dialog .el-dialog__body){flex:1;min-width:0;min-height:0;overflow-x:hidden;overflow-y:auto}:global(.candidate-list-dialog .candidate-toolbar){position:sticky;top:0;z-index:2;padding-bottom:10px;background:var(--el-bg-color)}
:global(.candidate-editor-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.candidate-editor-dialog .el-dialog__header),:global(.candidate-editor-dialog .el-dialog__footer){flex:none}:global(.candidate-editor-dialog .el-dialog__body){display:flex;flex:1;min-height:0;overflow:hidden;padding-top:8px}:global(.candidate-editor-dialog .candidate-editor-body){box-sizing:border-box;flex:1;min-width:0;min-height:0;overflow-x:hidden;overflow-y:auto;padding:0 4px}:global(.candidate-editor-dialog .candidate-editor-body>.el-form){box-sizing:border-box;width:100%}:global(.candidate-editor-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
.editor-dialog-heading{display:flex;flex-direction:column;gap:4px;padding-right:36px}.editor-dialog-title{color:var(--el-text-color-primary);font-size:18px;font-weight:600;line-height:1.35}.editor-dialog-subtitle{color:var(--el-text-color-secondary);font-size:12px;font-weight:400}.editor-body{padding:16px 24px 20px;background:var(--el-fill-color-lighter)}.recruitment-form{max-width:100%}.form-section{margin-bottom:16px;padding:20px 20px 4px;border:1px solid var(--el-border-color-lighter);border-radius:10px;background:var(--el-bg-color);box-shadow:0 2px 8px rgb(15 23 42 / 4%)}.form-section:last-child{margin-bottom:0}.form-section h3{display:flex;align-items:center;gap:8px;margin:-20px -20px 20px;padding:12px 20px;border-bottom:1px solid var(--el-border-color-lighter);border-radius:10px 10px 0 0;background:linear-gradient(90deg,var(--el-color-primary-light-9),var(--el-fill-color-extra-light));color:var(--el-text-color-primary);font-size:15px;font-weight:600}.form-section h3::before{width:3px;height:16px;border-radius:2px;background:var(--el-color-primary);content:""}.recruitment-form :deep(.el-form-item){margin-bottom:18px}.recruitment-form :deep(.el-input__wrapper),.recruitment-form :deep(.el-select__wrapper),.recruitment-form :deep(.el-textarea__inner){transition:border-color .2s ease,box-shadow .2s ease}.soft-action-button{--el-button-bg-color:var(--el-color-primary-light-9);--el-button-border-color:var(--el-color-primary-light-7);--el-button-text-color:var(--el-color-primary-dark-2);--el-button-hover-bg-color:var(--el-color-primary-light-8);--el-button-hover-border-color:var(--el-color-primary-light-5);--el-button-hover-text-color:var(--el-color-primary);font-weight:500}.number-range{width:100%;min-width:0}.number-range .el-input-number{flex:1;width:auto;min-width:0}.number-range :deep(.el-input__inner),.money-field :deep(.el-input__inner){text-align:left}.range-separator,.range-unit{flex:none;color:var(--el-text-color-secondary)}.range-unit{font-size:13px}.money-field .el-input-number{flex:1;min-width:140px}.editor-footer{gap:10px}.editor-footer .el-button{min-width:88px}:deep(.recruitment-editor .el-dialog__body){padding:0}:deep(.recruitment-editor .el-dialog__footer){padding:14px 24px;background:var(--el-bg-color);box-shadow:0 -4px 14px rgb(15 23 42 / 5%)}
@media(max-width:720px){.search-form :deep(.el-form-item){display:flex;margin-right:0}.search-form :deep(.el-form-item__content){flex:1}.money-field,.progress-create,.subject-preview-toolbar{align-items:stretch;flex-direction:column}.money-field .el-select,.progress-create :deep(.el-date-editor){width:100%}.subject-preview-toolbar .el-button{align-self:flex-end}.recruitment-form :deep(.el-form-item){display:block}.recruitment-form :deep(.el-form-item__label){width:auto!important;margin-bottom:6px;justify-content:flex-start}.recruitment-form :deep(.el-form-item__content){margin-left:0!important}.editor-body{padding:12px 12px 16px}.form-section{padding:16px 14px 4px}.form-section h3{margin:-16px -14px 16px}.section-heading h3{padding-right:8px;padding-bottom:52px}.candidate-heading-actions{left:8px;right:auto;top:38px}}
</style>
