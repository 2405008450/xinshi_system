<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>薪酬管理</span>
        <el-button type="primary" @click="handleAdd">新增薪酬</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="employee_name" label="员工姓名" width="150" />
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column prop="salary_month" label="薪酬月份" width="120" />
      <el-table-column prop="base_salary" label="基本工资" width="120" />
      <el-table-column prop="bonus" label="奖金" width="100" />
      <el-table-column prop="deduction" label="扣款" width="100" />
      <el-table-column prop="total_salary" label="实发工资" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'paid' ? 'success' : 'warning'">
            {{ row.status === 'paid' ? '已发放' : '未发放' }}
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
      width="700px"
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
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="薪酬月份" prop="salary_month">
              <el-date-picker
                v-model="form.salary_month"
                type="month"
                placeholder="选择月份"
                style="width: 100%"
                value-format="YYYY-MM"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="基本工资" prop="base_salary">
              <el-input-number v-model="form.base_salary" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="奖金" prop="bonus">
              <el-input-number v-model="form.bonus" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="扣款" prop="deduction">
              <el-input-number v-model="form.deduction" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="实发工资" prop="total_salary">
              <el-input-number v-model="totalSalary" :disabled="true" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
                <el-option label="未发放" value="unpaid" />
                <el-option label="已发放" value="paid" />
              </el-select>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增薪酬')
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
  department: '',
  salary_month: '',
  base_salary: 0,
  bonus: 0,
  deduction: 0,
  status: 'unpaid',
  remarks: ''
})

const totalSalary = computed(() => {
  return form.base_salary + form.bonus - form.deduction
})

const rules = {
  employee_name: [{ required: true, message: '请输入员工姓名', trigger: 'blur' }],
  salary_month: [{ required: true, message: '请选择薪酬月份', trigger: 'change' }],
  base_salary: [{ required: true, message: '请输入基本工资', trigger: 'blur' }]
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
  dialogTitle.value = '新增薪酬'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑薪酬'
  Object.assign(form, {
    id: row.id,
    employee_name: row.employee_name || '',
    department: row.department || '',
    salary_month: row.salary_month || '',
    base_salary: row.base_salary || 0,
    bonus: row.bonus || 0,
    deduction: row.deduction || 0,
    status: row.status || 'unpaid',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该薪酬记录吗？', '提示', {
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
    department: '',
    salary_month: '',
    base_salary: 0,
    bonus: 0,
    deduction: 0,
    status: 'unpaid',
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
