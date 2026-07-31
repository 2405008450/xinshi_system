<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <span>客户信息</span>
          <small class="header-hint">母客户与子客户统一管理</small>
        </div>
        <el-button type="primary" @click="handleAdd">新增客户</el-button>
      </div>
    </template>

    <div class="search-bar">
      <el-form :inline="true" :model="searchForm" class="search-form-inline">
        <el-form-item label="客户编号">
          <el-input v-model="searchForm.client_code" placeholder="支持母客户或子客户编号" clearable />
        </el-form-item>
        <el-form-item label="客户全称">
          <el-input v-model="searchForm.client_name" placeholder="支持母客户或子客户名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="tableData" v-loading="loading" border :row-class-name="getRowClassName">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div style="padding: 10px 40px" v-if="row.sub_clients && row.sub_clients.length > 0">
            <el-table :data="row.sub_clients" border size="small">
              <el-table-column prop="sub_client_code" label="子客户编号" width="180" />
              <el-table-column prop="client_name" label="客户全称" />
              <el-table-column prop="client_short_name" label="客户简称" />
              <el-table-column prop="client_manager" label="客户负责人" />
              <el-table-column prop="manager_contact" label="负责人联系方式" />
              <el-table-column label="操作" width="120">
                <template #default="{ row: subRow }">
                  <el-button type="primary" link size="small" @click="handleEditSub(subRow, row)">编辑</el-button>
                  <el-button type="danger" link size="small" @click="handleDeleteSub(subRow, row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div style="padding: 10px 40px" v-else>
            <el-empty description="暂无子客户" :image-size="60" />
          </div>
        </template>
      </el-table-column>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户全称" width="200" />
      <el-table-column prop="client_short_name" label="客户简称" width="150" />
      <el-table-column prop="client_manager" label="客户负责人" width="150" />
      <el-table-column prop="manager_contact" label="负责人联系方式" width="150" />
      <el-table-column prop="field_level1" label="客户领域一级" width="150" />
      <el-table-column prop="field_level2" label="客户领域二级" width="150" />
      <el-table-column prop="country" label="国家" width="100" />
      <el-table-column prop="province" label="省份" width="100" />
      <el-table-column prop="city" label="地级市" width="100" />
      <el-table-column prop="district" label="区县" width="100" />
      <el-table-column prop="client_status" label="客户状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.client_status === 'active' ? 'success' : 'info'">
            {{ row.client_status === 'active' ? '合作中' : row.client_status === 'inactive' ? '已停止' : '待合作' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="cooperation_start_date" label="开始合作时间" width="120" />
      <el-table-column label="操作" width="285" fixed="right">
        <template #default="{ row }">
          <el-button type="success" size="small" @click="handleAddSubForParent(row)">新增子客户</el-button>
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
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 20px"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      @close="resetForm"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="140px"
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
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider v-if="form.id">子客户管理</el-divider>
        <div v-if="form.id" style="margin-bottom: 20px; padding: 0 40px;">
          <el-button type="success" size="small" @click="handleAddSub">添加子客户</el-button>
          <el-table :data="form.sub_clients" border size="small" style="margin-top: 10px;">
            <el-table-column prop="sub_client_code" label="子客户编号" width="160" />
            <el-table-column prop="client_name" label="客户全称" />
            <el-table-column prop="client_manager" label="负责人" />
            <el-table-column label="操作" width="120">
              <template #default="{ row: subRow }">
                <el-button type="primary" link size="small" @click="handleEditSub(subRow, form)">编辑</el-button>
                <el-button type="danger" link size="small" @click="handleDeleteSub(subRow, form)">删除</el-button>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as clientApi from '@/api/clients'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增客户')
const formRef = ref(null)

const subDialogVisible = ref(false)
const subDialogTitle = ref('新增子客户')
const subSubmitLoading = ref(false)
const subFormRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
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
  sub_clients: []
})

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
  client_code: '',
  client_name: ''
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const getRowClassName = ({ row }) => {
  return (!row.sub_clients || row.sub_clients.length === 0) ? 'hide-expand' : ''
}

const resetSearch = () => {
  searchForm.client_code = ''
  searchForm.client_name = ''
  handleSearch()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchData()
}

const handleCurrentChange = () => {
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    if (searchForm.client_code) params.client_code = searchForm.client_code
    if (searchForm.client_name) params.client_name = searchForm.client_name
    
    const countParams = {
      client_code: params.client_code,
      client_name: params.client_name
    }
    const [res, countRes] = await Promise.all([
      clientApi.getClients(params),
      clientApi.getClientCount(countParams)
    ])
    tableData.value = res || []
    pagination.total = countRes?.total || 0

    const lastPage = Math.max(1, Math.ceil(pagination.total / pagination.limit))
    if (pagination.page > lastPage) {
      pagination.page = lastPage
      await fetchData()
    }
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增客户'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑客户'
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
    sub_clients: row.sub_clients || []
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该客户吗？', '提示', {
      type: 'warning'
    })
    await clientApi.deleteClient(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
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
        // 日期选择器未填写时会产生空字符串，后端 Optional[datetime] 需要 null。
        submitData.cooperation_start_date = submitData.cooperation_start_date || null
        if (form.id) {
          await clientApi.updateClient(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await clientApi.createClient(submitData)
          ElMessage.success('创建成功')
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
  Object.assign(form, {
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
    sub_clients: []
  })
  formRef.value?.resetFields()
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
  subFormRef.value?.resetFields()
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
.card-header > div {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.header-hint {
  color: var(--el-text-color-secondary);
  font-weight: normal;
}
.search-bar {
  margin-bottom: 20px;
}
:deep(.hide-expand .el-table__expand-icon) {
  display: none !important;
}
</style>
