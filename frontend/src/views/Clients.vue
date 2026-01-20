<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>客户信息</span>
        <el-button type="primary" @click="handleAdd">新增客户</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="client_code" label="客户编号" width="150" />
      <el-table-column prop="client_name" label="客户名称" width="200" />
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
      <el-table-column label="操作" width="200" fixed="right">
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
            <el-form-item label="客户名称" prop="client_name">
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
import * as clientApi from '../api/clients'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增客户')
const formRef = ref(null)

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
  remarks: ''
})

const rules = {
  client_name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
  client_short_name: [{ required: true, message: '请输入客户简称', trigger: 'blur' }],
  client_manager: [{ required: true, message: '请输入客户负责人', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await clientApi.getClients({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    })
    tableData.value = res || []
    pagination.total = res?.length || 0
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
    remarks: row.remarks || ''
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
      try {
        const submitData = { ...form }
        delete submitData.id
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
    remarks: ''
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
</style>
