<template>
  <div>
    <div class="report-toolbar">
      <div class="toolbar-actions">
        <el-tag :type="report.status === 'finalized' ? 'success' : 'info'">
          {{ report.status === 'finalized' ? '已确认' : '草稿' }}
        </el-tag>
        <el-button :loading="loading" @click="loadReport(true)">重新汇总</el-button>
        <el-button v-if="report.status !== 'finalized'" type="primary" plain :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button v-if="report.status !== 'finalized'" type="success" :loading="saving" @click="save(true)">确认日报</el-button>
        <el-button type="primary" :disabled="report.status !== 'finalized'" :loading="exporting" @click="downloadReport">导出 Excel</el-button>
      </div>
    </div>

    <el-alert
      v-if="report.status === 'finalized'"
      title="日报已确认并保存快照，后续任务修改不会影响本日报。"
      type="success"
      :closable="false"
      show-icon
      class="report-alert"
    />

    <el-table v-loading="loading" :data="report.items" border size="small">
      <el-table-column label="来源" width="100">
        <template #default="{ row }">{{ SOURCE_LABEL[row.source_type] || row.source_type }}</template>
      </el-table-column>
      <el-table-column label="任务类型" width="130">
        <template #default="{ row }">
          <el-input v-if="editable" v-model="row.task_type" size="small" />
          <span v-else>{{ row.task_type }}</span>
        </template>
      </el-table-column>
      <el-table-column label="任务名称" min-width="190">
        <template #default="{ row }">
          <el-input v-if="editable" v-model="row.task_name" size="small" />
          <span v-else>{{ row.task_name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="工作进展" min-width="230">
        <template #default="{ row }">
          <el-input v-if="editable" v-model="row.progress_content" type="textarea" :rows="2" />
          <span v-else class="pre-wrap">{{ row.progress_content }}</span>
        </template>
      </el-table-column>
      <el-table-column label="工作成果" min-width="210">
        <template #default="{ row }">
          <el-input v-if="editable" v-model="row.result_content" type="textarea" :rows="2" />
          <span v-else class="pre-wrap">{{ row.result_content || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="220">
        <template #default="{ row }">
          <div v-if="editable" class="duration-editor">
            <el-input-number
              :model-value="durationInputValue(row)"
              :min="0"
              :max="row.duration_unit === 'hours' ? 24 : 1440"
              :precision="row.duration_unit === 'hours' ? 2 : 0"
              :step="row.duration_unit === 'hours' ? 0.5 : 1"
              size="small"
              controls-position="right"
              @update:model-value="updateDurationFromInput(row, $event)"
            />
            <el-select v-model="row.duration_unit" size="small" class="duration-unit">
              <el-option label="分钟" value="minutes" />
              <el-option label="小时" value="hours" />
            </el-select>
          </div>
          <span v-else>{{ formatDuration(row.duration_minutes) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="editable" label="操作" width="72" align="center">
        <template #default="{ $index }">
          <el-button type="danger" link size="small" @click="report.items.splice($index, 1)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="editable" class="manual-row">
      <el-button type="primary" link @click="addManualItem">+ 补充线下工作</el-button>
    </div>

    <el-form label-position="top" class="supplement-form">
      <el-form-item label="补充说明">
        <el-input
          v-model="report.supplemental_note"
          type="textarea"
          :rows="3"
          maxlength="10000"
          show-word-limit
          :disabled="!editable"
          placeholder="可补充会议、沟通、异常情况或明日计划"
        />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  exportDailyReport,
  finalizeDailyReport,
  previewDailyReport,
  saveDailyReport
} from '@/api/tasks'

const props = defineProps({
  reportDate: { type: String, required: true }
})

const SOURCE_LABEL = { project: '项目任务', non_project: '非项目任务', manual: '手工补充' }
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const report = reactive({
  id: null,
  status: 'draft',
  supplemental_note: '',
  items: []
})
const editable = computed(() => report.status !== 'finalized')

function applyReport(data) {
  report.id = data?.id || null
  report.status = data?.status || 'draft'
  report.supplemental_note = data?.supplemental_note || ''
  report.items = Array.isArray(data?.items)
    ? data.items.map(item => {
        const durationMinutes = Number(item.duration_minutes || 0)
        return {
          ...item,
          duration_minutes: durationMinutes,
          duration_unit: durationMinutes > 60 ? 'hours' : 'minutes'
        }
      })
    : []
}

function durationInputValue(row) {
  const minutes = Number(row.duration_minutes || 0)
  return row.duration_unit === 'hours'
    ? Number((minutes / 60).toFixed(2))
    : Math.round(minutes)
}

function updateDurationFromInput(row, value) {
  const numericValue = Number(value || 0)
  const durationMinutes =
    row.duration_unit === 'hours'
      ? Math.round(numericValue * 60)
      : Math.round(numericValue)
  row.duration_minutes = durationMinutes
  row.duration_unit = durationMinutes > 60 ? 'hours' : 'minutes'
}

function formatDuration(value) {
  const minutes = Math.max(0, Math.round(Number(value || 0)))
  if (minutes <= 60) return `${minutes}分钟`
  return `${Number((minutes / 60).toFixed(2))}小时`
}

async function loadReport(refresh = false) {
  if (!props.reportDate) return
  loading.value = true
  try {
    applyReport(await previewDailyReport(props.reportDate, refresh === true))
  } catch (error) {
    applyReport({})
    ElMessage.error(error?.detail || '加载日报失败')
  } finally {
    loading.value = false
  }
}

function reportPayload() {
  return {
    supplemental_note: report.supplemental_note || null,
    items: report.items.map(({ id, sort_order, duration_unit, ...item }) => ({
      ...item,
      result_content: item.result_content || null,
      display_metadata: item.display_metadata || null
    }))
  }
}

async function save(finalize) {
  if (report.items.some(item => !item.task_type?.trim() || !item.task_name?.trim() || !item.progress_content?.trim())) {
    ElMessage.warning('任务类型、任务名称和工作进展不能为空')
    return
  }
  try {
    if (finalize) {
      await ElMessageBox.confirm('确认后将保存日报快照且不能继续编辑，是否继续？', '确认日报', { type: 'warning' })
    }
    saving.value = true
    const api = finalize ? finalizeDailyReport : saveDailyReport
    applyReport(await api(props.reportDate, reportPayload()))
    ElMessage.success(finalize ? '日报已确认' : '草稿已保存')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.detail || error?.message || '保存日报失败')
    }
  } finally {
    saving.value = false
  }
}

function addManualItem() {
  report.items.push({
    source_type: 'manual',
    source_id: null,
    task_type: '其他',
    task_name: '',
    progress_content: '',
    result_content: '',
    duration_minutes: 0,
    duration_unit: 'minutes',
    display_metadata: null
  })
}

async function downloadReport() {
  exporting.value = true
  try {
    const blob = await exportDailyReport(props.reportDate)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `个人工作日报-${props.reportDate}.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error?.detail || error?.message || '导出日报失败')
  } finally {
    exporting.value = false
  }
}

watch(() => props.reportDate, () => loadReport(false))
onMounted(() => loadReport(false))
</script>

<style scoped>
.report-toolbar { display: flex; justify-content: flex-end; gap: 16px; align-items: flex-start; margin-bottom: 12px; }
.toolbar-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.report-alert { margin-bottom: 12px; }
.manual-row { margin-top: 8px; }
.supplement-form { margin-top: 14px; }
.pre-wrap { white-space: pre-wrap; }
.duration-editor { display: flex; align-items: center; gap: 6px; }
.duration-editor :deep(.el-input-number) { width: 125px; }
.duration-unit { width: 76px; }
</style>
