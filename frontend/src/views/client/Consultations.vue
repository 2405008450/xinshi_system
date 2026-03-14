<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>新咨询管理</span>
        <el-button type="primary" @click="handleAdd">新增咨询</el-button>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="咨询编号">
        <el-input v-model="searchForm.consultation_code" placeholder="输入编号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="客户名称">
        <el-input v-model="searchForm.client_name" placeholder="输入名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="咨询状态">
        <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
          <el-option label="跟进中" value="following" />
          <el-option label="重点跟进" value="emphasis" />
          <el-option label="未成交" value="failed" />
          <el-option label="已成交" value="success" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="consultation_code" label="咨询编号" width="160" />
      <el-table-column prop="status" label="咨询状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
             {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
      <el-table-column prop="consultation_time" label="咨询时间" width="180">
        <template #default="{ row }">{{ formatDatetime(row.consultation_time) }}</template>
      </el-table-column>
      <el-table-column prop="client_source" label="客户来源" width="120" />
      <el-table-column prop="source_keyword" label="来源关键词" width="150" />
      <el-table-column prop="consultation_method" label="咨询方式" width="120" />
      <el-table-column prop="consultation_type" label="咨询类型" width="120" />

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
                <el-descriptions-item label="ID" :span="2">
                  <span class="detail-value">{{ getDetailRow(row).id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="咨询编号">
                  <span class="detail-value">{{ getDetailRow(row).consultation_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户ID">
                  <span class="detail-value">{{ getDetailRow(row).client_id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ getDetailRow(row).client_code || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户名称">
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
                  <span class="detail-value">{{ getDetailRow(row).consultation_method || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户来源">
                  <span class="detail-value">{{ getDetailRow(row).client_source || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="来源关键词">
                  <span class="detail-value">{{ getDetailRow(row).source_keyword || '-' }}</span>
                </el-descriptions-item>

                <el-descriptions-item label="咨询类型">
                  <span class="detail-value">{{ getDetailRow(row).consultation_type || '-' }}</span>
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
                <el-descriptions-item label="跟进次数">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_count ?? 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进时间">
                  <span class="detail-value">{{ formatDatetime(getDetailRow(row).follow_up_time) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进状态">
                  <span class="detail-value">{{ getDetailRow(row).follow_up_status || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="跟进人">
                  <span class="detail-value">{{ getUserName(getDetailRow(row).follow_up_person_id) }}</span>
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

      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="fetchData"
      @current-change="fetchData"
      style="margin-top: 20px"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户名称" prop="client_name">
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
            <el-form-item label="客户简称" prop="client_short_name">
              <el-input
                v-model="form.client_short_name"
                :disabled="!!form.client_id"
                :placeholder="!form.client_id && form.client_name ? '新客户请填写简称（必填）' : ''"
              />
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
                <el-option label="跟进中" value="following" />
                <el-option label="重点跟进" value="emphasis" />
                <el-option label="未成交" value="failed" />
                <el-option label="已成交" value="success" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="咨询类型" prop="consultation_type">
              <el-select v-model="form.consultation_type" placeholder="请选择" style="width: 100%">
                <el-option label="笔译" value="translation" />
                <el-option label="口译" value="interpretation" />
                <el-option label="设备租赁" value="equipment_rental" />
                <el-option label="招聘" value="recruitment" />
                <el-option label="其他" value="other" />
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
              <el-select v-model="form.consultation_method" placeholder="请选择" style="width: 100%">
                <el-option label="电话" value="phone" />
                <el-option label="邮件" value="email" />
                <el-option label="在线咨询" value="online" />
                <el-option label="上门" value="onsite" />
                <el-option label="其他" value="other" />
              </el-select>
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
            <el-form-item label="跟进状态" prop="follow_up_status">
              <el-input v-model="form.follow_up_status" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
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

        <el-form-item label="咨询描述" prop="consultation_description">
          <el-input v-model="form.consultation_description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="跟进备注" prop="follow_up_remarks">
          <el-input v-model="form.follow_up_remarks" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 创建翻译项目弹窗 -->
    <el-dialog
      v-model="createProjectDialogVisible"
      title="🎉 咨询已成交 — 创建翻译项目"
      width="500px"
      :close-on-click-modal="false"
      @close="createProjectForm.projectName = ''"
    >
      <p style="color: #606266; margin-bottom: 16px;">该咨询已标记为"已成交"，请输入翻译项目名称以自动建单：</p>
      <el-form :model="createProjectForm" ref="createProjectFormRef" @submit.prevent>
        <el-form-item
          label="项目名称"
          prop="projectName"
          :rules="[{ required: true, message: '请输入项目名称', trigger: 'blur' }]"
        >
          <el-input
            v-model="createProjectForm.projectName"
            placeholder="请输入翻译项目名称"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createProjectDialogVisible = false">跳过</el-button>
        <el-button
          type="primary"
          :loading="createProjectLoading"
          @click="handleCreateProject"
        >确认建单</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as consultationApi from '@/api/consultations'
import * as clientApi from '@/api/clients'
import * as userApi from '@/api/users'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增咨询')
const formRef = ref(null)
const userOptions = ref([])
const detailCache = reactive({})
const detailLoadingId = ref(null)
const clientSearchLoading = ref(false)

// 创建翻译项目弹窗
const createProjectDialogVisible = ref(false)
const createProjectLoading = ref(false)
const createProjectConsultationId = ref(null)
const createProjectFormRef = ref(null)
const createProjectForm = reactive({ projectName: '' })

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
})

const searchForm = reactive({
  consultation_code: '',
  client_name: '',
  status: '',
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const resetSearch = () => {
  searchForm.consultation_code = ''
  searchForm.client_name = ''
  searchForm.status = ''
  handleSearch()
}

const defaultForm = () => ({
  id: null,
  client_id: null,
  client_code: '',
  client_name: '',
  client_short_name: '',
  consultation_time: '',
  consultation_method: '',
  client_source: '',
  source_keyword: '',
  consultation_description: '',
  status: 'following',
  consultation_type: '',
  handling_method: '',
  remarks: '',
  customer_service_id: null,
  sales_person_id: null,
  editor_id: null,
  follow_up_count: 0,
  follow_up_time: '',
  follow_up_status: '',
  follow_up_remarks: '',
  follow_up_person_id: null,
})

const form = reactive(defaultForm())

// 是否为新客户：没有关联的 client_id 但已填写客户名称
const isNewClient = computed(() => !form.client_id && !!form.client_name)

const rules = {
  client_name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
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
    success: '已成交',
  }
  return statusMap[status] || status || '-'
}

const formatDatetime = (val) => {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { hour12: false })
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

// 用户从下拉列表选中了已有客户
const handleExistingClientSelect = (item) => {
  form.client_id = item.id
  form.client_name = item.client_name
  form.client_code = item.client_code || ''
  form.client_short_name = item.client_short_name || ''
}

// 用户手动输入（重新输入时清空已关联的客户）
const handleClientNameInput = () => {
  form.client_id = null
  form.client_code = ''
  form.client_short_name = ''
}

// 用户点击清空按钮
const handleClientNameClear = () => {
  form.client_id = null
  form.client_name = ''
  form.client_code = ''
  form.client_short_name = ''
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

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (searchForm.consultation_code) params.consultation_code = searchForm.consultation_code
    if (searchForm.client_name) params.client_name = searchForm.client_name
    if (searchForm.status) params.status = searchForm.status

    const [res, countRes] = await Promise.all([
      consultationApi.getConsultations(params),
      consultationApi.getConsultationCount({
        consultation_code: params.consultation_code,
        client_name: params.client_name,
        status: params.status,
      })
    ])
    tableData.value = Array.isArray(res) ? res : []
    pagination.total = countRes?.total || tableData.value.length
  } catch {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const toNullable = (v) => (v === '' ? null : v)

const buildPayload = () => ({
  client_id: form.client_id,
  consultation_time: toNullable(form.consultation_time),
  consultation_method: toNullable(form.consultation_method),
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
  resetForm()
  dialogVisible.value = true
}

const fillFormByRow = (row) => {
  Object.assign(form, {
    id: row.id,
    client_id: row.client_id || null,
    client_code: row.client_code || '',
    client_name: row.client_name || '',
    client_short_name: row.client_short_name || '',
    consultation_time: row.consultation_time || '',
    consultation_method: row.consultation_method || '',
    client_source: row.client_source || '',
    source_keyword: row.source_keyword || '',
    consultation_description: row.consultation_description || '',
    status: row.status || 'following',
    consultation_type: row.consultation_type || '',
    handling_method: row.handling_method || '',
    remarks: row.remarks || '',
    customer_service_id: row.customer_service_id || null,
    sales_person_id: row.sales_person_id || null,
    editor_id: row.editor_id || null,
    follow_up_count: row.follow_up_count ?? 0,
    follow_up_time: row.follow_up_time || '',
    follow_up_status: row.follow_up_status || '',
    follow_up_remarks: row.follow_up_remarks || '',
    follow_up_person_id: row.follow_up_person_id || null,
  })
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑咨询'
  try {
    const detail = await consultationApi.getConsultation(row.id)
    detailCache[row.id] = detail
    fillFormByRow(detail)
  } catch {
    fillFormByRow(row)
  }
  dialogVisible.value = true
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

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      // 新客户：先在客户表创建记录，获取自动生成的客户编号和 ID
      if (isNewClient.value) {
        const newClient = await clientApi.createClient({
          client_name: form.client_name,
          client_short_name: form.client_short_name,
        })
        form.client_id = newClient.id
        form.client_code = newClient.client_code
      }

      const payload = buildPayload()
      const isUpdate = !!form.id
      // 记录提交前咨询的旧状态（用于判断是否首次变为已成交）
      const prevStatus = isUpdate
        ? (detailCache[form.id]?.status ?? tableData.value.find((r) => r.id === form.id)?.status)
        : null
      const consultationId = form.id

      if (isUpdate) {
        await consultationApi.updateConsultation(consultationId, payload)
        ElMessage.success('更新成功')
      } else {
        const created = await consultationApi.createConsultation(payload)
        ElMessage.success('创建成功')
        // 新建咨询也支持立即成交触发建项目弹窗
        if (payload.status === 'success' && created?.id) {
          createProjectConsultationId.value = created.id
          createProjectForm.projectName = ''
          createProjectDialogVisible.value = true
        }
      }
      dialogVisible.value = false
      fetchData()

      // 若编辑时将状态改为「已成交」，则弹窗提示用户创建翻译项目
      if (isUpdate && payload.status === 'success' && prevStatus !== 'success') {
        createProjectConsultationId.value = consultationId
        createProjectForm.projectName = ''
        createProjectDialogVisible.value = true
      }
    } catch (error) {
      ElMessage.error(error?.response?.data?.detail || error?.detail || '操作失败')
    }
  })
}

const handleCreateProject = async () => {
  if (!createProjectFormRef.value) return
  const valid = await createProjectFormRef.value.validate().catch(() => false)
  if (!valid) return
  createProjectLoading.value = true
  try {
    const project = await consultationApi.createProjectFromConsultation(
      createProjectConsultationId.value,
      createProjectForm.projectName
    )
    ElMessage.success('\u9879\u76EE\u5DF2\u521B\u5EFA\uFF0C\u6B63\u5728\u8FDB\u5165\u6D41\u7A0B\u9875\u9762')
    createProjectDialogVisible.value = false
    createProjectConsultationId.value = null
    createProjectForm.projectName = ''
    if (project?.id) {
      router.push({ path: '/translation', query: { projectId: project.id } })
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '\u521B\u5EFA\u9879\u76EE\u5931\u8D25')
  } finally {
    createProjectLoading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, defaultForm())
  formRef.value?.resetFields()
}

onMounted(async () => {
  await loadUsers()
  await fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 15px;
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
</style>
