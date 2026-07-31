<template>
  <CollapsibleSection
    v-if="requests.length"
    title="待确认交接"
    subtitle="需要确认接收或拒绝的任务交接"
    storage-key="pending-handovers"
  >
    <template #badge>
      <el-tag type="warning" size="small">{{ requests.length }}</el-tag>
    </template>
    <el-alert type="warning" :closable="false" show-icon>
      <template #title>
        你有 {{ requests.length }} 个待确认的任务交接
      </template>
      <el-button type="warning" link @click="dialogVisible = true">立即处理</el-button>
    </el-alert>

    <el-dialog v-model="dialogVisible" title="待确认的任务交接" width="920px" destroy-on-close>
      <div class="request-list">
        <el-card v-for="request in requests" :key="request.id" shadow="never" class="request-card">
          <template #header>
            <div class="request-card__header">
              <div>
                <strong>{{ request.requester_name || '未知用户' }}</strong>
                <span>向你发起了 {{ request.tasks?.length || 0 }} 项任务交接</span>
              </div>
              <el-tag type="warning" effect="plain">{{ handoverTypeLabel(request.handover_type) }}</el-tag>
            </div>
          </template>

          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="发起时间">{{ formatDateTime(request.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="交接原因">
              {{ request.handover_type === 'other' ? request.reason_detail : handoverTypeLabel(request.handover_type) }}
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="request.content || request.content_json" class="request-note">
            <div class="request-section-title">交接留言</div>
            <RichTextContent :document="request.content_json" :fallback="request.content" />
          </div>

          <div v-if="request.attachments?.length" class="request-attachments">
            <div class="request-section-title">留言图片</div>
            <a
              v-for="attachment in request.attachments"
              :key="attachment.id"
              :href="attachmentUrls[attachment.id] || undefined"
              target="_blank"
              rel="noopener"
            >
              <img v-if="attachmentUrls[attachment.id]" :src="attachmentUrls[attachment.id]" :alt="attachment.original_name" />
              <span>{{ attachment.original_name }}</span>
            </a>
          </div>

          <div class="request-section-title">交接任务</div>
          <el-table :data="request.tasks || []" border size="small" max-height="260">
            <el-table-column prop="client_name" label="客户" min-width="140" show-overflow-tooltip />
            <el-table-column prop="project_name" label="母项目" min-width="170" show-overflow-tooltip />
            <el-table-column prop="sub_project_name" label="子项目" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.sub_project_name || '-' }}</template>
            </el-table-column>
            <el-table-column prop="order_no" label="订单编号" width="165" />
          </el-table>

          <el-input
            v-model="decisionNotes[request.id]"
            maxlength="500"
            show-word-limit
            placeholder="处理备注（可选）"
            class="decision-note"
          />
          <div class="request-actions">
            <el-button
              type="danger"
              plain
              :loading="processingId === request.id"
              @click="handleDecision(request, 'reject')"
            >
              拒绝交接
            </el-button>
            <el-button
              type="primary"
              :loading="processingId === request.id"
              @click="handleDecision(request, 'accept')"
            >
              确认接收
            </el-button>
          </div>
        </el-card>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">稍后处理</el-button>
      </template>
    </el-dialog>
  </CollapsibleSection>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import RichTextContent from '@/components/RichTextContent.vue'
import CollapsibleSection from './CollapsibleSection.vue'
import { getProjectChatAttachmentBlob } from '@/api/projectChat'
import {
  acceptHandoverRequestAPI,
  getIncomingHandoverRequestsAPI,
  rejectHandoverRequestAPI
} from '@/api/workflow'

const emit = defineEmits(['updated'])
const requests = ref([])
const dialogVisible = ref(false)
const processingId = ref('')
const decisionNotes = reactive({})
const attachmentUrls = reactive({})
const objectUrls = new Set()

const TYPE_LABELS = {
  daily_shift: '每日班次交接',
  weekend_holiday: '周末/节假日交接',
  leave_time_off: '请假调休交接',
  other: '其他'
}

const handoverTypeLabel = (type) => TYPE_LABELS[type] || type || '-'

const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const clearAttachmentUrls = () => {
  objectUrls.forEach(url => URL.revokeObjectURL(url))
  objectUrls.clear()
  Object.keys(attachmentUrls).forEach(key => delete attachmentUrls[key])
}

const loadAttachmentUrls = async () => {
  const attachments = requests.value.flatMap(request => request.attachments || [])
  await Promise.all(attachments.map(async (attachment) => {
    if (attachmentUrls[attachment.id]) return
    try {
      const blob = await getProjectChatAttachmentBlob(attachment.id)
      const url = URL.createObjectURL(blob)
      attachmentUrls[attachment.id] = url
      objectUrls.add(url)
    } catch (error) {
      console.error('加载交接图片失败', error)
    }
  }))
}

const loadRequests = async ({ openDialog = false } = {}) => {
  try {
    const result = await getIncomingHandoverRequestsAPI()
    requests.value = Array.isArray(result) ? result : []
    await loadAttachmentUrls()
    if (openDialog && requests.value.length) dialogVisible.value = true
    if (!requests.value.length) dialogVisible.value = false
  } catch (error) {
    requests.value = []
    ElMessage.error(error?.detail || error?.message || '加载待确认交接失败')
  }
}

const handleDecision = async (request, decision) => {
  const actionLabel = decision === 'accept' ? '确认接收' : '拒绝'
  try {
    await ElMessageBox.confirm(
      decision === 'accept'
        ? '确认后所列任务将正式转交给你，是否继续？'
        : '拒绝后任务仍由原负责人处理，是否继续？',
      actionLabel,
      { type: decision === 'accept' ? 'warning' : 'error', confirmButtonText: actionLabel, cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  processingId.value = request.id
  try {
    const payload = { note: decisionNotes[request.id] || undefined }
    if (decision === 'accept') {
      await acceptHandoverRequestAPI(request.id, payload)
      ElMessage.success('已确认接收，任务已转入你的工作台')
    } else {
      await rejectHandoverRequestAPI(request.id, payload)
      ElMessage.success('已拒绝本次交接')
    }
    delete decisionNotes[request.id]
    await loadRequests()
    emit('updated')
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || `${actionLabel}失败`)
    await loadRequests()
  } finally {
    processingId.value = ''
  }
}

const handlePendingNotification = () => loadRequests({ openDialog: true })

onMounted(() => {
  window.addEventListener('workflow-handover-pending', handlePendingNotification)
  loadRequests({ openDialog: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('workflow-handover-pending', handlePendingNotification)
  clearAttachmentUrls()
})

defineExpose({ refresh: loadRequests })
</script>

<style scoped>
.pending-handover {
  margin-bottom: 20px;
}

.request-list {
  display: grid;
  gap: 16px;
}

.request-card__header,
.request-card__header > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.request-card__header > div {
  justify-content: flex-start;
}

.request-note,
.request-attachments {
  margin: 14px 0;
}

.request-section-title {
  margin: 14px 0 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.request-attachments {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.request-attachments .request-section-title {
  width: 100%;
  margin: 0;
}

.request-attachments a {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 128px;
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: none;
}

.request-attachments img {
  width: 128px;
  height: 92px;
  object-fit: cover;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.decision-note {
  margin-top: 14px;
}

.request-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 720px) {
  .request-card__header,
  .request-card__header > div {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
