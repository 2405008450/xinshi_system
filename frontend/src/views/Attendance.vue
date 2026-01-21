<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>考勤管理</span>
        <el-button type="primary" @click="handleAdd">新增考勤</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="employee_name" label="员工姓名" width="150" />
      <el-table-column prop="attendance_date" label="日期" width="120" />
      <el-table-column prop="check_in_time" label="签到时间" width="120" />
      <el-table-column prop="check_out_time" label="签退时间" width="120" />
      <el-table-column prop="work_hours" label="工作时长" width="120" />
      <el-table-column prop="attendance_type" label="考勤类型" width="120">
        <template #default="{ row }">
          <el-tag :type="getAttendanceTypeColor(row.attendance_type)">
            {{ getAttendanceTypeText(row.attendance_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remarks" label="备注" show-overflow-tooltip />
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
            <el-form-item label="日期" prop="attendance_date">
              <el-date-picker
                v-model="form.attendance_date"
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
            <el-form-item label="签到时间" prop="check_in_time">
              <el-time-picker
                v-model="form.check_in_time"
                placeholder="选择时间"
                style="width: 100%"
                value-format="HH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="签退时间" prop="check_out_time">
              <el-time-picker
                v-model="form.check_out_time"
                placeholder="选择时间"
                style="width: 100%"
                value-format="HH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="考勤类型" prop="attendance_type">
              <el-select v-model="form.attendance_type" placeholder="请选择" style="width: 100%">
                <el-option label="正常" value="normal" />
                <el-option label="迟到" value="late" />
                <el-option label="早退" value="early_leave" />
                <el-option label="旷工" value="absent" />
                <el-option label="请假" value="leave" />
                <el-option label="出差" value="business_trip" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作时长" prop="work_hours">
              <el-input-number v-model="form.work_hours" :min="0" :precision="1" style="width: 100%" />
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

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增考勤')
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
  attendance_date: '',
  check_in_time: '',
  check_out_time: '',
  work_hours: 0,
  attendance_type: 'normal',
  remarks: ''
})

const rules = {
  employee_name: [{ required: true, message: '请输入员工姓名', trigger: 'blur' }],
  attendance_date: [{ required: true, message: '请选择日期', trigger: 'change' }]
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
  dialogTitle.value = '新增考勤'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑考勤'
  Object.assign(form, {
    id: row.id,
    employee_name: row.employee_name || '',
    attendance_date: row.attendance_date || '',
    check_in_time: row.check_in_time || '',
    check_out_time: row.check_out_time || '',
    work_hours: row.work_hours || 0,
    attendance_type: row.attendance_type || 'normal',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该考勤记录吗？', '提示', {
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
    attendance_date: '',
    check_in_time: '',
    check_out_time: '',
    work_hours: 0,
    attendance_type: 'normal',
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
