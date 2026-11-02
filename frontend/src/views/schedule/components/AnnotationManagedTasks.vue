<template>
  <section class="annotation-managed-tasks">
    <div class="annotation-status-toolbar"><h4>标注项目</h4><div><el-button type="primary" @click="openAnnotationWorkStatus({mode:'report'})">状态汇报</el-button></div></div>
    <p class="task-hint">显示本人负责的标注项目。安排状态持续保留到人工调整，今日暂不进行的项目可在对应筛选中恢复。</p>
    <el-radio-group v-model="arrangementScope" class="arrangement-scope" @change="refresh"><el-radio-button value="today">今日安排</el-radio-button><el-radio-button value="not_today">今日暂不进行</el-radio-button><el-radio-button value="all">全部项目</el-radio-button></el-radio-group>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border row-key="id">
      <el-table-column type="index" label="序号" width="55" />
      <el-table-column prop="orderNo" label="订单号" width="165"><template #default="{row}"><AnnotationProjectDetailPopover :project-id="row.id" :summary="row" :editable="canWrite" @updated="refresh"><template #reference><el-button type="primary" link class="business-clickable-cell" :title="row.orderNo" @click.stop>{{row.orderNo}}</el-button></template></AnnotationProjectDetailPopover></template></el-table-column>
      <el-table-column prop="projectName" label="项目名称" min-width="240"><template #header><ClickableColumnHeader label="项目名称" hint="点击项目名称查看项目进度" /></template><template #default="{row}"><el-button type="primary" link class="project-name-link business-clickable-cell" :title="row.projectName" @click.stop="progressProjectId=row.id">{{row.projectName||'-'}}</el-button></template></el-table-column>
      <el-table-column prop="taskDescription" label="具体任务" min-width="240" show-overflow-tooltip />
      <el-table-column label="项目状态" width="150"><template #default="{row}"><el-button type="primary" link title="点击查看项目进度" @click.stop="progressProjectId=row.id"><el-tag :type="annotationStatusType(row.projectStatus)" size="small">{{ annotationStatusLabel(row.projectStatus) }}<el-icon><EditPen /></el-icon></el-tag></el-button></template></el-table-column>
      <el-table-column label="安排状态" width="140"><template #default="{row}">{{row.arrangementStatus==='not_today'?'今日暂不进行':'今日进行中'}}</template></el-table-column>
      <el-table-column label="操作" width="210" fixed="right"><template #default="{row}"><el-button type="primary" link @click="openAnnotationWorkStatus({mode:'arrangement',projectId:row.id})">今日安排</el-button><el-button v-if="canOpen" type="primary" link @click="openArrangement(row)">项目安排</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <AnnotationProjectArrangementDialog v-if="activeProject" v-model="arrangementVisible" :initial-project="activeProject" :default-execution-date="day" :can-write="canWrite" @saved="refresh" />
    <AnnotationProgressHost v-if="progressProjectId" :key="progressProjectId" embedded progress-only :progress-project-id="progressProjectId" @progress-closed="closeProgress" />
  </section>
</template>

<script setup>
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { getManagedAnnotationTasks } from '@/api/projectArrangements'
import { annotationStatusLabel, annotationStatusType } from '@/utils/annotationStatus'
import { hasPermission } from '@/utils/permission'
import { openAnnotationWorkStatus } from '@/utils/annotationWorkStatus'
import { EditPen } from '@element-plus/icons-vue'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'

defineProps({ day: { type: String, default: '' } })
const AnnotationProjectArrangementDialog = defineAsyncComponent(() => import('@/components/annotation/AnnotationProjectArrangementDialog.vue'))
const AnnotationProgressHost = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const progressProjectId = ref('')
const canWrite = hasPermission('projects:write')
const canOpen = canWrite || hasPermission('projects:read')
const rows = ref([]), total = ref(0), page = ref(1), loading = ref(false), errorMessage = ref('')
const activeProject = ref(null), arrangementVisible = ref(false)
const arrangementScope=ref('today')
let controller, requestId = 0
async function load() {
  controller?.abort()
  controller = new AbortController()
  const id = ++requestId
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getManagedAnnotationTasks({ page: page.value, arrangement_scope:arrangementScope.value }, { signal: controller.signal })
    if (id !== requestId) return
    if (!data.items.length && data.total && page.value > 1) {
      page.value = Math.ceil(data.total / 10)
      return load()
    }
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    if (id === requestId && error.code !== 'ERR_CANCELED') {
      rows.value = []
      total.value = 0
      errorMessage.value = error.detail || '读取标注项目安排失败'
    }
  } finally {
    if (id === requestId) loading.value = false
  }
}
function refresh() { page.value = 1; return load() }
function closeProgress() { progressProjectId.value = ''; return load() }
function openArrangement(row) { activeProject.value = row; arrangementVisible.value = true }
onMounted(()=>{load();window.addEventListener('annotation-work-status-updated',refresh)})
onBeforeUnmount(() => { controller?.abort(); requestId++;window.removeEventListener('annotation-work-status-updated',refresh) })
defineExpose({ refresh })
</script>

<style scoped>
.annotation-managed-tasks{margin-top:24px;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}
.annotation-status-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.annotation-status-toolbar h4{margin:0;font-size:15px;font-weight:600;line-height:1.5}
.task-hint{color:var(--el-text-color-secondary);font-size:13px}
.el-pagination{margin-top:12px}
.arrangement-scope{margin-bottom:12px;display:flex;flex-wrap:wrap}
.project-name-link{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
</style>
