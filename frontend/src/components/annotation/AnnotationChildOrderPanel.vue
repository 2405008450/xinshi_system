<template>
  <div v-loading="loading" class="child-order-panel">
    <div class="child-order-panel__toolbar">
      <span>子订单 {{ total }} 个 · {{ statusSummary || '暂无子订单' }}</span>
      <div>
        <el-button v-if="editable" @click="$emit('create', parent, false, true)">分拆子订单</el-button>
        <el-button v-if="editable" type="primary" plain @click="$emit('create', parent, true)">新增子订单</el-button>
        <el-button v-if="editable" @click="$emit('create', parent, false)">批量新增子订单</el-button>
        <el-button @click="manage()">子订单管理</el-button>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-table :data="rows" row-key="id" border>
      <el-table-column prop="orderNo" label="子订单号" min-width="185" />
      <el-table-column prop="projectName" label="任务名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="languageItemsDisplay" label="语种方向" min-width="130" />
      <el-table-column label="状态" min-width="120"><template #default="{ row }">{{ labels[row.projectStatus] || row.projectStatus }}</template></el-table-column>
      <el-table-column label="负责人" min-width="130"><template #default="{ row }">{{ managers(row) }}</template></el-table-column>
      <el-table-column label="提交时间" min-width="165"><template #default="{ row }">{{ formatDateTime(row.taskSubmittedAt) }}</template></el-table-column>
      <el-table-column label="详情" width="100" fixed="right"><template #default="{ row }"><AnnotationProjectDetailPopover :project-id="row.id" :summary="row" :editable="false"><template #reference><el-button link type="primary">查看详情</el-button></template></AnnotationProjectDetailPopover></template></el-table-column>
      <el-table-column v-if="editable" label="操作" width="88" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="manage(row.id)">编辑</el-button></template></el-table-column>
    </el-table>
    <el-button v-if="total > rows.length" link type="primary" @click="manage()">查看全部 {{ total }} 个子订单</el-button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getAnnotationChildren } from '@/api/annotationProjects'
import AnnotationProjectDetailPopover from './AnnotationProjectDetailPopover.vue'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const props = defineProps({ parent: { type: Object, required: true }, editable: Boolean, revision: { type: Number, default: 0 } })
const emit = defineEmits(['create', 'navigate'])
const router = useRouter()
const rows = ref([]), total = ref(0), loading = ref(false), error = ref('')
let controller, requestId = 0
const labels = { initial_consultation:'初步咨询', consultation_no_result:'初步咨询后无结果', resource_sourcing:'资源开拓', resource_sourcing_cancelled:'取消资源开拓', trial_preparation:'试标准备', trial_in_progress:'试标中', trial_submitted:'试标已提交', trial_passed:'试标通过', trial_failed:'试标未通过', trial_partially_passed:'部分试标通过', project_in_progress:'项目进行中', sent_to_client:'已发客户', client_feedback:'客户反馈', cancelled:'已取消', partially_cancelled:'已部分取消', paused:'暂停', actively_abandoned:'主动放弃', ended:'已结束' }
const statusSummary = computed(() => Object.entries(props.parent.childStatusCounts || {}).map(([status,count]) => `${labels[status] || status} ${count}`).join('、'))
const managers = (row) => (row.roleAssignments || []).filter(item => item.roleCode === 'project_manager').map(item => item.assigneeName).filter(Boolean).join('、') || '-'
const manage = (id) => {
  emit('navigate')
  router.push({ name: 'AnnotationChildOrders', query: { parentProjectId: props.parent.id, ...(id ? { projectId: id, openEditor: '1' } : {}) } })
}
const load = async () => {
  controller?.abort(); controller = new AbortController()
  const current = ++requestId
  loading.value = true; error.value = ''
  try {
    const page = await getAnnotationChildren(props.parent.id, { limit: 10 }, { signal: controller.signal })
    if (current !== requestId) return
    rows.value = page.items; total.value = page.total
  } catch (failure) {
    if (current === requestId && failure.code !== 'ERR_CANCELED') error.value = failure.detail || '子订单加载失败'
  } finally { if (current === requestId) loading.value = false }
}
watch(() => [props.parent.id, props.revision], load, { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<style scoped>
.child-order-panel { padding: 12px; }
.child-order-panel__toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
</style>
