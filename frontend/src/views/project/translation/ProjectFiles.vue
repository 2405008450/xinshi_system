<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目文件</span>
        <el-button type="primary" @click="handleAdd">新增文件</el-button>
      </div>
    </template>

    <el-form :inline="true" class="search-form">
      <el-form-item label="订单号">
        <el-input
          v-model="orderNoFilter"
          clearable
          placeholder="请输入订单号搜索"
          style="width: 240px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="order_no" label="订单号" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.order_no">{{ row.order_no }}</span>
          <span v-else style="color: #c0c4cc;">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.project_name">{{ row.project_name }}</span>
          <span v-else style="color: #c0c4cc;">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="project_status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.project_status" :type="getStatusType(row.project_status)">
            {{ getStatusLabel(row.project_status) }}
          </el-tag>
          <span v-else style="color: #c0c4cc;">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="file_name" label="文件名" min-width="180" show-overflow-tooltip />
      <el-table-column label="原文路径" min-width="240">
        <template #default="{ row }">
          <PathCell :path="row.storage_path" @copy="copyPath" />
        </template>
      </el-table-column>
      <el-table-column label="派稿文路径" min-width="240">
        <template #default="{ row }">
          <PathCell :path="row.dispatch_path" @copy="copyPath" />
        </template>
      </el-table-column>
      <el-table-column label="译文路径" min-width="240">
        <template #default="{ row }">
          <PathCell :path="row.translation_path" @copy="copyPath" />
        </template>
      </el-table-column>
      <el-table-column label="发客户路径" min-width="240">
        <template #default="{ row }">
          <PathCell :path="row.client_delivery_path" @copy="copyPath" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160" fixed="right">
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

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="620px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="关联项目" prop="translation_project_id">
          <el-select
            v-model="form.translation_project_id"
            filterable
            remote
            clearable
            :remote-method="fetchProjectOptions"
            :loading="projectSelectLoading"
            placeholder="请输入订单号或项目名称搜索"
            style="width: 100%"
            @focus="() => { if (!projectOptions.length) fetchProjectOptions() }"
          >
            <el-option
              v-for="opt in projectOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件名" prop="file_name">
          <el-input v-model="form.file_name" placeholder="请输入文件名" />
        </el-form-item>
        <el-form-item label="原文路径" prop="storage_path">
          <el-input v-model="form.storage_path" placeholder="如 \\win-server\原文" />
        </el-form-item>
        <el-form-item label="派稿文路径">
          <el-input v-model="form.dispatch_path" placeholder="如 \\win-server\派稿" />
        </el-form-item>
        <el-form-item label="译文路径">
          <el-input v-model="form.translation_path" placeholder="如 \\win-server\译文" />
        </el-form-item>
        <el-form-item label="发客户路径">
          <el-input v-model="form.client_delivery_path" placeholder="如 \\win-server\发客户" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElMessage, ElMessageBox } from 'element-plus'
import * as projectFileApi from '@/api/projectFiles'
import { getProjects } from '@/api/projects'

// ---- 路径单元格组件（复用 4 列） ----
const PathCell = defineComponent({
  props: { path: { type: String, default: '' } },
  emits: ['copy'],
  setup(props, { emit }) {
    return () => {
      if (!props.path) return h('span', { style: 'color:#c0c4cc' }, '—')
      const href = 'openpath://' + props.path.replace(/^\\\\/, '').replace(/\\/g, '/')
      return h('span', { style: 'display:flex;align-items:center;gap:4px;flex-wrap:wrap' }, [
        h('a', {
          href,
          style: 'word-break:break-all;color:#409eff;text-decoration:none;font-size:12px;flex:1;min-width:0'
        }, props.path),
        h(ElButton, {
          link: true,
          type: 'primary',
          size: 'small',
          onClick: (e) => { e.preventDefault(); emit('copy', props.path) }
        }, () => '复制')
      ])
    }
  }
})

const route = useRoute()
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增文件')
const formRef = ref(null)
const orderNoFilter = ref('')

const tableData = ref([])
const pagination = reactive({ page: 1, limit: 10, total: 0 })

const form = reactive({
  id: null,
  translation_project_id: '',
  file_name: '',
  storage_path: '',
  dispatch_path: '',
  translation_path: '',
  client_delivery_path: '',
  uploaded_by: null
})

const rules = {
  translation_project_id: [{ required: true, message: '请选择关联项目', trigger: 'change' }],
  file_name: [{ required: true, message: '请输入文件名', trigger: 'blur' }],
  storage_path: [{ required: true, message: '请输入原文路径', trigger: 'blur' }]
}

