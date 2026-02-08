<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>办公室设备管理</span>
        <el-button type="primary" @click="handleAdd">新增设备</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="equipment_no" label="设备编号" width="150" />
      <el-table-column prop="equipment_name" label="设备名称" width="200" />
      <el-table-column prop="equipment_type" label="设备类型" width="120" />
      <el-table-column prop="location" label="放置位置" width="150" />
      <el-table-column prop="purchase_date" label="采购日期" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="responsible_person" label="责任人" width="120" />
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
            <el-form-item label="设备编号" prop="equipment_no">
              <el-input v-model="form.equipment_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备名称" prop="equipment_name">
              <el-input v-model="form.equipment_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备类型" prop="equipment_type">
              <el-select v-model="form.equipment_type" placeholder="请选择" style="width: 100%">
                <el-option label="电脑" value="computer" />
                <el-option label="打印机" value="printer" />
                <el-option label="投影仪" value="projector" />
                <el-option label="电话" value="phone" />
                <el-option label="家具" value="furniture" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="放置位置" prop="location">
              <el-input v-model="form.location" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="采购日期" prop="purchase_date">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人" prop="responsible_person">
              <el-input v-model="form.responsible_person" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
                <el-option label="正常" value="normal" />
                <el-option label="维修中" value="repairing" />
                <el-option label="报废" value="scrapped" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增设备')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  equipment_no: '',
  equipment_name: '',
  equipment_type: '',
  location: '',
  purchase_date: '',
  status: 'normal',
  responsible_person: '',
  remarks: ''
})

const rules = {
  equipment_no: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  equipment_name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const typeMap = {
    normal: 'success',
    repairing: 'warning',
    scrapped: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    normal: '正常',
    repairing: '维修中',
    scrapped: '报废'
  }
  return textMap[status] || status
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
  dialogTitle.value = '新增设备'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑设备'
  Object.assign(form, {
    id: row.id,
    equipment_no: row.equipment_no || '',
    equipment_name: row.equipment_name || '',
    equipment_type: row.equipment_type || '',
    location: row.location || '',
    purchase_date: row.purchase_date || '',
    status: row.status || 'normal',
    responsible_person: row.responsible_person || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该设备吗？', '提示', {
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
    equipment_no: '',
    equipment_name: '',
    equipment_type: '',
    location: '',
    purchase_date: '',
    status: 'normal',
    responsible_person: '',
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
