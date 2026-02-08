<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>KPI管理</span>
        <el-button type="primary" @click="handleAdd">新增KPI</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="employee_name" label="员工姓名" width="150" />
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column prop="assessment_period" label="考核周期" width="120" />
      <el-table-column prop="target_score" label="目标分数" width="100" />
      <el-table-column prop="actual_score" label="实际分数" width="100" />
      <el-table-column prop="completion_rate" label="完成率" width="100">
        <template #default="{ row }">
          {{ row.completion_rate }}%
        </template>
      </el-table-column>
      <el-table-column prop="rating" label="评级" width="100">
        <template #default="{ row }">
          <el-tag :type="getRatingColor(row.rating)">
            {{ row.rating }}
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
            <el-form-item label="考核周期" prop="assessment_period">
              <el-date-picker
                v-model="form.assessment_period"
                type="month"
                placeholder="选择月份"
                style="width: 100%"
                value-format="YYYY-MM"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标分数" prop="target_score">
              <el-input-number v-model="form.target_score" :min="0" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="实际分数" prop="actual_score">
              <el-input-number v-model="form.actual_score" :min="0" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="完成率" prop="completion_rate">
              <el-input-number v-model="completionRate" :disabled="true" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="评级" prop="rating">
              <el-select v-model="form.rating" placeholder="请选择" style="width: 100%">
                <el-option label="优秀" value="excellent" />
                <el-option label="良好" value="good" />
                <el-option label="合格" value="qualified" />
                <el-option label="不合格" value="unqualified" />
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
const dialogTitle = ref('新增KPI')
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
  assessment_period: '',
  target_score: 100,
  actual_score: 0,
  rating: '',
  remarks: ''
})

const completionRate = computed(() => {
  if (form.target_score === 0) return 0
  return (form.actual_score / form.target_score) * 100
})

const rules = {
  employee_name: [{ required: true, message: '请输入员工姓名', trigger: 'blur' }],
  assessment_period: [{ required: true, message: '请选择考核周期', trigger: 'change' }]
}

const getRatingColor = (rating) => {
  const colorMap = {
    excellent: 'success',
    good: 'primary',
    qualified: 'warning',
    unqualified: 'danger'
  }
  return colorMap[rating] || 'info'
}

const getAttendanceTypeColor = (type) => {
  const colorMap = {
    normal: 'success',
    late: 'warning',
    early_leave: 'warning',
    absent: 'danger',
    leave: 'info',
    business_trip: 'primary'
  }
  return colorMap[type] || 'info'
}

const getAttendanceTypeText = (type) => {
  const textMap = {
    normal: '正常',
    late: '迟到',
    early_leave: '早退',
    absent: '旷工',
    leave: '请假',
    business_trip: '出差'
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
  dialogTitle.value = '新增KPI'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑KPI'
  Object.assign(form, {
    id: row.id,
    employee_name: row.employee_name || '',
    department: row.department || '',
    assessment_period: row.assessment_period || '',
    target_score: row.target_score || 100,
    actual_score: row.actual_score || 0,
    rating: row.rating || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该KPI记录吗？', '提示', {
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
    assessment_period: '',
    target_score: 100,
    actual_score: 0,
    rating: '',
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
