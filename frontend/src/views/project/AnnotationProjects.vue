<template>
  <el-card class="annotation-card">
    <template #header>
      <div class="card-header">
        <span>标注项目详情</span>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
          <el-button v-if="canWrite" type="primary" @click="handleAdd">新增标注项目</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input
          v-model="searchForm.keyword"
          placeholder="订单号、项目名称、客户名称或客户单号"
          clearable
          style="width: 320px"
          @input="handleTextSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="项目状态">
        <el-select v-model="searchForm.projectStatus" clearable placeholder="全部" style="width: 150px" @change="handleSearch">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="annotation-advanced-popover">
          <template #reference>
            <el-button>高级筛选<span v-if="advancedCount" class="filter-count">{{ advancedCount }}</span></el-button>
          </template>
          <div class="advanced-panel">
            <div class="advanced-header">
              <span>高级筛选</span>
              <div>
                <el-button v-if="advancedCount" link type="primary" @click="clearAdvanced">清空高级条件</el-button>
                <el-button link @click="advancedVisible = false">关闭</el-button>
              </div>
            </div>
            <el-form label-position="top">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="项目类型"><el-select v-model="searchForm.projectType" clearable style="width:100%" @change="handleSearch"><el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="语言"><el-select v-model="searchForm.languageId" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="item in languages" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户经理"><el-select v-model="searchForm.clientManagerId" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="item in activeUsers" :key="item.id" :label="userLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="任务派发日期"><el-date-picker v-model="searchForm.dispatchedRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="任务提交日期"><el-date-picker v-model="searchForm.submittedRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户/子客户"><el-select v-model="searchForm.clientSelection" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="item in filterClientOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="标注人员"><el-select v-model="searchForm.assigneePersonId" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="person in annotationTalents" :key="person.id" :label="`${person.fullName}${person.resourceCode ? `（${person.resourceCode}）` : ''}`" :value="person.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="创建时间"><el-date-picker v-model="searchForm.createdRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="咨询时间"><el-date-picker v-model="searchForm.consultationRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="确认时间"><el-date-picker v-model="searchForm.confirmationRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
              </el-row>
            </el-form>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border class="annotation-table project-detail-list-table">
      <el-table-column type="index" label="序号" :width="PROJECT_LIST_COLUMN_WIDTHS.index" align="center" fixed="left" />
      <el-table-column label="订单号" :width="PROJECT_LIST_COLUMN_WIDTHS.orderNo" fixed="left">
        <template #header><ClickableColumnHeader label="订单号" hint="点击订单号查看标注项目详情" /></template>
        <template #default="{ row }">
          <div class="order-cell">
            <el-popover trigger="click" placement="left" :width="760" :title="`${row.orderNo} 详情`" popper-class="annotation-detail-popover" @show="loadDetail(row.id)">
              <template #reference><el-button type="primary" link class="order-no-link business-clickable-cell" :title="row.orderNo" @click.stop>{{ row.orderNo }}</el-button></template>
              <div class="detail-content" v-loading="detailLoadingId === row.id">
                <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="订单号">{{ textValue(detailRow(row).orderNo) }}</el-descriptions-item>
                <el-descriptions-item label="项目状态">
                  <el-tag :type="statusType(detailRow(row).projectStatus)">{{ statusLabel(detailRow(row).projectStatus) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="项目名称" :span="2">{{ textValue(detailRow(row).projectName) }}</el-descriptions-item>
                <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(detailRow(row).projectTypes) }}</el-descriptions-item>
                <el-descriptions-item label="具体任务" :span="2"><div class="pre-wrap">{{ textValue(detailRow(row).taskDescription) }}</div></el-descriptions-item>
                <el-descriptions-item label="语言方向" :span="2">{{ textValue(detailRow(row).languageItemsDisplay) }}</el-descriptions-item>
                <el-descriptions-item label="（潜在）需求量" :span="2"><div class="pre-wrap">{{ textValue(detailRow(row).potentialDemand) }}</div></el-descriptions-item>
                <el-descriptions-item label="客户简称">{{ textValue(detailRow(row).clientShortName) }}</el-descriptions-item>
                <el-descriptions-item label="客户编号">{{ textValue(detailRow(row).clientCode) }}</el-descriptions-item>
                <el-descriptions-item label="客户全称" :span="2">{{ textValue(detailRow(row).clientFullName) }}</el-descriptions-item>
                <el-descriptions-item label="子客户/联系人">{{ textValue(detailRow(row).subClientContact) }}</el-descriptions-item>
                <el-descriptions-item label="客户单号/项目标识">{{ textValue(detailRow(row).customerOrderNo) }}</el-descriptions-item>
                <el-descriptions-item label="邮件主题预览" :span="2"><div class="pre-wrap">{{ textValue(detailRow(row).emailSubjectPreview) }}</div></el-descriptions-item>
                <el-descriptions-item label="客户单价" :span="2">
                  <div v-if="detailRow(row).priceItems?.length" class="price-detail-list">
                    <div v-for="item in detailRow(row).priceItems" :key="item.id">{{ item.display }}<span v-if="item.remarks">（{{ item.remarks }}）</span></div>
                  </div>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="标注人员安排" :span="2">
                  <div v-if="detailRow(row).assignees?.length" class="assignee-detail-list">
                    <div v-for="item in detailRow(row).assignees" :key="item.id" class="assignee-detail-item">
                      <div>
                        <span>{{ item.personName }}</span>
                        <span v-if="item.resourceCode" class="detail-secondary">（{{ item.resourceCode }}）</span>
                        <el-tag size="small" :type="assignmentStatusType(item.assignmentStatus)">{{ assignmentStatusLabel(item.assignmentStatus) }}</el-tag>
                      </div>
                      <div v-if="item.qualityScore || item.evaluationNote" class="detail-secondary">
                        <span v-if="item.qualityScore">质量评分：{{ item.qualityScore }}</span>
                        <span v-if="item.evaluationNote">评价备注：{{ item.evaluationNote }}</span>
                      </div>
                    </div>
                  </div>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="任务派发时间">{{ formatDateTime(detailRow(row).taskDispatchedAt) }}</el-descriptions-item>
                <el-descriptions-item label="任务提交时间">{{ formatDateTime(detailRow(row).taskSubmittedAt) }}</el-descriptions-item>
                <el-descriptions-item label="客户经理">{{ textValue(detailRow(row).clientManagerName) }}</el-descriptions-item>
                <el-descriptions-item label="创建人">{{ textValue(detailRow(row).createdByName) }}</el-descriptions-item>
                <el-descriptions-item label="项目路径" :span="2">{{ textValue(detailRow(row).projectPath) }}</el-descriptions-item>
                <el-descriptions-item label="报价单路径" :span="2">{{ textValue(detailRow(row).quotationPath) }}</el-descriptions-item>
                <el-descriptions-item label="合同路径" :span="2">{{ textValue(detailRow(row).contractPath) }}</el-descriptions-item>
                <el-descriptions-item label="关联咨询编号">{{ textValue(detailRow(row).consultationCode) }}</el-descriptions-item>
                <el-descriptions-item label="客户咨询时间">{{ formatDateTime(detailRow(row).customerConsultationTime) }}</el-descriptions-item>
                <el-descriptions-item label="客户确认时间">{{ formatDateTime(detailRow(row).customerConfirmationTime) }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ formatDateTime(detailRow(row).createdAt) }}</el-descriptions-item>
                <el-descriptions-item label="更新时间">{{ formatDateTime(detailRow(row).updatedAt) }}</el-descriptions-item>
                <el-descriptions-item v-if="detailRow(row).legacyOrderNo" label="原笔译订单号">{{ detailRow(row).legacyOrderNo }}</el-descriptions-item>
                <el-descriptions-item v-if="detailRow(row).legacyStatus" label="迁移前状态">{{ detailRow(row).legacyStatus }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </el-popover>
            <PathActionButtons @open="openProjectPath(row)" @copy="copyProjectPath(row)" />
          </div>
        </template>
      </el-table-column>
      <el-table-column v-for="column in visibleTableColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="!['projectName', 'projectStatus'].includes(column.key)">
        <template #header>
          <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
          <span v-else>{{ column.label }}</span>
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
          <span v-else-if="column.key === 'projectName'" class="project-name-cell">{{ textValue(row.projectName) }}</span>
          <span v-else-if="column.key === 'projectTypes'">{{ projectTypesText(row.projectTypes) }}</span>
          <el-popover
            v-else-if="column.key === 'clientShortName'"
            trigger="click"
            placement="bottom-start"
            :width="360"
            title="客户关联信息"
            popper-class="annotation-client-popover"
            @show="loadDetail(row.id)"
          >
            <template #reference>
              <el-button type="primary" link class="business-clickable-cell" @click.stop>{{ textValue(row.clientShortName) }}</el-button>
            </template>
            <div v-loading="detailLoadingId === row.id">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="子客户/联系人">{{ textValue(detailRow(row).subClientContact) }}</el-descriptions-item>
                <el-descriptions-item label="客户单号/项目标识">{{ textValue(detailRow(row).customerOrderNo) }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
          <el-tooltip
            v-else-if="column.type === 'datetime'"
            :content="formatDateTime(row[column.key])"
            :disabled="!row[column.key]"
            placement="top"
          >
            <span class="compact-datetime">{{ compactDateTime(row[column.key]) }}</span>
          </el-tooltip>
          <span v-else>{{ textValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="PROJECT_LIST_COLUMN_WIDTHS.actions" fixed="right" align="center">
        <template #default="{ row }">
          <div v-if="canWrite" class="action-buttons">
            <TableActionButton action="edit" @click="handleEdit(row)" />
            <TableActionButton action="delete" @click="handleDelete(row)" />
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @size-change="fetchData" @current-change="fetchData" />

    <el-dialog v-model="dialogVisible" class="annotation-editor-dialog" width="min(1080px, calc(100vw - 32px))" top="5vh" @closed="resetForm">
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
        <el-form ref="formRef" :model="form" :rules="rules" label-width="125px">
          <section class="form-section">
            <h3>基础与客户</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="项目状态" prop="projectStatus"><el-select v-model="form.projectStatus" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24"><el-form-item label="项目名称"><GeneratedProjectNameInput v-model="form.projectName" placeholder="可手工填写，或根据客户、方向和类型生成" @manual-input="nameManuallyEdited=true" @regenerate="generateProjectName" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="项目类型"><el-select v-model="form.projectTypes" multiple clearable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户经理"><el-select v-model="form.clientManagerId" filterable clearable style="width:100%"><el-option v-for="item in activeUsers" :key="item.id" :label="userLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
            </el-row>
            <el-form-item label="具体任务"><el-input v-model="form.taskDescription" type="textarea" :rows="3" /></el-form-item>
            <el-form-item label="（潜在）需求量"><el-input v-model="form.potentialDemand" type="textarea" :rows="5" placeholder="可填写批次、交付周期、项目周期等完整说明" /></el-form-item>
            <div class="section-title-row section-title-row--compact"><span class="inline-section-label">客户单价</span><el-button type="primary" plain @click="addPriceItem">添加报价</el-button></div>
            <el-empty v-if="!form.priceItems.length" description="暂无客户单价明细" :image-size="70" />
            <div v-for="(item,index) in form.priceItems" :key="index" class="price-card">
              <div class="repeat-title"><span>报价 {{ index + 1 }}</span><el-button link type="danger" @click="form.priceItems.splice(index,1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="8"><el-form-item label="项目类型" label-width="80px"><el-select v-model="item.projectType" clearable style="width:100%"><el-option v-for="type in selectedProjectTypeOptions" :key="type.value" :label="type.label" :value="type.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="语言范围" label-width="80px"><el-select v-model="item.languageKey" clearable style="width:100%"><el-option v-for="language in currentLanguageOptions" :key="language.key" :label="language.label" :value="language.key" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="金额" label-width="60px"><el-input-number v-model="item.amount" :min="0.000001" :precision="6" :controls="false" style="width:100%" /></el-form-item></el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :xs="24" :md="6"><el-form-item label="币种" label-width="60px"><el-select v-model="item.currency" clearable placeholder="￥" style="width:100%"><el-option v-for="option in currencyOptions" :key="option.value" :label="option.symbol" :value="option.value">{{ option.symbol }} {{ option.name }}</el-option></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="6"><el-form-item label="单位" label-width="60px"><el-input v-model="item.unit" placeholder="条/小时/分钟等" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="备注" label-width="60px"><el-input v-model="item.remarks" /></el-form-item></el-col>
              </el-row>
            </div>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8">
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
              <el-col :xs="24" :md="8"><el-form-item label="客户编号"><el-input v-model="form.clientCode" :disabled="!!form.clientId" placeholder="新客户不填则自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户全称"><el-input v-model="form.clientFullName" :disabled="!!form.clientId" placeholder="新客户可补充全称" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="联系人"><el-input v-model="form.contactName" placeholder="填写联系人姓名或联系方式" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户单号/项目标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="负责人联系方式"><el-input v-model="form.managerContact" disabled placeholder="选择客户后自动带出" /></el-form-item></el-col>
            </el-row>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>语言方向</h3><div><el-button @click="addLanguage">新增共享语种</el-button><el-button type="primary" plain @click="addLanguageItem">添加语言项</el-button></div></div>
            <el-empty v-if="!form.languageItems.length" description="暂无语言项" :image-size="70" />
            <div v-for="(item,index) in form.languageItems" :key="index" class="language-row">
              <el-select v-model="item.mode" style="width:110px" @change="item.targetLanguageId = ''"><el-option label="单语种" value="single" /><el-option label="翻译方向" value="direction" /></el-select>
              <el-select v-model="item.sourceLanguageId" filterable placeholder="语种" style="flex:1"><el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-tag">新</el-tag></el-option></el-select>
              <template v-if="item.mode === 'direction'"><span class="direction-arrow">→</span><el-select v-model="item.targetLanguageId" filterable placeholder="目标语种" style="flex:1"><el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-tag">新</el-tag></el-option></el-select></template>
              <el-button link type="danger" @click="form.languageItems.splice(index,1)">删除</el-button>
            </div>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>标注人员安排</h3><el-button type="primary" plain @click="addAssignee">添加人员</el-button></div>
            <el-empty v-if="!form.assignees.length" description="暂无标注人员" :image-size="70" />
            <div v-for="(item,index) in form.assignees" :key="index" class="price-card">
              <div class="repeat-title"><span>人员 {{ index + 1 }}</span><el-button link type="danger" @click="form.assignees.splice(index,1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="10"><el-form-item label="标注人员" label-width="80px"><el-select v-model="item.personId" filterable style="width:100%"><el-option v-for="person in annotationTalents" :key="person.id" :label="`${person.fullName}${person.resourceCode ? `（${person.resourceCode}）` : ''}`" :value="person.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="7"><el-form-item label="安排状态" label-width="80px"><el-select v-model="item.assignmentStatus" style="width:100%"><el-option label="已安排" value="assigned" /><el-option label="进行中" value="in_progress" /><el-option label="已完成" value="completed" /><el-option label="已取消" value="cancelled" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="7"><el-form-item label="质量评分" label-width="80px"><el-input v-model="item.qualityScore" /></el-form-item></el-col>
              </el-row>
              <el-form-item label="评价备注" label-width="80px"><el-input v-model="item.evaluationNote" /></el-form-item>
            </div>
          </section>

          <section class="form-section">
            <h3>任务时间</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="任务派发时间"><el-date-picker v-model="form.taskDispatchedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="任务提交时间"><el-date-picker v-model="form.taskSubmittedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col>
            </el-row>
          </section>

          <section class="form-section">
            <h3>项目资料</h3>
            <el-form-item label="项目路径"><PathInput v-model="form.projectPath" @open="openPathValue(form.projectPath)" @copy="copyPathValue(form.projectPath)" /></el-form-item>
            <el-form-item label="报价单路径"><PathInput v-model="form.quotationPath" @open="openPathValue(form.quotationPath)" @copy="copyPathValue(form.quotationPath)" /></el-form-item>
            <el-form-item label="合同路径"><PathInput v-model="form.contractPath" @open="openPathValue(form.contractPath)" @copy="copyPathValue(form.contractPath)" /></el-form-item>
            <el-form-item label="标题前缀"><el-input v-model="form.subjectPrefix" maxlength="50" show-word-limit clearable placeholder="可选，例如：紧急、请优先处理" /></el-form-item>
            <el-form-item label="邮件主题预览">
              <div class="subject-preview-field">
                <el-input v-model="form.emailSubjectPreview" type="textarea" :rows="3" />
                <div class="subject-preview-toolbar">
                  <span>按“标题前缀、订单号、客户简称、负责人联系方式、客户单号/标识、项目名称”顺序生成</span>
                  <el-button class="soft-action-button" :icon="MagicStick" @click="generateEmailSubject">生成邮件主题</el-button>
                </div>
              </div>
            </el-form-item>
          </section>
        </el-form>
      </div>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CaretBottom, Check, MagicStick } from '@element-plus/icons-vue'
import * as annotationApi from '@/api/annotationProjects'
import * as clientApi from '@/api/clients'
import * as talentApi from '@/api/talents'
import * as userApi from '@/api/users'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import GeneratedProjectNameInput from '@/components/common/GeneratedProjectNameInput.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import PathInput from '@/components/common/PathInput.vue'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'
import { notifyEmailSubjectGenerated } from '@/utils/emailSubject'
import { fetchProjectClientSuggestions } from '@/utils/projectClientAutocomplete'

const canWrite = hasPermission('projects:write')
const projectTypeOptions = [
  ['audio_collection','音频采集'],['audio_annotation','音频标注'],['audio_evaluation','音频评测'],['text_evaluation','文本评测'],['text_annotation','文本标注'],['quality_inspection','质检'],['listening_test','测听'],['slot_deduction','扣槽'],['generalization','泛化'],['translation','翻译'],
].map(([value,label]) => ({ value,label }))
const projectTypeMap = Object.fromEntries(projectTypeOptions.map((item) => [item.value,item.label]))
const statusOptions = [
  ['pending_confirmation','待确认'],['trial','试标中'],['in_progress','进行中'],['sent_to_client','已发客户'],['client_feedback','客户反馈'],['cancelled','已取消'],['partially_cancelled','已部分取消'],
].map(([value,label]) => ({ value,label }))
const statusMap = Object.fromEntries(statusOptions.map((item) => [item.value,item.label]))
const assignmentStatusMap = { assigned:'已安排',in_progress:'进行中',completed:'已完成',cancelled:'已取消' }
const currencyOptions = [
  { value:'CNY', symbol:'￥', name:'人民币' },
  { value:'USD', symbol:'$', name:'美元' },
  { value:'HKD', symbol:'HK$', name:'港币' },
  { value:'EUR', symbol:'€', name:'欧元' },
  { value:'GBP', symbol:'£', name:'英镑' },
]

const tableColumns = [
  { key:'projectName',label:'项目名称',minWidth:PROJECT_LIST_COLUMN_WIDTHS.projectName },{ key:'projectTypes',label:'项目类型',minWidth:96 },{ key:'taskDescription',label:'具体任务',minWidth:PROJECT_LIST_COLUMN_WIDTHS.longText },{ key:'projectStatus',label:'项目状态',width:PROJECT_LIST_COLUMN_WIDTHS.projectStatus },{ key:'clientShortName',label:'客户简称',width:PROJECT_LIST_COLUMN_WIDTHS.clientShortName,clickHint:'点击客户简称查看关联信息' },{ key:'subClientContact',label:'子客户/联系人',minWidth:125 },{ key:'customerOrderNo',label:'客户单号/项目标识',minWidth:135 },{ key:'languageItemsDisplay',label:'语言方向',minWidth:PROJECT_LIST_COLUMN_WIDTHS.languageDirection },{ key:'potentialDemand',label:'（潜在）需求量',minWidth:125 },{ key:'customerPriceSummary',label:'客户单价',minWidth:135 },{ key:'assigneeSummary',label:'标注人员安排',minWidth:140 },{ key:'taskDispatchedAt',label:'任务派发时间',width:98,type:'datetime' },{ key:'taskSubmittedAt',label:'任务提交时间',width:98,type:'datetime' },{ key:'clientManagerName',label:'客户经理',width:82 },{ key:'projectPath',label:'项目路径',minWidth:150 },{ key:'quotationPath',label:'报价单路径',minWidth:150 },{ key:'contractPath',label:'合同路径',minWidth:150 },
]
const defaultColumns = ['projectName','projectTypes','taskDescription','projectStatus','clientShortName','languageItemsDisplay','potentialDemand','customerPriceSummary','taskDispatchedAt','taskSubmittedAt','clientManagerName']
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns('annotation-details-v3',tableColumns,defaultColumns)
const visibleTableColumns = computed(() => tableColumns.filter((item) => isVisible(item.key)))

const loading=ref(false), dialogVisible=ref(false), submitLoading=ref(false), advancedVisible=ref(false)
const dialogTitle=ref('新增标注项目'), formRef=ref(), dialogBodyRef=ref(), detailLoadingId=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(dialogBodyRef)
const tableData=ref([]), clients=ref([]), users=ref([]), languages=ref([]), annotationTalents=ref([])
const projectStatusSavingIds=ref(new Set())
const detailCache=reactive({}), pagination=reactive({page:1,limit:10,total:0})
const searchForm=reactive({keyword:'',projectStatus:'',projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[],clientSelection:'',assigneePersonId:'',createdRange:[],consultationRange:[],confirmationRange:[]})
let requestController, requestId=0, searchTimer
let autoNameTimer
const nameManuallyEdited=ref(false)

const emptyForm=()=>({id:'',orderNo:'',projectName:'',projectTypes:[],taskDescription:'',clientId:'',subClientId:'',clientShortName:'',clientCode:'',clientFullName:'',managerContact:'',contactName:'',customerOrderNo:'',subjectPrefix:'',emailSubjectPreview:'',projectStatus:'pending_confirmation',potentialDemand:'',projectPath:'',quotationPath:'',contractPath:'',taskDispatchedAt:'',taskSubmittedAt:'',clientManagerId:'',languageItems:[],priceItems:[],assignees:[]})
const form=reactive(emptyForm())
const rules={projectStatus:[{required:true,message:'请选择项目状态',trigger:'change'}]}
const activeUsers=computed(()=>users.value.filter((item)=>item.is_active ?? item.isActive ?? true))
const filterClientOptions=computed(()=>clients.value.flatMap((client)=>[{value:`client:${client.id}`,label:client.client_short_name||client.client_name},...((client.sub_clients||[]).map((sub)=>({value:`sub:${sub.id}`,label:`${client.client_short_name||client.client_name} / ${sub.client_short_name||sub.client_name}`})))]))
const selectedProjectTypeOptions=computed(()=>projectTypeOptions.filter((item)=>form.projectTypes.includes(item.value)))
const currentLanguageOptions=computed(()=>form.languageItems.filter((item)=>item.sourceLanguageId && (item.mode==='single'||item.targetLanguageId)).map((item)=>({key:`${item.sourceLanguageId}:${item.mode==='direction'?item.targetLanguageId:''}`,label:languageItemLabel(item)})))
const advancedCount=computed(()=>[searchForm.projectType,searchForm.languageId,searchForm.clientManagerId,searchForm.dispatchedRange?.length===2?1:'',searchForm.submittedRange?.length===2?1:'',searchForm.clientSelection,searchForm.assigneePersonId,searchForm.createdRange?.length===2?1:'',searchForm.consultationRange?.length===2?1:'',searchForm.confirmationRange?.length===2?1:''].filter(Boolean).length)

const userLabel=(item)=>item.full_name||item.fullName||item.username
const textValue=(value)=>value===null||value===undefined||value===''?'-':String(value)
const formatDateTime=(value)=>{if(!value)return '-';const date=new Date(String(value).replace(' ','T'));return Number.isNaN(date.getTime())?String(value):date.toLocaleString('zh-CN',{hour12:false})}
const compactDateTime=(value)=>{if(!value)return '-';const date=new Date(String(value).replace(' ','T'));if(Number.isNaN(date.getTime()))return String(value);const monthDay=`${date.getMonth()+1}/${date.getDate()}`;return date.getFullYear()===new Date().getFullYear()?monthDay:`${date.getFullYear()}/${monthDay}`}
const projectTypesText=(values)=>Array.isArray(values)&&values.length?values.map((value)=>projectTypeMap[value]||value).join('；'):'-'
const statusLabel=(value)=>statusMap[value]||value||'-'
const statusType=(value)=>({pending_confirmation:'info',trial:'warning',in_progress:'primary',sent_to_client:'success',client_feedback:'warning',cancelled:'danger',partially_cancelled:'warning'}[value]||'info')
const assignmentStatusLabel=(value)=>assignmentStatusMap[value]||value||'-'
const assignmentStatusType=(value)=>({assigned:'info',in_progress:'primary',completed:'success',cancelled:'danger'}[value]||'info')
const languageName=(id)=>languages.value.find((item)=>item.id===id)?.label||''
const languageItemLabel=(item)=>item.mode==='direction'?`${languageName(item.sourceLanguageId)}→${languageName(item.targetLanguageId)}`:languageName(item.sourceLanguageId)
const detailRow=(row)=>detailCache[row.id]||row

const buildFilters=()=>{const [ds,de]=searchForm.dispatchedRange||[],[ss,se]=searchForm.submittedRange||[];const selection=searchForm.clientSelection||'';return {keyword:searchForm.keyword.trim()||undefined,project_status:searchForm.projectStatus||undefined,project_type:searchForm.projectType||undefined,language_id:searchForm.languageId||undefined,client_manager_id:searchForm.clientManagerId||undefined,dispatched_date_start:ds||undefined,dispatched_date_end:de||undefined,submitted_date_start:ss||undefined,submitted_date_end:se||undefined,client_id:selection.startsWith('client:')?selection.slice(7):undefined,sub_client_id:selection.startsWith('sub:')?selection.slice(4):undefined,assignee_person_id:searchForm.assigneePersonId||undefined,created_date_start:searchForm.createdRange?.[0]||undefined,created_date_end:searchForm.createdRange?.[1]||undefined,consultation_date_start:searchForm.consultationRange?.[0]||undefined,consultation_date_end:searchForm.consultationRange?.[1]||undefined,confirmation_date_start:searchForm.confirmationRange?.[0]||undefined,confirmation_date_end:searchForm.confirmationRange?.[1]||undefined}}
const fetchData=async()=>{requestController?.abort();requestController=new AbortController();const current=++requestId;loading.value=true;const filters=buildFilters();try{const [rows,count]=await Promise.all([annotationApi.getAnnotationProjects({skip:(pagination.page-1)*pagination.limit,limit:pagination.limit,...filters},{signal:requestController.signal}),annotationApi.getAnnotationProjectCount(filters,{signal:requestController.signal})]);if(current!==requestId)return;tableData.value=Array.isArray(rows)?rows:[];pagination.total=count?.total||0}catch(error){if(current!==requestId||error?.code==='ERR_CANCELED')return;ElMessage.error(error.detail||'加载标注项目失败')}finally{if(current===requestId)loading.value=false}}
const handleSearch=()=>{clearTimeout(searchTimer);pagination.page=1;fetchData()}
const handleTextSearch=(value)=>{clearTimeout(searchTimer);if(!value?.trim())return handleSearch();searchTimer=setTimeout(handleSearch,400)}
const clearAdvanced=()=>{Object.assign(searchForm,{projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[],clientSelection:'',assigneePersonId:'',createdRange:[],consultationRange:[],confirmationRange:[]});handleSearch()}
const resetSearch=()=>{Object.assign(searchForm,{keyword:'',projectStatus:'',projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[],clientSelection:'',assigneePersonId:'',createdRange:[],consultationRange:[],confirmationRange:[]});handleSearch()}
const loadReferenceData=async()=>{const results=await Promise.allSettled([clientApi.getClients({skip:0,limit:500,frequent_first:true}),userApi.getUsers({skip:0,limit:500}),getProjectLanguages(),talentApi.getProjectTalentOptions('annotation')]);clients.value=results[0].status==='fulfilled'&&Array.isArray(results[0].value)?results[0].value:[];users.value=results[1].status==='fulfilled'&&Array.isArray(results[1].value)?results[1].value:[];languages.value=results[2].status==='fulfilled'?results[2].value:[];annotationTalents.value=results[3].status==='fulfilled'&&Array.isArray(results[3].value)?results[3].value:[]}
const loadDetail=async(id,force=false)=>{if(!force&&detailCache[id])return detailCache[id];detailLoadingId.value=id;try{const detail=await annotationApi.getAnnotationProject(id);detailCache[id]=detail;return detail}catch(error){ElMessage.error(error.detail||'加载项目详情失败');return null}finally{detailLoadingId.value=null}}

const fetchClientSuggestions=fetchProjectClientSuggestions
const handleClientSelect=(client)=>{form.clientId=client.parent_client_id||client.id||'';form.subClientId=client.sub_client_id||'';form.clientShortName=client.client_short_name||'';form.clientFullName=client.client_name||'';form.clientCode=client.client_code||'';form.managerContact=client.manager_contact||''}
const handleClientShortNameInput=()=>{const hadSelectedClient=Boolean(form.clientId||form.subClientId);form.clientId='';form.subClientId='';form.clientCode='';form.managerContact='';if(hadSelectedClient)form.clientFullName=''}
const clearSelectedClient=()=>{form.clientId='';form.subClientId='';form.clientShortName='';form.clientFullName='';form.clientCode='';form.managerContact=''}
const addLanguageItem=()=>form.languageItems.push({mode:'single',sourceLanguageId:'',targetLanguageId:''})
const addPriceItem=()=>form.priceItems.push({projectType:'',languageKey:'',amount:null,currency:'',unit:'',remarks:''})
const addAssignee=()=>form.assignees.push({personId:'',assignmentStatus:'assigned',qualityScore:'',evaluationNote:''})
const addLanguage=async()=>{try{const {value}=await ElMessageBox.prompt('请输入要新增的语种或方言名称','新增共享语种',{inputPlaceholder:'例如：粤语',inputValidator:(text)=>!!text?.trim()||'语种名称不能为空'});const created=await createProjectLanguage(value.trim());languages.value.push(created);ElMessage.success('语种已新增并标记为“新”')}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'新增语种失败')}}
const normalizedLanguageItems=()=>form.languageItems.filter((item)=>item.sourceLanguageId).map((item)=>({sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.mode==='direction'?(item.targetLanguageId||null):null}))
const splitLanguageKey=(key)=>{if(!key)return {sourceLanguageId:null,targetLanguageId:null};const [source,target]=key.split(':');return {sourceLanguageId:source||null,targetLanguageId:target||null}}
const validateLanguageItems=()=>{for(const item of form.languageItems){if(!item.sourceLanguageId)throw new Error('每个语言项都必须选择语种');if(item.mode==='direction'&&!item.targetLanguageId)throw new Error('翻译方向必须选择目标语种');if(item.targetLanguageId===item.sourceLanguageId)throw new Error('语言方向的两个语种不能相同')}const keys=normalizedLanguageItems().map((item)=>`${item.sourceLanguageId}:${item.targetLanguageId||''}`);if(new Set(keys).size!==keys.length)throw new Error('同一语言或语言方向不能重复')}
const validateFormData=()=>{validateLanguageItems();if(form.taskDispatchedAt&&form.taskSubmittedAt&&new Date(form.taskSubmittedAt)<new Date(form.taskDispatchedAt))throw new Error('任务提交时间不能早于任务派发时间');const languageKeys=new Set(currentLanguageOptions.value.map((item)=>item.key));for(const item of form.priceItems){if(item.projectType&&!form.projectTypes.includes(item.projectType))throw new Error('报价引用了当前项目未选择的项目类型');if(item.languageKey&&!languageKeys.has(item.languageKey))throw new Error('报价引用了当前项目未选择的语言项');if(!item.amount||item.amount<=0)throw new Error('报价金额必须大于零');if(!item.unit?.trim())throw new Error('报价必须填写计价单位')}for(const item of form.assignees){if(!item.personId)throw new Error('每条标注人员安排都必须选择人员')}const personIds=form.assignees.map((item)=>item.personId);if(new Set(personIds).size!==personIds.length)throw new Error('同一标注人员不能重复安排')}
const buildPayload=()=>{validateFormData();return {projectName:form.projectName?.trim()||null,projectTypes:form.projectTypes,taskDescription:form.taskDescription?.trim()||null,clientId:form.clientId||null,subClientId:form.subClientId||null,clientName:form.clientFullName?.trim()||null,clientShortName:form.clientShortName?.trim()||null,clientCode:form.clientCode?.trim()||null,contactName:form.contactName?.trim()||null,customerOrderNo:form.customerOrderNo?.trim()||null,emailSubjectPreview:form.emailSubjectPreview?.trim()||null,projectStatus:form.projectStatus,potentialDemand:form.potentialDemand?.trim()||null,projectPath:form.projectPath?.trim()||null,quotationPath:form.quotationPath?.trim()||null,contractPath:form.contractPath?.trim()||null,taskDispatchedAt:form.taskDispatchedAt||null,taskSubmittedAt:form.taskSubmittedAt||null,clientManagerId:form.clientManagerId||null,languageItems:normalizedLanguageItems(),priceItems:form.priceItems.map((item)=>({projectType:item.projectType||null,...splitLanguageKey(item.languageKey),amount:item.amount,currency:item.currency||null,unit:item.unit.trim(),remarks:item.remarks?.trim()||null})),assignees:form.assignees.filter(item=>item.personId).map(item=>({personId:item.personId,assignmentStatus:item.assignmentStatus,qualityScore:item.qualityScore?.trim()||null,evaluationNote:item.evaluationNote?.trim()||null}))}}
const generateProjectName=async()=>{try{validateLanguageItems();const result=await annotationApi.previewAnnotationProjectName({clientShortName:form.clientShortName?.trim()||null,projectTypes:form.projectTypes,languageItems:normalizedLanguageItems()});form.projectName=result.projectName;nameManuallyEdited.value=false;ElMessage.success('项目名称已生成，仍可手工修改')}catch(error){ElMessage.warning(error.detail||error.message||'无法生成项目名称')}}
const generateEmailSubject=()=>notifyEmailSubjectGenerated(form,ElMessage)
const assignForm=(detail)=>{const client=clients.value.find((item)=>item.id===detail.clientId);Object.assign(form,emptyForm(),{...detail,projectName:detail.projectName||'',clientId:detail.clientId||'',subClientId:detail.subClientId||'',clientShortName:detail.clientShortName||'',clientCode:detail.clientCode||'',clientFullName:detail.clientFullName||'',managerContact:detail.managerContact||client?.manager_contact||'',contactName:detail.contactName||'',customerOrderNo:detail.customerOrderNo||'',emailSubjectPreview:detail.emailSubjectPreview||'',potentialDemand:detail.potentialDemand||'',projectPath:detail.projectPath||'',quotationPath:detail.quotationPath||'',contractPath:detail.contractPath||'',taskDispatchedAt:detail.taskDispatchedAt||'',taskSubmittedAt:detail.taskSubmittedAt||'',clientManagerId:detail.clientManagerId||'',languageItems:(detail.languageItems||[]).map((item)=>({mode:item.targetLanguageId?'direction':'single',sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.targetLanguageId||''})),priceItems:(detail.priceItems||[]).map((item)=>({projectType:item.projectType||'',languageKey:item.sourceLanguageId?`${item.sourceLanguageId}:${item.targetLanguageId||''}`:'',amount:Number(item.amount),currency:item.currency||'',unit:item.unit||'',remarks:item.remarks||''})),assignees:(detail.assignees||[]).map(item=>({personId:item.personId,assignmentStatus:item.assignmentStatus||'assigned',qualityScore:item.qualityScore||'',evaluationNote:item.evaluationNote||''}))});nameManuallyEdited.value=!!detail.projectName}
const handleAdd=()=>{dialogTitle.value='新增标注项目';resetForm();nameManuallyEdited.value=false;dialogVisible.value=true}
const handleEdit=async(row)=>{const detail=await loadDetail(row.id,true);if(!detail)return;dialogTitle.value=`编辑标注项目 · ${detail.orderNo}`;assignForm(detail);dialogVisible.value=true}
const scrollEditorToTop=()=>dialogBodyRef.value?.parentElement?.scrollTo({top:0,behavior:'smooth'})
const handleSubmit=async()=>{const valid=await formRef.value?.validate().catch(()=>false);if(!valid){scrollEditorToTop();return}submitLoading.value=true;try{const payload=buildPayload();const saved=form.id?await annotationApi.updateAnnotationProject(form.id,payload):await annotationApi.createAnnotationProject(payload);if(form.id)delete detailCache[form.id];if(saved?.id)detailCache[saved.id]=saved;ElMessage.success(form.id?'标注项目已更新':'标注项目已创建');dialogVisible.value=false;await fetchData()}catch(error){ElMessage.error(error.detail||error.message||'保存失败');scrollEditorToTop()}finally{submitLoading.value=false}}
const setProjectStatusSaving=(id,saving)=>{const next=new Set(projectStatusSavingIds.value);if(saving)next.add(id);else next.delete(id);projectStatusSavingIds.value=next}
const changeProjectStatus=async(row,value)=>{if(!value||value===row.projectStatus)return;setProjectStatusSaving(row.id,true);try{const updated=await annotationApi.updateAnnotationProjectStatus(row.id,value);Object.assign(row,updated);detailCache[row.id]=updated;ElMessage.success('项目状态已更新');if(searchForm.projectStatus&&searchForm.projectStatus!==updated.projectStatus)await fetchData()}catch(error){ElMessage.error(error?.response?.data?.detail||error?.detail||'项目状态更新失败')}finally{setProjectStatusSaving(row.id,false)}}
const handleDelete=async(row)=>{try{await ElMessageBox.confirm(`确定删除标注项目“${row.orderNo}”吗？`,'删除确认',{type:'warning'});await annotationApi.deleteAnnotationProject(row.id);delete detailCache[row.id];ElMessage.success('删除成功');await fetchData()}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'删除失败')}}
const resetForm=()=>{Object.assign(form,emptyForm());nameManuallyEdited.value=false;formRef.value?.clearValidate();clearFieldSearch()}

