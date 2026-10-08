<template>
  <div v-loading="loading" class="sub-order-panel">
    <div class="sub-order-panel__header">
      <div class="sub-order-panel__meta"><span>子订单列表</span><el-tag size="small" type="info">共 {{ total }} 条</el-tag><el-tag v-for="item in statusSummary" :key="item.status" size="small" :type="statusType(item.status)">{{ item.label }} {{ item.count }}</el-tag><span v-if="!total">暂无子订单</span></div>
      <div class="sub-order-panel__actions">
        <el-button v-if="editable" type="primary" plain @click="$emit('create', parent, false, true)">分拆子订单</el-button>
        <el-button v-if="editable" type="primary" plain @click="$emit('create', parent, true)">新增子订单</el-button>
        <el-button v-if="editable" type="primary" plain @click="$emit('create', parent, false)">批量新增子订单</el-button>
        <el-button type="primary" plain @click="manage()">子订单管理</el-button>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-table :data="rows" row-key="id" border size="small" class="sub-order-table">
      <el-table-column label="子订单号" min-width="185">
        <template #default="{ row }">
          <AnnotationProjectDetailPopover :project-id="row.id" :summary="row" :editable="false">
            <template #reference><el-button link type="primary" class="child-order-no-link business-clickable-cell" :title="row.orderNo" @click.stop>{{ row.orderNo }}</el-button></template>
          </AnnotationProjectDetailPopover>
        </template>
      </el-table-column>
      <el-table-column prop="projectName" label="任务名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="languageItemsDisplay" label="语种方向" min-width="130" />
      <el-table-column label="状态" min-width="120"><template #default="{ row }"><el-tag size="small" :type="statusType(row.projectStatus)">{{ statusLabel(row.projectStatus) }}</el-tag></template></el-table-column>
      <el-table-column label="负责人" min-width="130"><template #default="{ row }">{{ managers(row) }}</template></el-table-column>
      <el-table-column label="提交时间" min-width="165"><template #default="{ row }">{{ formatDateTime(row.taskSubmittedAt) }}</template></el-table-column>
      <el-table-column v-if="showRowActions" label="操作" width="80" fixed="right" align="center">
        <template #default="{ row }">
          <ProjectListRowActions
            :editable="editable"
            edit-in-more
            :show-start-request="editable"
            :start-request-label="startRequestLabel(row.id)"
            :extra-actions="rowExtraActions(row)"
            @edit="manage(row.id)"
            @start-request="$emit('start-request', row)"
            @extra-command="(command) => $emit('extra-command', command, row)"
          />
        </template>
      </el-table-column>
    </el-table>
    <el-button v-if="total > rows.length" link type="primary" @click="manage()">查看全部 {{ total }} 个子订单</el-button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getAnnotationChildren } from '@/api/annotationProjects'
import AnnotationProjectDetailPopover from './AnnotationProjectDetailPopover.vue'
import ProjectListRowActions from '@/components/common/ProjectListRowActions.vue'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { annotationStatusLabel as statusLabel, annotationStatusType as statusType, annotationStatusSummary } from '@/utils/annotationStatus'

const props = defineProps({
  parent: { type: Object, required: true },
  editable: Boolean,
  revision: { type: Number, default: 0 },
  showRowActions: { type: Boolean, default: true },
  rowExtraActions: { type: Function, default: () => [] },
  startRequestLabel: { type: Function, default: () => '发起需求' },
})
const emit = defineEmits(['create', 'navigate', 'start-request', 'extra-command'])
const router = useRouter()
const rows = ref([]), total = ref(0), loading = ref(false), error = ref('')
let controller, requestId = 0
const statusSummary = computed(() => annotationStatusSummary(props.parent.childStatusCounts))
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
.child-order-no-link {
  display: block;
  width: 100%;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