// ---- 关联项目下拉（新增时过滤已占用项目） ----
const projectOptions = ref([])
const projectSelectLoading = ref(false)
const usedProjectIds = ref(new Set())

const loadUsedProjectIds = async () => {
  try {
    const res = await projectFileApi.getProjectFiles({ skip: 0, limit: 10000 })
    usedProjectIds.value = new Set(
      (Array.isArray(res) ? res : []).map(f => f.translation_project_id)
    )
  } catch {
    usedProjectIds.value = new Set()
  }
}

const toOptions = (list) =>
  list.map(p => ({ value: p.id, label: `${p.orderNo} - ${p.projectName}` }))

const fetchProjectOptions = async (query = '') => {
  projectSelectLoading.value = true
  try {
    const params = { limit: 50 }
    if (query) params.order_no = query
    let res = await getProjects(params)
    let list = Array.isArray(res) ? res : []
    if (query && list.length === 0) {
      const res2 = await getProjects({ limit: 50, project_name: query })
      list = Array.isArray(res2) ? res2 : []
    }
    if (!form.id) list = list.filter(p => !usedProjectIds.value.has(p.id))
    projectOptions.value = toOptions(list)
  } catch {
    projectOptions.value = []
  } finally {
    projectSelectLoading.value = false
  }
}

const ensureCurrentProjectOption = (row) => {
  if (!row.translation_project_id) return
  const exists = projectOptions.value.some(o => o.value === row.translation_project_id)
  if (!exists && row.order_no) {
    projectOptions.value.unshift({
      value: row.translation_project_id,
      label: `${row.order_no} - ${row.project_name || ''}`
    })
  }
}

// ---- 状态标签（与 ProjectDetails.vue 一致） ----
const projectStatusOptions = [
  { label: '待启动', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '已暂停', value: 'paused' },
  { label: '已终止', value: 'terminated' }
]
const getStatusLabel = (status) =>
  projectStatusOptions.find(item => item.value === status)?.label || status || '-'
const getStatusType = (status) =>
  ({ pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger', terminated: 'info' }[status] || 'info')

const copyPath = (path) => {
  navigator.clipboard.writeText(path)
  ElMessage.success('路径已复制')
}

// ---- 数据加载 ----
const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    if (orderNoFilter.value) params.order_no = orderNoFilter.value
    const [res, countRes] = await Promise.all([
      projectFileApi.getProjectFiles(params),
      projectFileApi.getProjectFileCount(orderNoFilter.value ? { order_no: orderNoFilter.value } : {})
    ])
    tableData.value = Array.isArray(res) ? res : []
    pagination.total = countRes?.total || tableData.value.length
  } catch (error) {
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || '加载文件失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const resetSearch = () => { orderNoFilter.value = ''; handleSearch() }

const handleAdd = async () => {
  dialogTitle.value = '新增文件'
  resetForm()
  await Promise.all([loadUsedProjectIds(), fetchProjectOptions()])
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑文件'
  Object.assign(form, {
    id: row.id,
    translation_project_id: row.translation_project_id,
    file_name: row.file_name,
    storage_path: row.storage_path || '',
    dispatch_path: row.dispatch_path || '',
    translation_path: row.translation_path || '',
    client_delivery_path: row.client_delivery_path || '',
    uploaded_by: row.uploaded_by
  })
  ensureCurrentProjectOption(row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确认删除该文件记录？', '提示', { type: 'warning' })
    await projectFileApi.deleteProjectFile(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.detail || '删除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const submitData = { ...form }
      delete submitData.id
      // 空字符串转 null，避免后端写入空串
      ;['dispatch_path', 'translation_path', 'client_delivery_path'].forEach(k => {
        if (!submitData[k]) submitData[k] = null
      })
      if (form.id) {
        await projectFileApi.updateProjectFile(form.id, submitData)
        ElMessage.success('更新成功')
      } else {
        await projectFileApi.createProjectFile(submitData)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (error) {
      ElMessage.error(error.detail || '保存失败')
    }
  })
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    translation_project_id: '',
    file_name: '',
    storage_path: '',
    dispatch_path: '',
    translation_path: '',
    client_delivery_path: '',
    uploaded_by: null
  })
  formRef.value?.resetFields()
}

onMounted(() => {
  const routeProjectId = Array.isArray(route.query.projectId)
    ? route.query.projectId[0]
    : route.query.projectId
  if (routeProjectId) {
    orderNoFilter.value = route.query.orderNo || ''
  }
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-form {
  margin-bottom: 16px;
}
</style>
