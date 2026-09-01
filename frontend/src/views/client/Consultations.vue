<template>
  <el-card class="consultations-card compact-list-card">
    <template #header>
      <div class="card-header">
        <span>新咨询管理</span>
        <div class="header-actions">
          <el-popover placement="bottom-end" :width="360" trigger="click" title="首页显示字段">
            <template #reference>
              <el-button>字段设置</el-button>
            </template>
            <el-checkbox-group v-model="visibleColumnKeys" class="column-settings">
              <el-checkbox
                v-for="column in consultationColumnOptions"
                :key="column.key"
                :label="column.key"
              >
                {{ column.label }}
              </el-checkbox>
            </el-checkbox-group>
            <div class="column-settings-footer">
              <el-button link type="primary" @click="resetVisibleColumns">恢复默认</el-button>
            </div>
          </el-popover>
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmConsultationBatchDelete" />
          <el-tooltip content="快捷键：N" placement="bottom" :disabled="!canWrite || deleteMode">
            <el-button v-if="canWrite && !deleteMode" type="primary" :icon="Plus" @click="handleAdd">新增咨询</el-button>
          </el-tooltip>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input
          v-model="searchForm.keyword"
          placeholder="咨询编号、项目名称、客户名称或客户单号"
          clearable
          style="width: 320px"
          @input="handleDebouncedSearchInput"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="咨询状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
          <el-option
            v-for="item in consultationStatusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <AdvancedFilterPopover
          v-model:visible="advancedFilterVisible"
          :count="advancedFilterCount"
          popper-class="consultation-advanced-filter-popover"
          @clear="clearAdvancedFilters"
          @reset="resetSearch"
        >
          <el-form :model="searchForm" label-position="top" class="advanced-filter-form">
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="咨询日期">
                    <el-date-picker
                      v-model="searchForm.consultation_date_range"
                      type="daterange"
                      range-separator="至"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      value-format="YYYY-MM-DD"
                      unlink-panels
                      @change="handleSearch"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="咨询方式">
                    <el-select v-model="searchForm.consultation_method" placeholder="全部" clearable @change="handleSearch">
                      <el-option
                        v-for="item in consultationMethodOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="咨询类型">
                    <el-select v-model="searchForm.consultation_type" placeholder="全部" clearable @change="handleSearch">
                      <el-option
                        v-for="item in consultationTypeOptions"
                        :key="item"
                        :label="item"
                        :value="item"
                        :class="{ 'consultation-type-option--simple': isSimpleConsultationType(item) }"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="客户来源">
                    <el-input
                      v-model="searchForm.client_source"
                      placeholder="输入客户来源"
                      clearable
                      @input="handleDebouncedSearchInput"
                      @keyup.enter="handleSearch"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="客服人员">
                    <el-select v-model="searchForm.customer_service_id" placeholder="全部" clearable filterable @change="handleSearch">
                      <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="销售人员">
                    <el-select v-model="searchForm.sales_person_id" placeholder="全部" clearable filterable @change="handleSearch">
                      <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="跟进人">
                    <el-select v-model="searchForm.follow_up_person_id" placeholder="全部" clearable filterable @change="handleSearch">
                      <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="跟进状态">
                    <el-input
                      v-model="searchForm.follow_up_status"
                      placeholder="输入跟进状态"
                      clearable
                      @input="handleDebouncedSearchInput"
                      @keyup.enter="handleSearch"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
          </el-form>
        </AdvancedFilterPopover>
      </el-form-item>
    </el-form>

    <el-table ref="consultationTableRef" :data="tableData" v-loading="loading" row-key="id" border @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="consultation_code" label="咨询编号" width="160" show-overflow-tooltip>
        <template #header>
          <ClickableColumnHeader label="咨询编号" hint="点击咨询编号查看咨询详情" />
        </template>
        <template #default="{ row }">
          <el-popover
            placement="left"
            :width="760"
            trigger="click"
            popper-class="consultation-detail-popover"
            :title="`${row.consultation_code || '咨询'} 详情`"
            @show="loadConsultationDetail(row.id)"
            @hide="cancelInlineDetailEdit"
          >
            <template #reference>
              <el-button
                type="primary"
                link
                class="consultation-code-link business-clickable-cell"
                :title="`${row.consultation_code || '-'}（点击查看详情）`"
                @click.stop
              >
                {{ row.consultation_code || '-' }}
              </el-button>
            </template>
            <div class="detail-popover" v-loading="detailLoadingId === row.id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="咨询编号">
                  <span class="detail-value">{{ getDetailRow(row).consultation_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ getDetailRow(row).client_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户全称">
                  <span class="detail-value">{{ getDetailRow(row).client_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="子客户">
                  <span class="detail-value">{{ getDetailRow(row).sub_client_short_name || getDetailRow(row).sub_client_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).consultation_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询状态">
                  <span class="detail-value">{{ getStatusText(getDetailRow(row).status) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询方式">
                  <span class="detail-value">{{ consultationMethodDisplay(getDetailRow(row)) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户来源">
                  <InlineTextField :model-value="getDetailRow(row).client_source" :editable="canWrite && !deleteMode" label="客户来源" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'client_source', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="来源关键词">
                  <InlineTextField :model-value="getDetailRow(row).source_keyword" :editable="canWrite && !deleteMode" label="来源关键词" :maxlength="255" :save-field="(value) => saveConsultationTextField(row, 'source_keyword', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="咨询类型">
                  <span class="detail-value">{{ consultationTypeLabel(getDetailRow(row).consultation_type) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="处理方式">
                  <InlineTextField :model-value="getDetailRow(row).handling_method" :editable="canWrite && !deleteMode" label="处理方式" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'handling_method', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="项目名称"><InlineTextField :model-value="getDetailRow(row).project_name" :editable="canWrite && !deleteMode" label="项目名称" :maxlength="500" :save-field="(value) => saveConsultationTextField(row, 'project_name', value)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                <el-descriptions-item label="子客户/联系人"><InlineTextField :model-value="getDetailRow(row).contact_name" :editable="canWrite && !deleteMode" label="子客户/联系人" :maxlength="255" :save-field="(value) => saveConsultationTextField(row, 'contact_name', value)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                <el-descriptions-item label="客户单号/标识"><InlineTextField :model-value="getDetailRow(row).customer_order_no" :editable="canWrite && !deleteMode" label="客户单号/标识" :maxlength="150" :save-field="(value) => saveConsultationTextField(row, 'customer_order_no', value)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                <el-descriptions-item label="客服人员">
                  <span class="detail-value">{{ getUserName(getDetailRow(row).customer_service_id) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="销售人员">
                  <span class="detail-value">{{ getUserName(getDetailRow(row).sales_person_id) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="编辑人">
                  <span class="detail-value">{{ getUserName(getDetailRow(row).editor_id) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进人">
                  <span class="detail-value">{{ getUserName(getDetailRow(row).follow_up_person_id) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进次数">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_count ?? 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).follow_up_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进状态" :span="2">
                  <InlineTextField :model-value="getDetailRow(row).follow_up_status" :editable="canWrite && !deleteMode" label="跟进状态" :maxlength="20" :save-field="(value) => saveConsultationTextField(row, 'follow_up_status', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="咨询描述" :span="2">
                  <InlineTextField :model-value="getDetailRow(row).consultation_description" :editable="canWrite && !deleteMode" label="咨询描述" multiline :save-field="(value) => saveConsultationTextField(row, 'consultation_description', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="跟进备注" :span="2">
                  <InlineTextField :model-value="getDetailRow(row).follow_up_remarks" :editable="canWrite && !deleteMode" label="跟进备注" multiline :save-field="(value) => saveConsultationTextField(row, 'follow_up_remarks', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <el-descriptions-item label="备注" :span="2">
                  <InlineTextField :model-value="getDetailRow(row).remarks" :editable="canWrite && !deleteMode" label="备注" multiline :save-field="(value) => saveConsultationTextField(row, 'remarks', value)" @conflict="loadConsultationDetail(row.id, true)" />
                </el-descriptions-item>
                <template v-if="isTranslationConsultationType(getDetailRow(row).consultation_type)">
                  <el-descriptions-item label="服务内容"><InlineTextField :model-value="getDetailRow(row).project_intake?.service_content" :editable="canWrite && !deleteMode" label="服务内容" :maxlength="255" :save-field="(value) => saveConsultationTextField(row, 'service_content', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="文本类型"><InlineTextField :model-value="getDetailRow(row).project_intake?.file_type_secondary" :editable="canWrite && !deleteMode" label="文本类型" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'file_type_secondary', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="合同类型"><InlineTextField :model-value="getDetailRow(row).project_intake?.project_contract_type" :editable="canWrite && !deleteMode" label="合同类型" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'project_contract_type', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="合同状态"><InlineTextField :model-value="getDetailRow(row).project_intake?.project_contract_status" :editable="canWrite && !deleteMode" label="合同状态" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'project_contract_status', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="报价单状态"><InlineTextField :model-value="getDetailRow(row).project_intake?.quotation_status" :editable="canWrite && !deleteMode" label="报价单状态" :maxlength="100" :save-field="(value) => saveConsultationTextField(row, 'quotation_status', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="报价单路径" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.quotation_path" :editable="canWrite && !deleteMode" label="报价单路径" multiline :save-field="(value) => saveConsultationTextField(row, 'quotation_path', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户专业要求" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.customer_requirement_professional" :editable="canWrite && !deleteMode" label="客户专业要求" multiline :save-field="(value) => saveConsultationTextField(row, 'customer_requirement_professional', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="客户特殊要求" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.customer_requirement_special" :editable="canWrite && !deleteMode" label="客户特殊要求" multiline :save-field="(value) => saveConsultationTextField(row, 'customer_requirement_special', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                </template>
                <template v-else-if="isInterpretationConsultationType(getDetailRow(row).consultation_type)">
                  <el-descriptions-item label="具体任务" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.task_description" :editable="canWrite && !deleteMode" label="具体任务" multiline :save-field="(value) => saveConsultationTextField(row, 'task_description', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                </template>
                <template v-else-if="isAnnotationConsultationType(getDetailRow(row).consultation_type)">
                  <el-descriptions-item label="具体任务" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.task_description" :editable="canWrite && !deleteMode" label="具体任务" required multiline :save-field="(value) => saveConsultationTextField(row, 'task_description', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="潜在需求量" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.potential_demand" :editable="canWrite && !deleteMode" label="潜在需求量" multiline :save-field="(value) => saveConsultationTextField(row, 'potential_demand', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                </template>
                <template v-else-if="isRecruitmentConsultationType(getDetailRow(row).consultation_type)">
                  <el-descriptions-item label="职位名称/类型"><InlineTextField :model-value="getDetailRow(row).project_intake?.position_title" :editable="canWrite && !deleteMode" label="职位名称/类型" required :maxlength="255" :save-field="(value) => saveConsultationTextField(row, 'position_title', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="工作地点"><InlineTextField :model-value="getDetailRow(row).project_intake?.work_location" :editable="canWrite && !deleteMode" label="工作地点" required :maxlength="500" :save-field="(value) => saveConsultationTextField(row, 'work_location', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                  <el-descriptions-item label="职位描述" :span="2"><InlineTextField :model-value="getDetailRow(row).project_intake?.job_description" :editable="canWrite && !deleteMode" label="职位描述" multiline :save-field="(value) => saveConsultationTextField(row, 'job_description', value, true)" @conflict="loadConsultationDetail(row.id, true)" /></el-descriptions-item>
                </template>
                <el-descriptions-item label="创建时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).created_at) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="更新时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).updated_at) }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column
        v-for="column in displayedConsultationColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :show-overflow-tooltip="column.key !== 'status'"
      >
        <template #header>
          <ClickableColumnHeader v-if="column.key === 'client_short_name'" :label="column.label" hint="点击客户简称查看客户信息" />
          <span v-else>{{ column.label }}</span>
        </template>
        <template #default="{ row }">
          <el-popover
            v-if="column.key === 'client_short_name' && row.client_id"
            placement="left"
            :width="760"
            trigger="click"
            popper-class="consultation-client-detail-popover"
            :title="`${row.client_short_name || row.client_name || '客户'} 客户信息`"
            @show="loadClientDetail(row.client_id)"
          >
            <template #reference>
              <el-button
                type="primary"
                link
                class="client-short-name-link business-clickable-cell"
                :title="`${row.client_short_name || '-'}（点击查看详情）`"
                @click.stop
              >
                {{ row.sub_client_short_name ? `${row.client_short_name || '-'} / ${row.sub_client_short_name}` : (row.client_short_name || '-') }}
              </el-button>
            </template>
            <div class="detail-popover" v-loading="clientDetailLoadingId === row.client_id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ getClientDetailRow(row).client_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户全称">
                  <span class="detail-value">{{ getClientDetailRow(row).client_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getClientDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户经理">
                  <span class="detail-value">{{ getClientDetailRow(row).client_manager || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户经理联系方式">
                  <span class="detail-value">{{ getClientDetailRow(row).manager_contact || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户状态">
                  <span class="detail-value">{{ getClientStatusLabel(getClientDetailRow(row).client_status) }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
          <span v-else-if="column.key === 'client_short_name'">
            {{ row.sub_client_short_name ? `${row.client_short_name || '-'} / ${row.sub_client_short_name}` : (row.client_short_name || '-') }}
          </span>
          <el-dropdown
            v-else-if="column.key === 'status'"
            trigger="click"
            :disabled="statusUpdatingId === row.id"
            @command="(command) => handleInlineStatusChange(row, command)"
          >
            <el-tag
              :type="getStatusType(row.status)"
              size="small"
              class="status-switch-tag"
              :class="{ 'is-updating': statusUpdatingId === row.id }"
            >
              <span class="status-switch-text">{{ getStatusText(row.status) }}</span>
              <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
            </el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="item in consultationStatusOptions"
                  :key="item.value"
                  :command="item.value"
                  :disabled="item.value === row.status || statusUpdatingId === row.id || (item.value === CONFIRMED_CONSULTATION_STATUS && isSimpleConsultationType(row.consultation_type))"
                >
                  <span class="status-option-row">
                    <el-tag :type="getStatusType(item.value)" size="small" effect="plain" class="status-option-tag">
                      {{ item.label }}
                    </el-tag>
                    <el-icon v-if="item.value === row.status" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <template v-else-if="column.key === 'consultation_time'">
            <el-tag
              v-if="isToday(row.consultation_time)"
              type="success"
              effect="light"
              round
              class="today-consultation-time"
            >
              今日 {{ formatTime(row.consultation_time) }}
            </el-tag>
            <el-tag
              v-else-if="isYesterday(row.consultation_time)"
              type="warning"
              effect="light"
              round
              class="yesterday-consultation-time"
            >
              昨日 {{ formatTime(row.consultation_time) }}
            </el-tag>
            <span v-else>{{ formatDatetime(row.consultation_time) }}</span>
          </template>
          <span v-else-if="column.type === 'datetime'">{{ formatDatetime(row[column.key]) }}</span>
          <span v-else-if="column.type === 'user'">{{ getUserName(row[column.key]) }}</span>
          <span v-else-if="column.key === 'consultation_method'">{{ consultationMethodDisplay(row) }}</span>
          <span v-else-if="column.key === 'consultation_type'">{{ consultationTypeLabel(row.consultation_type) }}</span>
          <span v-else>{{ row[column.key] ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <PrimaryEditButton @click="handleEdit(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="consultations-pagination"
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="fetchData"
      @current-change="fetchData"
    />

    <el-dialog
      ref="consultationDialogRef"
      v-model="dialogVisible"
      class="consultation-dialog draggable-form-dialog"
      width="min(1040px, calc(100vw - 32px))"
      top="5vh"
      draggable
      :overflow="false"
      @opened="handleConsultationDialogOpened"
      @close="handleDialogClose"
    >
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          v-model="fieldSearchKeyword"
          :title="dialogTitle"
          subtitle="搜索并快速定位表单字段"
          :fetch-suggestions="fetchFieldSuggestions"
          placeholder="搜索字段，如客户交稿时间"
          @select="handleLocateConsultationField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="consultationEditorRef" v-loading="editorLoading" class="consultation-editor">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <section v-if="isSimpleConsultationType(form.consultation_type)" class="form-section consultation-form-section consultation-form-section--primary simple-consultation-form">
          <div class="consultation-form-section__header">
            <h3>简单咨询</h3>
            <span>仅记录初步咨询；如需确认建项，请先切换为具体项目类型</span>
          </div>
          <el-alert title="简单咨询不能直接设为“已确认”，确定项目方向后再切换咨询类型并补充项目资料。" type="info" :closable="false" show-icon />
          <el-row :gutter="20">
            <el-col :xs="24" :md="12">
              <el-form-item label="咨询类型" prop="consultation_type">
                <el-select v-model="form.consultation_type" filterable allow-create placeholder="请选择咨询类型" style="width:100%" @change="handleConsultationTypeChange">
                  <el-option
                    v-for="item in consultationTypeOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                    :class="{ 'consultation-type-option--simple': isSimpleConsultationType(item) }"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="咨询状态" prop="status">
                <el-select v-model="form.status" placeholder="请选择" style="width:100%">
                  <el-option v-for="item in consultationStatusOptions" :key="item.value" :label="item.label" :value="item.value" :disabled="item.value === CONFIRMED_CONSULTATION_STATUS" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :xs="24" :md="12">
              <el-form-item label="客户简称" prop="client_short_name">
                <el-autocomplete
                  v-model="form.client_short_name"
                  :fetch-suggestions="searchClientsByShortName"
                  placeholder="输入简称联想客户，无匹配时保存后自动新增"
                  value-key="client_short_name"
                  clearable
                  style="width:100%"
                  @select="handleExistingClientSelect"
                  @clear="handleClientShortNameClear"
                  @input="handleClientShortNameInput"
                >
                  <template #default="{ item }">
                    <div class="client-suggestion">
                      <span>{{ item.client_short_name || item.client_name }}</span>
                      <span class="client-suggestion-meta">{{ [item.client_code, item.client_name].filter(Boolean).join(' · ') }}</span>
                    </div>
                  </template>
                </el-autocomplete>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="客户来源" prop="client_source">
                <el-input v-model="form.client_source" placeholder="不知道可写“未知”" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :xs="24" :md="12">
              <el-form-item label="客户经理联系方式" prop="manager_contact">
                <el-input
                  v-model="form.manager_contact"
                  maxlength="100"
                  clearable
                  placeholder="填写后同步到客户资料"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :xs="24" :md="12">
              <el-form-item label="咨询时间" prop="consultation_time">
                <el-date-picker v-model="form.consultation_time" type="datetime" placeholder="选择日期时间" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="咨询方式" prop="consultation_method">
                <div class="consultation-method-field">
                  <el-select v-model="form.consultation_method" placeholder="请选择" clearable>
                    <el-option v-for="item in consultationMethodOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                  <el-input
                    v-if="form.consultation_method"
                    v-model="form.consultation_method_custom"
                    :placeholder="consultationMethodDetailPlaceholder(form.consultation_method)"
                    maxlength="255"
                    clearable
                  />
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="咨询描述" prop="consultation_description">
            <el-input
              v-model="form.consultation_description"
              type="textarea"
              :rows="3"
              placeholder="不知道可写“无”"
            />
          </el-form-item>
        </section>

        <template v-else>
        <section class="form-section consultation-form-section consultation-form-section--primary">
          <div class="consultation-form-section__header">
            <h3>咨询基本信息</h3>
            <span>请先选择咨询类型，后续售前字段将按项目类型显示</span>
          </div>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="咨询类型" prop="consultation_type">
                <el-select
                  v-model="form.consultation_type"
                  filterable
                  allow-create
                  placeholder="请选择；其他项目可直接输入自定义类型"
                  style="width: 100%"
                  @change="handleConsultationTypeChange"
                >
                  <el-option
                    v-for="item in consultationTypeOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                    :class="{ 'consultation-type-option--simple': isSimpleConsultationType(item) }"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-if="!isCoreFieldsRequiredProjectType(form.consultation_type)" :span="12">
              <el-form-item
                label="客户来源"
                prop="client_source"
              >
                <el-input v-model="form.client_source" placeholder="不知道可写“未知”" />
              </el-form-item>
            </el-col>
          </el-row>

          <div
            v-if="isCoreFieldsRequiredProjectType(form.consultation_type)"
            class="consultation-confirmation-fields consultation-core-required-fields"
          >
            <div class="consultation-confirmation-fields__title">
              {{ consultationTypeLabel(form.consultation_type) }}关键必填信息
              <span>请优先填写以下咨询信息</span>
            </div>
            <el-row :gutter="20">
              <el-col :xs="24" :md="12">
                <el-form-item label="客户来源" prop="client_source">
                  <el-input v-model="form.client_source" placeholder="不知道可写“未知”" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="咨询方式" prop="consultation_method">
                  <div class="consultation-method-field">
                    <el-select v-model="form.consultation_method" placeholder="请选择" clearable>
                      <el-option
                        v-for="item in consultationMethodOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                    <el-input
                      v-if="form.consultation_method"
                      v-model="form.consultation_method_custom"
                      :placeholder="consultationMethodDetailPlaceholder(form.consultation_method)"
                      maxlength="255"
                      clearable
                    />
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :xs="24" :md="12">
                <el-form-item label="咨询时间" prop="consultation_time">
                  <el-date-picker
                    v-model="form.consultation_time"
                    type="datetime"
                    placeholder="选择日期时间"
                    style="width: 100%"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm"
                    time-format="HH:mm"
                    :show-now="true"
                    :show-confirm="true"
                    :show-footer="true"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="来源关键词" prop="source_keyword">
                  <el-input v-model="form.source_keyword" placeholder="请输入来源渠道或推广关键词" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="咨询描述" prop="consultation_description">
              <el-input v-model="form.consultation_description" type="textarea" :rows="3" placeholder="不知道可写“无”" />
            </el-form-item>
          </div>

          <div v-if="isTranslationConsultationType(form.consultation_type)" class="consultation-confirmation-fields">
            <div class="consultation-confirmation-fields__title">
              笔译确认关键信息
              <span>将用于“已确认”后的邮件预览</span>
            </div>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="服务内容" required>
                  <el-select
                    v-model="form.project_intake.service_content"
                    filterable
                    allow-create
                    default-first-option
                    clearable
                    placeholder="可选择翻译、排版，或输入自定义内容"
                    style="width: 100%"
                  >
                    <el-option v-for="item in serviceContentOptions" :key="item" :label="item" :value="item" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="翻译方向" required>
                  <LanguagePairSelect v-model="form.project_intake.language_pair" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="客户交稿时间">
                  <el-date-picker
                    v-model="form.project_intake.customer_deadline_time"
                    type="datetime"
                    value-format="YYYY-MM-DDTHH:mm:ss"
                    style="width: 100%"
                    format="YYYY-MM-DD HH:mm"
                    time-format="HH:mm"
                    :show-now="true"
                    :show-confirm="true"
                    :show-footer="true"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="项目字数统计">
              <div class="consultation-word-count-field">
                <span>{{ formatWordCountMatrix(form.project_intake.word_count_matrix) }}</span>
                <WordCountMatrixPopover
                  v-model="form.project_intake.word_count_matrix"
                  local
                  title="项目字数统计"
                >
                  <template #reference><el-button type="primary" link>展开字数统计</el-button></template>
                </WordCountMatrixPopover>
              </div>
            </el-form-item>
          </div>

          <el-row v-if="!isCoreFieldsRequiredProjectType(form.consultation_type)" :gutter="20">
            <el-col :span="12">
              <el-form-item label="咨询方式" prop="consultation_method">
                <div class="consultation-method-field">
                  <el-select v-model="form.consultation_method" placeholder="请选择" clearable>
                    <el-option
                      v-for="item in consultationMethodOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                  <el-input
                    v-if="form.consultation_method"
                    v-model="form.consultation_method_custom"
                    :placeholder="consultationMethodDetailPlaceholder(form.consultation_method)"
                    maxlength="255"
                    clearable
                  />
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="咨询时间" prop="consultation_time">
                <el-date-picker
                  v-model="form.consultation_time"
                  type="datetime"
                  placeholder="选择日期时间"
                  style="width: 100%"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  format="YYYY-MM-DD HH:mm"
                  time-format="HH:mm"
                  :show-now="true"
                  :show-confirm="true"
                  :show-footer="true"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col v-if="!isCoreFieldsRequiredProjectType(form.consultation_type)" :span="12">
              <el-form-item label="来源关键词" prop="source_keyword">
                <el-input v-model="form.source_keyword" placeholder="请输入来源渠道或推广关键词" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="咨询状态" prop="status">
                <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
                  <el-option
                    v-for="item in consultationStatusOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item
            v-if="!isCoreFieldsRequiredProjectType(form.consultation_type)"
            label="咨询描述"
            prop="consultation_description"
          >
            <el-input v-model="form.consultation_description" type="textarea" :rows="3" placeholder="不知道可写“无”" />
          </el-form-item>
        </section>

        <section class="form-section consultation-form-section consultation-form-section--plain">
          <div class="consultation-form-section__header">
            <h3>客户信息</h3>
          </div>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="客户简称" prop="client_short_name">
                <div class="client-short-name-field">
                  <div class="client-short-name-control">
                    <el-autocomplete
                      v-model="form.client_short_name"
                      :fetch-suggestions="searchClientsByShortName"
                      placeholder="输入简称联想客户，无匹配时保存后自动新增"
                      style="flex: 1;"
                      value-key="client_short_name"
                      clearable
                      @select="handleExistingClientSelect"
                      @clear="handleClientShortNameClear"
                      @input="handleClientShortNameInput"
                    >
                      <template #default="{ item }">
                        <div class="client-suggestion">
                          <span>{{ item.client_short_name || item.client_name }}</span>
                          <span class="client-suggestion-meta">
                            {{ [item.client_code, item.client_name].filter(Boolean).join(' · ') }}
                          </span>
                        </div>
                      </template>
                    </el-autocomplete>
                    <el-tag v-if="form.client_id" type="success" size="small" effect="plain">老客户</el-tag>
                    <el-tag v-else-if="form.client_short_name" type="warning" size="small" effect="plain">新客户</el-tag>
                  </div>
                  <div class="client-short-name-hint">
                    未匹配已有客户时，新增或编辑咨询都会自动创建客户并完成关联。
                  </div>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="客户编号">
                <ReadonlyField
                  :model-value="form.client_code"
                  source="auto"
                  :placeholder="!form.client_id && form.client_short_name ? '保存后自动生成' : '选择客户后自动带出'"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row v-if="form.client_id" :gutter="20">
            <el-col :span="12">
              <el-form-item label="子客户">
                <el-select
                  v-model="form.sub_client_id"
                  clearable
                  filterable
                  placeholder="不选则关联母客户"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in availableSubClients"
                    :key="item.id"
                    :label="`${item.client_short_name || item.client_name}${item.sub_client_code ? `（${item.sub_client_code}）` : ''}`"
                    :value="item.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="客户全称" prop="client_name">
                <el-autocomplete
                  v-model="form.client_name"
                  :fetch-suggestions="searchClientsByName"
                  placeholder="可选填客户全称"
                  value-key="client_name"
                  clearable
                  style="width: 100%"
                  @select="handleExistingClientSelect"
                  @clear="handleClientNameClear"
                  @input="handleClientNameInput"
                >
                  <template #default="{ item }">
                    <div class="client-suggestion">
                      <span>{{ item.client_name }}</span>
                      <span class="client-suggestion-meta">{{ item.client_code }}</span>
                    </div>
                  </template>
                </el-autocomplete>
              </el-form-item>
            </el-col>
            <el-col v-if="showManagerContactInput" :xs="24" :md="12">
              <el-form-item label="客户经理联系方式" prop="manager_contact">
                <el-input
                  v-model="form.manager_contact"
                  maxlength="100"
                  clearable
                  placeholder="填写后同步到客户资料，并用于邮件预览"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </section>

        <div
          v-if="isSupportedProjectType(form.consultation_type)"
          class="form-section consultation-project-intake consultation-form-section--plain"
        >
          <div class="consultation-form-section__header">
            <h3>项目售前信息</h3>
            <span>以下内容随咨询类型变化，用于后续确认建项</span>
          </div>
          <el-row :gutter="20">
            <el-col :xs="24" :md="12"><el-form-item label="项目名称" prop="project_name"><el-input v-model="form.project_name" placeholder="可留空并在确认前自动生成" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="客户单号/标识"><el-input v-model="form.customer_order_no" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="子客户/联系人"><el-input v-model="form.contact_name" /></el-form-item>

          <template v-if="isTranslationConsultationType(form.consultation_type)">
            <el-row :gutter="20">
              <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="form.project_intake.file_type_secondary" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.project_intake.priority" clearable style="width:100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :xs="24" :md="12"><el-form-item label="合同类型"><el-input v-model="form.project_intake.project_contract_type" clearable /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="合同状态"><el-input v-model="form.project_intake.project_contract_status" clearable /></el-form-item></el-col>
            </el-row>
            <el-form-item label="需提供报价单"><el-checkbox v-model="form.project_intake.quotation_required" @change="handleTranslationQuotationRequiredChange">需要提供项目报价单</el-checkbox></el-form-item>
            <el-row v-if="form.project_intake.quotation_required" :gutter="20">
              <el-col :xs="24" :md="8"><el-form-item label="报价单状态"><el-input v-model="form.project_intake.quotation_status" clearable /></el-form-item></el-col>
              <el-col :xs="24" :md="16"><el-form-item label="报价单路径"><el-input v-model="form.project_intake.quotation_path" clearable placeholder="如：\\win-server\项目报价单" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="客户专业要求"><el-input v-model="form.project_intake.customer_requirement_professional" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="客户特殊要求"><el-input v-model="form.project_intake.customer_requirement_special" type="textarea" :rows="2" /></el-form-item>
          </template>

          <template v-else-if="isInterpretationConsultationType(form.consultation_type)">
            <el-form-item label="项目类型" prop="project_intake.project_types"><el-select v-model="form.project_intake.project_types" multiple style="width:100%"><el-option v-for="item in interpretationTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
            <el-form-item label="具体任务"><el-input v-model="form.project_intake.task_description" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="地点" prop="project_intake.locations">
              <el-input v-model="interpretationLocationText" clearable placeholder="请输入地点，如：广州" />
            </el-form-item>
            <el-form-item label="预定时段" prop="project_intake.time_ranges">
              <div class="intake-list-field">
                <div class="intake-list-header intake-list-header--field intake-list-header--actions-only"><el-button link type="primary" @click="addIntakeTimeRange">增加时段</el-button></div>
                <div v-for="(item,index) in form.project_intake.time_ranges" :key="index" class="intake-inline-row">
                  <StableDateTimePicker v-model="item.scheduled_start" placeholder="开始时间" />
                  <StableDateTimePicker v-model="item.scheduled_end" placeholder="结束时间" />
                  <el-button
                    link
                    type="danger"
                    :disabled="form.project_intake.time_ranges.length <= 1"
                    @click="removeIntakeTimeRange(index)"
                  >删除</el-button>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="口译方向" prop="project_intake.language_directions">
              <div class="intake-list-field">
                <div class="intake-list-header intake-list-header--field">
                  <span>每个方向填写对应需求人数；合计 {{ interpretationRequiredTotal }} 人</span>
                  <el-button link type="primary" @click="addIntakeDirection">增加方向</el-button>
                </div>
                <div v-for="(item,index) in form.project_intake.language_directions" :key="index" class="intake-inline-row">
                  <el-select v-model="item.source_language_id" filterable placeholder="语种 A"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-select v-model="item.target_language_id" filterable placeholder="语种 B"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-input-number v-model="item.required_count" :min="1" :precision="0" placeholder="需求人数" class="intake-direction-count" />
                  <el-button
                    link
                    type="danger"
                    :disabled="form.project_intake.language_directions.length === 1"
                    @click="removeIntakeDirection(index)"
                  >删除</el-button>
                </div>
              </div>
            </el-form-item>
          </template>

          <template v-else-if="isAnnotationConsultationType(form.consultation_type)">
            <el-form-item label="项目类型" prop="project_intake.project_types"><el-select v-model="form.project_intake.project_types" multiple filterable allow-create style="width:100%"><el-option v-for="item in annotationTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
            <el-form-item label="具体任务" prop="project_intake.task_description"><el-input v-model="form.project_intake.task_description" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="潜在需求量"><el-input v-model="form.project_intake.potential_demand" /></el-form-item>
            <el-form-item label="语言范围" prop="project_intake.language_items">
              <div class="intake-list-field">
                <div class="intake-list-header intake-list-header--field"><span>至少保留一组语种</span><el-button link type="primary" @click="addAnnotationLanguage">增加语言</el-button></div>
                <div v-for="(item,index) in form.project_intake.language_items" :key="index" class="intake-inline-row">
                  <el-select v-model="item.source_language_id" filterable placeholder="语种"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-select v-model="item.target_language_id" filterable clearable placeholder="目标语种（可选）"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-button link type="danger" @click="form.project_intake.language_items.splice(index,1)">删除</el-button>
                </div>
              </div>
            </el-form-item>
          </template>

          <template v-else-if="isRecruitmentConsultationType(form.consultation_type)">
            <el-row :gutter="20"><el-col :xs="24" :md="12"><el-form-item label="职位名称/类型" prop="project_intake.position_title"><el-input v-model="form.project_intake.position_title" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="招聘人数" prop="project_intake.headcount_min"><div class="intake-inline-row"><el-input-number v-model="form.project_intake.headcount_min" :min="1" /><span>至</span><el-input-number v-model="form.project_intake.headcount_max" :min="form.project_intake.headcount_min || 1" /></div></el-form-item></el-col></el-row>
            <el-form-item label="职位描述"><el-input v-model="form.project_intake.job_description" type="textarea" :rows="3" /></el-form-item>
            <el-form-item label="外语/翻译方向" prop="project_intake.language_directions">
              <div class="intake-list-field">
                <div class="intake-list-header intake-list-header--field"><span>可选，确认建项时会同步到招聘项目</span><el-button link type="primary" @click="addRecruitmentDirection">增加方向</el-button></div>
                <div v-for="(item,index) in form.project_intake.language_directions" :key="index" class="intake-inline-row">
                  <el-select v-model="item.direction_type" style="width:126px" @change="item.direction_type==='single' && (item.target_language_id='')">
                    <el-option label="单语/方言" value="single" />
                    <el-option label="翻译方向" value="translation" />
                  </el-select>
                  <el-select v-model="item.source_language_id" filterable placeholder="语种/方言"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-select v-if="item.direction_type==='translation'" v-model="item.target_language_id" filterable placeholder="目标语种"><el-option v-for="lang in languageOptions" :key="lang.id" :label="lang.label" :value="lang.id" /></el-select>
                  <el-button link type="danger" @click="form.project_intake.language_directions.splice(index,1)">删除</el-button>
                </div>
              </div>
            </el-form-item>
            <el-row :gutter="20"><el-col :xs="24" :md="12"><el-form-item label="拟履职周期" prop="project_intake.employment_range"><el-date-picker v-model="form.project_intake.employment_range" type="daterange" value-format="YYYY-MM-DD" clearable style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="工作地点" prop="project_intake.work_location"><el-input v-model="form.project_intake.work_location" /></el-form-item></el-col></el-row>
          </template>
        </div>

        <section class="form-section consultation-form-section">
          <div class="consultation-form-section__header">
            <h3>跟进信息</h3>
          </div>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="处理方式" prop="handling_method">
                <el-input v-model="form.handling_method" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="跟进状态" prop="follow_up_status">
                <el-input v-model="form.follow_up_status" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="跟进次数" prop="follow_up_count">
              <el-input-number v-model="form.follow_up_count" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进时间" prop="follow_up_time">
              <el-date-picker
                v-model="form.follow_up_time"
                type="datetime"
                placeholder="选择日期时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                time-format="HH:mm"
                :show-now="true"
                :show-confirm="true"
                :show-footer="true"
              />
            </el-form-item>
          </el-col>
          </el-row>

          <section class="personnel-assignment-section">
          <button
            type="button"
            class="personnel-assignment-toggle"
            :aria-expanded="personnelAssignmentExpanded"
            @click="personnelAssignmentExpanded = !personnelAssignmentExpanded"
          >
            <span class="personnel-assignment-heading">
              <span class="personnel-assignment-title">人员分配</span>
              <span class="personnel-assignment-summary">{{ personnelAssignmentSummary }}</span>
            </span>
            <span class="personnel-assignment-action">
              {{ personnelAssignmentExpanded ? '收起' : '展开调整' }}
              <el-icon class="personnel-assignment-arrow" :class="{ 'is-expanded': personnelAssignmentExpanded }">
                <ArrowDown />
              </el-icon>
            </span>
          </button>

          <el-collapse-transition>
            <div v-show="personnelAssignmentExpanded" class="personnel-assignment-fields">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="客服人员" prop="customer_service_id">
                    <el-select
                      v-model="form.customer_service_id"
                      filterable
                      clearable
                      placeholder="请选择客服人员"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="user in userOptions"
                        :key="user.id"
                        :label="user.full_name || user.username"
                        :value="user.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="销售人员" prop="sales_person_id">
                    <el-select
                      v-model="form.sales_person_id"
                      filterable
                      clearable
                      placeholder="请选择销售人员"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="user in userOptions"
                        :key="user.id"
                        :label="user.full_name || user.username"
                        :value="user.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="编辑人" prop="editor_id">
                    <el-select
                      v-model="form.editor_id"
                      filterable
                      clearable
                      placeholder="请选择编辑人"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="user in userOptions"
                        :key="user.id"
                        :label="user.full_name || user.username"
                        :value="user.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="跟进人" prop="follow_up_person_id">
                    <el-select
                      v-model="form.follow_up_person_id"
                      filterable
                      clearable
                      placeholder="请选择跟进人"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="user in userOptions"
                        :key="user.id"
                        :label="user.full_name || user.username"
                        :value="user.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <div class="personnel-assignment-hint">默认使用当前用户；仅在需要转交或协作时调整。</div>
            </div>
          </el-collapse-transition>
          </section>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="跟进备注" prop="follow_up_remarks">
                <el-input v-model="form.follow_up_remarks" type="textarea" :rows="2" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="备注" prop="remarks">
                <el-input v-model="form.remarks" type="textarea" :rows="2" />
              </el-form-item>
            </el-col>
          </el-row>
        </section>
        </template>
      </el-form>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="!form.id" :disabled="formSubmitting" @click="handleSubmit(true)">保存并继续新增</el-button>
        <el-button type="primary" :loading="formSubmitting" @click="handleSubmit()">确定</el-button>
      </template>
    </el-dialog>

    <!-- 四类咨询确认、建项与内部邮件发送中间层 -->
    <el-dialog
      ref="confirmationDialogRef"
      v-model="confirmationDialogVisible"
      class="consultation-confirmation-dialog draggable-form-dialog"
      title="确认咨询并生成项目"
      width="min(720px, calc(100vw - 32px))"
      :close-on-click-modal="false"
      top="8vh"
      draggable
      :overflow="false"
      @opened="resetConfirmationDialogPosition"
      @close="resetConfirmationDraft"
    >
      <div v-loading="confirmationPreviewLoading" class="confirmation-preview-body">
        <el-alert
          title="确认后将更新咨询状态并生成对应项目；可选择仅建项，或同时向内部用户发送邮件。邮件投递失败不会回滚已生成项目。"
          type="info"
          :closable="false"
          show-icon
        />
        <el-descriptions :column="2" border size="small" class="confirmation-summary">
          <el-descriptions-item label="咨询类型">{{ confirmationTypeLabel }}</el-descriptions-item>
          <el-descriptions-item label="预计订单号">{{ confirmationPreview.order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ confirmationPreview.client_short_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户经理联系方式">{{ confirmationPreview.manager_contact || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发件人" :span="2">
            {{ confirmationPreview.sender_name || '未识别' }}
            <span v-if="confirmationPreview.sender_email"> · {{ confirmationPreview.sender_email }}</span>
            <el-tag
              v-if="confirmationPreview.sender_mode === 'personal'"
              size="small"
              :type="confirmationPreview.sender_verified ? 'success' : 'warning'"
              effect="plain"
            >个人邮箱</el-tag>
            <el-button
              v-if="confirmationPreview.sender_mode === 'personal' && !confirmationPreview.sender_verified"
              type="primary"
              link
              @click="openMailProfile"
            >查看发件邮箱状态</el-button>
          </el-descriptions-item>
        </el-descriptions>
        <el-form :model="confirmationForm" ref="confirmationFormRef" label-width="120px" @submit.prevent>
          <el-form-item
            label="项目名称"
            prop="projectName"
            :rules="[{ required: true, message: '请输入项目名称', trigger: 'blur' }]"
          >
            <el-input v-model="confirmationForm.projectName" maxlength="255" show-word-limit @input="regenerateConfirmationSubject" />
            <div class="project-name-hint">已按“客户简称-当前日期”预填，可在确认前修改。</div>
          </el-form-item>
          <el-form-item label="标题前缀">
            <el-select
              v-model="confirmationForm.subjectPrefix"
              filterable
              allow-create
              default-first-option
              clearable
              placeholder="可直接选择常用前缀，也可自行输入"
              style="width: 100%"
              @change="regenerateConfirmationSubject"
            >
              <el-option v-for="item in COMMON_SUBJECT_PREFIX_OPTIONS" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="confirmationPreview.project_type !== 'translation'" label="客户单号/标识">
            <el-input
              v-model="confirmationForm.customerOrderNo"
              maxlength="150"
              show-word-limit
              clearable
              @input="regenerateConfirmationSubject"
            />
          </el-form-item>
          <template v-if="confirmationPreview.project_type === 'translation'">
            <el-form-item label="客户经理联系方式" prop="managerContact">
              <el-input
                v-model="confirmationForm.managerContact"
                maxlength="100"
                show-word-limit
                clearable
                placeholder="可在此补充，填写后将同步到客户资料"
                @input="handleConfirmationManagerContactInput"
              />
            </el-form-item>
            <el-form-item
              label="服务内容"
              prop="serviceContent"
              :rules="[{ required: true, message: '请选择或输入服务内容', trigger: 'change' }]"
            >
              <el-select
                v-model="confirmationForm.serviceContent"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="请选择翻译、排版，或输入自定义内容"
                style="width: 100%"
                @change="refreshConfirmationMailPreview"
              >
                <el-option v-for="item in serviceContentOptions" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
            <el-form-item
              label="翻译方向"
              prop="languagePair"
              :rules="[{ required: true, message: '请选择翻译方向', trigger: 'change' }]"
            >
              <LanguagePairSelect
                :model-value="confirmationForm.languagePair"
                @update:model-value="handleConfirmationLanguagePairChange"
              />
            </el-form-item>
          </template>
          <el-form-item label="收件人" required>
            <InternalMailRecipientSelector
              v-model="confirmationForm.toUserIds"
              :users="validInternalUsers"
              :groups="confirmationRecipientGroups"
              placeholder="请选择收件人"
            />
          </el-form-item>
          <el-form-item label="抄送">
            <InternalMailRecipientSelector
              v-model="confirmationForm.ccUserIds"
              :users="validInternalUsers"
              :groups="confirmationRecipientGroups"
              :excluded-user-ids="confirmationForm.toUserIds"
              placeholder="请选择抄送人"
            />
          </el-form-item>
          <el-form-item label="邮件主题" required>
            <el-input v-model="confirmationForm.emailSubject" type="textarea" :rows="2" maxlength="1000" />
          </el-form-item>
          <el-form-item label="邮件正文" required>
            <MailBodyEditor
              ref="confirmationBodyEditorRef"
              v-model="confirmationForm.emailBody"
              v-model:html-value="confirmationForm.emailBodyHtml"
              :images="confirmationForm.inlineImages"
              @update:images="confirmationForm.inlineImages = $event"
              @uploading-change="confirmationImageUploading = $event"
            />
          </el-form-item>
          <el-form-item v-if="confirmationMissingFields.length" label="缺失字段">
            <div class="missing-field-list">
              <el-tag v-for="item in confirmationMissingFields" :key="item" type="warning" effect="plain">{{ item }}</el-tag>
              <span class="missing-field-hint">核心缺失项会阻止确认，其余字段只提示。</span>
            </div>
          </el-form-item>
          <el-alert v-if="confirmationPreview.blocking_reasons?.length" :title="confirmationPreview.blocking_reasons.join('；')" type="error" :closable="false" show-icon />
        </el-form>
      </div>
      <template #footer>
        <el-button :disabled="confirmationSubmitting" @click="confirmationDialogVisible = false">取消</el-button>
        <el-button
          :loading="confirmationSubmitting && confirmationSubmitAction === 'project-only'"
          :disabled="confirmationSubmitting || confirmationPreviewLoading || !confirmationPreview.order_no"
          @click="handleConfirmConsultation(false)"
        >只建项（不发邮件）</el-button>
        <el-button
          type="primary"
          :loading="confirmationSubmitting && confirmationSubmitAction === 'with-email'"
          :disabled="confirmationSubmitting || confirmationImageUploading || confirmationPreviewLoading || !confirmationPreview.order_no || !confirmationPreview.can_send || !confirmationForm.toUserIds.length || !confirmationForm.emailSubject.trim() || !confirmationForm.emailBody.trim()"
          @click="handleConfirmConsultation(true)"
        >确认建项并发送邮件</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Plus } from '@element-plus/icons-vue'
import * as consultationApi from '@/api/consultations'
import * as mailApi from '@/api/businessMails'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import * as clientApi from '@/api/clients'
import * as userApi from '@/api/users'
import { getProjectLanguages } from '@/api/projectLanguages'
import { buildAutoProjectName } from '@/utils/projectNaming'
import { formatDateTimeMinute as formatDatetime, formatTimeMinute as formatTime } from '@/utils/dateTime'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useFormDraft } from '@/composables/useFormDraft'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import InternalMailRecipientSelector from '@/components/common/InternalMailRecipientSelector.vue'
import MailBodyEditor from '@/components/common/MailBodyEditor.vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import StableDateTimePicker from '@/components/common/StableDateTimePicker.vue'
import InlineTextField from '@/components/common/InlineTextField.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { hasPermission } from '@/utils/permission'
import { COMMON_SUBJECT_PREFIX_OPTIONS } from '@/utils/emailSubject'
import { createEmptyWordCountMatrix, formatWordCountMatrix, normalizeWordCountMatrix } from '@/utils/wordCountMatrix'

const router = useRouter()
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增咨询')
const consultationDialogRef = ref(null)
const formRef = ref(null)
const consultationEditorRef = ref(null)
const {
  fieldSearchRef,
  fieldSearchKeyword,
  fetchFieldSuggestions,
  locateDialogField,
  clearFieldSearch,
} = useDialogFieldSearch(consultationEditorRef)
const userOptions = ref([])
const languageOptions = ref([])
const detailCache = reactive({})
const detailLoadingId = ref(null)
const clientDetailCache = reactive({})
const clientDetailLoadingId = ref(null)
const clientSearchLoading = ref(false)

// 口译/笔译咨询确认中间层
const confirmationDialogVisible = ref(false)
const confirmationPreviewLoading = ref(false)
const confirmationSubmitting = ref(false)
const confirmationSubmitAction = ref('')
const formSubmitting = ref(false)
const editorLoading = ref(false)
const createIdempotencyKey = ref('')
const confirmationFormRef = ref(null)
const confirmationBodyEditorRef = ref(null)
const confirmationImageUploading = ref(false)
const confirmationDialogRef = ref(null)
const confirmationRecipientGroups = ref([])
let confirmationMailPreviewRequestId = 0
let confirmationMailPreviewController = null
let confirmationManagerContactPreviewTimer = null
let confirmationRecipientGroupsLoaded = false
let confirmationRecipientGroupsPromise = null
let editorSessionId = 0
let subClientRequestId = 0
const confirmationContext = reactive({ mode: '', consultationId: null, consultationPayload: null, row: null, continueCreate: false })
const confirmationForm = reactive({
  projectName: '', subjectPrefix: '', customerOrderNo: '', managerContact: '', serviceContent: '', languagePair: '',
  emailSubject: '', emailBody: '', emailBodyHtml: '', inlineImages: [], toUserIds: [], ccUserIds: [],
})
const confirmationPreview = reactive({
  project_type: '', order_no: '', client_short_name: '', manager_contact: '',
  project_name: '', customer_order_no: '', email_subject_preview: '', missing_fields: [],
  to_users: [], cc_users: [], email_body: '', can_send: false, blocking_reasons: [],
  sender_mode: 'system', sender_name: '', sender_email: '', sender_verified: false,
})
const CONFIRMED_CONSULTATION_STATUS = 'success'
const currentUserId = localStorage.getItem('user_id') || null
const CONSULTATION_COLUMNS_STORAGE_KEY = `consultation_visible_columns:${currentUserId || 'anonymous'}`

const consultationColumnOptions = [
  { key: 'client_code', label: '客户编号', width: 150 },
  { key: 'client_name', label: '客户全称', width: 200 },
  { key: 'client_short_name', label: '客户简称', width: 150 },
  { key: 'status', label: '咨询状态', width: 120 },
  { key: 'consultation_time', label: '咨询时间', width: 180 },
  { key: 'consultation_method', label: '咨询方式', width: 120 },
  { key: 'consultation_type', label: '咨询类型', width: 140 },
  { key: 'client_source', label: '客户来源', width: 120 },
  { key: 'source_keyword', label: '来源关键词', width: 150 },
  { key: 'handling_method', label: '处理方式', width: 120 },
  { key: 'customer_service_id', label: '客服人员', width: 120, type: 'user' },
  { key: 'sales_person_id', label: '销售人员', width: 120, type: 'user' },
  { key: 'editor_id', label: '编辑人', width: 120, type: 'user' },
  { key: 'follow_up_person_id', label: '跟进人', width: 120, type: 'user' },
  { key: 'follow_up_count', label: '跟进次数', width: 100 },
  { key: 'follow_up_time', label: '跟进时间', width: 180, type: 'datetime' },
  { key: 'follow_up_status', label: '跟进状态', width: 150 },
  { key: 'consultation_description', label: '咨询描述', width: 220 },
  { key: 'follow_up_remarks', label: '跟进备注', width: 220 },
  { key: 'remarks', label: '备注', width: 220 },
  { key: 'created_at', label: '创建时间', width: 180, type: 'datetime' },
  { key: 'updated_at', label: '更新时间', width: 180, type: 'datetime' },
]
const defaultVisibleColumnKeys = [
  'status',
  'client_short_name',
  'follow_up_person_id',
  'follow_up_count',
  'consultation_time',
  'client_source',
  'source_keyword',
  'handling_method',
  'customer_service_id',
  'consultation_method',
  'consultation_type',
]
const legacyDefaultVisibleColumnKeys = [
  'status',
  'client_short_name',
  'follow_up_person_id',
  'consultation_time',
  'client_source',
  'source_keyword',
  'consultation_method',
  'consultation_type',
]

const loadVisibleColumnKeys = () => {
  try {
    const savedKeys = JSON.parse(localStorage.getItem(CONSULTATION_COLUMNS_STORAGE_KEY) || 'null')
    if (!Array.isArray(savedKeys)) return [...defaultVisibleColumnKeys]
    const availableKeys = new Set(consultationColumnOptions.map((column) => column.key))
    const filteredKeys = savedKeys.filter((key) => availableKeys.has(key))
    const usesLegacyDefault = filteredKeys.length === legacyDefaultVisibleColumnKeys.length
      && filteredKeys.every((key, index) => key === legacyDefaultVisibleColumnKeys[index])
    return usesLegacyDefault ? [...defaultVisibleColumnKeys] : filteredKeys
  } catch {
    localStorage.removeItem(CONSULTATION_COLUMNS_STORAGE_KEY)
    return [...defaultVisibleColumnKeys]
  }
}

const visibleColumnKeys = ref(loadVisibleColumnKeys())
const displayedConsultationColumns = computed(() => {
  const visibleKeys = new Set(visibleColumnKeys.value)
  return consultationColumnOptions.filter((column) => visibleKeys.has(column.key))
})

watch(visibleColumnKeys, (keys) => {
  localStorage.setItem(CONSULTATION_COLUMNS_STORAGE_KEY, JSON.stringify(keys))
}, { deep: true })

const resetVisibleColumns = () => {
  visibleColumnKeys.value = [...defaultVisibleColumnKeys]
}
const SEARCH_DEBOUNCE_MS = 400
let searchDebounceTimer = null
let consultationSearchController = null
let consultationRequestId = 0

const tableData = ref([])
const consultationTableRef = ref(null)
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows:tableData,tableRef:consultationTableRef,pagination,deleteRow:(row)=>consultationApi.deleteConsultation(row.id),getLabel:(row)=>row.client_name||row.client_short_name||row.consultation_description,reload:()=>fetchData(),onDeleted:(row)=>{delete detailCache[row.id]},entityName:'咨询记录'})

const linkedProjectIdFields = [
  'translation_project_id',
  'interpretation_project_id',
  'annotation_project_id',
  'recruitment_project_id',
]

const isProtectedConsultation = (row) => (
  row?.status === CONFIRMED_CONSULTATION_STATUS
  || linkedProjectIdFields.some((field) => Boolean(row?.[field]))
)

const confirmConsultationBatchDelete = async () => {
  const protectedRows = selectedRows.value.filter(isProtectedConsultation)
  if (protectedRows.length) {
    const codes = protectedRows
      .slice(0, 5)
      .map((row) => row.consultation_code)
      .filter(Boolean)
      .join('、')
    const codeHint = codes ? `（${codes}${protectedRows.length > 5 ? ' 等' : ''}）` : ''
    await ElMessageBox.alert(
      `已确认或已关联项目的咨询无法删除。当前选择中有 ${protectedRows.length} 条此类咨询${codeHint}，请取消选择后重试。`,
      '无法删除',
      { type: 'warning', confirmButtonText: '知道了' },
    )
    return
  }
  await confirmBatchDelete()
}

const searchForm = reactive({
  keyword: '',
  status: '',
  consultation_date_range: [],
  consultation_method: '',
  consultation_type: '',
  client_source: '',
  customer_service_id: '',
  sales_person_id: '',
  follow_up_person_id: '',
  follow_up_status: '',
})
const advancedFilterVisible = ref(false)
const advancedFilterFields = [
  'consultation_date_range',
  'consultation_method',
  'consultation_type',
  'client_source',
  'customer_service_id',
  'sales_person_id',
  'follow_up_person_id',
  'follow_up_status',
]
const advancedFilterCount = computed(() => advancedFilterFields.reduce((count, field) => {
  const value = searchForm[field]
  return count + (Array.isArray(value) ? Number(value.length > 0) : Number(!!value))
}, 0))

const handleSearch = () => {
  exitDeleteMode()
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  pagination.page = 1
  fetchData()
}

const handleDebouncedSearchInput = (value) => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)

  // 清空时立即恢复完整列表；有内容时等待用户结束本轮输入。
  if (!value?.trim()) {
    searchDebounceTimer = null
    handleSearch()
    return
  }

  searchDebounceTimer = setTimeout(() => {
    searchDebounceTimer = null
    handleSearch()
  }, SEARCH_DEBOUNCE_MS)
}

const resetSearch = () => {
  Object.assign(searchForm, {
    keyword: '',
    status: '',
    consultation_date_range: [],
    consultation_method: '',
    consultation_type: '',
    client_source: '',
    customer_service_id: '',
    sales_person_id: '',
    follow_up_person_id: '',
    follow_up_status: '',
  })
  handleSearch()
}

const clearAdvancedFilters = () => {
  advancedFilterFields.forEach((field) => {
    searchForm[field] = field === 'consultation_date_range' ? [] : ''
  })
  handleSearch()
}

const emptyProjectIntake = () => ({
  service_content: '', language_pair: '', customer_deadline_time: '', file_type_secondary: '',
  priority: '', project_contract_type: '', project_contract_status: '', quotation_required: false,
  quotation_status: '', quotation_path: '',
  customer_requirement_professional: '', customer_requirement_special: '',
  project_types: [], task_description: '', locations: [], time_ranges: [], language_directions: [],
  required_interpreter_count: null, potential_demand: '', language_items: [], price_items: [],
  position_title: '', job_description: '', headcount_min: null, headcount_max: null,
  employment_range: [], employment_start: null, employment_end: null, work_location: '',
  target_onboard_type: 'date', target_onboard_date: null,
  word_count_matrix: createEmptyWordCountMatrix(),
})

const serializeWordCountMatrix = (matrix) => {
  const normalized = normalizeWordCountMatrix(matrix)
  return {
    company: normalized.company,
    customer: normalized.customer,
    translator_estimate: normalized.translatorEstimate,
  }
}

const emptyLanguageDirection = () => ({ source_language_id: '', target_language_id: '', required_count: null })
const emptyTimeRange = () => ({ scheduled_start: '', scheduled_end: '' })

const normalizeLegacyInterpretationIntake = (projectIntake) => {
  const normalized = { ...emptyProjectIntake(), ...(projectIntake || {}) }
  const directions = (normalized.language_directions || []).map((item) => ({ ...item }))
  const legacyTotal = normalized.required_interpreter_count
  const missing = directions.filter((item) => !item.required_count)
  if (directions.length === 1 && missing.length === 1 && Number.isInteger(legacyTotal) && legacyTotal > 0) {
    directions[0].required_count = legacyTotal
  } else if (directions.length > 1 && missing.length === directions.length && legacyTotal === directions.length) {
    directions.forEach((item) => { item.required_count = 1 })
  }
  normalized.language_directions = directions
  const counts = directions.map((item) => item.required_count)
  if (counts.length && counts.every((value) => Number.isInteger(value) && value > 0)) {
    normalized.required_interpreter_count = counts.reduce((total, value) => total + value, 0)
  }
  return normalized
}

const ensureInterpretationDirection = (projectIntake = form.project_intake) => {
  if (!Array.isArray(projectIntake.language_directions) || !projectIntake.language_directions.length) {
    projectIntake.language_directions = [emptyLanguageDirection()]
  }
}

const ensureInterpretationTimeRange = (projectIntake = form.project_intake) => {
  if (!Array.isArray(projectIntake.time_ranges) || !projectIntake.time_ranges.length) {
    projectIntake.time_ranges = [emptyTimeRange()]
  }
}

const defaultForm = () => ({
  id: null,
  client_id: null,
  sub_client_id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  manager_contact: '',
  contact_name: '',
  customer_order_no: '',
  project_name: '',
  project_intake: emptyProjectIntake(),
  consultation_time: '',
  consultation_method: '',
  consultation_method_custom: '',
  client_source: '',
  source_keyword: '',
  consultation_description: '',
  status: 'following',
  consultation_type: '',
  handling_method: '',
  remarks: '',
  customer_service_id: currentUserId,
  sales_person_id: currentUserId,
  editor_id: currentUserId,
  follow_up_count: 0,
  follow_up_time: '',
  follow_up_status: '',
  follow_up_remarks: '',
  follow_up_person_id: currentUserId,
  updated_at: null,
})

const form = reactive(defaultForm())
const showManagerContactInput = computed(() => !form.client_id)
const interpretationLocationText = computed({
  get: () => (Array.isArray(form.project_intake.locations) ? form.project_intake.locations : [])
    .filter((item) => String(item || '').trim())
    .join('、'),
  set: (value) => {
    const location = String(value || '')
    form.project_intake.locations = location.trim() ? [location] : []
  },
})
const interpretationRequiredTotal = computed(() => (
  form.project_intake.language_directions || []
).reduce((total, item) => total + (Number.isInteger(item.required_count) && item.required_count > 0 ? item.required_count : 0), 0))
const canWrite = hasPermission('consultations:write')
const availableSubClients = ref([])
const personnelAssignmentExpanded = ref(false)
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({
  namespace: 'consultation',
  form,
  createDefault: defaultForm,
  formRef,
  legacyStorageKeys: [`consultation_form_drafts:${currentUserId || 'anonymous'}`],
  applyDraft: (draft) => {
    Object.assign(form, defaultForm(), draft)
    if (form.consultation_method && !consultationMethodLabels[form.consultation_method]) {
      form.consultation_method_custom = form.consultation_method
      form.consultation_method = 'other'
    }
    if (isInterpretationConsultationType(form.consultation_type)) {
      form.project_intake = normalizeLegacyInterpretationIntake(form.project_intake)
      ensureInterpretationDirection()
      ensureInterpretationTimeRange()
    }
  },
})
const consultationTypeOptions = [
  '简单咨询',
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
const consultationStatusOptions = [
  { label: '跟进中', value: 'following' },
  { label: '重点跟进', value: 'emphasis' },
  { label: '未成交', value: 'failed' },
  { label: '已确认', value: CONFIRMED_CONSULTATION_STATUS },
]
const consultationMethodOptions = [
  { label: '电话', value: 'phone' },
  { label: '邮件', value: 'email' },
  { label: '在线咨询', value: 'online' },
  { label: '上门', value: 'onsite' },
  { label: '其他', value: 'other' },
]
const consultationMethodLabels = Object.fromEntries(
  consultationMethodOptions.map((item) => [item.value, item.label])
)
const consultationMethodLabel = (value) => consultationMethodLabels[value] || value || '-'
const consultationMethodDisplay = (row) => {
  const label = consultationMethodLabel(row?.consultation_method)
  const detail = row?.consultation_method_detail?.trim()
  return detail ? `${label}（${detail}）` : label
}
const consultationMethodDetailPlaceholder = (method) => (
  method === 'other'
    ? '请输入具体咨询方式'
    : '可补充具体号码、邮箱、平台或联系人（选填）'
)
const normalizeConsultationMethod = (value, detail = '') => {
  if (!value || consultationMethodLabels[value]) {
    return { method: value || '', custom: detail || '' }
  }
  return { method: 'other', custom: detail || value }
}
const legacyConsultationTypeLabels = {
  simple: '简单咨询',
  translation: '笔译项目',
  interpretation: '口译项目',
  recruitment: '招聘项目',
  annotation: '标注项目',
  dubbing: '配音项目',
  subtitle: '字幕项目',
  notarization: '公证项目',
  certification: '认证项目',
  equipment_rental: '其他项目',
  other: '其他项目',
  笔译: '笔译项目',
  口译: '口译项目',
  招聘: '招聘项目',
  其他: '其他项目',
}
const consultationTypeLabel = (value) => legacyConsultationTypeLabels[value] || value || '-'
const isSimpleConsultationType = (value) => ['简单咨询', 'simple'].includes(value)
const isInterpretationConsultationType = (value) => (
  ['口译项目', 'interpretation', '口译'].includes(value)
)
const isAnnotationConsultationType = (value) => (
  ['标注项目', 'annotation'].includes(value)
)
const isRecruitmentConsultationType = (value) => (
  ['招聘项目', 'recruitment', '招聘'].includes(value)
)
const isTranslationConsultationType = (value) => (
  [
    '笔译项目', 'translation', '笔译',
    '配音项目', 'dubbing',
    '字幕项目', 'subtitle',
    '公证项目', 'notarization',
    '认证项目', 'certification',
    '其他项目', 'equipment_rental', 'other', '其他',
  ].includes(value)
)
const isCoreFieldsRequiredProjectType = (value) => (
  isInterpretationConsultationType(value)
  || isRecruitmentConsultationType(value)
  || isAnnotationConsultationType(value)
)
const isSupportedProjectType = (value) => (
  isTranslationConsultationType(value) || isInterpretationConsultationType(value)
  || isAnnotationConsultationType(value) || isRecruitmentConsultationType(value)
)
const interpretationTypeOptions = [
  { value: 'onsite', label: '现场口译' }, { value: 'booth', label: '展会摊位口译' },
  { value: 'exhibition_escort', label: '展会陪同口译' }, { value: 'escort', label: '陪同口译' },
  { value: 'small_business_meeting', label: '小型商务会议口译' }, { value: 'consecutive', label: '会议交传口译' },
  { value: 'small_non_business_meeting', label: '小型（非商务）会议口译' },
  { value: 'simultaneous', label: '会议同传口译' }, { value: 'online_meeting', label: '线上会议口译' },
  { value: 'online_simultaneous', label: '线上同传口译' },
]
const annotationTypeOptions = [
  { value: 'audio_collection', label: '音频采集' },
  { value: 'audio_annotation', label: '音频标注' },
  { value: 'audio_evaluation', label: '音频评测' },
  { value: 'text_evaluation', label: '文本评测' },
  { value: 'text_annotation', label: '文本标注' },
  { value: 'quality_inspection', label: '质检' },
  { value: 'listening_test', label: '测听' },
  { value: 'slot_deduction', label: '扣槽' },
  { value: 'generalization', label: '泛化' },
  { value: 'translation', label: '翻译' },
]
const serviceContentOptions = ['翻译', '排版']
const priorityOptions = ['低', '中', '高', '紧急']
const handleConsultationTypeChange = (consultationType) => {
  form.project_intake = emptyProjectIntake()
  if (isSimpleConsultationType(consultationType) && form.status === CONFIRMED_CONSULTATION_STATUS) {
    form.status = 'following'
    ElMessage.info('简单咨询不能直接确认，咨询状态已调整为“跟进中”')
  }
  if (isInterpretationConsultationType(consultationType)) {
    ensureInterpretationDirection()
    ensureInterpretationTimeRange()
  }
  nextTick(() => formRef.value?.clearValidate())
}
const handleTranslationQuotationRequiredChange = (required) => {
  if (required) return
  form.project_intake.quotation_status = ''
  form.project_intake.quotation_path = ''
}
const addIntakeTimeRange = () => form.project_intake.time_ranges.push(emptyTimeRange())
const removeIntakeTimeRange = (index) => {
  if (form.project_intake.time_ranges.length <= 1) return
  form.project_intake.time_ranges.splice(index, 1)
}
const addIntakeDirection = () => form.project_intake.language_directions.push(emptyLanguageDirection())
const removeIntakeDirection = (index) => {
  if (form.project_intake.language_directions.length <= 1) return
  form.project_intake.language_directions.splice(index, 1)
}
const addAnnotationLanguage = () => form.project_intake.language_items.push({ source_language_id: '', target_language_id: null })
const addRecruitmentDirection = () => form.project_intake.language_directions.push({ direction_type: 'single', source_language_id: '', target_language_id: '' })
const projectRouteName = (consultationType) => {
  if (isTranslationConsultationType(consultationType)) return 'TranslationProjectDetails'
  if (isInterpretationConsultationType(consultationType)) return 'InterpretationProjectDetails'
  if (isAnnotationConsultationType(consultationType)) return 'AnnotationProjectDetails'
  if (isRecruitmentConsultationType(consultationType)) return 'RecruitmentProjectDetails'
  return ''
}
const routeToProjectBoard = async (consultationType, projectId = null) => {
  const name = projectRouteName(consultationType)
  if (!name) return false
  if (!hasPermission('projects:read')) {
    ElMessage.warning('项目已生成，但当前账号没有项目查看权限，无法打开项目编辑窗口')
    return false
  }
  const query = projectId ? { projectId, openEditor: '1' } : undefined
  try {
    await router.push({ name, query })
    return true
  } catch {
    ElMessage.warning('项目已生成，但项目页面打开失败，请稍后从项目列表进入')
    return false
  }
}
const confirmationTypeLabel = computed(() => {
  const sourceType = confirmationContext.consultationPayload?.consultation_type
    || confirmationContext.row?.consultation_type
  if (sourceType) return consultationTypeLabel(sourceType)
  return ({ translation: '笔译项目', interpretation: '口译项目', annotation: '标注项目', recruitment: '招聘项目' }[confirmationPreview.project_type] || '-')
})
const validInternalUsers = computed(() => userOptions.value.filter((item) => item.is_active && item.email))
const confirmationRecipientCount = computed(() => new Set([
  ...confirmationForm.toUserIds,
  ...confirmationForm.ccUserIds,
]).size)
const confirmationAllMembersSelected = computed(() => (
  validInternalUsers.value.length > 1
  && confirmationRecipientCount.value >= validInternalUsers.value.length
))
const confirmationSubjectParts = computed(() => {
  const parts = [
    confirmationForm.subjectPrefix,
    confirmationPreview.order_no,
    confirmationPreview.client_short_name,
    confirmationPreview.manager_contact,
  ]
  if (confirmationPreview.project_type !== 'translation') {
    parts.push(confirmationForm.customerOrderNo)
  }
  parts.push(confirmationForm.projectName)
  return parts.map((item) => item?.trim()).filter(Boolean)
})
const confirmationSubjectPreview = computed(() => confirmationSubjectParts.value.join('，'))
const confirmationMissingFields = computed(() => {
  return (confirmationPreview.missing_fields || []).filter((item) => !(
    confirmationPreview.project_type === 'translation'
    && item === '客户经理联系方式'
  ))
})
const regenerateConfirmationSubject = () => { confirmationForm.emailSubject = confirmationSubjectPreview.value }

const validateInterpretationDirections = (_rule, value, callback) => {
  if (!isInterpretationConsultationType(form.consultation_type)) {
    callback()
    return
  }
  if (!Array.isArray(value) || !value.length) {
    callback(new Error('请选择口译方向'))
    return
  }
  if (value.some((item) => !item?.source_language_id || !item?.target_language_id)) {
    callback(new Error('请选择完整的口译方向'))
    return
  }
  if (value.some((item) => !Number.isInteger(item?.required_count) || item.required_count < 1)) {
    callback(new Error('请为每个口译方向填写大于等于 1 的需求人数'))
    return
  }
  callback()
}

const validateWhen = (match, validator) => (_rule, value, callback) => {
  if (!match()) return callback()
  return validator(_rule, value, callback)
}
const requireIntakeText = (message) => (_rule, value, callback) => {
  if (String(value || '').trim()) return callback()
  callback(new Error(message))
}
const requireIntakeArray = (message) => (_rule, value, callback) => {
  if (Array.isArray(value) && value.length) return callback()
  callback(new Error(message))
}
const validateInterpretationTimeRanges = (_rule, value, callback) => {
  if (!Array.isArray(value) || !value.length) {
    callback(new Error('请至少保留一个预定时段'))
    return
  }
  if (value.some((item) => !item?.scheduled_start || !item?.scheduled_end)) {
    callback(new Error('请填写完整的预定时段'))
    return
  }
  callback()
}
const validateAnnotationLanguages = (_rule, value, callback) => {
  if (!Array.isArray(value) || !value.length) {
    callback(new Error('请至少选择一组语言范围'))
    return
  }
  if (value.some((item) => !item?.source_language_id)) {
    callback(new Error('请选择完整的语言范围'))
    return
  }
  callback()
}
const validateRecruitmentHeadcount = (_rule, value, callback) => {
  if (value || form.project_intake.headcount_max) return callback()
  callback(new Error('请填写招聘人数'))
}
const validateCoreConsultationRequired = (message, includeSimple = false) => (_rule, value, callback) => {
  const required = isCoreFieldsRequiredProjectType(form.consultation_type)
    || (includeSimple && isSimpleConsultationType(form.consultation_type))
  if (!required) return callback()
  if (value !== null && value !== undefined && String(value).trim()) return callback()
  callback(new Error(message))
}
const validateConsultationMethod = (_rule, value, callback) => {
  if (!value) return callback(new Error('请选择咨询方式'))
  if (value === 'other' && !form.consultation_method_custom?.trim()) {
    return callback(new Error('请输入其他咨询方式'))
  }
  callback()
}
const validateConsultationStatus = (_rule, value, callback) => {
  if (!value) return callback(new Error('请选择咨询状态'))
  if (isSimpleConsultationType(form.consultation_type) && value === CONFIRMED_CONSULTATION_STATUS) {
    return callback(new Error('简单咨询不能直接确认，请先选择具体项目类型'))
  }
  callback()
}

const rules = {
  client_short_name: [{ required: true, message: '请输入客户简称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择咨询状态', validator: validateConsultationStatus, trigger: 'change' }],
  consultation_type: [{ required: true, message: '请选择咨询类型', trigger: 'change' }],
  consultation_time: [{ required: true, message: '请选择咨询时间', validator: validateCoreConsultationRequired('请选择咨询时间', true), trigger: 'change' }],
  consultation_method: [{ required: true, message: '请选择咨询方式', validator: validateConsultationMethod, trigger: ['change', 'blur'] }],
  client_source: [{ required: true, message: '请输入客户来源，不知道可写“未知”', trigger: 'blur' }],
  source_keyword: [{ required: true, message: '请输入来源关键词', validator: validateCoreConsultationRequired('请输入来源关键词'), trigger: 'blur' }],
  consultation_description: [{ required: true, message: '请输入咨询描述，不知道可写“无”', trigger: 'blur' }],
  'project_intake.language_directions': [{
    required: true,
    message: '请至少添加一个口译方向',
    validator: validateInterpretationDirections,
    trigger: 'change',
  }],
  'project_intake.project_types': [{
    required: true,
    message: '请选择项目类型',
    validator: validateWhen(
      () => isInterpretationConsultationType(form.consultation_type) || isAnnotationConsultationType(form.consultation_type),
      requireIntakeArray('请选择项目类型'),
    ),
    trigger: 'change',
  }],
  'project_intake.locations': [{
    required: true,
    message: '请输入地点',
    validator: validateWhen(() => isInterpretationConsultationType(form.consultation_type), requireIntakeArray('请输入地点')),
    trigger: ['change', 'blur'],
  }],
  'project_intake.time_ranges': [{
    required: true,
    message: '请至少添加一个预定时段',
    validator: validateWhen(() => isInterpretationConsultationType(form.consultation_type), validateInterpretationTimeRanges),
    trigger: 'change',
  }],
  'project_intake.task_description': [{
    required: true,
    message: '请填写具体任务',
    validator: validateWhen(() => isAnnotationConsultationType(form.consultation_type), requireIntakeText('请填写具体任务')),
    trigger: 'blur',
  }],
  'project_intake.language_items': [{
    required: true,
    message: '请至少添加一个语言范围',
    validator: validateWhen(() => isAnnotationConsultationType(form.consultation_type), validateAnnotationLanguages),
    trigger: 'change',
  }],
  'project_intake.position_title': [{
    required: true,
    message: '请填写职位名称/类型',
    validator: validateWhen(() => isRecruitmentConsultationType(form.consultation_type), requireIntakeText('请填写职位名称/类型')),
    trigger: 'blur',
  }],
  'project_intake.headcount_min': [{
    required: true,
    message: '请填写招聘人数',
    validator: validateWhen(() => isRecruitmentConsultationType(form.consultation_type), validateRecruitmentHeadcount),
    trigger: 'change',
  }],
  'project_intake.employment_range': [{
    required: true,
    message: '请选择拟履职周期',
    validator: validateWhen(() => isRecruitmentConsultationType(form.consultation_type), requireIntakeArray('请选择拟履职周期')),
    trigger: 'change',
  }],
  'project_intake.work_location': [{
    required: true,
    message: '请填写工作地点',
    validator: validateWhen(() => isRecruitmentConsultationType(form.consultation_type), requireIntakeText('请填写工作地点')),
    trigger: 'blur',
  }],
}

const getStatusType = (status) => {
  const statusMap = {
    following: 'warning',
    emphasis: 'danger',
    failed: 'info',
    success: 'success',
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusMap = {
    following: '跟进中',
    emphasis: '重点跟进',
    failed: '未成交',
    success: '已确认',
  }
  return statusMap[status] || status || '-'
}

const isToday = (val) => {
  if (!val) return false
  const date = new Date(String(val).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return false
  const today = new Date()
  return date.getFullYear() === today.getFullYear()
    && date.getMonth() === today.getMonth()
    && date.getDate() === today.getDate()
}

const isYesterday = (val) => {
  if (!val) return false
  const date = new Date(String(val).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return false
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return date.getFullYear() === yesterday.getFullYear()
    && date.getMonth() === yesterday.getMonth()
    && date.getDate() === yesterday.getDate()
}

const getDetailRow = (row) => detailCache[row.id] || row
const cancelInlineDetailEdit = () => window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
const saveConsultationTextField = async (row, field, value, intake = false) => {
  const current = getDetailRow(row)
  const request = intake ? consultationApi.updateConsultationIntakeTextField : consultationApi.updateConsultationTextField
  const updated = await request(row.id, field, value, current.updated_at)
  detailCache[row.id] = updated
  Object.assign(row, updated)
  if (Object.values(buildSearchFilters()).some(Boolean)) void fetchData()
  return updated
}

const getClientDetailRow = (row) => clientDetailCache[row.client_id] || {
  client_code: row.client_code,
  client_name: row.client_name,
  client_short_name: row.client_short_name,
  manager_contact: row.manager_contact,
}

const getClientStatusLabel = (status) => {
  if (!status) return '-'
  return status === 'active' ? '合作中' : status === 'inactive' ? '已停止' : '待合作'
}

// el-autocomplete 模糊搜索客户
const searchClientsByName = async (queryString, cb) => {
  if (!queryString?.trim()) {
    cb([])
    return
  }
  clientSearchLoading.value = true
  try {
    const res = await clientApi.getClients({ client_name: queryString.trim(), skip: 0, limit: 10 })
    cb(Array.isArray(res) ? res : [])
  } catch {
    cb([])
  } finally {
    clientSearchLoading.value = false
  }
}

const searchClientsByShortName = async (queryString, cb) => {
  if (!queryString?.trim()) {
    cb([])
    return
  }
  clientSearchLoading.value = true
  try {
    const res = await clientApi.getClients({
      client_short_name: queryString.trim(),
      skip: 0,
      limit: 10,
    })
    cb(Array.isArray(res) ? res : [])
  } catch {
    cb([])
  } finally {
    clientSearchLoading.value = false
  }
}

// 用户从下拉列表选中了已有客户
const handleExistingClientSelect = (item) => {
  form.client_id = item.id
  form.sub_client_id = null
  form.client_name = item.client_name
  form.client_code = item.client_code || ''
  form.client_short_name = item.client_short_name || ''
  form.manager_contact = item.manager_contact || ''
  availableSubClients.value = item.sub_clients || []
  if (!availableSubClients.value.length) loadSubClients(item.id)
}

const loadSubClients = async (clientId, sessionId = editorSessionId) => {
  const requestId = ++subClientRequestId
  if (!clientId) {
    availableSubClients.value = []
    return
  }
  try {
    const detail = await clientApi.getClient(clientId)
    if (requestId !== subClientRequestId || sessionId !== editorSessionId || form.client_id !== clientId) return
    availableSubClients.value = detail?.sub_clients || []
  } catch {
    if (requestId !== subClientRequestId || sessionId !== editorSessionId) return
    availableSubClients.value = []
  }
}

// 用户手动输入（重新输入时清空已关联的客户）
const handleClientNameInput = () => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.sub_client_id = null
  form.client_code = ''
  availableSubClients.value = []
  if (hadSelectedClient) {
    form.client_short_name = ''
    form.manager_contact = ''
  }
}

// 简称可直接录入；客户全称可留空，后端创建客户时会以简称作为默认全称。
const handleClientShortNameInput = (value) => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.sub_client_id = null
  form.client_code = ''
  availableSubClients.value = []
  if (hadSelectedClient) {
    form.client_name = ''
    form.manager_contact = ''
  }
}

const handleClientShortNameClear = () => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.sub_client_id = null
  form.client_code = ''
  availableSubClients.value = []
  form.client_short_name = ''
  if (hadSelectedClient) {
    form.client_name = ''
    form.manager_contact = ''
  }
}

// 用户点击清空按钮
const handleClientNameClear = () => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.client_name = ''
  form.client_code = ''
  if (hadSelectedClient) {
    form.client_short_name = ''
    form.manager_contact = ''
  }
}

const loadUsers = async () => {
  try {
    const res = await userApi.getUsers({ skip: 0, limit: 500 })
    userOptions.value = Array.isArray(res) ? res : []
  } catch {
    userOptions.value = []
  }
}

const loadLanguages = async () => {
  try {
    languageOptions.value = await getProjectLanguages()
  } catch {
    languageOptions.value = []
  }
}

const getUserName = (id) => {
  if (!id) return '-'
  const user = userOptions.value.find((u) => u.id === id)
  return user ? (user.full_name || user.username) : id
}

const personnelAssignmentSummary = computed(() => {
  const assignments = [
    ['客服', form.customer_service_id],
    ['销售', form.sales_person_id],
    ['编辑', form.editor_id],
    ['跟进', form.follow_up_person_id],
  ].map(([label, id]) => [label, id ? getUserName(id) : '未指定'])
  const names = assignments.map(([, name]) => name)
  if (names.every((name) => name === names[0])) {
    return `客服、销售、编辑、跟进均为 ${names[0]}`
  }
  return assignments.map(([label, name]) => `${label}：${name}`).join('｜')
})

const personnelFieldLabels = new Set(['客服人员', '销售人员', '编辑人', '跟进人'])
const handleLocateConsultationField = async (item) => {
  if (personnelFieldLabels.has(item?.searchLabel)) {
    personnelAssignmentExpanded.value = true
    await nextTick()
  }
  await locateDialogField(item)
}

const buildSearchFilters = () => {
  const [consultationDateStart, consultationDateEnd] = searchForm.consultation_date_range || []
  return {
    keyword: searchForm.keyword?.trim() || undefined,
    status: searchForm.status || undefined,
    consultation_date_start: consultationDateStart || undefined,
    consultation_date_end: consultationDateEnd || undefined,
    consultation_method: searchForm.consultation_method || undefined,
    consultation_type: searchForm.consultation_type || undefined,
    client_source: searchForm.client_source?.trim() || undefined,
    customer_service_id: searchForm.customer_service_id || undefined,
    sales_person_id: searchForm.sales_person_id || undefined,
    follow_up_person_id: searchForm.follow_up_person_id || undefined,
    follow_up_status: searchForm.follow_up_status?.trim() || undefined,
  }
}

const fetchData = async () => {
  consultationSearchController?.abort()
  consultationSearchController = new AbortController()
  const requestId = ++consultationRequestId
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      ...buildSearchFilters(),
    }
    const countParams = buildSearchFilters()

    const [res, countRes] = await Promise.all([
      consultationApi.getConsultations(params, { signal: consultationSearchController.signal }),
      consultationApi.getConsultationCount(countParams, { signal: consultationSearchController.signal })
    ])
    if (requestId !== consultationRequestId) return
    tableData.value = Array.isArray(res) ? res : []
    pagination.total = countRes?.total || tableData.value.length
  } catch (error) {
    if (requestId !== consultationRequestId) return
    if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError') return
    ElMessage.error(error?.detail || '网络异常，咨询列表未刷新，请检查网络后重试')
  } finally {
    if (requestId === consultationRequestId) loading.value = false
  }
}

const toNullable = (v) => (v === '' || v === undefined ? null : v)

const buildPayload = () => ({
  client_id: form.client_id,
  sub_client_id: toNullable(form.sub_client_id),
  client_code: form.client_code?.trim() || null,
  client_name: form.client_name?.trim() || null,
  client_short_name: form.client_short_name?.trim() || null,
  manager_contact: form.manager_contact?.trim() || null,
  contact_name: form.contact_name?.trim() || null,
  customer_order_no: form.customer_order_no?.trim() || null,
  project_name: form.project_name?.trim() || null,
  project_intake: {
    ...form.project_intake,
    word_count_matrix: serializeWordCountMatrix(form.project_intake.word_count_matrix),
    required_interpreter_count: isInterpretationConsultationType(form.consultation_type)
      ? (interpretationRequiredTotal.value || null)
      : form.project_intake.required_interpreter_count,
    employment_start: form.project_intake.employment_range?.[0] || null,
    employment_end: form.project_intake.employment_range?.[1] || null,
    employment_range: undefined,
  },
  project_intake_version: 2,
  consultation_time: toNullable(form.consultation_time),
  consultation_method: toNullable(form.consultation_method),
  consultation_method_detail: toNullable(form.consultation_method_custom?.trim()),
  client_source: toNullable(form.client_source),
  source_keyword: toNullable(form.source_keyword),
  consultation_description: toNullable(form.consultation_description),
  remarks: toNullable(form.remarks),
  customer_service_id: toNullable(form.customer_service_id),
  sales_person_id: toNullable(form.sales_person_id),
  status: toNullable(form.status),
  consultation_type: toNullable(form.consultation_type),
  handling_method: toNullable(form.handling_method),
  editor_id: toNullable(form.editor_id),
  follow_up_count: form.follow_up_count ?? 0,
  follow_up_time: toNullable(form.follow_up_time),
  follow_up_status: toNullable(form.follow_up_status),
  follow_up_remarks: toNullable(form.follow_up_remarks),
  follow_up_person_id: toNullable(form.follow_up_person_id),
  expected_updated_at: form.updated_at || null,
})

const loadConsultationDetail = async (id, force = false) => {
  if (!id || (!force && detailCache[id])) return
  detailLoadingId.value = id
  try {
    const detail = await consultationApi.getConsultation(id)
    detailCache[id] = detail
  } catch {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoadingId.value = null
  }
}

const loadClientDetail = async (clientId) => {
  if (!clientId || clientDetailCache[clientId]) return
  clientDetailLoadingId.value = clientId
  try {
    clientDetailCache[clientId] = await clientApi.getClient(clientId)
  } catch {
    ElMessage.error('加载客户信息失败')
  } finally {
    clientDetailLoadingId.value = null
  }
}

const handleAdd = async () => {
  editorSessionId += 1
  subClientRequestId += 1
  editorLoading.value = false
  dialogTitle.value = '新增咨询'
  clearFieldSearch()
  personnelAssignmentExpanded.value = false
  resetForm()
  dialogVisible.value = true
  await nextTick()
  await beginDraft('create')
}

const fillFormByRow = (row) => {
  const consultationMethod = normalizeConsultationMethod(
    row.consultation_method,
    row.consultation_method_detail,
  )
  const consultationType = consultationTypeLabel(row.consultation_type) === '-'
    ? ''
    : consultationTypeLabel(row.consultation_type)
  let projectIntake = {
    ...emptyProjectIntake(),
    ...(row.project_intake || {}),
    employment_range: row.project_intake?.employment_start && row.project_intake?.employment_end
      ? [row.project_intake.employment_start, row.project_intake.employment_end]
      : [],
  }
  if (isInterpretationConsultationType(consultationType)) {
    projectIntake = normalizeLegacyInterpretationIntake(projectIntake)
    ensureInterpretationDirection(projectIntake)
    ensureInterpretationTimeRange(projectIntake)
  }
  Object.assign(form, {
    id: row.id,
    client_id: row.client_id || null,
    sub_client_id: row.sub_client_id || null,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    manager_contact: row.manager_contact || '',
    contact_name: row.contact_name || '',
    customer_order_no: row.customer_order_no || '',
    project_name: row.project_name || '',
    project_intake: projectIntake,
    consultation_time: row.consultation_time || '',
    consultation_method: consultationMethod.method,
    consultation_method_custom: consultationMethod.custom,
    client_source: row.client_source || '',
    source_keyword: row.source_keyword || '',
    consultation_description: row.consultation_description || '',
    status: row.status || 'following',
    consultation_type: consultationType,
    handling_method: row.handling_method || '',
    remarks: row.remarks || '',
    customer_service_id: row.customer_service_id ?? null,
    sales_person_id: row.sales_person_id ?? null,
    editor_id: row.editor_id ?? null,
    follow_up_count: row.follow_up_count ?? 0,
    follow_up_time: row.follow_up_time || '',
    follow_up_status: row.follow_up_status || '',
    follow_up_remarks: row.follow_up_remarks || '',
    follow_up_person_id: row.follow_up_person_id ?? null,
    updated_at: row.updated_at || null,
  })
  availableSubClients.value = []
  void loadSubClients(row.client_id, editorSessionId)
}

const handleEdit = async (row) => {
  editorSessionId += 1
  const sessionId = editorSessionId
  subClientRequestId += 1
  editorLoading.value = true
  dialogTitle.value = '编辑咨询'
  clearFieldSearch()
  personnelAssignmentExpanded.value = false
  dialogVisible.value = true
  await nextTick()
  if (sessionId !== editorSessionId) return
  detailCache[row.id] = row
  fillFormByRow(row)
  editorLoading.value = false
  await nextTick()
  resetConsultationDialogPosition()
  await beginDraft(`edit:${row.id}`)
}

const statusUpdatingId = ref(null)

// 列表内直接切换咨询状态：仅提交 status 字段（后端支持局部更新）。
// 普通状态直接切换；切到「已确认」时保留与编辑弹窗一致的联动：
// 四类项目统一确认建项信息并向内部用户发送邮件。
const handleInlineStatusChange = async (row, newStatus) => {
  if (!newStatus || newStatus === row.status || statusUpdatingId.value === row.id) return

  if (newStatus === CONFIRMED_CONSULTATION_STATUS && isSimpleConsultationType(row.consultation_type)) {
    ElMessage.warning('简单咨询不能直接确认，请先编辑并选择具体项目类型')
    return
  }

  if (
    newStatus === CONFIRMED_CONSULTATION_STATUS
    && isSupportedProjectType(row.consultation_type)
  ) {
    await openConfirmationDialog({
      mode: 'inline',
      consultationId: row.id,
      consultationPayload: null,
      row,
      previewSource: row,
    })
    return
  }

  if (newStatus === CONFIRMED_CONSULTATION_STATUS) {
    try {
      await ElMessageBox.confirm(
        isAnnotationConsultationType(row.consultation_type)
            ? '切换为「已确认」后，系统将自动建立标注项目档案，是否继续？'
            : isRecruitmentConsultationType(row.consultation_type)
              ? '切换为「已确认」后，系统将自动生成招聘项目，是否继续？'
              : '确定将该咨询切换为「已确认」吗？',
        '切换咨询状态',
        { type: 'warning', confirmButtonText: '确认切换', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }

  statusUpdatingId.value = row.id
  try {
    const saved = await consultationApi.updateConsultation(row.id, { status: newStatus })
    row.status = newStatus
    delete detailCache[row.id]
    ElMessage.success(`状态已切换为「${getStatusText(newStatus)}」`)
    // 列表若按状态筛选，切换后该行可能不再命中条件，重新拉取保持一致。
    if (searchForm.status) fetchData()

    if (newStatus === CONFIRMED_CONSULTATION_STATUS) {
      if (isRecruitmentConsultationType(row.consultation_type)) {
        ElMessage.success(
          saved?.recruitment_project_id
            ? '咨询已确认，招聘项目已自动生成'
            : '咨询已确认，招聘项目已存在'
        )
      }
      await routeToProjectBoard(row.consultation_type)
    }
  } catch (error) {
    ElMessage.error(error?.detail || '切换状态失败')
  } finally {
    statusUpdatingId.value = null
  }
}

const handleSubmit = async (continueCreate = false) => {
  if (!formRef.value || formSubmitting.value) return
  formSubmitting.value = true

  await formRef.value.validate(async (valid) => {
    if (!valid) {
      formSubmitting.value = false
      return
    }
    try {
      const payload = buildPayload()
      const isUpdate = !!form.id
      const shouldContinueCreate = continueCreate === true && !isUpdate
      // 记录提交前咨询的旧状态（用于判断是否首次变为已确认）
      const prevStatus = isUpdate
        ? (detailCache[form.id]?.status ?? tableData.value.find((r) => r.id === form.id)?.status)
        : null
      const consultationId = form.id
      let savedConsultation = null

      if (
        payload.status === CONFIRMED_CONSULTATION_STATUS
        && prevStatus !== CONFIRMED_CONSULTATION_STATUS
        && isSupportedProjectType(payload.consultation_type)
      ) {
        await openConfirmationDialog({
          mode: isUpdate ? 'update' : 'create',
          consultationId,
          consultationPayload: payload,
          row: null,
          previewSource: payload,
          continueCreate: shouldContinueCreate,
        })
        return
      }

      if (isUpdate) {
        savedConsultation = await consultationApi.updateConsultation(consultationId, payload)
        delete detailCache[consultationId]
        ElMessage.success('更新成功')
      } else {
        const created = await consultationApi.createConsultation(payload, createIdempotencyKey.value)
        savedConsultation = created
        ElMessage.success(shouldContinueCreate ? '创建成功，可继续录入下一条' : '创建成功')
        // 新建咨询也支持立即确认并生成项目详情。
        if (payload.status === CONFIRMED_CONSULTATION_STATUS && created?.id) {
          if (isRecruitmentConsultationType(payload.consultation_type)) {
            ElMessage.success('咨询已确认，招聘项目已自动生成')
          }
        }
      }
      clearDraft()
      if (shouldContinueCreate) {
        // 连续录入：保持弹窗打开并重置表单，草稿键切回 create 以继续记录新草稿。
        resetForm()
        await beginDraft('create')
        await fetchData()
        await nextTick()
        resetConsultationDialogScroll()
      } else {
        dialogVisible.value = false
        await fetchData()
      }

      // 若编辑时首次改为「已确认」，使用统一命名规则预填项目名称并二次确认。
      if (
        isUpdate &&
        payload.status === CONFIRMED_CONSULTATION_STATUS &&
        prevStatus !== CONFIRMED_CONSULTATION_STATUS
      ) {
        if (isRecruitmentConsultationType(payload.consultation_type)) {
          ElMessage.success(
            savedConsultation?.recruitment_project_id
              ? '咨询已确认，招聘项目已自动生成'
              : '咨询已确认，招聘项目已存在'
          )
        }
      }
      if (
        payload.status === CONFIRMED_CONSULTATION_STATUS
        && prevStatus !== CONFIRMED_CONSULTATION_STATUS
      ) {
        await routeToProjectBoard(payload.consultation_type)
      }
    } catch (error) {
      ElMessage.error(error?.detail || '操作失败')
    } finally {
      formSubmitting.value = false
    }
  })
}

const applyConfirmationPreview = (preview, { preserveRecipients = false } = {}) => {
  Object.assign(confirmationPreview, {
    project_type: preview?.project_type || '',
    order_no: preview?.order_no || '',
    client_short_name: preview?.client_short_name || '',
    manager_contact: preview?.manager_contact || '',
    project_name: preview?.project_name || '',
    customer_order_no: preview?.customer_order_no || '',
    email_subject_preview: preview?.email_subject_preview || '',
    missing_fields: Array.isArray(preview?.missing_fields) ? preview.missing_fields : [],
    to_users: Array.isArray(preview?.to_users) ? preview.to_users : [],
    cc_users: Array.isArray(preview?.cc_users) ? preview.cc_users : [],
    email_body: preview?.email_body || '',
    sender_mode: preview?.sender_mode || 'system',
    sender_name: preview?.sender_name || '',
    sender_email: preview?.sender_email || '',
    sender_verified: !!preview?.sender_verified,
    can_send: !!preview?.can_send,
    blocking_reasons: Array.isArray(preview?.blocking_reasons) ? preview.blocking_reasons : [],
  })
  confirmationForm.projectName = preview?.project_name || confirmationForm.projectName
  confirmationForm.customerOrderNo = preview?.customer_order_no || confirmationForm.customerOrderNo
  confirmationForm.managerContact = preview?.manager_contact || ''
  confirmationForm.emailSubject = preview?.email_subject_preview || ''
  if (!confirmationForm.inlineImages.length) {
    confirmationForm.emailBody = preview?.email_body || ''
    confirmationForm.emailBodyHtml = preview?.email_body_html || ''
    confirmationForm.inlineImages = preview?.inline_images || []
  }
  if (!preserveRecipients) {
    confirmationForm.toUserIds = (preview?.to_users || []).map((item) => item.user_id)
    confirmationForm.ccUserIds = (preview?.cc_users || []).map((item) => item.user_id)
  }
}

const buildConfirmationProjectIntake = () => {
  const source = confirmationContext.consultationPayload || confirmationContext.row || {}
  const intake = { ...(source.project_intake || {}) }
  if (confirmationPreview.project_type === 'translation' || isTranslationConsultationType(source.consultation_type)) {
    intake.service_content = confirmationForm.serviceContent?.trim() || null
    intake.language_pair = confirmationForm.languagePair?.trim() || null
    intake.word_count_matrix = serializeWordCountMatrix(intake.word_count_matrix)
  }
  return intake
}

const loadConfirmationRecipientGroups = async () => {
  if (confirmationRecipientGroupsLoaded) return confirmationRecipientGroups.value
  if (!confirmationRecipientGroupsPromise) {
    confirmationRecipientGroupsPromise = mailApi.getAvailableMailGroups()
      .then((groups) => {
        confirmationRecipientGroups.value = Array.isArray(groups) ? groups : []
        confirmationRecipientGroupsLoaded = true
        return confirmationRecipientGroups.value
      })
      .finally(() => {
        confirmationRecipientGroupsPromise = null
      })
  }
  return confirmationRecipientGroupsPromise
}

const beginConfirmationPreviewRequest = () => {
  confirmationMailPreviewController?.abort()
  confirmationMailPreviewController = new AbortController()
  return {
    requestId: ++confirmationMailPreviewRequestId,
    signal: confirmationMailPreviewController.signal,
  }
}

const isCanceledRequest = (error) => (
  error?.code === 'ERR_CANCELED'
  || error?.name === 'CanceledError'
  || error?.name === 'AbortError'
)

const refreshConfirmationMailPreview = async () => {
  const { requestId, signal } = beginConfirmationPreviewRequest()
  const source = confirmationContext.consultationPayload || confirmationContext.row || {}
  confirmationPreviewLoading.value = true
  try {
    const preview = await consultationApi.previewConfirmation({
      consultation_id: confirmationContext.consultationId || null,
      consultation_type: source.consultation_type,
      client_id: source.client_id || null,
      client_short_name: source.client_short_name || null,
      manager_contact: confirmationForm.managerContact?.trim() || null,
      project_name: confirmationForm.projectName?.trim() || null,
      subject_prefix: confirmationForm.subjectPrefix?.trim() || null,
      customer_order_no: confirmationPreview.project_type !== 'translation'
        ? confirmationForm.customerOrderNo?.trim() || null
        : null,
      project_intake: buildConfirmationProjectIntake(),
      consultation_description: source.consultation_description || null,
      remarks: source.remarks || null,
    }, { signal })
    if (requestId !== confirmationMailPreviewRequestId) return
    applyConfirmationPreview(preview, { preserveRecipients: true })
    await nextTick()
    confirmationFormRef.value?.validateField(['serviceContent', 'languagePair']).catch(() => {})
  } catch (error) {
    if (requestId !== confirmationMailPreviewRequestId) return
    if (isCanceledRequest(error)) return
    ElMessage.error(error?.detail || '刷新邮件预览失败')
  } finally {
    if (requestId === confirmationMailPreviewRequestId) confirmationPreviewLoading.value = false
  }
}

const handleConfirmationLanguagePairChange = (value) => {
  confirmationForm.languagePair = value
  refreshConfirmationMailPreview()
}

const handleConfirmationManagerContactInput = (value) => {
  confirmationMailPreviewController?.abort()
  confirmationMailPreviewController = null
  confirmationMailPreviewRequestId += 1
  confirmationPreviewLoading.value = false
  confirmationPreview.manager_contact = value?.trim() || ''
  regenerateConfirmationSubject()
  if (confirmationManagerContactPreviewTimer) clearTimeout(confirmationManagerContactPreviewTimer)
  confirmationManagerContactPreviewTimer = setTimeout(() => {
    confirmationManagerContactPreviewTimer = null
    refreshConfirmationMailPreview()
  }, 400)
}

const openMailProfile = () => {
  confirmationDialogVisible.value = false
  router.push('/profile')
}

const openConfirmationDialog = async ({ mode, consultationId, consultationPayload, row, previewSource, continueCreate = false }) => {
  const { requestId, signal } = beginConfirmationPreviewRequest()
  Object.assign(confirmationContext, { mode, consultationId, consultationPayload, row, continueCreate })
  Object.assign(confirmationForm, {
    projectName: previewSource?.project_name || buildAutoProjectName(
      previewSource?.client_short_name,
      0,
      new Date(),
      previewSource?.project_intake?.language_pair,
      previewSource?.project_intake?.customer_deadline_time,
    ),
    subjectPrefix: '',
    customerOrderNo: previewSource?.customer_order_no || '',
    managerContact: previewSource?.manager_contact || '',
    serviceContent: previewSource?.project_intake?.service_content || '',
    languagePair: previewSource?.project_intake?.language_pair || '',
    emailSubject: '', emailBody: '', emailBodyHtml: '', inlineImages: [], toUserIds: [], ccUserIds: [],
  })
  Object.assign(confirmationPreview, {
    project_type: '', order_no: '', client_short_name: '', manager_contact: '',
    project_name: '', customer_order_no: '', email_subject_preview: '', missing_fields: [],
    to_users: [], cc_users: [], email_body: '', can_send: false, blocking_reasons: [],
    sender_mode: 'system', sender_name: '', sender_email: '', sender_verified: false,
  })
  confirmationDialogVisible.value = true
  confirmationPreviewLoading.value = true
  try {
    const [preview, groups] = await Promise.all([
      consultationApi.previewConfirmation({
        consultation_id: consultationId || null,
        consultation_type: previewSource?.consultation_type,
        client_id: previewSource?.client_id || null,
        client_short_name: previewSource?.client_short_name || null,
        manager_contact: previewSource?.manager_contact?.trim() || null,
        project_name: confirmationForm.projectName || null,
        subject_prefix: null,
        customer_order_no: confirmationForm.customerOrderNo || null,
        project_intake: previewSource?.project_intake || {},
        consultation_description: previewSource?.consultation_description || null,
        remarks: previewSource?.remarks || null,
      }, { signal }),
      loadConfirmationRecipientGroups(),
    ])
    if (requestId !== confirmationMailPreviewRequestId) return
    confirmationRecipientGroups.value = groups || []
    applyConfirmationPreview(preview)
    await nextTick()
    confirmationFormRef.value?.clearValidate()
  } catch (error) {
    if (requestId !== confirmationMailPreviewRequestId || isCanceledRequest(error)) return
    confirmationDialogVisible.value = false
    ElMessage.error(error?.detail || '加载确认预览失败')
  } finally {
    if (requestId === confirmationMailPreviewRequestId) confirmationPreviewLoading.value = false
  }
}

const handleConfirmConsultation = async (sendEmail) => {
  if (!confirmationFormRef.value) return
  const valid = await confirmationFormRef.value.validate().catch(() => false)
  if (!valid || !confirmationPreview.order_no) return
  if (
    sendEmail
    && (!confirmationPreview.can_send
      || !confirmationForm.toUserIds.length
      || !confirmationForm.emailSubject.trim()
      || !confirmationForm.emailBody.trim()
      || confirmationImageUploading.value)
  ) return
  if (sendEmail && confirmationAllMembersSelected.value) {
    try {
      await ElMessageBox.confirm(
        `本邮件将发送给全体 ${validInternalUsers.value.length} 名内部成员，并同时确认建项。确认继续吗？`,
        '全体成员发送确认',
        { type: 'warning', confirmButtonText: '确认发送', cancelButtonText: '取消' },
      )
    } catch { return }
  }

  const confirmation = {
    project_name: confirmationForm.projectName?.trim() || null,
    expected_order_no: confirmationPreview.order_no,
    subject_prefix: confirmationForm.subjectPrefix?.trim() || null,
    manager_contact: confirmationForm.managerContact?.trim() || null,
    customer_order_no: confirmationPreview.project_type !== 'translation'
      ? confirmationForm.customerOrderNo?.trim() || null
      : null,
    project_intake: buildConfirmationProjectIntake(),
    to_user_ids: sendEmail ? confirmationForm.toUserIds : [],
    cc_user_ids: sendEmail
      ? confirmationForm.ccUserIds.filter((id) => !confirmationForm.toUserIds.includes(id))
      : [],
    email_subject: sendEmail ? confirmationForm.emailSubject.trim() : null,
    email_body: sendEmail ? confirmationForm.emailBody.trim() : null,
    email_body_html: sendEmail ? confirmationForm.emailBodyHtml || null : null,
    inline_image_ids: sendEmail ? confirmationForm.inlineImages.map(item => item.id) : [],
    idempotency_key: sendEmail
      ? (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`)
      : null,
  }
  confirmationSubmitAction.value = sendEmail ? 'with-email' : 'project-only'
  confirmationSubmitting.value = true
  if (confirmationContext.mode === 'inline') {
    statusUpdatingId.value = confirmationContext.consultationId
  }
  try {
    const result = confirmationContext.mode === 'create'
      ? await consultationApi.createConfirmedConsultation(confirmationContext.consultationPayload, confirmation)
      : await consultationApi.updateConfirmedConsultation(
          confirmationContext.consultationId,
          confirmationContext.mode === 'update' ? confirmationContext.consultationPayload : null,
          confirmation
        )
    // 关闭确认弹窗会重置 confirmationContext，跳转判断必须先保存快照。
    const shouldContinueCreate = (
      confirmationContext.mode === 'create'
      && confirmationContext.continueCreate
    )
    const targetProjectType = result?.project_type
    const targetProjectId = result?.project_id

    if (confirmationContext.row) confirmationContext.row.status = CONFIRMED_CONSULTATION_STATUS
    if (confirmationContext.consultationId) delete detailCache[confirmationContext.consultationId]
    if (confirmationContext.mode === 'create' || confirmationContext.mode === 'update') {
      clearDraft()
      if (confirmationContext.mode === 'create' && confirmationContext.continueCreate) {
        // 连续录入：确认建项成功后同样保持主弹窗打开并重置表单。
        resetForm()
        await beginDraft('create')
        nextTick(resetConsultationDialogScroll)
      } else {
        dialogVisible.value = false
      }
    }
    if (sendEmail && result?.mail) confirmationBodyEditorRef.value?.markImagesSaved()
    confirmationDialogVisible.value = false
    if (!sendEmail) {
      ElMessage.success(`${confirmationTypeLabel.value}咨询已确认，项目已生成（未发送内部邮件）`)
    } else {
      ElMessage.success(
        result?.mail?.status === 'sent'
          ? `${confirmationTypeLabel.value}咨询已确认，项目已生成且内部邮件已发送`
          : `${confirmationTypeLabel.value}咨询已确认，项目已生成，但邮件发送失败：${result?.mail?.send_error || '未知错误'}`
      )
    }
    const navigated = shouldContinueCreate
      ? false
      : await routeToProjectBoard(targetProjectType, targetProjectId)
    if (!navigated) await fetchData()
  } catch (error) {
    const detail = error?.rawDetail || error?.detail
    if (error?.response?.status === 409 && detail?.preview) {
      applyConfirmationPreview(detail.preview)
      ElMessage.warning(detail.message || '订单号已变化，请核对刷新后的主题并再次确认')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '确认咨询失败')
    }
  } finally {
    confirmationSubmitting.value = false
    confirmationSubmitAction.value = ''
    statusUpdatingId.value = null
  }
}

const resetConfirmationDraft = () => {
  confirmationBodyEditorRef.value?.cleanupDraftImages()
  confirmationMailPreviewController?.abort()
  confirmationMailPreviewController = null
  if (confirmationManagerContactPreviewTimer) {
    clearTimeout(confirmationManagerContactPreviewTimer)
    confirmationManagerContactPreviewTimer = null
  }
  confirmationMailPreviewRequestId += 1
  confirmationPreviewLoading.value = false
  Object.assign(confirmationContext, { mode: '', consultationId: null, consultationPayload: null, row: null, continueCreate: false })
  Object.assign(confirmationForm, {
    projectName: '', subjectPrefix: '', customerOrderNo: '', managerContact: '', serviceContent: '', languagePair: '',
    emailSubject: '', emailBody: '', emailBodyHtml: '', inlineImages: [], toUserIds: [], ccUserIds: [],
  })
  confirmationFormRef.value?.clearValidate()
}

const resetForm = () => {
  Object.assign(form, defaultForm())
  createIdempotencyKey.value = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  formRef.value?.clearValidate()
}

const handleDialogClose = () => {
  editorSessionId += 1
  subClientRequestId += 1
  clearFieldSearch()
  personnelAssignmentExpanded.value = false
  availableSubClients.value = []
  editorLoading.value = false
  pauseDraft()
  resetForm()
}

const resetConsultationDialogScroll = () => {
  const dialogBody = formRef.value?.$el?.closest('.el-dialog__body')
  if (dialogBody) dialogBody.scrollTop = 0
}

const resetConsultationDialogPosition = () => {
  nextTick(() => consultationDialogRef.value?.resetPosition?.())
}

const handleConsultationDialogOpened = () => {
  resetConsultationDialogPosition()
  resetConsultationDialogScroll()
}

const resetConfirmationDialogPosition = () => {
  nextTick(() => confirmationDialogRef.value?.resetPosition?.())
}

const isEditableTarget = (target) => {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

const handleGlobalKeydown = (event) => {
  if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return
  if (event.key?.toLowerCase() !== 'n') return
  if (isEditableTarget(event.target)) return
  if (!canWrite || deleteMode.value || dialogVisible.value || confirmationDialogVisible.value) return
  event.preventDefault()
  handleAdd()
}

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown)
  await Promise.allSettled([fetchData(), loadUsers(), loadLanguages()])
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  if (confirmationManagerContactPreviewTimer) clearTimeout(confirmationManagerContactPreviewTimer)
  consultationSearchController?.abort()
  confirmationMailPreviewController?.abort()
})
</script>

<style scoped>
.consultation-word-count-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
  padding: 0 12px;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  background: var(--el-fill-color-blank);
}

.consultation-word-count-field > span {
  min-width: 0;
  overflow: hidden;
  color: var(--el-text-color-regular);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.column-settings {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  max-height: 420px;
  overflow-y: auto;
  gap: 4px 12px;
}

.column-settings .el-checkbox {
  margin-right: 0;
}

.column-settings-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.consultation-editor {
  padding: 0 6px;
}

.consultation-form-section,
.consultation-project-intake {
  position: relative;
  margin: 0;
  padding: 22px 8px 8px;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.consultation-editor .form-section + .form-section {
  border-top: 1px solid var(--el-border-color-lighter);
}

.consultation-form-section--primary {
  padding-top: 4px;
}

.consultation-form-section--plain {
  background: transparent;
}

.consultation-confirmation-fields {
  margin: 2px 0 18px;
  padding: 14px 0 0;
  border: 0;
  border-top: 1px dashed var(--el-border-color-lighter);
  border-radius: 0;
  background: transparent;
}

.consultation-confirmation-fields__title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin: 0 0 14px 4px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
}

.consultation-confirmation-fields__title span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}

.consultation-form-section__header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin: 0 0 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.consultation-form-section__header h3 {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 16px;
  line-height: 22px;
}

.consultation-form-section__header h3::before {
  width: 3px;
  height: 15px;
  border-radius: 2px;
  background: var(--el-color-primary);
  content: '';
}

.consultation-form-section__header span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.intake-list-header { display: flex; align-items: center; justify-content: space-between; margin: 10px 0 8px; color: var(--el-text-color-regular); font-size: 14px; font-weight: 500; }
.intake-list-field { width: 100%; }
.intake-list-header--field { margin-top: 0; }
.intake-list-header--actions-only { justify-content: flex-end; }
.intake-list-header--field > span { color: var(--el-text-color-secondary); font-size: 12px; font-weight: 400; }
.intake-inline-row { display: flex; align-items: center; gap: 10px; width: 100%; margin-bottom: 8px; }
.intake-inline-row > .el-select, .intake-inline-row > .el-date-editor { flex: 1; }
.intake-direction-count { width: 150px; flex: 0 0 150px; }
@media (max-width: 768px) { .intake-inline-row { align-items: stretch; flex-direction: column; } .intake-direction-count { width: 100%; flex-basis: auto; } }

.consultations-card :deep(.el-card__header) {
  padding: 10px 16px;
}

.consultations-card :deep(.el-card__body) {
  padding: 12px 16px 14px;
}

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

.search-form :deep(.el-form-item) {
  margin: 0;
}

.search-form :deep(.el-form-item:last-child) {
  margin-left: auto;
}

.advanced-filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 10px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-8);
  font-size: 12px;
  line-height: 20px;
}

.advanced-filter-panel {
  max-height: min(560px, calc(100vh - 120px));
  padding: 4px 4px 0;
  overflow-y: auto;
}

.advanced-filter-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 600;
}

.advanced-filter-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.advanced-filter-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.advanced-filter-form :deep(.el-select),
.advanced-filter-form :deep(.el-date-editor) {
  width: 100%;
}

:global(.consultation-advanced-filter-popover),
:global(.consultation-detail-popover),
:global(.consultation-client-detail-popover) {
  max-width: calc(100vw - 32px);
}

.consultations-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  overflow-x: auto;
}

.status-switch-tag.el-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  max-width: 100%;
  cursor: pointer;
  user-select: none;
  vertical-align: middle;
  transition: opacity 0.15s ease;
}

.status-switch-tag :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;
  line-height: 1;
}

.status-switch-text {
  line-height: 1;
}

.status-switch-caret {
  width: 10px;
  height: 10px;
  font-size: 10px;
  flex-shrink: 0;
  margin: 0;
}

.status-switch-tag:hover {
  opacity: 0.85;
}

.status-switch-tag.is-updating {
  pointer-events: none;
  opacity: 0.55;
}

.status-option-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.status-current-icon {
  color: var(--el-color-primary);
}

.consultation-method-field {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 8px;
}

.consultation-method-field .el-select {
  width: 100%;
}

.personnel-assignment-section {
  margin-bottom: 18px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}

.personnel-assignment-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  min-height: 48px;
  padding: 10px 14px;
  border: 0;
  color: var(--el-text-color-primary);
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.personnel-assignment-toggle:hover {
  background: var(--el-fill-color-light);
}

.personnel-assignment-toggle:focus-visible {
  outline: 2px solid var(--el-color-primary-light-5);
  outline-offset: -2px;
}

.personnel-assignment-heading {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
}

.personnel-assignment-title {
  flex: none;
  font-weight: 600;
}

.personnel-assignment-summary {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.personnel-assignment-action {
  display: inline-flex;
  align-items: center;
  flex: none;
  gap: 6px;
  color: var(--el-color-primary);
  font-size: 13px;
  line-height: 20px;
}

.personnel-assignment-arrow {
  width: 14px;
  height: 14px;
  flex: none;
  font-size: 14px;
  transition: transform 0.2s ease;
}

.personnel-assignment-arrow.is-expanded {
  transform: rotate(180deg);
}

.personnel-assignment-fields {
  padding: 16px 14px 2px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}

.personnel-assignment-hint {
  margin: -4px 0 12px 120px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.detail-popover {
  max-height: 560px;
  overflow-y: auto;
}

.detail-value {
  word-break: break-all;
  color: #606266;
  font-size: 13px;
}

.client-short-name-link,
.consultation-code-link {
  display: block;
  max-width: 100%;
  height: auto;
  padding: 0;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today-consultation-time {
  font-weight: 600;
  letter-spacing: 0.2px;
}

.yesterday-consultation-time {
  font-weight: 600;
  letter-spacing: 0.2px;
}

.project-name-hint {
  width: 100%;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.confirmation-preview-body {
  min-height: 260px;
}

.confirmation-summary {
  margin: 16px 0 20px;
}

.missing-field-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.missing-field-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.client-short-name-field {
  width: 100%;
}

.client-short-name-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.client-short-name-hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.client-suggestion {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.client-suggestion-meta {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:global(.el-select-dropdown__item.consultation-type-option--simple) {
  color: #47705a;
  font-weight: 600;
  background-color: #f1f8f3;
  box-shadow: inset 3px 0 #a8cdb3;
}

:global(.el-select-dropdown__item.consultation-type-option--simple:hover),
:global(.el-select-dropdown__item.consultation-type-option--simple.is-hovering),
:global(.el-select-dropdown__item.consultation-type-option--simple.is-selected) {
  color: #365b47;
  background-color: #e8f3eb;
}

:global(.consultation-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  margin-bottom: 0;
  overflow: hidden;
  border-radius: 10px;
}

:global(.consultation-dialog.is-draggable .el-dialog__header),
:global(.consultation-confirmation-dialog.is-draggable .el-dialog__header) {
  cursor: grab;
}

:global(.consultation-dialog.is-dragging),
:global(.consultation-confirmation-dialog.is-dragging) {
  box-shadow: 0 18px 48px rgb(15 23 42 / 24%);
}

:global(.consultation-dialog.is-dragging .el-dialog__header),
:global(.consultation-confirmation-dialog.is-dragging .el-dialog__header) {
  cursor: grabbing;
}

:global(.consultation-dialog .el-dialog__headerbtn),
:global(.consultation-dialog .el-dialog__header button),
:global(.consultation-dialog .el-dialog__header a),
:global(.consultation-confirmation-dialog .el-dialog__headerbtn),
:global(.consultation-confirmation-dialog .el-dialog__header button),
:global(.consultation-confirmation-dialog .el-dialog__header a) {
  cursor: pointer;
}

:global(.consultation-dialog .el-dialog__header input),
:global(.consultation-dialog .el-dialog__header textarea) {
  cursor: text;
  user-select: text;
}

:global(.consultation-confirmation-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 84vh;
  margin-bottom: 0;
  overflow: hidden;
}

:global(.consultation-confirmation-dialog .el-dialog__header),
:global(.consultation-confirmation-dialog .el-dialog__footer) {
  flex: none;
}

:global(.consultation-confirmation-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

:global(.consultation-confirmation-dialog .el-dialog__footer) {
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  box-shadow: 0 -4px 12px rgb(0 0 0 / 4%);
}

:global(.consultation-dialog .el-dialog__header) {
  flex: none;
  margin-right: 0;
  padding: 18px 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

:global(.consultation-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 4px;
}

:global(.consultation-dialog .el-dialog__footer) {
  flex: none;
  padding: 14px 24px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  box-shadow: 0 -4px 12px rgb(0 0 0 / 4%);
}

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

  :global(.consultation-dialog .el-col-12) {
    flex: 0 0 100%;
    max-width: 100%;
  }

  :global(.consultation-dialog .el-dialog__body) {
    padding: 16px 16px 4px;
  }

  .personnel-assignment-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }

  .personnel-assignment-summary {
    max-width: min(58vw, 420px);
  }

  .personnel-assignment-hint {
    margin-left: 0;
  }
}
</style>
