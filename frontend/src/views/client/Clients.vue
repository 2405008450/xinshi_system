<template>
  <el-card class="common-page-card viewport-list-card compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span>客户管理</span>
          <small class="header-hint">客户与子客户统一管理</small>
        </div>
        <div class="header-actions">
          <TableColumnSettings settings-key="client-information"
            v-model="visibleColumnKeys"
            :columns="clientColumnOptions"
            :column-count="2"
            title="客户列表字段"
            @reset="resetVisibleColumns"
          />
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite && !deleteMode" type="primary" @click="handleAdd">新增客户</el-button>
        </div>
      </div>
    </template>

    <div class="search-bar">
      <AppForm :inline="true" :model="searchForm" class="search-form-inline">
        <el-form-item label="客户名称">
          <el-input
            v-model="advancedFilters.client_name"
            placeholder="支持客户全称、简称及子客户名称模糊搜索"
            clearable
            @input="handleSearchInput"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="客户状态">
          <el-select
            v-model="advancedFilters.client_status"
            multiple
            collapse-tags
            :max-collapse-tags="1"
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
          <AdvancedFilterPopover
            v-model:visible="advancedFilterVisible"
            :count="advancedFilterCount"
            popper-class="client-advanced-filter-popper"
            @clear="clearAdvancedFilters"
            @reset="resetSearch"
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
            <CompactFilterGrid :fields="clientAdvancedFilterFields" :model="advancedFilters" @update="updateConfiguredFilter" @text-input="handleAdvancedTextInput" @change="handleSelectionChange" @enter="handleSearch" />
          </AdvancedFilterPopover>
        </el-form-item>
      </AppForm>
    </div>

    <div class="viewport-list-table">
    <el-table height="100%"
      ref="clientTableRef"
      :data="tableData"
      v-loading="loading"
      border
      row-key="id"
      @expand-change="handleExpandChange"
      @selection-change="handleDeleteSelectionChange"
    >
