<template>
  <div>
    <div class="toolbar">
      <el-select v-model="filters.direction" clearable placeholder="翻译方向" style="width: 140px" @change="loadData">
        <el-option label="中英" value="zh_en" /><el-option label="英中" value="en_zh" />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="接稿状态" style="width: 140px" @change="loadData">
        <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-input v-model="filters.keyword" clearable placeholder="译员姓名" style="width: 180px" @input="onKeywordInput" @clear="loadData" @keyup.enter="loadData" />
      <el-button type="primary" @click="loadData">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <div class="week-label">{{ weekDates[0] }} 至 {{ weekDates[6] }}</div>
      <el-button v-if="canEdit" type="warning" @click="importVisible = true">导入译员排期</el-button>
    </div>

    <el-table :data="translators" border size="small" v-loading="loading">
      <el-table-column prop="default_priority" label="优先" width="65" fixed="left" />
      <el-table-column prop="name" label="译员" width="105" fixed="left" show-overflow-tooltip />
      <el-table-column prop="quality" label="质量" width="70" />
      <el-table-column v-for="(scheduleDay, index) in weekDates" :key="scheduleDay" :label="`${weekdayLabels[index]} ${scheduleDay.slice(5)}`" width="174">
        <template #default="{ row }">
          <el-popover v-if="canEdit" trigger="click" placement="bottom" :width="340" @show="startEdit(row, scheduleDay)">
            <template #reference><button class="availability-cell" type="button"><StatusContent :day="dayOf(row, scheduleDay)" /></button></template>
            <div class="editor">
              <el-select v-model="editForm.availability_status" style="width: 100%">
                <el-option v-for="option in statusOptions.filter(item => item.value !== 'unconfirmed')" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <el-input v-if="editForm.availability_status === 'available'" v-model="editForm.available_time_slot" placeholder="可接时段，如 12:00 后" />
              <el-input-number v-if="editForm.availability_status === 'available'" v-model="editForm.remaining_capacity" :min="0" placeholder="剩余容量" style="width: 100%" />
              <el-input v-model="editForm.remarks" type="textarea" :rows="2" placeholder="排期备注" />
              <div class="editor-actions"><el-button type="primary" :loading="saving" @click="saveAvailability(row, scheduleDay)">保存</el-button></div>
            </div>
          </el-popover>
          <div v-else class="availability-cell readonly"><StatusContent :day="dayOf(row, scheduleDay)" /></div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="importVisible" title="导入译员排期" width="min(900px, calc(100vw - 32px))" top="5vh" class="translator-import-dialog" @closed="resetImport">
      <el-alert type="info" :closable="false" show-icon title="支持现有外部收集表（G–P）和系统标准模板；请先预览，确认匹配结果后再导入。" />
      <div class="import-actions">
        <input type="file" accept=".xlsx" @change="onFileChange" />
        <el-checkbox v-model="overwrite">覆盖同日期已有排期</el-checkbox>
        <el-button @click="downloadTemplate">下载标准模板</el-button>
        <el-button :loading="previewing" :disabled="!importFile" @click="previewImport">生成预览</el-button>
      </div>
      <p v-if="preview" class="summary">识别格式：{{ preview.format === 'standard' ? '标准模板' : '外部收集表' }}；共 {{ preview.preview_count }} 条，匹配 {{ preview.matched_translators }} 位译员。</p>
      <el-alert v-if="preview?.unmatched_names?.length" type="warning" :closable="false" :title="`未匹配：${preview.unmatched_names.join('，')}`" />
      <el-alert v-if="preview?.errors?.length" type="error" :closable="false" :title="`发现 ${preview.errors.length} 个格式错误，请修正后重新预览`" />
      <el-table v-if="preview?.preview_items?.length" :data="preview.preview_items" border size="small" max-height="380">
        <el-table-column prop="row_no" label="行" width="55" />
        <el-table-column prop="translator_name" label="译员" width="110" />
        <el-table-column prop="schedule_date" label="日期" width="110" />
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ statusLabel(row.availability_status) }}</template></el-table-column>
        <el-table-column prop="available_time_slot" label="时段" min-width="130" show-overflow-tooltip />
        <el-table-column label="动作" width="80"><template #default="{ row }"><el-tag :type="row.action === 'update' ? 'warning' : 'success'" size="small">{{ row.action === 'update' ? '覆盖' : '新增' }}</el-tag></template></el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!preview?.preview_items?.length || preview?.errors?.length" @click="submitImport">确认导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElTag } from 'element-plus'
import {
  downloadTranslatorScheduleTemplate, getTranslatorAvailabilityGrid,
  importTranslatorScheduleDemo, previewTranslatorScheduleDemo, updateTranslatorAvailability
} from '@/api/schedule'

const props = defineProps({ selectedDate: { type: String, default: '' }, canEdit: { type: Boolean, default: false } })
const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const statusOptions = [
  { value: 'available', label: '可接稿', type: 'success' },
  { value: 'unavailable', label: '不可接稿', type: 'info' },
  { value: 'cycle_blocked', label: '本周期不可接', type: 'danger' },
  { value: 'unconfirmed', label: '未反馈', type: 'warning' }
]
const filters = reactive({ direction: '', status: '', keyword: '' })
const loading = ref(false)
const saving = ref(false)
const translators = ref([])
const editForm = reactive({ availability_status: 'available', available_time_slot: '', remaining_capacity: null, remarks: '' })
const importVisible = ref(false)
const importFile = ref(null)
const overwrite = ref(true)
const preview = ref(null)
const previewing = ref(false)
const importing = ref(false)
let debounceTimer = null
let controller = null
let sequence = 0

