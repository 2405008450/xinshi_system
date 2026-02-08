<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>财务管理</span>
        <el-button type="primary" @click="handleAdd">新增记录</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="record_no" label="记录编号" width="150" />
      <el-table-column prop="record_type" label="记录类型" width="120">
        <template #default="{ row }">
          <el-tag :type="row.record_type === 'income' ? 'success' : 'danger'">
            {{ row.record_type === 'income' ? '收入' : '支出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="amount" label="金额" width="120" />
      <el-table-column prop="category" label="类别" width="150" />
      <el-table-column prop="project_name" label="项目名称" width="200" />
      <el-table-column prop="record_date" label="日期" width="120" />
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
            <el-form-item label="记录编号" prop="record_no">
              <el-input v-model="form.record_no" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="记录类型" prop="record_type">
              <el-select v-model="form.record_type" placeholder="请选择" style="width: 100%">
                <el-option label="收入" value="income" />
                <el-option label="支出" value="expense" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="金额" prop="amount">
              <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类别" prop="category">
              <el-input v-model="form.category" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目名称" prop="project_name">
              <el-input v-model="form.project_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="日期" prop="record_date">
              <el-date-picker
                v-model="form.record_date"
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

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增记录')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  record_no: '',
  record_type: 'income',
  amount: 0,
  category: '',
  project_name: '',
  record_date: '',
  remarks: ''
})

const rules = {
  record_no: [{ required: true, message: '请输入记录编号', trigger: 'blur' }],
  record_type: [{ required: true, message: '请选择记录类型', trigger: 'change' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }]
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
  dialogTitle.value = '新增记录'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑记录'
  Object.assign(form, {
    id: row.id,
    record_no: row.record_no || '',
    record_type: row.record_type || 'income',
    amount: row.amount || 0,
    category: row.category || '',
    project_name: row.project_name || '',
    record_date: row.record_date || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该记录吗？', '提示', {
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
    record_no: '',
    record_type: 'income',
    amount: 0,
    category: '',
    project_name: '',
    record_date: '',
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