<OrderedTableColumns settings-key="client-information">
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
              <el-table-column prop="client_manager" label="客户联系人" />
              <el-table-column prop="manager_contact" label="联系方式" />
              <el-table-column v-if="canWrite" label="操作" width="100" fixed="right" align="center">
                <template #default="{ row: subRow }">
                  <TableActionButton action="edit" @click="handleEditSub(subRow, row)" />
                  <TableActionButton action="delete" @click="handleDeleteSub(subRow, row)" />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="序号" width="84" align="center">
        <template #default="{ row, $index }">
          <div class="client-index-cell">
            <span>{{ $index + 1 }}</span>
            <TableExpandButton
              v-if="hasSubClients(row)"
              :expanded="expandedClientIds.has(row.id)"
              :count="row.sub_clients.length"
              expand-label="展开子客户"
              collapse-label="收起子客户"
              @click="toggleClientExpansion(row)"
            />
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
          <ConfiguredColumnHeaderFilter v-if="headerFilterDefinition(column.key)" :definition="headerFilterDefinition(column.key)" :model-value="advancedFilters[column.key]" @update:model-value="advancedFilters[column.key]=$event" @text-input="handleAdvancedTextInput" @change="handleSelectionChange" @enter="handleSearch" @clear="handleSelectionChange">
            <template #label><ClickableColumnHeader v-if="column.key === 'client_short_name'" :label="column.label" hint="点击客户简称查看客户详情" /><span v-else>{{ column.label }}</span></template>
          </ConfiguredColumnHeaderFilter>
          <template v-else><ClickableColumnHeader v-if="column.key === 'client_short_name'" :label="column.label" hint="点击客户简称查看客户详情" /><span v-else>{{ column.label }}</span></template>
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
                <el-descriptions-item label="客户类型">{{ getDetailRow(row).customer_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ getDetailRow(row).client_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="英文全称">
                  <span class="detail-value">{{ getDetailRow(row).english_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="英文简称">
                  <span class="detail-value">{{ getDetailRow(row).english_short_name || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户联系人">
                  <span class="detail-value">{{ getDetailRow(row).client_manager || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="联系方式">
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
                <el-descriptions-item label="操作人">{{ getDetailRow(row).operator_name || '未能回溯' }}</el-descriptions-item>
                <el-descriptions-item label="操作人来源">{{ operatorSourceText(getDetailRow(row)) }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).created_at) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="财务" :span="2"><CustomerFinancePanel :client-id="row.id" :can-write="canWrite" /></el-descriptions-item>
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
          <span v-else-if="column.key === 'client_manager'">{{ (row.contact_names?.length ? row.contact_names : [row.client_manager]).filter(Boolean).join('、') || '-' }}</span>
          <span v-else>{{ row[column.key] || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <PrimaryEditButton @click="handleEdit(row)" />
        </template>
      </el-table-column>
    </OrderedTableColumns>
</el-table>
    </div>

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

    <DraggableFormDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      class="client-form-dialog"
      width="min(960px, calc(100vw - 32px))"
      top="5vh"
      @close="handleDialogClose"
    >
      <template #header>
        <DialogFieldSearchHeader
          ref="clientFieldSearchRef"
          v-model="clientFieldSearchKeyword"
          :title="dialogTitle"
          subtitle="搜索并快速定位客户字段"
          :fetch-suggestions="fetchClientFieldSuggestions"
          placeholder="搜索客户字段，如客户联系人"
          @select="locateClientField"
          @clear="clearClientFieldSearch"
        />
      </template>
      <div ref="clientEditorBodyRef">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px" data-dialog-field-search-label="操作人" data-dialog-field-search-aliases="录入人,咨询录入人">
          <el-descriptions-item label="操作人">
            <ReadonlyField :model-value="form.operator_name || ''" source="auto" :placeholder="form.id ? '未能回溯' : '保存后自动生成'" tooltip="客户首次录入操作人；历史数据按关联咨询录入人回溯，后续编辑不覆盖" />
          </el-descriptions-item>
          <el-descriptions-item label="来源">{{ form.id ? operatorSourceText(form) : '保存后记录当前登录用户' }}</el-descriptions-item>
        </el-descriptions>
        <el-tabs v-model="clientActiveTab" class="client-editor-tabs">
        <el-tab-pane label="基本信息" name="basic">
        <AppForm number-scope="client" number-field="client_code" :number-active="dialogVisible && !form.id"
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="120px"
        >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户编号" prop="client_code">
              <ReadonlyField v-if="!form.id" :model-value="form.client_code" source="auto" placeholder="正在占用编号" /><el-input v-else v-model="form.client_code" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户简称" prop="client_short_name">
              <ClientShortNameInput v-model="form.client_short_name" v-model:full-name="form.client_name" />
            <ClientNameGuidance />
</el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户全称" prop="client_name">
              <el-input v-model="form.client_name" />
            </el-form-item>
            <el-form-item label="客户类型" prop="customer_type"><el-select v-model="form.customer_type" clearable placeholder="请选择客户类型" @clear="form.customer_type=null"><el-option v-for="item in customerTypes" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          </el-col>
        </el-row>
        <el-form-item prop="contact_names" :rules="contactListRules" label-width="0px"><ClientContactNamesEditor :model-value="peopleFor(form)" @update:model-value="rows=>setPeople(form,rows)" /></el-form-item>
        <el-row :gutter="20">
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
        <CustomerRegionFields :model-value="form" @update:model-value="value=>Object.assign(form,value)" />

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始合作时间" prop="cooperation_start_date">
              <el-date-picker
                v-model="form.cooperation_start_date"
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
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider v-if="form.id">子客户管理</el-divider>

        <div v-if="form.id" style="margin-bottom: 20px; padding: 0 40px;">
          <el-button v-if="canWrite" type="success" size="small" @click="handleAddSub">添加子客户</el-button>
          <el-table :data="form.sub_clients" border size="small" style="margin-top: 10px;">
            <el-table-column prop="sub_client_code" label="子客户编号" width="160" />
            <el-table-column prop="client_name" label="客户全称" />
            <el-table-column prop="client_short_name" label="客户简称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="customer_type" label="客户类型" min-width="120" />
            <el-table-column label="客户联系人" min-width="150"><template #default="{row}">{{ (row.contact_names?.length?row.contact_names:[row.client_manager]).filter(Boolean).join('、')||'-' }}</template></el-table-column>
            <el-table-column label="联系方式" min-width="180"><template #default="{row}"><div v-for="(person,index) in peopleFor(row)" :key="index">{{person.name}}：{{person.contact_method||'-'}}</div></template></el-table-column>
            <el-table-column label="说明" min-width="180"><template #default="{row}"><div v-for="(person,index) in peopleFor(row)" :key="index">{{person.description?`${person.name}：${person.description}`:''}}</div></template></el-table-column>
            <el-table-column label="详情" width="100" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="子客户详情"><template #reference><el-button link type="primary">查看详情</el-button></template><div style="max-height:560px;overflow-y:auto;overflow-wrap:anywhere"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="field in subDetailFields" :key="field.key" :label="field.label">{{subDetailValue(row,field.key)}}</el-descriptions-item><el-descriptions-item v-for="(person,index) in peopleFor(row)" :key="`person-${index}`" :label="`联系人${index+1}`">{{person.name}}　联系方式：{{person.contact_method||'-'}}　说明：{{person.description||'-'}}</el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="100" fixed="right" align="center">
              <template #default="{ row: subRow }">
                <TableActionButton action="edit" @click="handleEditSub(subRow, form)" />
                <TableActionButton action="delete" @click="handleDeleteSub(subRow, form)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
        </AppForm>
        </el-tab-pane>
        <el-tab-pane label="客户来源" name="sources">
          <CustomerSourceAnalysis v-if="clientActiveTab === 'sources'" :key="form.id || 'new'" :client-id="form.id" customer-mode />
        </el-tab-pane>
        <el-tab-pane label="财务信息" name="finance">
          <CustomerFinancePanel v-if="clientActiveTab === 'finance'" :key="form.id || 'new'" :client-id="form.id" :can-write="canWrite" />
        </el-tab-pane>
        <el-tab-pane label="合作信息" name="cooperation">
          <div data-dialog-field-search-label="合作信息" class="cooperation-editor">
            <label for="client-cooperation-info">合作信息</label>
            <el-input id="client-cooperation-info" v-model="form.cooperation_info" type="textarea" :rows="14" placeholder="请输入客户合作信息" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="合作项目" name="projects">
          <CustomerCooperationProjects v-if="clientActiveTab === 'projects'" :client-id="form.id" />
        </el-tab-pane>
        <el-tab-pane label="对账单" name="statements">
          <div data-dialog-field-search-label="对账单">
            <el-empty v-if="!form.id" description="请先保存客户，再查看对账单" />
            <el-empty v-else-if="!canReadStatements" description="暂无财务对账单查看权限" />
            <CustomerStatementHistory v-else-if="clientActiveTab === 'statements'" :key="form.id" :client-id="form.id" />
          </div>
        </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </DraggableFormDialog>

    <DraggableFormDialog
      v-model="subDialogVisible"
      :title="subDialogTitle"
      width="min(900px, calc(100vw - 32px))"
      top="5vh"
      class="sub-client-editor-dialog"
      append-to-body
      @close="resetSubForm"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <template #header>
        <DialogFieldSearchHeader
          ref="subClientFieldSearchRef"
          v-model="subClientFieldSearchKeyword"
          :title="subDialogTitle"
          subtitle="搜索并快速定位子客户字段"
          :fetch-suggestions="fetchSubClientFieldSuggestions"
          placeholder="搜索子客户字段，如开始合作时间"
          @select="locateSubClientField"
          @clear="clearSubClientFieldSearch"
        />
      </template>
      <div ref="subClientEditorBodyRef">
        <AppForm number-scope="subclient" number-field="sub_client_code" :number-active="subDialogVisible && !subForm.id" :number-parent="subForm.parent_client_id || undefined" ref="subFormRef" :model="subForm" :rules="subRules" label-width="120px">
        <div class="sub-client-section" data-dialog-field-search-group data-dialog-field-search-group-title="客户基本资料">
          <h4>客户基本资料</h4>
          <el-row :gutter="20">
            <el-col :xs="24" :md="12"><el-form-item label="客户简称" prop="client_short_name"><ClientShortNameInput v-model="subForm.client_short_name" v-model:full-name="subForm.client_name" :parent-client-id="subForm.parent_client_id || ''" /><ClientNameGuidance /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="客户全称" prop="client_name"><el-input v-model="subForm.client_name" placeholder="子客户全称（选填）" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="英文全称"><el-input v-model="subForm.english_name" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="英文简称"><el-input v-model="subForm.english_short_name" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="子客户编号" prop="sub_client_code"><ReadonlyField v-if="!subForm.id" :model-value="subForm.sub_client_code" source="auto" placeholder="正在占用编号" /><el-input v-else v-model="subForm.sub_client_code" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="客户类型" prop="customer_type"><el-select v-model="subForm.customer_type" clearable style="width:100%" placeholder="请选择客户类型" @clear="subForm.customer_type=null"><el-option v-for="item in customerTypes" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
          </el-row>
        </div>
        <div class="sub-client-section" data-dialog-field-search-group data-dialog-field-search-group-title="联系信息">
          <h4>联系信息</h4><el-form-item prop="contact_names" :rules="contactListRules" label-width="0px"><ClientContactNamesEditor :model-value="peopleFor(subForm)" @update:model-value="rows=>setPeople(subForm,rows)" /></el-form-item>
        </div>
        <div class="sub-client-section" data-dialog-field-search-group data-dialog-field-search-group-title="业务与地区信息">
          <h4>业务与地区信息</h4><el-row :gutter="20">
            <el-col :xs="24" :md="12"><el-form-item label="客户领域一级"><el-input v-model="subForm.field_level1" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="客户领域二级"><el-input v-model="subForm.field_level2" /></el-form-item></el-col>
          </el-row>
          <CustomerRegionFields :model-value="subForm" @update:model-value="value=>Object.assign(subForm,value)" />
        </div>
        <div class="sub-client-section" data-dialog-field-search-group data-dialog-field-search-group-title="合作信息">
          <h4>合作信息</h4><el-row :gutter="20">
            <el-col :xs="24" :md="12"><el-form-item label="开始合作时间" prop="cooperation_start_date"><el-date-picker v-model="subForm.cooperation_start_date" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="状态" prop="client_status"><el-select v-model="subForm.client_status" style="width:100%"><el-option label="合作中" value="active" /><el-option label="已停止" value="inactive" /><el-option label="待合作" value="pending" /></el-select></el-form-item></el-col>
          </el-row><el-form-item label="备注"><el-input v-model="subForm.remarks" type="textarea" :rows="3" /></el-form-item>
        </div>
      </AppForm>
      </div>
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="subSubmitLoading" @click="handleSubSubmit">确定</el-button>
      </template>
    </DraggableFormDialog>
  </el-card>
</template>

<script setup>
import ClientShortNameInput from '@/components/common/ClientShortNameInput.vue'
import ClientNameGuidance from '@/components/common/ClientNameGuidance.vue'
import ClientContactNamesEditor from '@/components/common/ClientContactNamesEditor.vue'
import { CUSTOMER_TYPES as customerTypes } from '@/utils/customerTypes'
import CustomerCooperationProjects from '@/components/common/CustomerCooperationProjects.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import CustomerSourceAnalysis from '@/components/common/CustomerSourceAnalysis.vue'
import CustomerFinancePanel from '@/components/common/CustomerFinancePanel.vue'
import CustomerRegionFields from '@/components/common/CustomerRegionFields.vue'
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import { refreshAfterSave } from '@/utils/postSaveRefresh.js'
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch, defineAsyncComponent } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import * as clientApi from '@/api/clients'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { hasPermission } from '@/utils/permission'
import { formatDateTimeMinute as formatDatetime, businessDateTimeInputValue } from '@/utils/dateTime'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useFormDraft } from '@/composables/useFormDraft'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'

const loading = ref(false)
const canWrite = hasPermission('clients:write')
const canReadStatements = hasPermission('projects:read')
const CustomerStatementHistory = defineAsyncComponent(() => import('@/components/common/CustomerStatementHistory.vue'))
const submitLoading = ref(false)
const dialogVisible = ref(false)
const clientActiveTab = ref('basic')
const dialogTitle = ref('新增客户')
const formRef = ref(null)
const clientEditorBodyRef = ref(null)
const {
  fieldSearchRef: clientFieldSearchRef,
  fieldSearchKeyword: clientFieldSearchKeyword,
  fetchFieldSuggestions: fetchClientFieldSuggestions,
  locateDialogField: locateClientField,
  clearFieldSearch: clearClientFieldSearch,
} = useDialogFieldSearch(clientEditorBodyRef)
const detailCache = reactive({})
const detailLoadingId = ref(null)
const currentUserId = localStorage.getItem('user_id') || null
const CLIENT_COLUMNS_STORAGE_KEY = `client_visible_columns:${currentUserId || 'anonymous'}`

const clientColumnOptions = [
  { key: 'operator_name', label: '操作人', width: 120 },
  { key: 'client_code', label: '客户编号', width: 140 },
  { key: 'client_name', label: '客户全称', width: 175 },
  { key: 'client_short_name', label: '客户简称', width: 150 },
  { key: 'customer_type', label: '客户类型', width: 150 },
  { key: 'english_name', label: '英文全称', width: 200 },
  { key: 'english_short_name', label: '英文简称', width: 150 },
  { key: 'client_manager', label: '客户联系人', width: 140 },
  { key: 'manager_contact', label: '联系方式', width: 150 },
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
const operatorSourceText = (row) => {
  const labels = {
    client_create: '客户管理新增',
    consultation_create: '新咨询新增客户',
    consultation_edit_create: '咨询编辑时新增客户',
    consultation_editor_backfill: '历史咨询录入人回溯',
    consultation_capture_backfill: '历史咨询登录账号回溯',
  }
  const label = labels[row.operator_source] || '未能回溯'
  return row.operator_consultation_code ? `${label} · ${row.operator_consultation_code}` : label
}
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
const subClientEditorBodyRef = ref(null)
const {
  fieldSearchRef: subClientFieldSearchRef,
  fieldSearchKeyword: subClientFieldSearchKeyword,
  fetchFieldSuggestions: fetchSubClientFieldSuggestions,
  locateDialogField: locateSubClientField,
  clearFieldSearch: clearSubClientFieldSearch,
} = useDialogFieldSearch(subClientEditorBodyRef)

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
  operator_name: null,
  operator_source: null,
  operator_consultation_code: null,
  customer_type: null,
  id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  client_manager: '',
  contact_names: [],
  contact_people: [],
  manager_contact: '',
  field_level1: '',
  field_level2: '',
  country: '',
  province: '',
  city: '',
  district: '',
  full_address: '',
  detailed_address: '',
  client_status: 'pending',
  cooperation_start_date: '',
  remarks: '',
  cooperation_info: '',
  sub_clients: [],
  updated_at: null,
})

const form = reactive(defaultClientForm())
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({
  namespace: 'client', form, createDefault: defaultClientForm, formRef,
  applyDraft: draft=>{const contacts=Array.isArray(draft.contact_names)?draft.contact_names:form.contact_names;Object.assign(form,{...defaultClientForm(),...form,...draft,contact_names:contacts})},
  legacyStorageKeys: [`client_form_drafts:${currentUserId || 'anonymous'}`],
})

const subForm = reactive({
  customer_type: null,
  id: null,
  parent_client_id: null,
  sub_client_code: '',
  client_name: '',
  client_short_name: '',
  client_manager: '',
  contact_names: [],
  contact_people: [],
  manager_contact: '',
  english_name: '',
  english_short_name: '',
  field_level1: '',
  field_level2: '',
  country: '',
  province: '',
  city: '',
  district: '',
  full_address: '',
  detailed_address: '',
  cooperation_start_date: '',
  remarks: '',
  client_status: 'pending'
})

const subDetailFields=[['sub_client_code','子客户编号'],['client_name','客户全称'],['client_short_name','客户简称'],['english_name','英文全称'],['english_short_name','英文简称'],['customer_type','客户类型'],['field_level1','客户领域一级'],['field_level2','客户领域二级'],['country','国家'],['province','省份'],['city','地级市'],['district','区县'],['detailed_address','详细地址'],['full_address','完整地址'],['client_status','状态'],['cooperation_start_date','开始合作时间'],['remarks','备注']].map(([key,label])=>({key,label}))
function subDetailValue(row,key){if(key==='cooperation_start_date')return formatDatetime(row[key]);if(key==='client_status')return clientStatusOptions.find(item=>item.value===row[key])?.label||row[key]||'-';return row[key]||'-'}
function peopleFor(model){const stored=model.contact_people||[];return (model.contact_names?.length?model.contact_names:['']).map((name,index)=>{const row=stored.find(item=>item.name===name)||stored[index]||{};return {name,contact_method:row.contact_method??(index===0?model.manager_contact||'':''),description:row.description||''}})}
function setPeople(model,rows){model.contact_people=rows;model.contact_names=rows.map(row=>row.name);model.manager_contact=rows[0]?.contact_method||''}
const contactListRules=[{required:true,type:'array',min:1,message:'请至少填写一位客户联系人',trigger:'change'}]
const rules = {
  client_name: [{ required: true, pattern: /\S/, message: '请输入客户全称', trigger: ['blur','change'] }],
  client_short_name: [{ required: true, pattern: /\S/, message: '请输入客户简称', trigger: 'blur' }],
}

for(const model of [form,subForm])watch(()=>[model.customer_type,model.client_short_name],([type,name],previous=[])=>{
  if(type==='个人客户'&&String(name||'').trim()&&(!model.contact_names?.length||!String(model.contact_names[0]||'').trim()||model.contact_names[0]===previous[1]))model.contact_names=[String(name).trim(),...(model.contact_names||[]).slice(1)]
})

const subRules = {
  ...rules,
  client_name: [],
  cooperation_start_date: [{ required: true, message: '请选择开始合作时间', trigger: 'change' }]
}

const searchForm = reactive({
  client_name: '',
  client_status: ''
})

const clientStatusOptions=[{label:'合作中',value:'active'},{label:'已停止',value:'inactive'},{label:'待合作',value:'pending'}]
const clientFilterFields=[
  {key:'client_code',label:'客户编号',type:'text'},{key:'client_name',label:'客户全称',type:'text'},
  {key:'client_short_name',label:'客户简称',type:'text'},{key:'english_name',label:'英文全称',type:'text'},
  {key:'english_short_name',label:'英文简称',type:'text'},{key:'client_manager',label:'客户联系人',type:'text'},
  {key:'manager_contact',label:'联系方式',type:'text'},{key:'field_level1',label:'客户领域一级',type:'text'},
  {key:'field_level2',label:'客户领域二级',type:'text'},{key:'country',label:'国家',type:'text'},
  {key:'province',label:'省份',type:'text'},{key:'city',label:'地级市',type:'text'},
  {key:'district',label:'区县',type:'text'},{key:'client_status',label:'客户状态',type:'select',options:clientStatusOptions},
  {key:'cooperation_start_date',label:'开始合作时间',type:'date-range',wide:true},{key:'remarks',label:'备注',type:'text'},
]
const createDefaultAdvancedFilters = () => createFilterModel(clientFilterFields)

const advancedFilters = reactive(createDefaultAdvancedFilters())
const advancedFilterVisible = ref(false)
const clientAdvancedFilterFields=clientFilterFields.filter((item)=>!['client_name','client_status'].includes(item.key))
const advancedFilterCount = computed(() => countActiveFilters(advancedFilters,clientAdvancedFilterFields))
const headerFilterDefinition=(key)=>clientFilterFields.find((item)=>item.key===key)||null

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

const updateConfiguredFilter = (key, value) => {
  advancedFilters[key] = value
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
  resetFilterModel(advancedFilters,clientFilterFields)
  handleSearch()
}

const clearAdvancedFilters = () => {
  exitDeleteMode()
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  resetFilterModel(advancedFilters,clientAdvancedFilterFields)
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
  return {field_filters:serializeFieldFilters(advancedFilters,clientFilterFields)}
}

const fetchData = async () => {
  clientsRequestController?.abort()
  clientsRequestController = new AbortController()
  const requestId = ++clientsRequestId
  loading.value = true
  try {
    const params = {
      ...buildFilterParams(),
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const page = await clientApi.getClientPage(params, { signal: clientsRequestController.signal })
    if (requestId !== clientsRequestId) return
    tableData.value = page?.items || []
    expandedClientIds.value = new Set()
    pagination.total = page?.total || 0

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
  resetForm()
  dialogVisible.value = true
  await nextTick()
  await beginDraft('create')
}

const getClientStatusLabel = (status) => {
  return status === 'active' ? '合作中' : status === 'inactive' ? '已停止' : '待合作'
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

const handleEdit = async (row) => {
  try { row = { ...row, ...await clientApi.getClient(row.id) } } catch { ElMessage.error('读取最新客户联系人失败，请重试');return }
  dialogTitle.value = '客户管理 · 编辑窗口'
  resetForm()
  Object.assign(form, {
    id: row.id,
    operator_name: row.operator_name || null,
    operator_source: row.operator_source || null,
    operator_consultation_code: row.operator_consultation_code || null,
    customer_type: row.customer_type || null,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    client_manager: row.client_manager || '',
    contact_people: row.contact_people || [],
    contact_names: row.contact_names?.length ? [...row.contact_names] : row.client_manager ? [row.client_manager] : [],
    manager_contact: row.manager_contact || '',
    field_level1: row.field_level1 || '',
    field_level2: row.field_level2 || '',
    country: row.country || '',
    province: row.province || '',
    city: row.city || '',
    district: row.district || '',
    client_status: row.client_status || 'pending',
    cooperation_start_date: businessDateTimeInputValue(row.cooperation_start_date||''),
    remarks: row.remarks || '',
    cooperation_info: row.cooperation_info || '',
    full_address: row.full_address || '',
    detailed_address: row.detailed_address || '',
    sub_clients: row.sub_clients || [],
    updated_at: row.updated_at || null,
  })
  dialogVisible.value = true
  await nextTick()
  await beginDraft(`edit:${row.id}`)
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      if (submitLoading.value) return
      submitLoading.value = true
      try {
        const submitData = { ...form, client_manager: form.contact_names[0]?.trim() || '', contact_people: peopleFor(form), manager_contact: peopleFor(form)[0]?.contact_method || '' }
        delete submitData.operator_name
        delete submitData.operator_source
        delete submitData.operator_consultation_code
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
        clearDraft()
        dialogVisible.value = false
        fetchData()
      } catch (error) {
    await formRef.value?.applyServerErrors(error)
        ElMessage.error(error.detail || '操作失败')
      } finally {
        submitLoading.value = false
      }
    }
  })
}

const resetForm = () => {
  clientActiveTab.value = 'basic'
  clearClientFieldSearch()
  formRef.value?.resetFields()
  Object.assign(form, defaultClientForm())
  nextTick(() => formRef.value?.clearValidate())
}

const handleDialogClose = () => {
  pauseDraft()
  resetForm()
}

const handleAddSub = () => {
  handleAddSubForParent(form)
}

const handleAddSubForParent = (parent) => {
  if (!parent?.id) {
    ElMessage.warning('请先保存客户，再新增子客户')
    return
  }
  subDialogTitle.value = '新增子客户'
  resetSubForm()
  subForm.parent_client_id = parent.id
  subForm.customer_type = '企业客户'
  subForm.client_manager = ''
  subForm.contact_names = []
  subForm.contact_people = []
  subForm.manager_contact = ''
  subForm.client_status = parent.client_status || 'pending'
  subDialogVisible.value = true
}

const handleEditSub = (subRow, parentRow = null) => {
  subDialogTitle.value = '编辑子客户'
  resetSubForm()
  Object.assign(subForm, { ...subRow, contact_names: subRow.contact_names?.length ? [...subRow.contact_names] : subRow.client_manager ? [subRow.client_manager] : [], cooperation_start_date: businessDateTimeInputValue(subRow.cooperation_start_date||'') })
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
        const submitData = { ...subForm, client_manager: subForm.contact_names[0]?.trim() || '', contact_people: peopleFor(subForm), manager_contact: peopleFor(subForm)[0]?.contact_method || '' }
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
        delete detailCache[subForm.parent_client_id]
        await refreshAfterSave(async () => {
          if (form.id) {
            const res = await clientApi.getClient(form.id)
            form.sub_clients = res.sub_clients || []
          }
          await fetchData()
        })
      } catch (error) {
    await subFormRef.value?.applyServerErrors(error)
        ElMessage.error(error.detail || '操作失败')
      } finally {
        subSubmitLoading.value = false
      }
    }
  })
}

const resetSubForm = () => {
  clearSubClientFieldSearch()
  subFormRef.value?.resetFields()
  Object.assign(subForm, {
    customer_type: null,
    id: null,
    parent_client_id: null,
    sub_client_code: '',
    client_name: '',
    client_short_name: '',
    client_manager: '',
  contact_names: [],
  contact_people: [],
    manager_contact: '',
    english_name: '',
    english_short_name: '',
    field_level1: '',
    field_level2: '',
    country: '',
    province: '',
    city: '',
    district: '',
  full_address: '',
  detailed_address: '',
    cooperation_start_date: '',
    remarks: '',
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
.cooperation-editor label { display: block; margin-bottom: 12px; color: var(--el-text-color-regular); }
.client-editor-tabs > :deep(.el-tabs__header) { position: sticky; top: -20px; z-index: 2; padding-top: 4px; background: var(--el-bg-color); }

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
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

:global(.client-form-dialog) {
  display: flex;
  max-width: calc(100vw - 32px) !important;
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

:global(.sub-client-editor-dialog) {
  display: flex;
  max-height: 90vh;
  flex-direction: column;
  overflow: hidden;
}

:global(.sub-client-editor-dialog .el-dialog__header),
:global(.sub-client-editor-dialog .el-dialog__footer) { flex: none; }
:global(.sub-client-editor-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.sub-client-editor-dialog .el-dialog__footer) {
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

<style scoped>
.sub-client-section + .sub-client-section{border-top:1px solid var(--el-border-color-lighter);padding-top:16px;margin-top:4px}.sub-client-section h4{margin:0 0 16px;color:var(--el-text-color-primary)}
</style>
