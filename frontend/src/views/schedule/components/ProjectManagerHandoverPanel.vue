<template>
  <div class="management-handover">
    <el-alert
      title="管理层项目归属"
      description="这里交接的是项目的管理主负责人，不会改变下方执行任务的当前环节、处理人或流程状态。"
      type="info"
      :closable="false"
      show-icon
      class="scope-alert"
    />

    <div v-if="incomingRequests.length" class="incoming-list">
      <div class="panel-title">
        待确认的管理层交接
        <el-tag type="warning" size="small">{{ incomingRequests.length }}</el-tag>
      </div>
      <el-card
        v-for="request in incomingRequests"
        :key="request.id"
        shadow="never"
        class="request-card"
      >
        <div class="request-header">
          <div>
            <strong>{{ request.requester_name || '未知发起人' }}</strong>
            <span>向你交接 {{ request.projects?.length || 0 }} 个管理项目</span>
          </div>
          <span class="request-time">{{ formatDateTime(request.created_at) }}</span>
        </div>
        <div v-if="request.reason" class="request-note">原因：{{ request.reason }}</div>
        <div v-if="request.note" class="request-note">说明：{{ request.note }}</div>
        <el-table :data="request.projects || []" border size="small" class="request-projects">
          <el-table-column prop="order_no" label="订单号" width="180" />
          <el-table-column prop="project_name" label="项目名称" min-width="220" show-overflow-tooltip />
          <el-table-column prop="client_short_name" label="客户" width="130" show-overflow-tooltip />
        </el-table>
        <div class="request-actions">
          <el-button size="small" type="danger" plain @click="decideRequest(request, 'reject')">拒绝</el-button>
          <el-button size="small" type="primary" @click="decideRequest(request, 'accept')">确认接收</el-button>
        </div>
      </el-card>
    </div>

    <div class="panel-title">
      <span>我负责的管理项目</span>
      <el-button
        type="primary"
        size="small"
        :disabled="!selectedProjects.length"
        @click="openHandoverDialog"
      >
        交接管理归属（{{ selectedProjects.length }}）
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="projects"
      border
      size="small"
      row-key="translation_project_id"
      @selection-change="selectedProjects = $event"
    >
      <el-table-column type="selection" width="46" />
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="project_name" label="项目名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户" width="130" show-overflow-tooltip />
      <el-table-column prop="project_manager_name" label="管理主负责人" width="140">
        <template #default="{ row }">{{ row.project_manager_name || '未绑定' }}</template>
      </el-table-column>
      <el-table-column label="客户交稿时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.customer_deadline_time) }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !projects.length" description="暂无可交接的管理项目" :image-size="72" />

    <el-dialog
      v-model="dialogVisible"
      title="发起管理层项目归属交接"
      width="620px"
      destroy-on-close
    >
      <el-alert
        :title="`将 ${selectedProjects.length} 个项目的管理主负责人交接给另一位项目经理，需由接收人确认。`"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-width="100px" class="handover-form">
        <el-form-item label="接收经理" required>
          <el-select
            v-model="targetManagerId"
            filterable
            placeholder="请选择项目经理"
            style="width: 100%"
          >
            <el-option
              v-for="manager in managerCandidates"
              :key="manager.id"
              :label="manager.full_name || manager.username"
              :value="manager.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交接原因">
          <el-input v-model="reason" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="交接说明">
          <el-input v-model="note" type="textarea" :rows="4" maxlength="5000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!targetManagerId"
          @click="submitHandover"
        >
          发起管理层交接
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  acceptProjectManagerHandoverAPI,
  createProjectManagerHandoverAPI,
  getIncomingProjectManagerHandoversAPI,
  getManagementProjectsAPI,
  getProjectManagerCandidatesAPI,
  rejectProjectManagerHandoverAPI
} from '@/api/workflow'

const emit = defineEmits(['updated'])
const projects = ref([])
const incomingRequests = ref([])
const managerCandidates = ref([])
const selectedProjects = ref([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const targetManagerId = ref('')
const reason = ref('')
const note = ref('')

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

async function loadData() {
  loading.value = true
  try {
    const [managed, incoming] = await Promise.all([
      getManagementProjectsAPI(),
      getIncomingProjectManagerHandoversAPI()
    ])
    projects.value = Array.isArray(managed) ? managed : []
    incomingRequests.value = Array.isArray(incoming) ? incoming : []
  } catch (error) {
    projects.value = []
    incomingRequests.value = []
    ElMessage.error(error?.detail || error?.message || '加载管理层项目交接失败')
  } finally {
    loading.value = false
  }
}

async function openHandoverDialog() {
  if (!selectedProjects.value.length) return
  targetManagerId.value = ''
  reason.value = ''
  note.value = ''
  try {
    const response = await getProjectManagerCandidatesAPI()
    managerCandidates.value = Array.isArray(response) ? response : []
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '加载项目经理列表失败')
  }
}

async function submitHandover() {
  if (!targetManagerId.value || !selectedProjects.value.length) return
  submitting.value = true
  try {
    await createProjectManagerHandoverAPI({
      translation_project_ids: selectedProjects.value.map(item => item.translation_project_id),
      target_manager_id: targetManagerId.value,
      reason: reason.value.trim() || undefined,
      note: note.value.trim() || undefined
    })
    ElMessage.success('管理层项目交接已发起，等待接收经理确认')
    dialogVisible.value = false
    selectedProjects.value = []
    await loadData()
    emit('updated')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '发起管理层项目交接失败')
  } finally {
    submitting.value = false
  }
}

async function decideRequest(request, decision) {
  const isAccept = decision === 'accept'
  try {
    await ElMessageBox.confirm(
      isAccept
        ? `确认接收这 ${request.projects?.length || 0} 个项目的管理主负责人归属吗？`
        : '确认拒绝这次管理层项目交接吗？',
      isAccept ? '确认管理归属' : '拒绝管理归属',
      { type: isAccept ? 'warning' : 'error' }
    )
    const api = isAccept
      ? acceptProjectManagerHandoverAPI
      : rejectProjectManagerHandoverAPI
    await api(request.id, {})
    ElMessage.success(isAccept ? '已接收管理项目' : '已拒绝管理层交接')
    await loadData()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '处理管理层交接失败')
    }
  }
}

function handlePendingNotification() {
  loadData()
}

onMounted(() => {
  loadData()
  window.addEventListener('project-manager-handover-pending', handlePendingNotification)
})

onBeforeUnmount(() => {
  window.removeEventListener('project-manager-handover-pending', handlePendingNotification)
})
</script>

<style scoped>
.management-handover {
  margin-bottom: 18px;
}

.scope-alert {
  margin-bottom: 14px;
}

.panel-title,
.request-header,
.request-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  margin: 12px 0 10px;
  font-size: 14px;
  font-weight: 600;
}

.incoming-list {
  margin-bottom: 18px;
}

.request-card {
  margin-bottom: 10px;
}

.request-header > div {
  display: flex;
  gap: 6px;
}

.request-time,
.request-note {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.request-note {
  margin-top: 8px;
}

.request-projects {
  margin-top: 10px;
}

.request-actions {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.handover-form {
  margin-top: 18px;
}
</style>
