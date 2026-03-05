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
      <el-table-column prop="translator_name" label="姓名" width="100" />
      <el-table-column prop="cooperation_type" label="合作形式" width="100" />
      <el-table-column prop="languages" label="语种" width="120" />
      <el-table-column prop="gender" label="性别" width="70" />
      <el-table-column prop="translation_type" label="翻译类型" width="100" />
      <el-table-column prop="nationality" label="国籍" width="80" />
      <el-table-column prop="phone" label="联系电话" width="130" />
      <el-table-column prop="email1" label="邮箱" width="180" />
      <el-table-column prop="quality_score" label="质量评分" width="90" />
      <el-table-column prop="direction" label="方向" width="80" />
      <el-table-column prop="daily_rate" label="日费率" width="100" />
      <el-table-column prop="overdue_count" label="超时次数" width="90" />
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
        <!-- 基本信息 -->
        <el-divider content-position="left">基本信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="译员编号" prop="translator_code">
              <el-input v-model="form.translator_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="translator_name">
              <el-input v-model="form.translator_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合作形式" prop="cooperation_type">
              <el-select v-model="form.cooperation_type" placeholder="请选择" style="width: 100%">
                <el-option label="全职" value="全职" />
                <el-option label="兼职" value="兼职" />
                <el-option label="自由职业" value="自由职业" />
                <el-option label="外包" value="外包" />
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
                <el-option label="男" value="男" />
                <el-option label="女" value="女" />
                <el-option label="其他" value="其他" />
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
            <el-form-item label="翻译类型" prop="translation_type">
              <el-select v-model="form.translation_type" placeholder="请选择" style="width: 100%">
                <el-option label="口译" value="口译" />
                <el-option label="笔译" value="笔译" />
                <el-option label="同传" value="同传" />
                <el-option label="交传" value="交传" />
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

        <!-- 联系方式 -->
        <el-divider content-position="left">联系方式</el-divider>
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
            <el-form-item label="其他联系方式" prop="other_contact">
              <el-input v-model="form.other_contact" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系信息(综合)" prop="contact_info">
              <el-input v-model="form.contact_info" placeholder="综合联系方式备注" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 专业能力 -->
        <el-divider content-position="left">专业能力与排班</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="方向" prop="direction">
              <el-select v-model="form.direction" placeholder="请选择" style="width: 100%">
                <el-option label="中译外" value="中译外" />
                <el-option label="外译中" value="外译中" />
                <el-option label="双向" value="双向" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="质量评分" prop="quality_score">
              <el-input v-model="form.quality_score" placeholder="如 A / B / C" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="云端修改" prop="cloud_revision">
              <el-input v-model="form.cloud_revision" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="日费率" prop="daily_rate">
              <el-input v-model="form.daily_rate" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="默认优先级" prop="default_priority">
              <el-input-number v-model="form.default_priority" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="回稿超时次数" prop="overdue_count">
              <el-input-number v-model="form.overdue_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 其他 -->
        <el-divider content-position="left">其他信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="简历路径" prop="resume_path">
              <el-input v-model="form.resume_path" />
            </el-form-item>
          </el-col>
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
        </el-row>
        <el-form-item label="排班备注" prop="schedule_remarks">
          <el-input v-model="form.schedule_remarks" type="textarea" :rows="2" />
        </el-form-item>
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
import * as translatorApi from '@/api/translators'

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

const defaultForm = {
  id: null,
  translator_code: '',
  translator_name: '',
  cooperation_type: '',
  contact_info: '',
  translation_type: '',
  quality_score: '',
  cloud_revision: '',
  daily_rate: '',
  direction: '',
  default_priority: 0,
  schedule_remarks: '',
  languages: '',
  gender: '',
  height: '',
  appearance: '',
  nationality: '',
  ethnicity: '',
  phone: '',
  phone2: '',
  email1: '',
  email2: '',
  resume_path: '',
  other_contact: '',
  overdue_count: 0,
  overall_rating: '',
  first_contact_date: '',
  remarks: ''
}

const form = reactive({ ...defaultForm })

const rules = {
  translator_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
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
  const fields = Object.keys(defaultForm)
  const data = {}
  for (const key of fields) {
    if (key === 'overdue_count' || key === 'default_priority') {
      data[key] = row[key] ?? 0
    } else {
      data[key] = row[key] ?? ''
    }
  }
  data.id = row.id
  Object.assign(form, data)
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
  Object.assign(form, { ...defaultForm })
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
