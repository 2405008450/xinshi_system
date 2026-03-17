<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>译员资源库</span>
        <el-button type="primary" @click="handleAdd">新增译员</el-button>
      </div>
    </template>

    <!-- 查询区域 -->
    <div class="search-area">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 100px">
            <el-option label="活跃" value="active" />
            <el-option label="备用" value="standby" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="searchForm.translator_name" placeholder="请输入" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item label="语种">
          <el-input v-model="searchForm.languages" placeholder="请输入" clearable style="width: 100px" />
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="searchForm.direction" placeholder="请选择" clearable style="width: 100px">
            <el-option label="中译外" value="中译外" />
            <el-option label="外译中" value="外译中" />
            <el-option label="双向" value="双向" />
          </el-select>
        </el-form-item>
        <el-form-item label="合作形式">
          <el-select v-model="searchForm.cooperation_type" placeholder="请选择" clearable style="width: 100px">
            <el-option label="全职" value="全职" />
            <el-option label="兼职" value="兼职" />
            <el-option label="自由职业" value="自由职业" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="翻译类型">
          <el-select v-model="searchForm.translation_type" placeholder="请选择" clearable style="width: 100px">
            <el-option label="口译" value="口译" />
            <el-option label="笔译" value="笔译" />
            <el-option label="同传" value="同传" />
            <el-option label="交传" value="交传" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 主表格 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      border
      :default-sort="{ prop: 'default_priority', order: 'ascending' }"
      @sort-change="handleSortChange"
    >
      <el-table-column prop="default_priority" label="优先级" width="80" sortable />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="translator_name" label="姓名" width="100" />
      <el-table-column prop="translation_type" label="类型" width="80" />
      <el-table-column prop="quality_score" label="质量" width="70" />
      <el-table-column label="云端/修订" width="100">
        <template #default="{ row }">
          <span>{{ boolLabel(row.can_cloud_edit) }}/{{ boolLabel(row.can_revision) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="产能(接/速/字)" width="130">
        <template #default="{ row }">
          {{ row.daily_accept_count ?? '-' }}/{{ row.hourly_speed ?? '-' }}/{{ row.daily_word_capacity ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="available_time_slot" label="可接时段" width="110" show-overflow-tooltip />
      <el-table-column prop="languages" label="语种" width="80" />
      <el-table-column prop="direction" label="方向" width="70" />
      <el-table-column label="领域能力" min-width="180">
        <template #default="{ row }">
          <template v-if="row.domain_skills && row.domain_skills.length">
            <el-tag
              v-for="(skill, idx) in row.domain_skills"
              :key="idx"
              :type="domainTagType(skill.level)"
              size="small"
              class="domain-tag"
            >
              {{ skill.domain }}:{{ skill.level }}
            </el-tag>
          </template>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="remarks" label="备注" min-width="200" show-overflow-tooltip />
      <el-table-column prop="availability_updated_at" label="可用性更新" width="110">
        <template #default="{ row }">
          <span :class="{ 'text-stale': isStale(row.availability_updated_at) }">
            {{ formatDate(row.availability_updated_at) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button type="success" size="small" @click="handleQuickUpdate(row)">更新可用性</el-button>
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

    <!-- ========== 完整编辑弹窗 ========== -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="950px"
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
          <el-col :span="8">
            <el-form-item label="姓名" prop="translator_name">
              <el-input v-model="form.translator_name" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="译员编号" prop="translator_code">
              <el-input v-model="form.translator_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="活跃" value="active" />
                <el-option label="备用" value="standby" />
                <el-option label="停用" value="inactive" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="合作形式" prop="cooperation_type">
              <el-select v-model="form.cooperation_type" placeholder="请选择" style="width: 100%">
                <el-option label="全职" value="全职" />
                <el-option label="兼职" value="兼职" />
                <el-option label="自由职业" value="自由职业" />
                <el-option label="外包" value="外包" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="语种" prop="languages">
              <el-input v-model="form.languages" placeholder="如：中英、中日" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
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
          <el-col :span="8">
            <el-form-item label="性别" prop="gender">
              <el-select v-model="form.gender" placeholder="请选择" style="width: 100%">
                <el-option label="男" value="男" />
                <el-option label="女" value="女" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="国籍" prop="nationality">
              <el-input v-model="form.nationality" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="民族" prop="ethnicity">
              <el-input v-model="form.ethnicity" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="身高" prop="height">
              <el-input v-model="form.height" placeholder="cm" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="形象" prop="appearance">
              <el-input v-model="form.appearance" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 联系方式 -->
        <el-divider content-position="left">联系方式</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系电话2" prop="phone2">
              <el-input v-model="form.phone2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="其他联系方式" prop="other_contact">
              <el-input v-model="form.other_contact" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="邮箱1" prop="email1">
              <el-input v-model="form.email1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="邮箱2" prop="email2">
              <el-input v-model="form.email2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系信息(综合)" prop="contact_info">
              <el-input v-model="form.contact_info" placeholder="综合联系方式备注" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 专业能力与产能 -->
        <el-divider content-position="left">专业能力与产能</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="方向" prop="direction">
              <el-select v-model="form.direction" placeholder="请选择" style="width: 100%">
                <el-option label="中译外" value="中译外" />
                <el-option label="外译中" value="外译中" />
                <el-option label="双向" value="双向" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="质量评分" prop="quality_score">
              <el-input v-model="form.quality_score" placeholder="如 73 / 80 / A" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="默认优先级" prop="default_priority">
              <el-input-number v-model="form.default_priority" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="云端编辑">
              <el-switch v-model="form.can_cloud_edit" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="修订模式">
              <el-switch v-model="form.can_revision" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="日费率" prop="daily_rate">
              <el-input v-model="form.daily_rate" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="回稿超时次数" prop="overdue_count">
              <el-input-number v-model="form.overdue_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 可用性（项目助理定期更新） -->
        <el-divider content-position="left">可用性（项目助理定期更新）</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="可接稿时段">
              <el-input v-model="form.available_time_slot" placeholder="如：中午12点后" />
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="日均可接次数">
              <el-input-number v-model="form.daily_accept_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="小时速度(字)">
              <el-input-number v-model="form.hourly_speed" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="日均总字数">
              <el-input-number v-model="form.daily_word_capacity" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 领域能力 -->
        <el-divider content-position="left">领域能力</el-divider>
        <div class="domain-skills-editor">
          <el-table :data="form.domain_skills" border size="small" style="margin-bottom: 10px">
            <el-table-column label="领域" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.domain" placeholder="如：法律、银行、医学" />
              </template>
            </el-table-column>
            <el-table-column label="能力等级" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.level" placeholder="如：擅长、需审改、一般" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="removeDomainSkill($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" link @click="addDomainSkill">+ 新增领域</el-button>
        </div>

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
              <el-date-picker v-model="form.first_contact_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
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

    <!-- ========== 快速更新可用性弹窗 ========== -->
    <el-dialog
      v-model="quickUpdateVisible"
      :title="`更新可用性 - ${quickForm.translator_name}`"
      width="520px"
    >
      <el-form :model="quickForm" label-width="120px">
        <el-form-item label="状态">
          <el-select v-model="quickForm.status" style="width: 100%">
            <el-option label="活跃" value="active" />
            <el-option label="备用" value="standby" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="可接稿时段">
          <el-input v-model="quickForm.available_time_slot" placeholder="如：中午12点后、全天、傍晚5点后" />
        </el-form-item>
        <el-form-item label="日均可接次数">
          <el-input-number v-model="quickForm.daily_accept_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="小时速度(字)">
          <el-input-number v-model="quickForm.hourly_speed" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="日均总字数">
          <el-input-number v-model="quickForm.daily_word_capacity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="quickForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickUpdateVisible = false">取消</el-button>
        <el-button type="primary" @click="submitQuickUpdate">保存</el-button>
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
const pagination = reactive({ page: 1, limit: 20, total: 0 })

const searchForm = reactive({
  translator_code: '',
  translator_name: '',
  cooperation_type: '',
  languages: '',
  translation_type: '',
  direction: '',
  status: ''
})

const statusLabel = (s) => ({ active: '活跃', standby: '备用', inactive: '停用' }[s] || '备用')
const statusTagType = (s) => ({ active: 'success', standby: 'info', inactive: 'danger' }[s] || 'info')

const boolLabel = (v) => {
  if (v === true) return '可'
  if (v === false) return '否'
  return '-'
}

const domainTagType = (level) => {
  if (!level) return 'info'
  if (level.includes('擅长')) return 'success'
  if (level.includes('审改')) return 'warning'
  return 'info'
}

const formatDate = (dt) => {
  if (!dt) return '-'
  return dt.substring(0, 10)
}

const isStale = (dt) => {
  if (!dt) return true
  const d = new Date(dt)
  const now = new Date()
  return (now - d) > 4 * 24 * 60 * 60 * 1000
}

const handleSearch = () => { pagination.page = 1; fetchData() }

const handleReset = () => {
  Object.keys(searchForm).forEach(k => { searchForm[k] = '' })
  pagination.page = 1
  fetchData()
}

const handleSortChange = ({ prop, order }) => {
  if (!prop) return
  const sorted = [...tableData.value]
  sorted.sort((a, b) => {
    const va = a[prop] ?? 999
    const vb = b[prop] ?? 999
    return order === 'ascending' ? va - vb : vb - va
  })
  tableData.value = sorted
}

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
  remarks: '',
  status: 'standby',
  available_time_slot: '',
  daily_accept_count: null,
  hourly_speed: null,
  daily_word_capacity: null,
  can_cloud_edit: null,
  can_revision: null,
  domain_skills: [],
  availability_updated_at: null
}

const form = reactive({ ...defaultForm })

const rules = {
  translator_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email1: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }],
  email2: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }]
}

const addDomainSkill = () => {
  form.domain_skills.push({ domain: '', level: '' })
}

const removeDomainSkill = (index) => {
  form.domain_skills.splice(index, 1)
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const trimFields = ['translator_code', 'translator_name', 'languages']
    trimFields.forEach(f => { if (searchForm[f]?.trim()) params[f] = searchForm[f].trim() })
    const selectFields = ['cooperation_type', 'translation_type', 'direction', 'status']
    selectFields.forEach(f => { if (searchForm[f]) params[f] = searchForm[f] })

    const res = await translatorApi.getTranslators(params)
    tableData.value = res || []
    pagination.total = res?.length || 0
  } catch {
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
    if (['overdue_count', 'default_priority', 'daily_accept_count', 'hourly_speed', 'daily_word_capacity'].includes(key)) {
      data[key] = row[key] ?? (key === 'overdue_count' || key === 'default_priority' ? 0 : null)
    } else if (key === 'domain_skills') {
      data[key] = JSON.parse(JSON.stringify(row[key] || []))
    } else if (key === 'can_cloud_edit' || key === 'can_revision') {
      data[key] = row[key] ?? null
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
    await ElMessageBox.confirm('确定要删除该译员吗？', '提示', { type: 'warning' })
    await translatorApi.deleteTranslator(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const submitData = { ...form }
        submitData.domain_skills = (form.domain_skills || []).filter(s => s.domain)
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
  const clean = { ...defaultForm, domain_skills: [] }
  Object.assign(form, clean)
  formRef.value?.resetFields()
}

// ========== 快速更新可用性 ==========
const quickUpdateVisible = ref(false)
const quickForm = reactive({
  id: null,
  translator_name: '',
  status: 'active',
  available_time_slot: '',
  daily_accept_count: null,
  hourly_speed: null,
  daily_word_capacity: null,
  remarks: ''
})

const handleQuickUpdate = (row) => {
  quickForm.id = row.id
  quickForm.translator_name = row.translator_name
  quickForm.status = row.status || 'standby'
  quickForm.available_time_slot = row.available_time_slot || ''
  quickForm.daily_accept_count = row.daily_accept_count ?? null
  quickForm.hourly_speed = row.hourly_speed ?? null
  quickForm.daily_word_capacity = row.daily_word_capacity ?? null
  quickForm.remarks = row.remarks || ''
  quickUpdateVisible.value = true
}

const submitQuickUpdate = async () => {
  try {
    const updateData = {
      status: quickForm.status,
      available_time_slot: quickForm.available_time_slot,
      daily_accept_count: quickForm.daily_accept_count,
      hourly_speed: quickForm.hourly_speed,
      daily_word_capacity: quickForm.daily_word_capacity,
      remarks: quickForm.remarks,
      availability_updated_at: new Date().toISOString()
    }
    await translatorApi.updateTranslator(quickForm.id, updateData)
    ElMessage.success('可用性已更新')
    quickUpdateVisible.value = false
    fetchData()
  } catch {
    ElMessage.error('更新失败')
  }
}

onMounted(() => { fetchData() })
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-area {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
.search-form {
  margin-bottom: 0;
}
.domain-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
.text-muted {
  color: var(--el-text-color-placeholder);
}
.text-stale {
  color: var(--el-color-danger);
  font-weight: 500;
}
.domain-skills-editor {
  padding: 0 20px;
}
</style>
