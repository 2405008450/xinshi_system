<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>离职管理</span>
        <el-button type="primary" @click="handleAdd">新增离职</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="employee_name" label="员工姓名" width="150" />
      <el-table-column prop="position" label="职位" width="150" />
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column prop="resignation_date" label="离职日期" width="120" />
      <el-table-column prop="resignation_type" label="离职类型" width="120">
        <template #default="{ row }">
          <el-tag :type="getResignationType(row.resignation_type)">
            {{ getResignationText(row.resignation_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">
            {{ row.status === 'completed' ? '已完成' : '进行中' }}
          </el-tag>
        </template>
      </el-table-column>
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
      width="800px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="员工姓名" prop="employee_name">
              <el-input v-model="form.employee_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职位" prop="position">
              <el-input v-model="form.position" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="离职日期" prop="resignation_date">
              <el-date-picker
                v-model="form.resignation_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="离职类型" prop="resignation_type">
              <el-select v-model="form.resignation_type" placeholder="请选择" style="width: 100%">
                <el-option label="主动离职" value="voluntary" />
                <el-option label="被动离职" value="involuntary" />
                <el-option label="合同到期" value="contract_end" />
                <el-option label="退休" value="retirement" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="离职原因" prop="resignation_reason">
          <el-input v-model="form.resignation_reason" type="textarea" :rows="3" />
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
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增离职')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  employee_name: '',
  position: '',
  department: '',
  resignation_date: '',
  resignation_type: '',
  resignation_reason: '',
  status: 'in_progress',
  remarks: ''
})

const rules = {
  employee_name: [{ required: true, message: '请输入员工姓名', trigger: 'blur' }],
  resignation_date: [{ required: true, message: '请选择离职日期', trigger: 'change' }]
}

const getResignationType = (type) => {
  const typeMap = {
    voluntary: 'info',
    involuntary: 'warning',
    contract_end: 'primary',
    retirement: 'success'
  }
  return typeMap[type] || 'info'
}

const getResignationText = (type) => {
  const textMap = {
    voluntary: '主动离职',
    involuntary: '被动离职',
    contract_end: '合同到期',
    retirement: '退休'
  }
  return textMap[type] || type
}

const fetchData = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 300))
    tableData.value = []
    pagination.total = 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增离职'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑离职'
  Object.assign(form, {
    id: row.id,
    employee_name: row.employee_name || '',
    position: row.position || '',
    department: row.department || '',
    resignation_date: row.resignation_date || '',
    resignation_type: row.resignation_type || '',
    resignation_reason: row.resignation_reason || '',
    status: row.status || 'in_progress',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该离职记录吗？', '提示', {
      type: 'warning'
    })
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
        await new Promise(resolve => setTimeout(resolve, 300))
        ElMessage.success(form.id ? '更新成功' : '创建成功')
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
    employee_name: '',
    position: '',
    department: '',
    resignation_date: '',
    resignation_type: '',
    resignation_reason: '',
    status: 'in_progress',
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
