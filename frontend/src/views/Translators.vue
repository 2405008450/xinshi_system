<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>译员信息</span>
        <el-button type="primary" @click="handleAdd">新增译员</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="translator_code" label="译员编号" width="120" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="cooperation_type" label="合作形式" width="120" />
      <el-table-column prop="languages" label="语种" width="150" />
      <el-table-column prop="gender" label="性别" width="80" />
      <el-table-column prop="translator_type" label="译员类型" width="120" />
      <el-table-column prop="nationality" label="国籍" width="100" />
      <el-table-column prop="phone" label="联系电话" width="150" />
      <el-table-column prop="email1" label="邮箱1" width="180" />
      <el-table-column prop="overdue_count" label="回稿超时次数" width="120" />
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
            <el-form-item label="译员编号" prop="translator_code">
              <el-input v-model="form.translator_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="译员合作形式" prop="cooperation_type">
              <el-select v-model="form.cooperation_type" placeholder="请选择" style="width: 100%">
                <el-option label="全职" value="fulltime" />
                <el-option label="兼职" value="parttime" />
                <el-option label="自由职业" value="freelance" />
                <el-option label="外包" value="outsource" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="语种" prop="languages">
              <el-input v-model="form.languages" placeholder="例如：中英、中日" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="性别" prop="gender">
              <el-select v-model="form.gender" placeholder="请选择" style="width: 100%">
                <el-option label="男" value="male" />
                <el-option label="女" value="female" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="身高" prop="height">
              <el-input v-model="form.height" placeholder="单位：cm" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="形象" prop="appearance">
              <el-input v-model="form.appearance" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="译员类型" prop="translator_type">
              <el-select v-model="form.translator_type" placeholder="请选择" style="width: 100%">
                <el-option label="口译" value="interpreter" />
                <el-option label="笔译" value="translator" />
                <el-option label="同传" value="simultaneous" />
                <el-option label="交传" value="consecutive" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="国籍" prop="nationality">
              <el-input v-model="form.nationality" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="民族" prop="ethnicity">
              <el-input v-model="form.ethnicity" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话2" prop="phone2">
              <el-input v-model="form.phone2" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="邮箱1" prop="email1">
              <el-input v-model="form.email1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱2" prop="email2">
              <el-input v-model="form.email2" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="简历路径" prop="resume_path">
              <el-input v-model="form.resume_path" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="其他联系方式" prop="other_contact">
              <el-input v-model="form.other_contact" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="初次沟通时间" prop="first_contact_date">
              <el-date-picker
                v-model="form.first_contact_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="回稿超时次数" prop="overdue_count">
              <el-input-number v-model="form.overdue_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="总评" prop="overall_rating">
          <el-input v-model="form.overall_rating" type="textarea" :rows="2" />
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
import * as translatorApi from '../api/translators'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增译员')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const form = reactive({
  id: null,
  translator_code: '',
  name: '',
  cooperation_type: '',
  languages: '',
  gender: '',
  height: '',
  appearance: '',
  translator_type: '',
  nationality: '',
  ethnicity: '',
  overall_rating: '',
  overdue_count: 0,
  phone: '',
  phone2: '',
  email1: '',
  email2: '',
  resume_path: '',
  other_contact: '',
  first_contact_date: '',
  remarks: ''
})

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email1: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  email2: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await translatorApi.getTranslators({
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
  dialogTitle.value = '新增译员'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑译员'
  Object.assign(form, {
    id: row.id,
    translator_code: row.translator_code || '',
    name: row.name || '',
    cooperation_type: row.cooperation_type || '',
    languages: row.languages || '',
    gender: row.gender || '',
    height: row.height || '',
    appearance: row.appearance || '',
    translator_type: row.translator_type || '',
    nationality: row.nationality || '',
    ethnicity: row.ethnicity || '',
    overall_rating: row.overall_rating || '',
    overdue_count: row.overdue_count || 0,
    phone: row.phone || '',
    phone2: row.phone2 || '',
    email1: row.email1 || '',
    email2: row.email2 || '',
    resume_path: row.resume_path || '',
    other_contact: row.other_contact || '',
    first_contact_date: row.first_contact_date || '',
    remarks: row.remarks || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该译员吗？', '提示', {
      type: 'warning'
    })
    await translatorApi.deleteTranslator(row.id)
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
          await translatorApi.updateTranslator(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await translatorApi.createTranslator(submitData)
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
    translator_code: '',
    name: '',
    cooperation_type: '',
    languages: '',
    gender: '',
    height: '',
    appearance: '',
    translator_type: '',
    nationality: '',
    ethnicity: '',
    overall_rating: '',
    overdue_count: 0,
    phone: '',
    phone2: '',
    email1: '',
    email2: '',
    resume_path: '',
    other_contact: '',
    first_contact_date: '',
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
