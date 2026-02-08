<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目详情</span>
        <el-button type="primary" @click="handleAdd">新增项目详情</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="orderNo" label="订单号" width="160" />
      <el-table-column prop="projectName" label="项目名称" width="200" show-overflow-tooltip />
      <el-table-column prop="clientShortName" label="客户简称" width="140" />
      <el-table-column prop="projectStatus" label="项目状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.projectStatus)">
            {{ getStatusLabel(row.projectStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="customerDeadlineTime" label="客户交稿时" width="170" />
      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <el-popover
            placement="left"
            :width="700"
            trigger="click"
            title="项目详细信息"
          >
            <template #reference>
              <el-button type="info" size="small" link>
                <el-icon><View /></el-icon>
                查看详情
              </el-button>
            </template>
            <div class="detail-popover">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="ID" :span="2">
                  <span class="detail-value">{{ row.id || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="订单号">
                  <span class="detail-value">{{ row.orderNo || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="项目名称">
                  <span class="detail-value">{{ row.projectName || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户简称">
                  <span class="detail-value">{{ row.clientShortName || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户编号">
                  <span class="detail-value">{{ row.clientCode || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="项目状态">
                  <el-tag :type="getStatusType(row.projectStatus)" size="small">
                    {{ getStatusLabel(row.projectStatus) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="客户接待时" :span="2">
                  <span class="detail-value">{{ row.customerReceptionTime || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户交稿时" :span="2">
                  <span class="detail-value">{{ row.customerDeadlineTime || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="译员合作形式">
                  <span class="detail-value">{{ row.translatorCooperationType || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="译员安排">
                  <span class="detail-value">{{ row.translatorAssignee || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="译员安排时间" :span="2">
                  <span class="detail-value">{{ row.translatorAssignmentTime || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="译员交稿进度">
                  <span class="detail-value">{{ row.translatorDeliveryProgress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="审核1进度">
                  <span class="detail-value">{{ row.review1Progress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="审核前专检进度">
                  <span class="detail-value">{{ row.preReviewQcProgress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="排版进度">
                  <span class="detail-value">{{ row.layoutProgress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="整理进度">
                  <span class="detail-value">{{ row.consolidationProgress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="发客户时间" :span="2">
                  <span class="detail-value">{{ row.sentToClientTime || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="客户反馈" :span="2">
                  <span class="detail-value">{{ row.clientFeedback || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="审核后专检进度">
                  <span class="detail-value">{{ row.postReviewQcProgress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="审核2进度">
                  <span class="detail-value">{{ row.review2Progress || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="预定译员统计方式">
                  <span class="detail-value">{{ row.reservedTranslatorStatMethod || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="预定译员字数">
                  <span class="detail-value">{{ row.reservedTranslatorWordCount || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="文件类型二级">
                  <span class="detail-value">{{ row.fileTypeSecondary || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="大项目经理确认">
                  <span class="detail-value">{{ row.leadPmId || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间" :span="2">
                  <span class="detail-value">{{ row.createdAt || '-' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="更新时间" :span="2">
                  <span class="detail-value">{{ row.updatedAt || '-' }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
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
      width="980px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="140px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="ID" prop="id">
              <el-input v-model="form.id" placeholder="自动生成UUID" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="订单号" prop="orderNo">
              <el-input v-model="form.orderNo" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目名称" prop="projectName">
              <el-input v-model="form.projectName" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户简称" prop="clientShortName">
              <el-input v-model="form.clientShortName" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户编号" prop="clientCode">
              <el-input v-model="form.clientCode" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目状态" prop="projectStatus">
              <el-select v-model="form.projectStatus" placeholder="请选择" style="width: 100%">
                <el-option label="待启动" value="pending" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
                <el-option label="已暂停" value="paused" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户接待时" prop="customerReceptionTime">
              <el-date-picker
                v-model="form.customerReceptionTime"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户交稿时" prop="customerDeadlineTime">
              <el-date-picker
                v-model="form.customerDeadlineTime"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="译员合作形式" prop="translatorCooperationType">
              <el-input v-model="form.translatorCooperationType" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="译员安排" prop="translatorAssignee">
              <el-input v-model="form.translatorAssignee" placeholder="姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="译员安排时间" prop="translatorAssignmentTime">
              <el-date-picker
                v-model="form.translatorAssignmentTime"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="译员交稿进度" prop="translatorDeliveryProgress">
              <el-input v-model="form.translatorDeliveryProgress" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="审核1进度" prop="review1Progress">
              <el-input v-model="form.review1Progress" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="审核前专检进度" prop="preReviewQcProgress">
              <el-input v-model="form.preReviewQcProgress" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="排版进度" prop="layoutProgress">
              <el-input v-model="form.layoutProgress" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="整理进度" prop="consolidationProgress">
              <el-input v-model="form.consolidationProgress" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="发客户时间" prop="sentToClientTime">
              <el-date-picker
                v-model="form.sentToClientTime"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户反馈" prop="clientFeedback">
              <el-input v-model="form.clientFeedback" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="审核后专检进度" prop="postReviewQcProgress">
              <el-input v-model="form.postReviewQcProgress" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="审核2进度" prop="review2Progress">
              <el-input v-model="form.review2Progress" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预定译员统计方式" prop="reservedTranslatorStatMethod">
              <el-input v-model="form.reservedTranslatorStatMethod" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预定译员字数" prop="reservedTranslatorWordCount">
              <el-input-number v-model="form.reservedTranslatorWordCount" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="文件类型二级" prop="fileTypeSecondary">
              <el-input v-model="form.fileTypeSecondary" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="大项目经理确认" prop="leadPmId">
              <el-input v-model="form.leadPmId" placeholder="用户ID" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="更新时间" prop="updatedAt">
              <el-date-picker
                v-model="form.updatedAt"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="创建时间" prop="createdAt">
              <el-date-picker
                v-model="form.createdAt"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
                value-format="YYYY-MM-DD HH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import { getProjects, createProject, updateProject, deleteProject } from '@/api/projects'
import { isMockEnabled } from '@/mock'
import { mockApi } from '@/mock'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增项目详情')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: '',
  orderNo: '',
  projectName: '',
  clientShortName: '',
  clientCode: '',
  projectStatus: '',
  customerReceptionTime: '',
  customerDeadlineTime: '',
  translatorCooperationType: '',
  translatorAssignee: '',
  translatorAssignmentTime: '',
  translatorDeliveryProgress: '',
  review1Progress: '',
  preReviewQcProgress: '',
  layoutProgress: '',
  consolidationProgress: '',
  sentToClientTime: '',
  clientFeedback: '',
  postReviewQcProgress: '',
  review2Progress: '',
  reservedTranslatorStatMethod: '',
  reservedTranslatorWordCount: 0,
  fileTypeSecondary: '',
  leadPmId: '',
  updatedAt: '',
  createdAt: ''
})

const rules = {
  projectName: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  clientShortName: [{ required: true, message: '请输入客户简称', trigger: 'blur' }],
  clientCode: [{ required: true, message: '请输入客户编号', trigger: 'blur' }],
  projectStatus: [{ required: true, message: '请选择项目状态', trigger: 'change' }]
}

const pad = (value) => String(value).padStart(2, '0')
const getNowDateTime = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = pad(now.getMonth() + 1)
  const day = pad(now.getDate())
  const hour = pad(now.getHours())
  const minute = pad(now.getMinutes())
  const second = pad(now.getSeconds())
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

const generateOrderNo = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = pad(now.getMonth() + 1)
  const day = pad(now.getDate())
  const sequence = String(Math.floor(Math.random() * 10000)).padStart(4, '0')
  return `${year}${month}${day}${sequence}`
}

const generateUuid = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  const random = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
  return `${random()}${random()}-${random()}-${random()}-${random()}-${random()}${random()}${random()}`
}

const getStatusLabel = (status) => {
  const statusMap = {
    'pending': '待启动',
    'in_progress': '进行中',
    'completed': '已完成',
    'paused': '已暂停'
  }
  return statusMap[status] || status
}

const getStatusType = (status) => {
  const typeMap = {
    'pending': 'info',
    'in_progress': 'warning',
    'completed': 'success',
    'paused': 'danger'
  }
  return typeMap[status] || ''
}

const fetchData = async () => {
  loading.value = true
  try {
    if (isMockEnabled()) {
      const { getMockTranslationProjects } = await import('@/mock/data')
      const allProjects = getMockTranslationProjects()
      pagination.total = allProjects.length
      const skip = (pagination.page - 1) * pagination.limit
      const end = skip + pagination.limit
      tableData.value = allProjects.slice(skip, end)
    } else {
      const response = await getProjects({
        page: pagination.page,
        limit: pagination.limit
      })
      tableData.value = Array.isArray(response) ? response : []
      pagination.total = Array.isArray(response) ? response.length : 0
    }
  } catch (error) {
    console.error('获取数据失败:', error)
    tableData.value = []
    pagination.total = 0
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增项目详情'
  resetForm()
  form.id = generateUuid()
  form.orderNo = generateOrderNo()
  form.createdAt = getNowDateTime()
  form.updatedAt = getNowDateTime()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑项目详情'
  Object.assign(form, {
    id: row.id || '',
    orderNo: row.orderNo || '',
    projectName: row.projectName || '',
    clientShortName: row.clientShortName || '',
    clientCode: row.clientCode || '',
    projectStatus: row.projectStatus || '',
    customerReceptionTime: row.customerReceptionTime || '',
    customerDeadlineTime: row.customerDeadlineTime || '',
    translatorCooperationType: row.translatorCooperationType || '',
    translatorAssignee: row.translatorAssignee || '',
    translatorAssignmentTime: row.translatorAssignmentTime || '',
    translatorDeliveryProgress: row.translatorDeliveryProgress || '',
    review1Progress: row.review1Progress || '',
    preReviewQcProgress: row.preReviewQcProgress || '',
    layoutProgress: row.layoutProgress || '',
    consolidationProgress: row.consolidationProgress || '',
    sentToClientTime: row.sentToClientTime || '',
    clientFeedback: row.clientFeedback || '',
    postReviewQcProgress: row.postReviewQcProgress || '',
    review2Progress: row.review2Progress || '',
    reservedTranslatorStatMethod: row.reservedTranslatorStatMethod || '',
    reservedTranslatorWordCount: row.reservedTranslatorWordCount || 0,
    fileTypeSecondary: row.fileTypeSecondary || '',
    leadPmId: row.leadPmId || '',
    updatedAt: row.updatedAt || '',
    createdAt: row.createdAt || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目详情吗？', '提示', {
      type: 'warning'
    })

    if (isMockEnabled()) {
      await mockApi.projects.delete(row.id)
    } else {
      await deleteProject(row.id)
    }

    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.detail || error.message || '删除失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (!form.id) form.id = generateUuid()
        if (!form.orderNo) form.orderNo = generateOrderNo()
        if (!form.createdAt) form.createdAt = getNowDateTime()
        form.updatedAt = getNowDateTime()

        if (isMockEnabled()) {
          if (dialogTitle.value === '新增项目详情') {
            await mockApi.projects.create(form)
          } else {
            await mockApi.projects.update(form.id, form)
          }
        } else {
          if (dialogTitle.value === '新增项目详情') {
            await createProject(form)
          } else {
            await updateProject(form.id, form)
          }
        }

        ElMessage.success(dialogTitle.value === '编辑项目详情' ? '更新成功' : '创建成功')
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || error.message || '操作失败')
      }
    }
  })
}

const resetForm = () => {
  Object.assign(form, {
    id: '',
    orderNo: '',
    projectName: '',
    clientShortName: '',
    clientCode: '',
    projectStatus: '',
    customerReceptionTime: '',
    customerDeadlineTime: '',
    translatorCooperationType: '',
    translatorAssignee: '',
    translatorAssignmentTime: '',
    translatorDeliveryProgress: '',
    review1Progress: '',
    preReviewQcProgress: '',
    layoutProgress: '',
    consolidationProgress: '',
    sentToClientTime: '',
    clientFeedback: '',
    postReviewQcProgress: '',
    review2Progress: '',
    reservedTranslatorStatMethod: '',
    reservedTranslatorWordCount: 0,
    fileTypeSecondary: '',
    leadPmId: '',
    updatedAt: '',
    createdAt: ''
  })
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-popover {
  max-height: 600px;
  overflow-y: auto;
}

.detail-value {
  word-break: break-all;
  color: #606266;
}
</style>