const toOpenPathHref=(path)=>`openpath://${encodeURIComponent(String(path).replace(/^\\\\/,'')).replace(/%5C/gi,'\\').replace(/%2F/gi,'/')}`
const openPathValue=(path)=>{const value=String(path||'').trim();if(!value)return ElMessage.warning('暂无可打开的路径');window.location.href=toOpenPathHref(value)}
const copyPathValue=async(path)=>{const value=String(path||'').trim();if(!value)return ElMessage.warning('暂无可复制的路径');try{await navigator.clipboard.writeText(value);ElMessage.success('路径已复制')}catch{ElMessage.error('复制失败，请手工复制')}}
const projectPath=async(row)=>(await loadDetail(row.id))?.projectPath||''
const openProjectPath=async(row)=>openPathValue(await projectPath(row))
const copyProjectPath=async(row)=>copyPathValue(await projectPath(row))

watch(()=>[form.clientShortName,[...form.projectTypes],form.languageItems.map((item)=>`${item.mode}:${item.sourceLanguageId}:${item.targetLanguageId}`).join('|')],()=>{clearTimeout(autoNameTimer);if(nameManuallyEdited.value||!dialogVisible.value)return;autoNameTimer=setTimeout(()=>{const labels=form.languageItems.map(languageItemLabel).filter(Boolean);const directionSummary=labels.length>3?`${labels.slice(0,3).join('、')}等方向`:labels.join('、');const typeSummary=form.projectTypes.map((value)=>projectTypeMap[value]||value).join('、');form.projectName=[form.clientShortName?.trim(),directionSummary,typeSummary].filter(Boolean).join('-')},300)},{deep:true})

