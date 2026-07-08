<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目详情</span>
        <el-button type="primary" @click="handleAdd">新增项目详情</el-button>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="项目名称">
        <el-input v-model="searchForm.projectName" placeholder="请输入项目名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="订单号">
        <el-input v-model="searchForm.orderNo" placeholder="请输入订单号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="客户简称">
        <el-input v-model="searchForm.clientShortName" placeholder="请输入客户简称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.projectStatus" placeholder="请选择状态" clearable style="width: 160px" @change="handleSearch">
          <el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" row-key="id" border :row-class-name="getProjectRowClassName">
      <el-table-column type="expand" width="48">
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
              <el-table-column prop="languagePair" label="语言" min-width="120" />
              <el-table-column prop="wordCount" label="字数" min-width="100" />
              <el-table-column prop="status" label="状态" min-width="120">
                <template #default="{ row: subRow }">
                  <el-tag :type="getStatusType(subRow.status)">{{ getStatusLabel(subRow.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="详情" width="100">
                <template #default="{ row: subRow }">
                  <DetailPopover :row="subRow" title="子订单详情" :items="subOrderDetailItems" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row: subRow }">
                  <el-button type="primary" size="small" link @click="openProjectEditorForSubOrder(row, subRow)">编辑</el-button>
                  <el-button type="danger" size="small" link @click="handleDeleteSubOrder(subRow)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="orderNo" label="订单号" min-width="170" />
      <el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="clientShortName" label="客户简称" min-width="140" />
      <el-table-column prop="projectStatus" label="状态" min-width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.projectStatus)">{{ getStatusLabel(row.projectStatus) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="customerDeadlineTime" label="客户交稿时间" min-width="170" />
      <el-table-column label="详情" width="100">
        <template #default="{ row }">
          <DetailPopover :row="row" title="项目详情" :items="projectDetailItems" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDeleteProject(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1160px" top="4vh" @closed="onProjectDialogClosed">
      <div class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
          <el-tabs v-model="projectDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="项目名称" prop="projectName"><el-input v-model="form.projectName" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户简称"><el-input v-model="form.clientShortName" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户编号"><el-input v-model="form.clientCode" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><el-input v-model="form.languagePair" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态" prop="projectStatus"><el-select v-model="form.projectStatus" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="字数"><el-input-number v-model="form.wordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户反馈"><el-input v-model="form.clientFeedback" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户接单时间"><el-date-picker v-model="form.customerReceptionTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="PM确认人 ID"><el-input v-model="form.pmConfirmedBy" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="分配与预估" name="assignment">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="译员 ID"><el-input v-model="form.translatorId" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="译员分配时间"><el-date-picker v-model="form.translatorAssignmentTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="预计统计方式"><el-input v-model="form.expectedTranslatorStatsMethod" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="预计译员字数"><el-input-number v-model="form.expectedTranslatorWordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="网络文件路径"><el-input v-model="form.networkFilePath" type="textarea" :rows="3" placeholder="如需多个路径，可按行填写" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in progressFieldConfigs" :key="item.key" class="progress-card">
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
                    <el-button type="primary" @click="openCreateSubOrderDialog">新增子订单</el-button>
                    <el-button @click="openBatchDialog">批量新增子订单</el-button>
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
                  <el-table-column prop="languagePair" label="语言" min-width="120" />
                  <el-table-column prop="wordCount" label="字数" min-width="100" />
                  <el-table-column prop="status" label="状态" min-width="120">
                    <template #default="{ row }">
                      <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="详情" width="100">
                    <template #default="{ row }">
                      <DetailPopover :row="row" title="子订单详情" :items="subOrderDetailItems" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="180" fixed="right">
                    <template #default="{ row }">
                      <el-button type="primary" size="small" link @click="handleEditSubOrder(row)">编辑</el-button>
                      <el-button type="danger" size="small" link @click="handleDeleteSubOrder(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
              <el-alert v-else title="请先保存母订单，再在此 Tab 中新增或批量新增子订单。" type="info" :closable="false" show-icon />
            </el-tab-pane>
          </el-tabs>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
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
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><el-input v-model="subOrderForm.languagePair" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="subOrderForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="字数"><el-input-number v-model="subOrderForm.wordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
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
                  <el-col :xs="24" :md="12"><el-form-item label="译员 ID"><el-input v-model="subOrderForm.translatorId" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="译员分配时间"><el-date-picker v-model="subOrderForm.translatorAssignmentTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="预计统计方式"><el-input v-model="subOrderForm.expectedTranslatorStatsMethod" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="预计译员字数"><el-input-number v-model="subOrderForm.expectedTranslatorWordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="网络文件路径"><el-input v-model="subOrderForm.networkFilePath" type="textarea" :rows="3" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in progressFieldConfigs" :key="item.key" class="progress-card">
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
          <el-col :span="12"><el-form-item label="翻译方向"><el-input v-model="batchForm.languagePair" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="字数"><el-input-number v-model="batchForm.wordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="batchForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="batchForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="batchForm.translatorId" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="预计统计方式"><el-input v-model="batchForm.expectedTranslatorStatsMethod" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="预计译员字数"><el-input-number v-model="batchForm.expectedTranslatorWordCount" :min="0" style="width: 100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchCreateSubOrders">批量创建</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { defineComponent, h, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox, ElPopover, ElTag } from 'element-plus'
import { getProjects, getProjectCount, createProject, updateProject, deleteProject, getNextOrderNo } from '@/api/projects'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'

const SUB_ORDER_PREVIEW_LIMIT = 10
const router = useRouter()
const projectDialogTab = ref('basic')
const subOrderDialogTab = ref('basic')
const projectStatusOptions = [
  { label: '待启动', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '已暂停', value: 'paused' },
  { label: '已终止', value: 'terminated' }
]
const priorityOptions = ['低', '中', '高', '紧急']
const progressFieldConfigs = [
  { key: 'translatorDeliveryProgress', label: '译员交付进度' },
  { key: 'preReviewQcProgress', label: '审校前 QC' },
  { key: 'review1Progress', label: '审校 1' },
  { key: 'review2Progress', label: '审校 2' },
  { key: 'postReviewQcProgress', label: '审校后 QC' },
  { key: 'layoutProgress', label: '排版进度' },
  { key: 'consolidationProgress', label: '整合进度' }
]
const progressFieldSet = new Set(progressFieldConfigs.map((item) => item.key))
const progressMarks = { 0: '0%', 50: '50%', 100: '100%' }
const projectDetailItems = [
  { label: 'ID', key: 'id', span: 2 },
  { label: '订单号', key: 'orderNo' },
  { label: '项目名称', key: 'projectName' },
  { label: '客户简称', key: 'clientShortName' },
  { label: '客户编号', key: 'clientCode' },
  { label: '状态', key: 'projectStatus', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数', key: 'wordCount' },
  { label: '客户接单时间', key: 'customerReceptionTime' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '译员ID', key: 'translatorId' },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '预计统计方式', key: 'expectedTranslatorStatsMethod' },
  { label: '预计译员字数', key: 'expectedTranslatorWordCount' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前QC', key: 'preReviewQcProgress' },
  { label: '审校1', key: 'review1Progress' },
  { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const subOrderDetailItems = [
  { label: 'ID', key: 'id', span: 2 },
  { label: '母订单ID', key: 'parentProjectId', span: 2 },
  { label: '子订单号', key: 'subOrderNo' },
  { label: '子项目名称', key: 'subProjectName' },
  { label: '状态', key: 'status', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数', key: 'wordCount' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '译员ID', key: 'translatorId' },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '预计统计方式', key: 'expectedTranslatorStatsMethod' },
  { label: '预计译员字数', key: 'expectedTranslatorWordCount' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前QC', key: 'preReviewQcProgress' },
  { label: '审校1', key: 'review1Progress' },
  { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '备注', key: 'remarks', span: 2 },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const createEmptyProjectForm = () => ({ id: '', orderNo: '', projectName: '', clientShortName: '', clientCode: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCount: 0, projectStatus: 'pending', customerReceptionTime: '', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', pmConfirmedBy: '', translatorId: '', translatorAssignmentTime: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, translatorDeliveryProgress: 0, preReviewQcProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '' })
const createEmptySubOrderForm = () => ({ id: '', parentProjectId: '', subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCount: 0, customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorAssignmentTime: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, status: 'pending', translatorDeliveryProgress: 0, preReviewQcProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '', remarks: '' })
const createBatchForm = () => ({ count: 1, startIndex: 1, subProjectNamePrefix: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCount: 0, customerDeadlineTime: '', sentToClientTime: '', translatorId: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, status: 'pending' })
const loading = ref(false)
const dialogVisible = ref(false)
const subOrderDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const dialogTitle = ref('新增项目详情')
const subOrderDialogTitle = ref('新增子订单')
const formRef = ref(null)
const subOrderFormRef = ref(null)
const batchFormRef = ref(null)
const tableData = ref([])
const currentProjectSubOrders = ref([])
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const searchForm = reactive({ projectName: '', orderNo: '', clientShortName: '', projectStatus: '' })
const form = reactive(createEmptyProjectForm())
const subOrderForm = reactive(createEmptySubOrderForm())
const batchForm = reactive(createBatchForm())
const rules = { projectName: [{ required: true, message: '请输入项目名称', trigger: 'blur' }], projectStatus: [{ required: true, message: '请选择状态', trigger: 'change' }] }
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const batchRules = { count: [{ required: true, message: '请输入生成数量', trigger: 'change' }] }
const NULLABLE_FIELDS = ['customerReceptionTime', 'customerDeadlineTime', 'sentToClientTime', 'pmConfirmedBy', 'translatorId', 'translatorAssignmentTime', 'expectedTranslatorStatsMethod', 'clientFeedback', 'networkFilePath', 'fileTypeSecondary', 'languagePair', 'priority', 'remarks', 'subProjectName']
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === status)?.label || status || '-'
const getStatusType = (status) => ({ pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger', terminated: 'info' }[status] || 'info')
const displayValue = (value) => (value === null || value === undefined || value === '' ? '-' : value)
const pad = (value) => String(value).padStart(2, '0')
const clampProgress = (value) => Math.max(0, Math.min(100, Number(value) || 0))
const parseProgressValue = (value) => {
  if (value === null || value === undefined || value === '') return 0
  if (typeof value === 'number') return clampProgress(value)
  const matched = String(value).match(/-?\d+/)
  return clampProgress(matched ? Number(matched[0]) : 0)
}
const normalizeProgressValue = (value) => `${clampProgress(value)}%`
const formatProgressDisplay = (value) => `${clampProgress(value)}%`
const normalizeProject = (project) => ({ ...project, subOrders: Array.isArray(project.subOrders) ? [...project.subOrders].sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : [] })
const getSubOrderCount = (row) => Array.isArray(row?.subOrders) ? row.subOrders.length : 0
const hasMoreSubOrders = (row) => getSubOrderCount(row) > SUB_ORDER_PREVIEW_LIMIT
const getVisibleSubOrders = (row) => (Array.isArray(row?.subOrders) ? row.subOrders.slice(0, SUB_ORDER_PREVIEW_LIMIT) : [])
const applyPagination = () => { fetchData() }
const cleanPayload = (payload) => {
  const result = { ...payload }
  NULLABLE_FIELDS.forEach((key) => {
    if (result[key] === '') result[key] = null
  })
  progressFieldConfigs.forEach(({ key }) => {
    result[key] = normalizeProgressValue(result[key])
  })
  if (result.wordCount === null || result.wordCount === undefined) result.wordCount = 0
  if (result.expectedTranslatorWordCount === null || result.expectedTranslatorWordCount === undefined) {
    result.expectedTranslatorWordCount = 0
  }
  return result
}
const assignReactive = (target, defaultsFactory, values = {}) => {
  const defaults = defaultsFactory()
  Object.keys(defaults).forEach((key) => {
    if (progressFieldSet.has(key)) {
      target[key] = parseProgressValue(values[key] ?? defaults[key])
    } else {
      target[key] = values[key] ?? defaults[key]
    }
  })
}
const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      project_name: searchForm.projectName || undefined,
      order_no: searchForm.orderNo || undefined,
      client_short_name: searchForm.clientShortName || undefined,
      project_status: searchForm.projectStatus || undefined
    }
    const [response, countResponse] = await Promise.all([
      getProjects(params),
      getProjectCount({
        project_name: params.project_name,
        order_no: params.order_no,
        client_short_name: params.client_short_name,
        project_status: params.project_status
      })
    ])
    tableData.value = (Array.isArray(response) ? response : []).map(normalizeProject)
    pagination.total = countResponse?.total || tableData.value.length
  } catch (error) {
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || error.message || 'Failed to load projects')
  } finally {
    loading.value = false
  }
}
const refreshProjectSubOrders = async (projectId) => {
  if (!projectId) return
  const response = await getSubOrdersByProject(projectId)
  const normalized = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
  currentProjectSubOrders.value = normalized
  tableData.value = tableData.value.map((item) => item.id === projectId ? { ...item, subOrders: normalized } : item)
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const resetSearch = () => { searchForm.projectName = ''; searchForm.orderNo = ''; searchForm.clientShortName = ''; searchForm.projectStatus = ''; handleSearch() }
const resetProjectForm = () => { assignReactive(form, createEmptyProjectForm); projectDialogTab.value = 'basic' }
const resetSubOrderForm = () => { assignReactive(subOrderForm, createEmptySubOrderForm); subOrderFormRef.value?.clearValidate(); subOrderDialogTab.value = 'basic' }
const resetBatchForm = () => { Object.assign(batchForm, createBatchForm()); batchFormRef.value?.clearValidate() }
const generateOrderNo = async () => { try { return await getNextOrderNo() } catch { const now = new Date(); return `TP-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${String(Math.floor(Math.random() * 9999)).padStart(4, '0')}` } }
const goToSubOrderManagement = (project) => {
  const projectId = project.id || form.id
  if (!projectId) return
  router.push({ name: 'TranslationSubOrderManagement', params: { projectId }, query: { orderNo: project.orderNo || form.orderNo || '', projectName: project.projectName || form.projectName || '' } })
}
const handleAdd = async () => { dialogTitle.value = '新增项目详情'; resetProjectForm(); currentProjectSubOrders.value = []; form.orderNo = await generateOrderNo(); dialogVisible.value = true }
const handleEdit = async (row) => { dialogTitle.value = '编辑项目详情'; assignReactive(form, createEmptyProjectForm, row); currentProjectSubOrders.value = Array.isArray(row.subOrders) ? [...row.subOrders] : []; projectDialogTab.value = 'basic'; dialogVisible.value = true; if (row.id) { try { await refreshProjectSubOrders(row.id) } catch (error) { ElMessage.error(error.detail || error.message || '加载子订单失败') } } }
const handleDeleteProject = async (row) => { try { await ElMessageBox.confirm(`确认删除母订单 ${row.orderNo} 吗？`, '提示', { type: 'warning' }); await deleteProject(row.id); ElMessage.success('删除成功'); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '删除失败') } }
const handleSubmit = async () => { if (!formRef.value) return; const valid = await formRef.value.validate().catch(() => false); if (!valid) return; try { const payload = cleanPayload({ ...form }); if (dialogTitle.value === '新增项目详情') { await createProject(payload); ElMessage.success('创建成功') } else { await updateProject(payload.id, payload); ElMessage.success('更新成功') } dialogVisible.value = false; await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '保存失败') } }
const onProjectDialogClosed = () => { resetProjectForm(); resetSubOrderForm(); resetBatchForm(); currentProjectSubOrders.value = [] }
const createSubOrderDefaultsFromProject = () => ({ fileTypeSecondary: form.fileTypeSecondary, languagePair: form.languagePair, priority: form.priority, wordCount: form.wordCount, customerDeadlineTime: form.customerDeadlineTime, sentToClientTime: form.sentToClientTime, translatorId: form.translatorId, translatorAssignmentTime: form.translatorAssignmentTime, expectedTranslatorStatsMethod: form.expectedTranslatorStatsMethod, expectedTranslatorWordCount: form.expectedTranslatorWordCount, status: form.projectStatus || 'pending', translatorDeliveryProgress: form.translatorDeliveryProgress, preReviewQcProgress: form.preReviewQcProgress, review1Progress: form.review1Progress, review2Progress: form.review2Progress, postReviewQcProgress: form.postReviewQcProgress, layoutProgress: form.layoutProgress, consolidationProgress: form.consolidationProgress, networkFilePath: form.networkFilePath, clientFeedback: form.clientFeedback })
const openCreateSubOrderDialog = () => { resetSubOrderForm(); subOrderDialogTitle.value = '新增子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...createSubOrderDefaultsFromProject(), parentProjectId: form.id }); subOrderDialogVisible.value = true }
const handleEditSubOrder = (row) => { resetSubOrderForm(); subOrderDialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...row, parentProjectId: row.parentProjectId || form.id }); subOrderDialogVisible.value = true }
const openProjectEditorForSubOrder = async (projectRow, subOrderRow) => { await handleEdit(projectRow); await nextTick(); handleEditSubOrder(subOrderRow) }
const buildSubOrderPayload = (source) => cleanPayload({ parentProjectId: form.id, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCount: source.wordCount ?? 0, customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', expectedTranslatorStatsMethod: source.expectedTranslatorStatsMethod || '', expectedTranslatorWordCount: source.expectedTranslatorWordCount ?? 0, status: source.status || 'pending', translatorDeliveryProgress: source.translatorDeliveryProgress ?? 0, preReviewQcProgress: source.preReviewQcProgress ?? 0, review1Progress: source.review1Progress ?? 0, review2Progress: source.review2Progress ?? 0, postReviewQcProgress: source.postReviewQcProgress ?? 0, layoutProgress: source.layoutProgress ?? 0, consolidationProgress: source.consolidationProgress ?? 0, networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
const handleSubmitSubOrder = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildSubOrderPayload(subOrderForm); if (subOrderDialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } subOrderDialogVisible.value = false; await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '子订单保存失败') } }
const handleDeleteSubOrder = async (row) => { try { await ElMessageBox.confirm(`确认删除子订单 ${row.subOrderNo} 吗？`, '提示', { type: 'warning' }); await deleteSubOrder(row.id); ElMessage.success('子订单删除成功'); if (form.id && row.parentProjectId === form.id) await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '子订单删除失败') } }
const openBatchDialog = () => { resetBatchForm(); Object.assign(batchForm, { ...createBatchForm(), ...createSubOrderDefaultsFromProject(), subProjectNamePrefix: form.projectName ? `${form.projectName}-子订单` : '' }); batchDialogVisible.value = true }
const createBatchSubProjectName = (index) => { const prefix = batchForm.subProjectNamePrefix || (form.projectName ? `${form.projectName}-子订单` : '子订单'); return `${prefix}${String(index).padStart(2, '0')}` }
const handleBatchCreateSubOrders = async () => { if (!batchFormRef.value) return; const valid = await batchFormRef.value.validate().catch(() => false); if (!valid) return; try { for (let offset = 0; offset < batchForm.count; offset += 1) { const sequence = batchForm.startIndex + offset; const payload = buildSubOrderPayload({ ...batchForm, subProjectName: createBatchSubProjectName(sequence), remarks: '' }); await createSubOrder(payload) } batchDialogVisible.value = false; ElMessage.success(`已批量创建 ${batchForm.count} 条子订单`); await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '批量新增失败') } }
const getProjectRowClassName = ({ row }) => (getSubOrderCount(row) ? '' : 'no-expand-row')
const DetailPopover = defineComponent({ name: 'DetailPopover', props: { row: { type: Object, required: true }, title: { type: String, default: '详情' }, items: { type: Array, default: () => [] } }, setup(props) { return () => h(ElPopover, { placement: 'left', width: 720, trigger: 'click', title: props.title }, { reference: () => h(ElButton, { type: 'info', size: 'small', link: true }, () => '查看详情'), default: () => h('div', { class: 'detail-popover' }, h(ElDescriptions, { column: 2, border: true }, () => props.items.map((item) => h(ElDescriptionsItem, { key: item.key, label: item.label, span: item.span || 1 }, () => item.type === 'status' ? h(ElTag, { type: getStatusType(props.row[item.key]) }, () => getStatusLabel(props.row[item.key])) : h('span', { class: 'detail-value' }, displayValue(props.row[item.key])))))) }) } })
onMounted(fetchData)
</script>

<style scoped>
.search-form { margin-bottom: 20px; }
.card-header,
.section-header,
.sub-order-panel__header { display: flex; align-items: center; justify-content: space-between; }
.sub-order-panel__meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.editor-body { max-height: 68vh; overflow-y: auto; padding-right: 4px; }
.editor-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.form-section { padding: 4px 2px 12px; }
.progress-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.progress-card { padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 10px; background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%); }
.progress-card__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-size: 14px; }
.section-title { margin: 12px 0; font-size: 15px; font-weight: 600; }
.section-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.sub-order-panel { padding: 12px 24px 20px; background: #fafafa; }
.sub-order-panel__header { margin-bottom: 12px; }
.sub-order-alert { margin-bottom: 12px; }
.detail-popover { max-height: 620px; overflow-y: auto; }
.detail-value { color: #606266; word-break: break-all; }
.el-alert { margin-top: 16px; }
:deep(.no-expand-row .el-table__expand-icon) { visibility: hidden; pointer-events: none; }
</style>

