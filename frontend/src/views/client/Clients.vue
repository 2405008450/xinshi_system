<template>
  <el-card class="compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span>客户信息</span>
          <small class="header-hint">母客户与子客户统一管理</small>
        </div>
        <div class="header-actions">
          <el-popover placement="bottom-end" :width="360" trigger="click" title="首页显示字段">
            <template #reference>
              <el-button>字段设置</el-button>
            </template>
            <el-checkbox-group v-model="visibleColumnKeys" class="column-settings">
              <el-checkbox
                v-for="column in clientColumnOptions"
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
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite && !deleteMode" type="primary" @click="handleAdd">新增客户</el-button>
        </div>
      </div>
    </template>

    <div class="search-bar">
      <el-form :inline="true" :model="searchForm" class="search-form-inline">
        <el-form-item label="客户名称">
          <el-input
            v-model="searchForm.client_name"
            placeholder="支持客户全称、简称及子客户名称模糊搜索"
            clearable
            @input="handleSearchInput"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="客户状态">
          <el-select
            v-model="searchForm.client_status"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            @change="handleSelectionChange"
          >
            <el-option label="合作中" value="active" />
            <el-option label="已停止" value="inactive" />
            <el-option label="待合作" value="pending" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-popover
            v-model:visible="advancedFilterVisible"
            trigger="click"
            placement="bottom-end"
            :width="760"
            popper-class="client-advanced-filter-popper"
          >
            <template #reference>
              <el-button>
                高级筛选
                <el-badge
                  v-if="advancedFilterCount"
                  :value="advancedFilterCount"
                  class="advanced-filter-badge"
                />
              </el-button>
            </template>
            <div class="advanced-filter-panel">
              <div class="advanced-filter-title">高级筛选</div>
              <el-form :model="advancedFilters" label-width="112px" class="advanced-filter-form">
                <el-row :gutter="16">
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="客户编号">
                      <el-input v-model="advancedFilters.client_code" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="客户简称">
                      <el-input v-model="advancedFilters.client_short_name" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="英文名称">
                      <el-input v-model="advancedFilters.english_name" placeholder="匹配英文全称、简称" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="客户负责人">
                      <el-input v-model="advancedFilters.client_manager" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="负责人联系方式">
                      <el-input v-model="advancedFilters.manager_contact" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="客户领域一级">
                      <el-input v-model="advancedFilters.field_level1" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="客户领域二级">
                      <el-input v-model="advancedFilters.field_level2" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="国家">
                      <el-input v-model="advancedFilters.country" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="省份">
                      <el-input v-model="advancedFilters.province" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="地级市">
                      <el-input v-model="advancedFilters.city" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="区县">
                      <el-input v-model="advancedFilters.district" clearable @input="handleAdvancedTextInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="开始合作日期">
                      <el-date-picker
                        v-model="advancedFilters.cooperation_date_range"
                        type="daterange"
                        range-separator="至"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY-MM-DD"
                        clearable
                        style="width: 100%"
                        @change="handleSelectionChange"
                      />
                    </el-form-item>
                  </el-col>
                </el-row>
              </el-form>
              <div class="advanced-filter-actions">
                <el-button link type="primary" @click="clearAdvancedFilters">清空高级条件</el-button>
                <el-button @click="advancedFilterVisible = false">关闭</el-button>
              </div>
            </div>
          </el-popover>
        </el-form-item>
      </el-form>
    </div>

    <el-table
      ref="clientTableRef"
      :data="tableData"
      v-loading="loading"
      border
      row-key="id"
      @expand-change="handleExpandChange"
      @selection-change="handleDeleteSelectionChange"
    >
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column
        type="expand"
        width="1"
        class-name="client-hidden-expand-column"
        label-class-name="client-hidden-expand-column"
      >
        <template #default="{ row }">
          <div style="padding: 10px 40px" v-if="row.sub_clients && row.sub_clients.length > 0">
            <el-table :data="row.sub_clients" border size="small">
              <el-table-column prop="sub_client_code" label="子客户编号" width="180" />
              <el-table-column prop="client_name" label="客户全称" />
              <el-table-column prop="client_short_name" label="客户简称" />
              <el-table-column prop="client_manager" label="客户负责人" />
              <el-table-column prop="manager_contact" label="负责人联系方式" />
              <el-table-column v-if="canWrite" label="操作" width="88" align="center">
                <template #default="{ row: subRow }">
                  <TableActionButton action="edit" @click="handleEditSub(subRow, row)" />
                  <TableActionButton action="delete" @click="handleDeleteSub(subRow, row)" />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="序号" width="68" align="center">
        <template #default="{ row, $index }">
          <div class="client-index-cell">
            <span>{{ $index + 1 }}</span>
            <button
              v-if="hasSubClients(row)"
              type="button"
              class="sub-client-expand-button"
              :class="{ 'is-expanded': expandedClientIds.has(row.id) }"
              :aria-label="expandedClientIds.has(row.id) ? '收起子客户' : '展开子客户'"
              :aria-expanded="expandedClientIds.has(row.id)"
              @click.stop="toggleClientExpansion(row)"
            >
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        v-for="column in displayedClientColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        show-overflow-tooltip
      >
        <template #header>
          <ClickableColumnHeader v-if="column.key === 'client_short_name'" :label="column.label" hint="点击客户简称查看客户详情" />
          <span v-else>{{ column.label }}</span>
        </template>
        <template #default="{ row }">
          <el-popover
            v-if="column.key === 'client_short_name'"
            placement="left"
            :width="760"
            trigger="click"
            :title="`${row.client_short_name || row.client_name || '客户'} 客户详情`"
            @show="loadClientDetail(row.id)"
          >
            <template #reference>
              <el-button
                type="primary"
                link
                class="client-short-name-link business-clickable-cell"
                :title="`${row.client_short_name || '-'}（点击查看详情）`"
                @click.stop
              >
                {{ row.client_short_name || '-' }}
              </el-button>
            </template>
            <div class="detail-popover" v-loading="detailLoadingId === row.id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ getDetailRow(row).client_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户全称">
                  <span class="detail-value">{{ getDetailRow(row).client_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="英文全称">
                  <span class="detail-value">{{ getDetailRow(row).english_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="英文简称">
                  <span class="detail-value">{{ getDetailRow(row).english_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户负责人">
                  <span class="detail-value">{{ getDetailRow(row).client_manager || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="负责人联系方式">
                  <span class="detail-value">{{ getDetailRow(row).manager_contact || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户状态">
                  <span class="detail-value">{{ getClientStatusLabel(getDetailRow(row).client_status) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户领域一级">
                  <span class="detail-value">{{ getDetailRow(row).field_level1 || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户领域二级">
                  <span class="detail-value">{{ getDetailRow(row).field_level2 || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="国家">
                  <span class="detail-value">{{ getDetailRow(row).country || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="省份">
                  <span class="detail-value">{{ getDetailRow(row).province || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="地级市">
                  <span class="detail-value">{{ getDetailRow(row).city || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="区县">
                  <span class="detail-value">{{ getDetailRow(row).district || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="开始合作时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).cooperation_start_date) }}</span>
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
          <el-tag
            v-else-if="column.key === 'client_status'"
            :type="row.client_status === 'active' ? 'success' : 'info'"
          >
            {{ getClientStatusLabel(row.client_status) }}
          </el-tag>
          <span v-else-if="column.key === 'cooperation_start_date'">
            {{ formatDatetime(row.cooperation_start_date) }}
          </span>
          <span v-else>{{ row[column.key] || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton action="edit" @click="handleEdit(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 20px"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      class="client-form-dialog"
      width="min(960px, calc(100vw - 32px))"
      top="5vh"
      @close="handleDialogClose"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户编号" prop="client_code">
              <el-input v-model="form.client_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户全称" prop="client_name">
              <el-input v-model="form.client_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称" prop="client_short_name">
              <el-input v-model="form.client_short_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户负责人" prop="client_manager">
              <el-input v-model="form.client_manager" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人联系方式" prop="manager_contact">
              <el-input v-model="form.manager_contact" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户状态" prop="client_status">
              <el-select v-model="form.client_status" placeholder="请选择状态" style="width: 100%">
                <el-option label="合作中" value="active" />
                <el-option label="已停止" value="inactive" />
                <el-option label="待合作" value="pending" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户领域一级" prop="field_level1">
              <el-input v-model="form.field_level1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户领域二级" prop="field_level2">
              <el-input v-model="form.field_level2" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="国家" prop="country">
              <el-input v-model="form.country" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="省份" prop="province">
              <el-input v-model="form.province" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="地级市" prop="city">
              <el-input v-model="form.city" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="区县" prop="district">
              <el-input v-model="form.district" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始合作时间" prop="cooperation_start_date">
              <el-date-picker
                v-model="form.cooperation_start_date"
                type="datetime"
                placeholder="选择日期时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider v-if="form.id">子客户管理</el-divider>
        <div v-if="form.id" style="margin-bottom: 20px; padding: 0 40px;">
          <el-button v-if="canWrite" type="success" size="small" @click="handleAddSub">添加子客户</el-button>
          <el-table :data="form.sub_clients" border size="small" style="margin-top: 10px;">
            <el-table-column prop="sub_client_code" label="子客户编号" width="160" />
            <el-table-column prop="client_name" label="客户全称" />
            <el-table-column prop="client_manager" label="负责人" />
            <el-table-column v-if="canWrite" label="操作" width="88" align="center">
              <template #default="{ row: subRow }">
                <TableActionButton action="edit" @click="handleEditSub(subRow, form)" />
                <TableActionButton action="delete" @click="handleDeleteSub(subRow, form)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="subDialogVisible"
      :title="subDialogTitle"
      width="800px"
      append-to-body
      @close="resetSubForm"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-form ref="subFormRef" :model="subForm" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="子客户编号" prop="sub_client_code">
              <el-input v-model="subForm.sub_client_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户全称" prop="client_name">
              <el-input v-model="subForm.client_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户简称" prop="client_short_name">
              <el-input v-model="subForm.client_short_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户负责人" prop="client_manager">
              <el-input v-model="subForm.client_manager" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系方式" prop="manager_contact">
              <el-input v-model="subForm.manager_contact" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="client_status">
              <el-select v-model="subForm.client_status" style="width: 100%">
                <el-option label="合作中" value="active" />
                <el-option label="已停止" value="inactive" />
                <el-option label="待合作" value="pending" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="subSubmitLoading" @click="handleSubSubmit">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import * as clientApi from '@/api/clients'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { hasPermission } from '@/utils/permission'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'

const loading = ref(false)
const canWrite = hasPermission('clients:write')
const submitLoading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增客户')
const formRef = ref(null)
const detailCache = reactive({})
const detailLoadingId = ref(null)
const currentUserId = localStorage.getItem('user_id') || null
const CLIENT_DRAFTS_STORAGE_KEY = `client_form_drafts:${currentUserId || 'anonymous'}`
const CLIENT_COLUMNS_STORAGE_KEY = `client_visible_columns:${currentUserId || 'anonymous'}`
const CREATE_DRAFT_KEY = 'create'

const clientColumnOptions = [
  { key: 'client_code', label: '客户编号', width: 140 },
  { key: 'client_name', label: '客户全称', width: 175 },
  { key: 'client_short_name', label: '客户简称', width: 150 },
  { key: 'english_name', label: '英文全称', width: 200 },
  { key: 'english_short_name', label: '英文简称', width: 150 },
  { key: 'client_manager', label: '客户负责人', width: 140 },
  { key: 'manager_contact', label: '负责人联系方式', width: 150 },
  { key: 'field_level1', label: '客户领域一级', width: 150 },
  { key: 'field_level2', label: '客户领域二级', width: 120 },
  { key: 'country', label: '国家', width: 100 },
  { key: 'province', label: '省份', width: 100 },
  { key: 'city', label: '地级市', width: 100 },
  { key: 'district', label: '区县', width: 100 },
  { key: 'client_status', label: '客户状态', width: 120 },
  { key: 'cooperation_start_date', label: '开始合作时间', width: 180 },
  { key: 'remarks', label: '备注', width: 220 }
]
const legacyDefaultVisibleColumnKeys = [
  'client_short_name',
  'client_manager',
  'manager_contact',
  'field_level1',
  'client_status',
  'cooperation_start_date'
]
const defaultVisibleColumnKeys = [
  'client_code',
  'client_name',
  'client_short_name',
  'client_manager',
  'manager_contact',
  'field_level1',
  'field_level2',
  'country',
  'client_status',
  'cooperation_start_date'
]

const loadVisibleColumnKeys = () => {
  try {
    const savedKeys = JSON.parse(localStorage.getItem(CLIENT_COLUMNS_STORAGE_KEY) || 'null')
    if (!Array.isArray(savedKeys)) return [...defaultVisibleColumnKeys]
    const availableKeys = new Set(clientColumnOptions.map((column) => column.key))
    const filteredKeys = savedKeys.filter((key) => availableKeys.has(key))
    const usesLegacyDefault = filteredKeys.length === legacyDefaultVisibleColumnKeys.length
      && filteredKeys.every((key, index) => key === legacyDefaultVisibleColumnKeys[index])
    return usesLegacyDefault ? [...defaultVisibleColumnKeys] : filteredKeys
  } catch {
    localStorage.removeItem(CLIENT_COLUMNS_STORAGE_KEY)
    return [...defaultVisibleColumnKeys]
  }
}

const visibleColumnKeys = ref(loadVisibleColumnKeys())
const displayedClientColumns = computed(() => {
  const visibleKeys = new Set(visibleColumnKeys.value)
  return clientColumnOptions.filter((column) => visibleKeys.has(column.key))
})

watch(visibleColumnKeys, (keys) => {
  localStorage.setItem(CLIENT_COLUMNS_STORAGE_KEY, JSON.stringify(keys))
}, { deep: true })

const resetVisibleColumns = () => {
  visibleColumnKeys.value = [...defaultVisibleColumnKeys]
}

const subDialogVisible = ref(false)
const subDialogTitle = ref('新增子客户')
const subSubmitLoading = ref(false)
const subFormRef = ref(null)

const tableData = ref([])
const clientTableRef = ref(null)
const expandedClientIds = ref(new Set())
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows:tableData,tableRef:clientTableRef,pagination,deleteRow:(row)=>clientApi.deleteClient(row.id),getLabel:(row)=>row.client_name||row.client_short_name||row.client_code,reload:()=>fetchData(),onDeleted:(row)=>{delete detailCache[row.id]},entityName:'客户'})

const defaultClientForm = () => ({
  id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  client_manager: '',
  manager_contact: '',
  field_level1: '',
  field_level2: '',
  country: '',
  province: '',
  city: '',
  district: '',
  client_status: 'pending',
  cooperation_start_date: '',
  remarks: '',
  sub_clients: [],
  updated_at: null,
})

const form = reactive(defaultClientForm())
const activeDraftKey = ref(null)
const draftSavingEnabled = ref(false)

const readDrafts = () => {
  try {
    const drafts = JSON.parse(sessionStorage.getItem(CLIENT_DRAFTS_STORAGE_KEY) || '{}')
    return drafts && typeof drafts === 'object' ? drafts : {}
  } catch {
    sessionStorage.removeItem(CLIENT_DRAFTS_STORAGE_KEY)
    return {}
  }
}

const writeDrafts = (drafts) => {
  if (Object.keys(drafts).length) {
    sessionStorage.setItem(CLIENT_DRAFTS_STORAGE_KEY, JSON.stringify(drafts))
  } else {
    sessionStorage.removeItem(CLIENT_DRAFTS_STORAGE_KEY)
  }
}

const removeDraft = (draftKey) => {
  if (!draftKey) return
  const drafts = readDrafts()
  delete drafts[draftKey]
  writeDrafts(drafts)
}

const saveActiveDraft = () => {
  if (!draftSavingEnabled.value || activeDraftKey.value !== CREATE_DRAFT_KEY) return
  const drafts = readDrafts()
  drafts[CREATE_DRAFT_KEY] = {
    form: { ...form },
    savedAt: new Date().toISOString()
  }
  writeDrafts(drafts)
}

const restoreDraftIfNeeded = async () => {
  const draft = readDrafts()[CREATE_DRAFT_KEY]
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
        closeOnPressEscape: false
      }
    )
    const restoredForm = defaultClientForm()
    Object.keys(restoredForm).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(draft.form, key)) {
        restoredForm[key] = draft.form[key]
      }
    })
    Object.assign(form, restoredForm)
  } catch {
    removeDraft(CREATE_DRAFT_KEY)
  } finally {
    draftSavingEnabled.value = true
    await nextTick()
    formRef.value?.clearValidate()
  }
}

watch(form, saveActiveDraft, { deep: true, flush: 'sync' })

const subForm = reactive({
  id: null,
  parent_client_id: null,
  sub_client_code: '',
  client_name: '',
  client_short_name: '',
  client_manager: '',
  manager_contact: '',
  client_status: 'pending'
})

const rules = {
  client_short_name: [{ required: true, message: '请输入客户简称', trigger: 'blur' }],
  client_manager: [{ required: true, message: '请输入客户负责人', trigger: 'blur' }]
}

const searchForm = reactive({
  client_name: '',
  client_status: ''
})

const createDefaultAdvancedFilters = () => ({
  client_code: '',
  client_short_name: '',
  english_name: '',
  client_manager: '',
  manager_contact: '',
  field_level1: '',
  field_level2: '',
  country: '',
  province: '',
  city: '',
  district: '',
  cooperation_date_range: []
})

const advancedFilters = reactive(createDefaultAdvancedFilters())
const advancedFilterVisible = ref(false)
const advancedFilterCount = computed(() => Object.entries(advancedFilters).reduce((count, [key, value]) => {
  if (key === 'cooperation_date_range') return count + (Array.isArray(value) && value.length === 2 ? 1 : 0)
  return count + (String(value || '').trim() ? 1 : 0)
}, 0))

let searchTimer = null
let clientsRequestController = null
let clientsRequestId = 0

const handleSearch = () => {
  exitDeleteMode()
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  pagination.page = 1
  fetchData()
}

const handleSearchInput = (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!value) {
    handleSearch()
    return
  }
  searchTimer = setTimeout(handleSearch, 400)
}

const handleAdvancedTextInput = (value) => {
  handleSearchInput(value)
}

const handleSelectionChange = () => {
  handleSearch()
}

const hasSubClients = (row) => Array.isArray(row?.sub_clients) && row.sub_clients.length > 0

const toggleClientExpansion = (row) => {
  if (!hasSubClients(row)) return
  clientTableRef.value?.toggleRowExpansion(row)
}

const handleExpandChange = (_row, expandedRows) => {
  expandedClientIds.value = new Set(expandedRows.map((row) => row.id))
}

const resetSearch = () => {
  exitDeleteMode()
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  Object.assign(searchForm, { client_name: '', client_status: '' })
  Object.assign(advancedFilters, createDefaultAdvancedFilters())
  handleSearch()
}

const clearAdvancedFilters = () => {
  exitDeleteMode()
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  Object.assign(advancedFilters, createDefaultAdvancedFilters())
  handleSearch()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchData()
}

const handleCurrentChange = () => {
  fetchData()
}

const buildFilterParams = () => {
  const params = {}
  const textFilters = {
    client_name: searchForm.client_name,
    client_code: advancedFilters.client_code,
    client_short_name: advancedFilters.client_short_name,
    english_name: advancedFilters.english_name,
    client_manager: advancedFilters.client_manager,
    manager_contact: advancedFilters.manager_contact,
    field_level1: advancedFilters.field_level1,
    field_level2: advancedFilters.field_level2,
    country: advancedFilters.country,
    province: advancedFilters.province,
    city: advancedFilters.city,
    district: advancedFilters.district
  }
  Object.entries(textFilters).forEach(([key, value]) => {
    const normalizedValue = String(value || '').trim()
    if (normalizedValue) params[key] = normalizedValue
  })
  if (searchForm.client_status) params.client_status = searchForm.client_status
  if (advancedFilters.cooperation_date_range?.length === 2) {
    params.cooperation_start_date_from = advancedFilters.cooperation_date_range[0]
    params.cooperation_start_date_to = advancedFilters.cooperation_date_range[1]
  }
  return params
}

const fetchData = async () => {
  clientsRequestController?.abort()
  clientsRequestController = new AbortController()
  const requestId = ++clientsRequestId
  loading.value = true
  try {
    const filterParams = buildFilterParams()
    const params = {
      ...filterParams,
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const [res, countRes] = await Promise.all([
      clientApi.getClients(params, { signal: clientsRequestController.signal }),
      clientApi.getClientCount(filterParams, { signal: clientsRequestController.signal })
    ])
    if (requestId !== clientsRequestId) return
    tableData.value = res || []
    expandedClientIds.value = new Set()
    pagination.total = countRes?.total || 0

    const lastPage = Math.max(1, Math.ceil(pagination.total / pagination.limit))
    if (pagination.page > lastPage) {
      pagination.page = lastPage
      await fetchData()
    }
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || requestId !== clientsRequestId) return
    ElMessage.error(error?.detail || '网络异常，客户列表未刷新，请检查网络后重试')
  } finally {
    if (requestId === clientsRequestId) loading.value = false
  }
}

const handleAdd = async () => {
  dialogTitle.value = '新增客户'
  draftSavingEnabled.value = false
  activeDraftKey.value = CREATE_DRAFT_KEY
  resetForm()
  dialogVisible.value = true
  await nextTick()
  await restoreDraftIfNeeded()
}

const getClientStatusLabel = (status) => {
  return status === 'active' ? '合作中' : status === 'inactive' ? '已停止' : '待合作'
}

const formatDatetime = (value) => {
  if (!value) return '-'
  const date = new Date(String(value).replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

const getDetailRow = (row) => detailCache[row.id] || row

const loadClientDetail = async (id) => {
  if (!id || detailCache[id]) return
  detailLoadingId.value = id
  try {
    detailCache[id] = await clientApi.getClient(id)
  } catch {
    ElMessage.error('加载客户详情失败')
  } finally {
    detailLoadingId.value = null
  }
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑客户'
  draftSavingEnabled.value = false
  activeDraftKey.value = null
  resetForm()
  Object.assign(form, {
    id: row.id,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    client_manager: row.client_manager || '',
    manager_contact: row.manager_contact || '',
    field_level1: row.field_level1 || '',
    field_level2: row.field_level2 || '',
    country: row.country || '',
    province: row.province || '',
    city: row.city || '',
    district: row.district || '',
    client_status: row.client_status || 'pending',
    cooperation_start_date: row.cooperation_start_date || '',
    remarks: row.remarks || '',
    sub_clients: row.sub_clients || [],
    updated_at: row.updated_at || null,
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        const submitData = { ...form }
        delete submitData.id
        delete submitData.sub_clients
        delete submitData.created_at
        submitData.expected_updated_at = form.updated_at || null
        delete submitData.updated_at
        // 日期选择器未填写时会产生空字符串，后端 Optional[datetime] 需要 null。
        submitData.cooperation_start_date = submitData.cooperation_start_date || null
        if (form.id) {
          await clientApi.updateClient(form.id, submitData)
          delete detailCache[form.id]
          ElMessage.success('更新成功')
        } else {
          await clientApi.createClient(submitData)
          pagination.page = 1
          ElMessage.success('创建成功')
        }
        if (!form.id) {
          draftSavingEnabled.value = false
          removeDraft(CREATE_DRAFT_KEY)
        }
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || '操作失败')
      } finally {
        submitLoading.value = false
      }
    }
  })
}

const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(form, defaultClientForm())
  nextTick(() => formRef.value?.clearValidate())
}

const handleDialogClose = () => {
  draftSavingEnabled.value = false
  activeDraftKey.value = null
  resetForm()
}

const handleAddSub = () => {
  handleAddSubForParent(form)
}

const handleAddSubForParent = (parent) => {
  if (!parent?.id) {
    ElMessage.warning('请先保存母客户，再新增子客户')
    return
  }
  subDialogTitle.value = '新增子客户'
  resetSubForm()
  subForm.parent_client_id = parent.id
  subForm.client_manager = parent.client_manager || ''
  subForm.manager_contact = parent.manager_contact || ''
  subForm.client_status = parent.client_status || 'pending'
  subDialogVisible.value = true
}

const handleEditSub = (subRow, parentRow = null) => {
  subDialogTitle.value = '编辑子客户'
  resetSubForm()
  Object.assign(subForm, { ...subRow })
  if (parentRow) subForm.parent_client_id = parentRow.id
  else subForm.parent_client_id = form.id
  subDialogVisible.value = true
}

const handleDeleteSub = async (subRow, parentRow = null) => {
  try {
    await ElMessageBox.confirm('确定要删除该子客户吗？', '提示', { type: 'warning' })
    await clientApi.deleteSubClient(subRow.id)
    ElMessage.success('删除子客户成功')
    
    if (form.id && parentRow?.id === form.id) {
       form.sub_clients = form.sub_clients.filter(s => s.id !== subRow.id)
    }
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleSubSubmit = async () => {
  if (!subFormRef.value) return
  await subFormRef.value.validate(async (valid) => {
    if (valid) {
      subSubmitLoading.value = true
      try {
        const submitData = { ...subForm }
        delete submitData.id
        delete submitData.created_at
        submitData.expected_updated_at = subForm.updated_at || null
        delete submitData.updated_at
        if (subForm.id) {
          await clientApi.updateSubClient(subForm.id, submitData)
          ElMessage.success('更新子客户成功')
        } else {
          await clientApi.createSubClient(subForm.parent_client_id, submitData)
          ElMessage.success('创建子客户成功')
        }
        subDialogVisible.value = false
        if (form.id) {
           const res = await clientApi.getClient(form.id)
           form.sub_clients = res.sub_clients || []
        }
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || '操作失败')
      } finally {
        subSubmitLoading.value = false
      }
    }
  })
}

const resetSubForm = () => {
  subFormRef.value?.resetFields()
  Object.assign(subForm, {
    id: null,
    parent_client_id: null,
    sub_client_code: '',
    client_name: '',
    client_short_name: '',
    client_manager: '',
    manager_contact: '',
    client_status: 'pending'
  })
  nextTick(() => subFormRef.value?.clearValidate())
}

onMounted(() => {
  fetchData()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  clientsRequestController?.abort()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header > div {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-hint {
  color: var(--el-text-color-secondary);
  font-weight: normal;
}
.column-settings {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
.search-bar {
  margin-bottom: 8px;
}
.search-form-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 6px 10px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}
.search-form-inline :deep(.el-form-item) {
  margin: 0;
}
.search-form-inline :deep(.el-form-item:last-child) {
  margin-left: auto;
}
.advanced-filter-badge {
  margin-left: 6px;
  vertical-align: middle;
}
.advanced-filter-title {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}
.advanced-filter-form :deep(.el-form-item) {
  margin-bottom: 16px;
}
.advanced-filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
:global(.client-advanced-filter-popper) {
  width: min(760px, calc(100vw - 32px)) !important;
  max-width: calc(100vw - 32px);
}
:global(.client-advanced-filter-popper .advanced-filter-panel) {
  max-height: min(560px, calc(100vh - 120px));
  overflow-y: auto;
  padding-right: 4px;
}
.detail-popover {
  max-height: 560px;
  overflow-y: auto;
}
.detail-value {
  color: #606266;
  font-size: 13px;
  word-break: break-all;
}
.client-short-name-link {
  display: block;
  max-width: 100%;
  height: auto;
  padding: 0;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.client-hidden-expand-column) {
  width: 1px !important;
  max-width: 1px !important;
  padding: 0 !important;
  visibility: hidden;
  border: 0 !important;
}
.client-index-cell {
  display: flex;
  min-height: 46px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
.sub-client-expand-button {
  display: inline-flex;
  width: 22px;
  height: 18px;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 4px;
}
.sub-client-expand-button:hover,
.sub-client-expand-button:focus-visible {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  outline: none;
}
.sub-client-expand-button .el-icon {
  transition: transform 0.2s ease;
}
.sub-client-expand-button.is-expanded .el-icon {
  transform: rotate(90deg);
}

:global(.client-form-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  margin-bottom: 0;
  overflow: hidden;
  border-radius: 10px;
}

:global(.client-form-dialog .el-dialog__header) {
  flex: none;
  margin-right: 0;
  padding: 18px 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

:global(.client-form-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 4px;
}

:global(.client-form-dialog .el-dialog__footer) {
  flex: none;
  padding: 14px 24px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  box-shadow: 0 -4px 12px rgb(0 0 0 / 4%);
}

@media (max-width: 768px) {
  .search-form-inline :deep(.el-form-item),
  .search-form-inline :deep(.el-form-item__content),
  .search-form-inline :deep(.el-input),
  .search-form-inline :deep(.el-select) {
    width: 100%;
  }

  .search-form-inline :deep(.el-form-item:last-child) {
    margin-left: 0;
  }

  :global(.client-form-dialog .el-col-12) {
    flex: 0 0 100%;
    max-width: 100%;
  }

  :global(.client-form-dialog .el-dialog__body) {
    padding: 16px 16px 4px;
  }
}
</style>
