<template>
  <el-empty v-if="!clientId" description="请先保存客户，再维护客户要求" />
  <el-tabs v-else v-model="active" v-loading="loading">
    <el-tab-pane v-for="(module, key) in requirementModules" :key="key" :name="key" :label="module.label" />
    <el-alert v-if="error" type="error" :title="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-collapse v-model="expandedRegions">
      <el-collapse-item title="通用要求区域" name="general" data-dialog-field-search-label="通用要求区域">
    <el-card v-for="(label, field) in fields" :key="`${active}:${field}`" shadow="never" class="requirement-card">
      <template #header><strong>{{ label }}</strong></template>
      <div :data-dialog-field-search-label="label">
        <ol v-if="history[field]?.length" class="requirement-history">
          <li v-for="item in history[field]" :key="item.id">
            <div class="requirement-content">{{ item.content }}</div>
            <small>增加日期 {{ formatDate(item.added_at) }}<template v-if="item.source_order_no"> · 来源订单 {{ item.source_order_no }}</template></small>
          </li>
        </ol>
        <p v-else>暂无记录</p>
        <el-input v-if="canWrite" v-model="draft[field]" type="textarea" :rows="2" :disabled="saving"
          maxlength="10000" :aria-label="`新增${label}`" placeholder="填写后新增一条记录" />
        <el-button v-if="canWrite" :disabled="loading || !!error || saving || !draft[field]?.trim()" @click="append(field)">新增记录</el-button>
      </div>
    </el-card>
      </el-collapse-item>
      <el-collapse-item title="项目要求区域" name="projects" data-dialog-field-search-label="项目要求区域">
      <div class="project-requirements-heading"><span>按项目查看已填写的要求和说明</span><el-button link :loading="projectsLoading" @click="loadProjects">刷新</el-button></div>
      <el-alert v-if="projectsError" :title="projectsError" type="error" :closable="false"><el-button link @click="loadProjects">重试</el-button></el-alert>
      <div v-else v-loading="projectsLoading">
        <el-empty v-if="!projects.length && !projectsLoading" description="暂无已填写要求或说明的项目" :image-size="60" />
        <el-collapse>
          <el-collapse-item v-for="project in projects" :key="project.id" :name="project.id"
            :title="project.order_no + ' · ' + (project.project_name || '')">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item v-for="(content, field) in project.values" :key="field" :label="fields[field]">
                <div class="requirement-content">{{ content }}</div>
              </el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
        <el-pagination v-if="projectsTotal" v-model:current-page="projectsPage" v-model:page-size="projectsPageSize"
          :total="projectsTotal" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next"
          @current-change="loadProjects" @size-change="projectsPage=1;loadProjects()" />
      </div>
      </el-collapse-item>
    </el-collapse>
  </el-tabs>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { requirementModules, projectRequirementFields, requirementPath } from '@/utils/customerRequirements'

const props = defineProps({ clientId: String, canWrite: Boolean })
const active = ref('translation')
const fields = computed(() => projectRequirementFields(active.value))
const history = ref({})
const draft = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const expandedRegions = ref([])
const projects = ref([])
const projectsTotal = ref(0)
const projectsPage = ref(1)
const projectsPageSize = ref(10)
const projectsLoading = ref(false)
const projectsError = ref('')
let projectsRequest
let historyRequest
const dateFormat = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Hong_Kong', dateStyle: 'medium', timeStyle: 'medium' })
const formatDate = value => dateFormat.format(new Date(value))
let requestId = 0

async function load() {
  historyRequest?.abort()
  historyRequest = new AbortController()
  const id = ++requestId
  history.value = {}
  error.value = ''
  loading.value = Boolean(props.clientId)
  if (!props.clientId) return
  try {
    const { items } = await api.get(requirementPath(props.clientId, active.value), { signal: historyRequest.signal })
    if (id !== requestId) return
    for (const item of [...items].reverse()) (history.value[item.field] ??= []).push(item)
  } catch (e) {
    if (id === requestId) error.value = getLocalizedErrorMessage(e, '读取客户要求失败')
  } finally {
    if (id === requestId) loading.value = false
  }
}

async function loadProjects() {
  projectsRequest?.abort()
  const request = projectsRequest = new AbortController()
  projectsError.value = ''
  projectsLoading.value = Boolean(props.clientId)
  if (!props.clientId) return
  try {
    const data = await api.get(requirementPath(props.clientId, active.value) + '/projects', {
      signal: request.signal, params: { page: projectsPage.value, page_size: projectsPageSize.value },
    })
    if (request.signal.aborted) return
    projects.value = data.items.map(project => ({ ...project, values: Object.fromEntries(
      Object.entries(project.values).filter(([field]) => Object.hasOwn(fields.value, field)),
    ) }))
    projectsTotal.value = data.total
  } catch (error) {
    if (!request.signal.aborted) projectsError.value = getLocalizedErrorMessage(error, '读取项目要求失败')
  } finally {
    if (!request.signal.aborted) projectsLoading.value = false
  }
}

async function append(field) {
  const { clientId } = props
  const module = active.value
  saving.value = true
  try {
    const { added } = await api.post(requirementPath(clientId, module), { values: { [field]: draft.value[field] } })
    ElMessage.success(added ? '已新增客户要求' : '与最新内容一致，无需新增')
    if (props.clientId === clientId && active.value === module) {
      draft.value[field] = ''
      await load()
    }
  } catch (e) {
    ElMessage.error(getLocalizedErrorMessage(e, '保存客户要求失败'))
  } finally {
    saving.value = false
  }
}

watch(() => [props.clientId, active.value], () => {
  draft.value = {}
  expandedRegions.value = []
  projects.value = []
  projectsTotal.value = 0
  projectsPage.value = 1
  void load()
  void loadProjects()
}, { immediate: true })
onBeforeUnmount(() => { requestId++; historyRequest?.abort(); projectsRequest?.abort() })
</script>

<style scoped>
.requirement-card + .requirement-card { margin-top: 12px; }
.requirement-history { margin-top: 0; padding-inline-start: 22px; }
.requirement-history li + li { margin-top: 12px; }
.requirement-content { white-space: pre-wrap; overflow-wrap: anywhere; }
small { color: var(--el-text-color-secondary); }
.el-input + .el-button { margin-top: 8px; }
.project-requirements-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; color: var(--el-text-color-secondary); }
.el-pagination { margin-top: 12px; flex-wrap: wrap; }
</style>
