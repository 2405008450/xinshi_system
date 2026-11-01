<template>
  <section class="annotation-managed-tasks">
    <div class="annotation-status-toolbar"><h3>标注项目安排</h3><div><el-button type="primary" @click="openAnnotationWorkStatus({mode:'report'})">状态汇报</el-button><el-button @click="openAnnotationWorkStatus({mode:'report',slot:'end_shift'})">下班汇报</el-button></div></div>
    <p class="task-hint">自动显示本人担任项目经理且符合状态条件的标注项目，按当前归属与状态更新。</p>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border row-key="id">
      <el-table-column type="index" label="序号" width="55" />
      <el-table-column prop="orderNo" label="订单号" width="165" />
      <el-table-column prop="projectName" label="项目名称" min-width="240" show-overflow-tooltip />
      <el-table-column prop="taskDescription" label="具体任务" min-width="240" show-overflow-tooltip />
      <el-table-column label="项目状态" width="150"><template #default="{row}"><el-tag :type="annotationStatusType(row.projectStatus)">{{ annotationStatusLabel(row.projectStatus) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="210" fixed="right"><template #default="{row}"><el-button type="primary" link @click="openAnnotationWorkStatus({mode:'arrangement',projectId:row.id})">项目进度</el-button><el-button v-if="canOpen" type="primary" link @click="openArrangement(row)">项目安排</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <AnnotationProjectArrangementDialog v-if="activeProject" v-model="arrangementVisible" :initial-project="activeProject" :default-execution-date="day" :can-write="canWrite" @saved="refresh" />
  </section>
</template>

<script setup>
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { getManagedAnnotationTasks } from '@/api/projectArrangements'
import { annotationStatusLabel, annotationStatusType } from '@/utils/annotationStatus'
import { hasPermission } from '@/utils/permission'
import { openAnnotationWorkStatus } from '@/utils/annotationWorkStatus'

defineProps({ day: { type: String, default: '' } })
const AnnotationProjectArrangementDialog = defineAsyncComponent(() => import('@/components/annotation/AnnotationProjectArrangementDialog.vue'))
const canWrite = hasPermission('projects:write')
const canOpen = canWrite || hasPermission('projects:read')
const rows = ref([]), total = ref(0), page = ref(1), loading = ref(false), errorMessage = ref('')
const activeProject = ref(null), arrangementVisible = ref(false)
let controller, requestId = 0
async function load() {
  controller?.abort()
  controller = new AbortController()
  const id = ++requestId
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getManagedAnnotationTasks({ page: page.value }, { signal: controller.signal })
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
function openArrangement(row) { activeProject.value = row; arrangementVisible.value = true }
onMounted(load)
onBeforeUnmount(() => { controller?.abort(); requestId++ })
defineExpose({ refresh })
</script>

<style scoped>
.annotation-managed-tasks{margin-top:24px;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}
.annotation-status-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.task-hint{color:var(--el-text-color-secondary);font-size:13px}
.el-pagination{margin-top:12px}
</style>