const weekDates = computed(() => {
  const base = props.selectedDate ? new Date(`${props.selectedDate}T00:00:00`) : new Date()
  const weekday = base.getDay() || 7
  base.setDate(base.getDate() - weekday + 1)
  return Array.from({ length: 7 }, (_, index) => {
    const value = new Date(base); value.setDate(base.getDate() + index)
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  })
})
function statusLabel(value) { return statusOptions.find(item => item.value === value)?.label || value || '未反馈' }
function dayOf(row, value) { return row.days?.find(day => day.date === value) }
const StatusContent = defineComponent({
  props: { day: { type: Object, default: null } },
  setup(componentProps) {
    return () => {
      const status = componentProps.day?.availability_status || 'unconfirmed'
      const option = statusOptions.find(item => item.value === status) || statusOptions[3]
      return h('div', { class: 'status-content' }, [
        h(ElTag, { type: option.type, size: 'small', effect: 'plain' }, () => option.label),
        componentProps.day?.available_time_slot ? h('small', componentProps.day.available_time_slot) : null,
        componentProps.day?.remaining_capacity != null ? h('small', `余量 ${componentProps.day.remaining_capacity}`) : null
      ])
    }
  }
})
async function loadData() {
  controller?.abort(); controller = new AbortController(); const current = ++sequence; loading.value = true
  try {
    const data = await getTranslatorAvailabilityGrid({ date_from: weekDates.value[0], date_to: weekDates.value[6], direction: filters.direction || undefined, keyword: filters.keyword.trim() || undefined, availability_status: filters.status || undefined }, controller.signal)
    if (current === sequence) translators.value = data.translators || []
  } catch (error) { if (error.code !== 'ERR_CANCELED' && current === sequence) ElMessage.error(error.detail || '读取译员排期失败') }
  finally { if (current === sequence) loading.value = false }
}
function onKeywordInput(value) { clearTimeout(debounceTimer); if (!value) loadData(); else debounceTimer = setTimeout(loadData, 400) }
function resetFilters() { Object.assign(filters, { direction: '', status: '', keyword: '' }); loadData() }
function startEdit(row, value) {
  const day = dayOf(row, value)
  Object.assign(editForm, { availability_status: day?.availability_status === 'unconfirmed' ? 'available' : day?.availability_status, available_time_slot: day?.available_time_slot || '', remaining_capacity: day?.remaining_capacity ?? null, remarks: day?.remarks || '' })
}
async function saveAvailability(row, value) {
  saving.value = true
  try {
    await updateTranslatorAvailability(row.translator_id, value, { ...editForm, available_time_slot: editForm.availability_status === 'available' ? editForm.available_time_slot : null, last_confirmed_at: new Date().toISOString(), source_type: 'manual' })
    ElMessage.success('译员排期已保存'); await loadData()
  } catch (error) { ElMessage.error(error.detail || '保存译员排期失败') }
  finally { saving.value = false }
}
function onFileChange(event) { importFile.value = event.target.files?.[0] || null; preview.value = null }
async function previewImport() { previewing.value = true; try { preview.value = await previewTranslatorScheduleDemo(importFile.value) } catch (error) { ElMessage.error(error.detail || '生成预览失败') } finally { previewing.value = false } }
async function submitImport() {
  importing.value = true
  try { const result = await importTranslatorScheduleDemo(importFile.value, overwrite.value); ElMessage.success(`导入完成：新增 ${result.created_records || 0}，更新 ${result.updated_records || 0}，跳过 ${result.skipped_records || 0}`); importVisible.value = false; await loadData() }
  catch (error) { ElMessage.error(error.detail || '导入失败') } finally { importing.value = false }
}
async function downloadTemplate() {
  try { const blob = await downloadTranslatorScheduleTemplate(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = '译员排期标准模板.xlsx'; link.click(); URL.revokeObjectURL(url) }
  catch (error) { ElMessage.error(error.detail || '下载模板失败') }
}
function resetImport() { importFile.value = null; preview.value = null; overwrite.value = true }
watch(() => props.selectedDate, loadData)
onMounted(loadData)
onBeforeUnmount(() => { clearTimeout(debounceTimer); controller?.abort() })
</script>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.week-label { margin-left: auto; font-weight: 600; }
.availability-cell { width: 100%; min-height: 60px; border: 0; background: transparent; cursor: pointer; }
.availability-cell.readonly { cursor: default; }
:deep(.status-content) { display: flex; flex-direction: column; align-items: center; gap: 4px; }
:deep(.status-content small) { color: var(--el-text-color-secondary); }
.editor { display: flex; flex-direction: column; gap: 10px; }
.editor-actions { text-align: right; }
.import-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 16px 0; }
.summary { color: var(--el-text-color-secondary); }
:global(.translator-import-dialog) { max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
:global(.translator-import-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.translator-import-dialog .el-dialog__footer) { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-extra-light); }
@media (max-width: 800px) { .week-label { width: 100%; margin-left: 0; } }
</style>
