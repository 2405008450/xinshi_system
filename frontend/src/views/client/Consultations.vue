<template>
  <el-card class="consultations-card">
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
          <el-button type="primary" @click="handleAdd">新增咨询</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="客户名称">
        <el-input
          v-model="searchForm.client_name"
          placeholder="输入客户全称或简称"
          clearable
          style="width: 240px"
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
        <el-popover
          v-model:visible="advancedFilterVisible"
          placement="bottom-end"
          trigger="click"
          :width="760"
          popper-class="consultation-advanced-filter-popover"
        >
          <template #reference>
            <el-button>
              高级筛选
              <span v-if="advancedFilterCount" class="advanced-filter-count">{{ advancedFilterCount }}</span>
            </el-button>
          </template>
          <div class="advanced-filter-panel">
            <div class="advanced-filter-header">
              <span>高级筛选</span>
              <div class="advanced-filter-header-actions">
                <el-button v-if="advancedFilterCount" type="primary" link @click="clearAdvancedFilters">
                  清空高级条件
                </el-button>
                <el-button link @click="advancedFilterVisible = false">关闭</el-button>
              </div>
            </div>
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
                      <el-option v-for="item in consultationTypeOptions" :key="item" :label="item" :value="item" />
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
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column
        v-for="column in displayedConsultationColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :show-overflow-tooltip="column.key !== 'status'"
      >
        <template #default="{ row }">
          <el-dropdown
            v-if="column.key === 'status'"
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
                  :disabled="item.value === row.status || statusUpdatingId === row.id"
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
          <span v-else-if="column.key === 'consultation_method'">{{ consultationMethodLabel(row.consultation_method) }}</span>
          <span v-else-if="column.key === 'consultation_type'">{{ consultationTypeLabel(row.consultation_type) }}</span>
          <span v-else>{{ row[column.key] ?? '-' }}</span>
        </template>
      </el-table-column>

      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <el-popover
            placement="left"
            :width="760"
            trigger="click"
            title="咨询详情"
            @show="loadConsultationDetail(row.id)"
          >
            <template #reference>
              <el-button type="info" size="small" link>
                查看详情
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
                <el-descriptions-item label="咨询时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).consultation_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询状态">
                  <span class="detail-value">{{ getStatusText(getDetailRow(row).status) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询方式">
                  <span class="detail-value">{{ consultationMethodLabel(getDetailRow(row).consultation_method) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户来源">
                  <span class="detail-value">{{ getDetailRow(row).client_source || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="来源关键词">
                  <span class="detail-value">{{ getDetailRow(row).source_keyword || '-' }}</span>
                </el-descriptions-item>

                <el-descriptions-item label="咨询类型">
                  <span class="detail-value">{{ consultationTypeLabel(getDetailRow(row).consultation_type) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="处理方式">
                  <span class="detail-value">{{ getDetailRow(row).handling_method || '-' }}</span>
                </el-descriptions-item>
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
                  <span class="detail-value">{{ getDetailRow(row).follow_up_status || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询描述" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).consultation_description || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进备注" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_remarks || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="备注" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).remarks || '-' }}</span>
                </el-descriptions-item>
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

      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton action="edit" @click="handleEdit(row)" />
          <TableActionButton action="delete" @click="handleDelete(row)" />
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
      v-model="dialogVisible"
      :title="dialogTitle"
      class="consultation-dialog"
      width="min(960px, calc(100vw - 32px))"
      top="5vh"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户全称" prop="client_name">
              <div style="display: flex; align-items: center; gap: 6px; width: 100%;">
                <el-autocomplete
                  v-model="form.client_name"
                  :fetch-suggestions="searchClientsByName"
                  placeholder="输入名称模糊搜索，无结果则新建"
                  style="flex: 1;"
                  value-key="client_name"
                  clearable
                  @select="handleExistingClientSelect"
                  @clear="handleClientNameClear"
                  @input="handleClientNameInput"
                >
                  <template #default="{ item }">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span>{{ item.client_name }}</span>
                      <span style="color: #909399; font-size: 12px; margin-left: 10px;">{{ item.client_code }}</span>
                    </div>
                  </template>
                </el-autocomplete>
                <el-tag v-if="form.client_id" type="success" size="small" effect="plain">老客户</el-tag>
                <el-tag v-else-if="form.client_name" type="warning" size="small" effect="plain">新客户</el-tag>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户编号">
              <el-input
                v-model="form.client_code"
                disabled
                :placeholder="!form.client_id && form.client_name ? '保存后自动生成' : '选择老客户后自动填充'"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人联系方式" prop="manager_contact">
              <el-input
                v-model="form.manager_contact"
                maxlength="100"
                clearable
                placeholder="请输入客户负责人联系方式"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称" prop="client_short_name">
              <div class="client-short-name-field">
                <el-autocomplete
                  v-model="form.client_short_name"
                  :fetch-suggestions="searchClientsByShortName"
                  placeholder="输入简称联想客户，无匹配时保存后自动新增"
                  value-key="client_short_name"
                  clearable
                  style="width: 100%"
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
                <div class="client-short-name-hint">
                  未匹配已有客户时，新增或编辑咨询都会自动创建客户并完成关联。
                </div>
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
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
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
          <el-col :span="12">
            <el-form-item label="咨询类型" prop="consultation_type">
              <el-select
                v-model="form.consultation_type"
                filterable
                allow-create
                placeholder="请选择；其他项目可直接输入自定义类型"
                style="width: 100%"
              >
                <el-option v-for="item in consultationTypeOptions" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户来源" prop="client_source">
              <el-input v-model="form.client_source" placeholder="请输入客户来源" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源关键词" prop="source_keyword">
              <el-input v-model="form.source_keyword" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="咨询方式" prop="consultation_method">
              <div class="consultation-method-field">
                <el-select v-model="form.consultation_method" placeholder="请选择">
                  <el-option
                    v-for="item in consultationMethodOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <el-input
                  v-if="form.consultation_method === 'other'"
                  v-model="form.consultation_method_custom"
                  placeholder="请输入其他咨询方式"
                  clearable
                />
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="处理方式" prop="handling_method">
              <el-input v-model="form.handling_method" />
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
              />
            </el-form-item>
          </el-col>
        </el-row>

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

        <el-form-item label="跟进状态" prop="follow_up_status">
          <el-input v-model="form.follow_up_status" />
        </el-form-item>

        <el-form-item label="咨询描述" prop="consultation_description">
          <el-input v-model="form.consultation_description" type="textarea" :rows="3" />
        </el-form-item>

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
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 口译/笔译咨询确认中间层 -->
    <el-dialog
      v-model="confirmationDialogVisible"
      title="确认咨询并生成项目"
      width="min(720px, calc(100vw - 32px))"
      :close-on-click-modal="false"
      top="8vh"
      @close="resetConfirmationDraft"
    >
      <div v-loading="confirmationPreviewLoading" class="confirmation-preview-body">
        <el-alert
          title="确认后将同时更新咨询状态、生成对应项目并保存邮件主题；取消不会改变咨询状态。"
          type="info"
          :closable="false"
          show-icon
        />
        <el-descriptions :column="2" border size="small" class="confirmation-summary">
          <el-descriptions-item label="咨询类型">{{ confirmationTypeLabel }}</el-descriptions-item>
          <el-descriptions-item label="预计订单号">{{ confirmationPreview.order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ confirmationPreview.client_short_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="负责人联系方式">{{ confirmationPreview.manager_contact || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-form :model="confirmationForm" ref="confirmationFormRef" label-width="120px" @submit.prevent>
          <el-form-item
            label="项目名称"
            prop="projectName"
            :rules="[{ required: true, message: '请输入项目名称', trigger: 'blur' }]"
          >
            <el-input v-model="confirmationForm.projectName" maxlength="255" show-word-limit />
            <div class="project-name-hint">已按“客户简称-当前日期”预填，可在确认前修改。</div>
          </el-form-item>
          <el-form-item label="标题前缀">
            <el-input
              v-model="confirmationForm.subjectPrefix"
              maxlength="50"
              show-word-limit
              clearable
              placeholder="例如：***急***"
            />
          </el-form-item>
          <el-form-item v-if="confirmationPreview.project_type === 'interpretation'" label="客户单号/标识">
            <el-input
              v-model="confirmationForm.customerOrderNo"
              maxlength="150"
              show-word-limit
              clearable
            />
          </el-form-item>
          <el-form-item label="邮件主题预览">
            <el-input :model-value="confirmationSubjectPreview" type="textarea" :rows="3" readonly />
          </el-form-item>
          <el-form-item v-if="confirmationMissingFields.length" label="缺失字段">
            <div class="missing-field-list">
              <el-tag v-for="item in confirmationMissingFields" :key="item" type="warning" effect="plain">{{ item }}</el-tag>
              <span class="missing-field-hint">缺失项不会写入主题，但不影响确认。</span>
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button :disabled="confirmationSubmitting" @click="confirmationDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="confirmationSubmitting"
          :disabled="confirmationPreviewLoading || !confirmationPreview.order_no"
          @click="handleConfirmConsultation"
        >确认并生成项目</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as consultationApi from '@/api/consultations'
import * as clientApi from '@/api/clients'
import * as userApi from '@/api/users'
import { buildAutoProjectName } from '@/utils/projectNaming'

const router = useRouter()
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增咨询')
const formRef = ref(null)
const userOptions = ref([])
const detailCache = reactive({})
const detailLoadingId = ref(null)
const clientSearchLoading = ref(false)

// 口译/笔译咨询确认中间层
const confirmationDialogVisible = ref(false)
const confirmationPreviewLoading = ref(false)
const confirmationSubmitting = ref(false)
const confirmationFormRef = ref(null)
const confirmationContext = reactive({ mode: '', consultationId: null, consultationPayload: null, row: null })
const confirmationForm = reactive({ projectName: '', subjectPrefix: '', customerOrderNo: '' })
const confirmationPreview = reactive({
  project_type: '', order_no: '', client_short_name: '', manager_contact: '',
  project_name: '', customer_order_no: '', email_subject_preview: '', missing_fields: [],
})
const CONFIRMED_CONSULTATION_STATUS = 'success'
const currentUserId = localStorage.getItem('user_id') || null
const CONSULTATION_DRAFTS_STORAGE_KEY = `consultation_form_drafts:${currentUserId || 'anonymous'}`
const CONSULTATION_COLUMNS_STORAGE_KEY = `consultation_visible_columns:${currentUserId || 'anonymous'}`

const consultationColumnOptions = [
  { key: 'consultation_code', label: '咨询编号', width: 160 },
  { key: 'client_code', label: '客户编号', width: 150 },
  { key: 'client_name', label: '客户全称', width: 200 },
  { key: 'client_short_name', label: '客户简称', width: 150 },
  { key: 'status', label: '咨询状态', width: 136 },
  { key: 'consultation_time', label: '咨询时间', width: 180 },
  { key: 'consultation_method', label: '咨询方式', width: 120 },
  { key: 'consultation_type', label: '咨询类型', width: 140 },
  { key: 'client_source', label: '客户来源', width: 120 },
  { key: 'source_keyword', label: '来源关键词', width: 150 },
  { key: 'handling_method', label: '处理方式', width: 150 },
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
    return savedKeys.filter((key) => availableKeys.has(key))
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
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
})

const searchForm = reactive({
  client_name: '',
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
    client_name: '',
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

const defaultForm = () => ({
  id: null,
  client_id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  manager_contact: '',
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
})

const form = reactive(defaultForm())
const activeDraftKey = ref(null)
const draftSavingEnabled = ref(false)

const readDrafts = () => {
  try {
    const drafts = JSON.parse(sessionStorage.getItem(CONSULTATION_DRAFTS_STORAGE_KEY) || '{}')
    return drafts && typeof drafts === 'object' ? drafts : {}
  } catch {
    sessionStorage.removeItem(CONSULTATION_DRAFTS_STORAGE_KEY)
    return {}
  }
}

const writeDrafts = (drafts) => {
  if (Object.keys(drafts).length) {
    sessionStorage.setItem(CONSULTATION_DRAFTS_STORAGE_KEY, JSON.stringify(drafts))
  } else {
    sessionStorage.removeItem(CONSULTATION_DRAFTS_STORAGE_KEY)
  }
}

const removeDraft = (draftKey) => {
  if (!draftKey) return
  const drafts = readDrafts()
  delete drafts[draftKey]
  writeDrafts(drafts)
}

const saveActiveDraft = () => {
  if (!draftSavingEnabled.value || !activeDraftKey.value) return
  const drafts = readDrafts()
  drafts[activeDraftKey.value] = {
    form: { ...form },
    savedAt: new Date().toISOString(),
  }
  writeDrafts(drafts)
}

const restoreDraftIfNeeded = async () => {
  const draftKey = activeDraftKey.value
  const draft = readDrafts()[draftKey]
  if (!draft?.form) {
    draftSavingEnabled.value = true
    return
  }

  try {
    await ElMessageBox.confirm(
      '检测到该表单有未提交的草稿，是否恢复上次填写的内容？',
      '恢复未提交草稿',
      {
        confirmButtonText: '恢复草稿',
        cancelButtonText: '放弃草稿',
        type: 'info',
        showClose: false,
        closeOnClickModal: false,
        closeOnPressEscape: false,
      }
    )
    const restoredForm = defaultForm()
    Object.keys(restoredForm).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(draft.form, key)) {
        restoredForm[key] = draft.form[key]
      }
    })
    Object.assign(form, restoredForm)
    if (form.consultation_method && !consultationMethodLabels[form.consultation_method]) {
      form.consultation_method_custom = form.consultation_method
      form.consultation_method = 'other'
    }
  } catch {
    removeDraft(draftKey)
  } finally {
    draftSavingEnabled.value = true
    await nextTick()
    formRef.value?.clearValidate()
  }
}

watch(form, saveActiveDraft, { deep: true, flush: 'sync' })
const consultationTypeOptions = [
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
const normalizeConsultationMethod = (value) => {
  if (!value || consultationMethodLabels[value]) {
    return { method: value || '', custom: '' }
  }
  return { method: 'other', custom: value }
}
const legacyConsultationTypeLabels = {
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
  ['笔译项目', 'translation', '笔译'].includes(value)
)
const projectRouteName = (consultationType) => {
  if (isTranslationConsultationType(consultationType)) return 'TranslationProjectDetails'
  if (isInterpretationConsultationType(consultationType)) return 'InterpretationProjectDetails'
  if (isAnnotationConsultationType(consultationType)) return 'AnnotationProjectDetails'
  if (isRecruitmentConsultationType(consultationType)) return 'RecruitmentProjectDetails'
  return ''
}
const routeToProjectBoard = async (consultationType) => {
  const name = projectRouteName(consultationType)
  if (name) await router.push({ name })
}
const confirmationTypeLabel = computed(() => (
  confirmationPreview.project_type === 'interpretation' ? '口译项目' : '笔译项目'
))
const confirmationSubjectParts = computed(() => {
  const parts = [
    confirmationForm.subjectPrefix,
    confirmationPreview.order_no,
    confirmationPreview.client_short_name,
    confirmationPreview.manager_contact,
  ]
  if (confirmationPreview.project_type === 'interpretation') {
    parts.push(confirmationForm.customerOrderNo)
  }
  parts.push(confirmationForm.projectName)
  return parts.map((item) => item?.trim()).filter(Boolean)
})
const confirmationSubjectPreview = computed(() => confirmationSubjectParts.value.join('，'))
const confirmationMissingFields = computed(() => {
  const fields = [
    ['订单号', confirmationPreview.order_no],
    ['客户简称', confirmationPreview.client_short_name],
    ['负责人联系方式', confirmationPreview.manager_contact],
  ]
  if (confirmationPreview.project_type === 'interpretation') {
    fields.push(['客户单号/标识', confirmationForm.customerOrderNo])
  }
  fields.push(['项目名称', confirmationForm.projectName])
  return fields.filter(([, value]) => !value?.trim()).map(([label]) => label)
})

// 是否为新客户：没有关联的 client_id 但已填写客户全称
const isNewClient = computed(() => !form.client_id && !!form.client_name)

const rules = {
  client_name: [{ required: true, message: '请输入客户全称', trigger: 'blur' }],
  client_short_name: [{
    validator: (_rule, value, callback) => {
      if (isNewClient.value && !value?.trim()) {
        callback(new Error('新客户必须填写客户简称'))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
  status: [{ required: true, message: '请选择咨询状态', trigger: 'change' }],
  consultation_type: [{ required: true, message: '请选择咨询类型', trigger: 'change' }],
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

const formatDatetime = (val) => {
  if (!val) return '-'
  const date = new Date(String(val).replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? val : date.toLocaleString('zh-CN', { hour12: false })
}

const formatTime = (val) => {
  if (!val) return '-'
  const date = new Date(String(val).replace(' ', 'T'))
  return Number.isNaN(date.getTime())
    ? '-'
    : date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
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
  form.client_name = item.client_name
  form.client_code = item.client_code || ''
  form.client_short_name = item.client_short_name || ''
  form.manager_contact = item.manager_contact || ''
}

// 用户手动输入（重新输入时清空已关联的客户）
const handleClientNameInput = () => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.client_code = ''
  if (hadSelectedClient) {
    form.client_short_name = ''
    form.manager_contact = ''
  }
}

// 简称可直接录入；未填写全称时，以简称作为待完善客户的默认全称。
const handleClientShortNameInput = (value) => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.client_code = ''
  if (hadSelectedClient) {
    form.client_name = ''
    form.manager_contact = ''
  }
  if (!form.client_name?.trim() && value?.trim()) {
    form.client_name = value.trim()
  }
}

const handleClientShortNameClear = () => {
  const hadSelectedClient = !!form.client_id
  form.client_id = null
  form.client_code = ''
  form.client_short_name = ''
  if (hadSelectedClient) {
    form.client_name = ''
    form.manager_contact = ''
  }
}

// 用户点击清空按钮
const handleClientNameClear = () => {
  form.client_id = null
  form.client_name = ''
  form.client_code = ''
  form.client_short_name = ''
  form.manager_contact = ''
}

const loadUsers = async () => {
  try {
    const res = await userApi.getUsers({ skip: 0, limit: 500 })
    userOptions.value = Array.isArray(res) ? res : []
  } catch {
    userOptions.value = []
  }
}

const getUserName = (id) => {
  if (!id) return '-'
  const user = userOptions.value.find((u) => u.id === id)
  return user ? (user.full_name || user.username) : id
}

const buildSearchFilters = () => {
  const [consultationDateStart, consultationDateEnd] = searchForm.consultation_date_range || []
  return {
    client_name: searchForm.client_name?.trim() || undefined,
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
  } catch {
    if (requestId !== consultationRequestId) return
    tableData.value = []
    pagination.total = 0
  } finally {
    if (requestId === consultationRequestId) loading.value = false
  }
}

const toNullable = (v) => (v === '' ? null : v)

const buildPayload = () => ({
  client_id: form.client_id,
  client_code: form.client_code?.trim() || null,
  client_name: form.client_name?.trim() || null,
  client_short_name: form.client_short_name?.trim() || null,
  manager_contact: form.manager_contact?.trim() || null,
  consultation_time: toNullable(form.consultation_time),
  consultation_method: toNullable(
    form.consultation_method === 'other'
      ? form.consultation_method_custom?.trim() || 'other'
      : form.consultation_method
  ),
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
})

const loadConsultationDetail = async (id) => {
  if (!id || detailCache[id]) return
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

const handleAdd = async () => {
  dialogTitle.value = '新增咨询'
  draftSavingEnabled.value = false
  activeDraftKey.value = 'create'
  resetForm()
  dialogVisible.value = true
  await nextTick()
  await restoreDraftIfNeeded()
}

const fillFormByRow = (row) => {
  const consultationMethod = normalizeConsultationMethod(row.consultation_method)
  Object.assign(form, {
    id: row.id,
    client_id: row.client_id || null,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    manager_contact: row.manager_contact || '',
    consultation_time: row.consultation_time || '',
    consultation_method: consultationMethod.method,
    consultation_method_custom: consultationMethod.custom,
    client_source: row.client_source || '',
    source_keyword: row.source_keyword || '',
    consultation_description: row.consultation_description || '',
    status: row.status || 'following',
    consultation_type: consultationTypeLabel(row.consultation_type) === '-'
      ? ''
      : consultationTypeLabel(row.consultation_type),
    handling_method: row.handling_method || '',
    remarks: row.remarks || '',
    customer_service_id: row.customer_service_id || currentUserId,
    sales_person_id: row.sales_person_id || currentUserId,
    editor_id: row.editor_id || currentUserId,
    follow_up_count: row.follow_up_count ?? 0,
    follow_up_time: row.follow_up_time || '',
    follow_up_status: row.follow_up_status || '',
    follow_up_remarks: row.follow_up_remarks || '',
    follow_up_person_id: row.follow_up_person_id || currentUserId,
  })
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑咨询'
  draftSavingEnabled.value = false
  activeDraftKey.value = `edit:${row.id}`
  try {
    const detail = await consultationApi.getConsultation(row.id)
    detailCache[row.id] = detail
    fillFormByRow(detail)
  } catch {
    fillFormByRow(row)
  }
  dialogVisible.value = true
  await nextTick()
  await restoreDraftIfNeeded()
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该咨询记录吗？', '提示', { type: 'warning' })
    await consultationApi.deleteConsultation(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const statusUpdatingId = ref(null)

// 列表内直接切换咨询状态：仅提交 status 字段（后端支持局部更新）。
// 普通状态直接切换；切到「已确认」时保留与编辑弹窗一致的联动：
// 笔译、口译先确认项目名称和邮件主题；标注、招聘由后端直接生成专用项目。
const handleInlineStatusChange = async (row, newStatus) => {
  if (!newStatus || newStatus === row.status || statusUpdatingId.value === row.id) return

  if (
    newStatus === CONFIRMED_CONSULTATION_STATUS
    && (isInterpretationConsultationType(row.consultation_type) || isTranslationConsultationType(row.consultation_type))
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
    ElMessage.error(error?.response?.data?.detail || '切换状态失败')
  } finally {
    statusUpdatingId.value = null
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const payload = buildPayload()
      const isUpdate = !!form.id
      // 记录提交前咨询的旧状态（用于判断是否首次变为已确认）
      const prevStatus = isUpdate
        ? (detailCache[form.id]?.status ?? tableData.value.find((r) => r.id === form.id)?.status)
        : null
      const consultationId = form.id
      let savedConsultation = null

      if (
        payload.status === CONFIRMED_CONSULTATION_STATUS
        && prevStatus !== CONFIRMED_CONSULTATION_STATUS
        && (isInterpretationConsultationType(payload.consultation_type) || isTranslationConsultationType(payload.consultation_type))
      ) {
        await openConfirmationDialog({
          mode: isUpdate ? 'update' : 'create',
          consultationId,
          consultationPayload: payload,
          row: null,
          previewSource: payload,
        })
        return
      }

      if (isUpdate) {
        savedConsultation = await consultationApi.updateConsultation(consultationId, payload)
        delete detailCache[consultationId]
        ElMessage.success('更新成功')
      } else {
        const created = await consultationApi.createConsultation(payload)
        savedConsultation = created
        ElMessage.success('创建成功')
        // 新建咨询也支持立即确认并生成项目详情。
        if (payload.status === CONFIRMED_CONSULTATION_STATUS && created?.id) {
          if (isRecruitmentConsultationType(payload.consultation_type)) {
            ElMessage.success('咨询已确认，招聘项目已自动生成')
          }
        }
      }
      draftSavingEnabled.value = false
      removeDraft(activeDraftKey.value)
      dialogVisible.value = false
      await fetchData()

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
      ElMessage.error(error?.response?.data?.detail || error?.detail || '操作失败')
    }
  })
}

const applyConfirmationPreview = (preview) => {
  Object.assign(confirmationPreview, {
    project_type: preview?.project_type || '',
    order_no: preview?.order_no || '',
    client_short_name: preview?.client_short_name || '',
    manager_contact: preview?.manager_contact || '',
    project_name: preview?.project_name || '',
    customer_order_no: preview?.customer_order_no || '',
    email_subject_preview: preview?.email_subject_preview || '',
    missing_fields: Array.isArray(preview?.missing_fields) ? preview.missing_fields : [],
  })
  confirmationForm.projectName = preview?.project_name || confirmationForm.projectName
  confirmationForm.customerOrderNo = preview?.customer_order_no || confirmationForm.customerOrderNo
}

const openConfirmationDialog = async ({ mode, consultationId, consultationPayload, row, previewSource }) => {
  Object.assign(confirmationContext, { mode, consultationId, consultationPayload, row })
  Object.assign(confirmationForm, {
    projectName: buildAutoProjectName(previewSource?.client_short_name),
    subjectPrefix: '',
    customerOrderNo: '',
  })
  Object.assign(confirmationPreview, {
    project_type: '', order_no: '', client_short_name: '', manager_contact: '',
    project_name: '', customer_order_no: '', email_subject_preview: '', missing_fields: [],
  })
  confirmationDialogVisible.value = true
  confirmationPreviewLoading.value = true
  try {
    const preview = await consultationApi.previewConfirmation({
      consultation_id: consultationId || null,
      consultation_type: previewSource?.consultation_type,
      client_id: previewSource?.client_id || null,
      client_short_name: previewSource?.client_short_name || null,
      manager_contact: previewSource?.manager_contact?.trim() || null,
      project_name: confirmationForm.projectName || null,
      subject_prefix: null,
      customer_order_no: null,
    })
    applyConfirmationPreview(preview)
    await nextTick()
    confirmationFormRef.value?.clearValidate()
  } catch (error) {
    confirmationDialogVisible.value = false
    ElMessage.error(error?.response?.data?.detail || error?.detail || '加载确认预览失败')
  } finally {
    confirmationPreviewLoading.value = false
  }
}

const handleConfirmConsultation = async () => {
  if (!confirmationFormRef.value) return
  const valid = await confirmationFormRef.value.validate().catch(() => false)
  if (!valid || !confirmationPreview.order_no) return

  const confirmation = {
    project_name: confirmationForm.projectName?.trim() || null,
    expected_order_no: confirmationPreview.order_no,
    subject_prefix: confirmationForm.subjectPrefix?.trim() || null,
    customer_order_no: confirmationPreview.project_type === 'interpretation'
      ? confirmationForm.customerOrderNo?.trim() || null
      : null,
  }
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

    if (confirmationContext.row) confirmationContext.row.status = CONFIRMED_CONSULTATION_STATUS
    if (confirmationContext.consultationId) delete detailCache[confirmationContext.consultationId]
    if (confirmationContext.mode === 'create' || confirmationContext.mode === 'update') {
      draftSavingEnabled.value = false
      removeDraft(activeDraftKey.value)
      dialogVisible.value = false
    }
    confirmationDialogVisible.value = false
    ElMessage.success(
      `${result?.project_type === 'interpretation' ? '口译' : '笔译'}咨询已确认，项目和邮件主题已生成`
    )
    await fetchData()
    await routeToProjectBoard(result?.project_type)
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.detail
    if (error?.response?.status === 409 && detail?.preview) {
      applyConfirmationPreview(detail.preview)
      ElMessage.warning(detail.message || '订单号已变化，请核对刷新后的主题并再次确认')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '确认咨询失败')
    }
  } finally {
    confirmationSubmitting.value = false
    statusUpdatingId.value = null
  }
}

const resetConfirmationDraft = () => {
  Object.assign(confirmationContext, { mode: '', consultationId: null, consultationPayload: null, row: null })
  Object.assign(confirmationForm, { projectName: '', subjectPrefix: '', customerOrderNo: '' })
  confirmationFormRef.value?.clearValidate()
}

const resetForm = () => {
  Object.assign(form, defaultForm())
  formRef.value?.clearValidate()
}

const handleDialogClose = () => {
  draftSavingEnabled.value = false
  activeDraftKey.value = null
  resetForm()
}

onMounted(async () => {
  await loadUsers()
  await fetchData()
})

onBeforeUnmount(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  consultationSearchController?.abort()
})
</script>

<style scoped>
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

.consultations-card :deep(.el-card__header) {
  padding: 16px 20px;
}

.consultations-card :deep(.el-card__body) {
  padding: 20px;
}

.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
  margin-bottom: 16px;
  padding: 16px;
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

:global(.consultation-advanced-filter-popover) {
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

.detail-popover {
  max-height: 560px;
  overflow-y: auto;
}

.detail-value {
  word-break: break-all;
  color: #606266;
  font-size: 13px;
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

:global(.consultation-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  margin-bottom: 0;
  overflow: hidden;
  border-radius: 10px;
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
}
</style>