onMounted(async()=>{await loadReferenceData();await fetchData()})
onBeforeUnmount(()=>{clearTimeout(searchTimer);clearTimeout(autoNameTimer);requestController?.abort()})
</script>

<style scoped>
.client-autocomplete-field{width:100%}.client-autocomplete-hint{margin-top:4px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.4}.client-suggestion{display:flex;flex-direction:column;min-width:0;padding:4px 0;line-height:1.45}.client-suggestion__meta{overflow:hidden;color:var(--el-text-color-secondary);font-size:12px;text-overflow:ellipsis;white-space:nowrap}
.card-header,.header-actions,.advanced-header,.section-title-row,.language-row,.repeat-title,.order-cell{display:flex;align-items:center}.card-header,.advanced-header,.section-title-row,.repeat-title{justify-content:space-between}.header-actions{gap:8px}.order-cell{min-width:0;gap:4px}.order-cell :deep(.el-popover__reference-wrapper){flex:1;min-width:0}.order-no-link{display:block;width:100%;height:auto;min-width:0;padding:0;overflow:hidden;text-align:left;text-overflow:ellipsis;white-space:nowrap}.filter-count{display:inline-flex;min-width:18px;height:18px;margin-left:5px;padding:0 5px;align-items:center;justify-content:center;border-radius:9px;color:#fff;background:var(--el-color-primary);font-size:11px}.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-header{margin-bottom:12px;font-weight:600}.pagination{margin-top:20px}.form-section{margin-bottom:18px;padding:16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.form-section h3{margin:0 0 16px;font-size:16px}.section-title-row{margin-bottom:12px}.section-title-row h3{margin:0}.section-title-row--compact{margin-top:4px}.inline-section-label{color:var(--el-text-color-primary);font-size:14px;font-weight:600}.language-row{gap:10px;margin-bottom:10px}.direction-arrow{color:var(--el-color-primary);font-size:20px;font-weight:700}.new-tag{float:right;margin-left:8px}.price-card{margin-bottom:12px;padding:12px 12px 0;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-fill-color-light)}.repeat-title{margin-bottom:8px;font-weight:600}.pre-wrap{white-space:pre-wrap;word-break:break-word}.price-detail-list>div+div{margin-top:4px}.assignee-detail-item+.assignee-detail-item{margin-top:8px;padding-top:8px;border-top:1px dashed var(--el-border-color-lighter)}.assignee-detail-item .el-tag{margin-left:8px}.detail-secondary{color:var(--el-text-color-secondary);font-size:12px}.assignee-detail-item>.detail-secondary{display:flex;gap:16px;margin-top:4px}.client-source-tip{margin:-4px 0 16px}.project-name-cell{display:block;white-space:normal;word-break:break-word;line-height:1.5}.compact-datetime{display:inline-block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:help}.action-buttons{display:inline-flex;align-items:center;flex-wrap:nowrap;white-space:nowrap}.status-switch-tag.el-tag{display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;max-width:100%;cursor:pointer;user-select:none;vertical-align:middle;transition:opacity .15s ease}.status-switch-tag :deep(.el-tag__content){display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;white-space:nowrap;line-height:1}.status-switch-text{line-height:1}.status-switch-caret{width:10px;height:10px;flex-shrink:0;margin:0;font-size:10px}.status-switch-tag:hover{opacity:.85}.status-switch-tag.is-updating{pointer-events:none;opacity:.55}.status-option-row{display:inline-flex;align-items:center;gap:8px;width:100%}.status-current-icon{color:var(--el-color-primary)}.subject-preview-field{width:100%;min-width:0}.subject-preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.5}.subject-preview-toolbar .el-button{flex:none}.soft-action-button{--el-button-bg-color:var(--el-color-primary-light-9);--el-button-border-color:var(--el-color-primary-light-7);--el-button-text-color:var(--el-color-primary-dark-2);--el-button-hover-bg-color:var(--el-color-primary-light-8);--el-button-hover-border-color:var(--el-color-primary-light-5);--el-button-hover-text-color:var(--el-color-primary);flex:none;font-weight:500}
</style>

<style>
.annotation-advanced-popover,.annotation-detail-popover,.annotation-client-popover{max-width:calc(100vw - 32px)!important}.annotation-detail-popover .detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.annotation-detail-popover .el-descriptions__content,.annotation-client-popover .el-descriptions__content{white-space:normal;word-break:break-word}.annotation-editor-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.annotation-editor-dialog .el-dialog__header,.annotation-editor-dialog .el-dialog__footer{flex:0 0 auto}.annotation-editor-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto;padding-top:12px}.annotation-editor-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
</style>
