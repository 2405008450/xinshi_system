<template>
  <div class="employee-shift-panel">
    <div class="toolbar">
      <el-select v-model="filters.department" clearable placeholder="选择部门" style="width: 150px" @change="onDepartmentChange">
        <el-option v-for="department in departments" :key="department" :label="department" :value="department" />
        <el-option label="未分部门" value="__unassigned__" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        clearable
        placeholder="姓名或用户名"
        style="width: 190px"
        @input="onKeywordInput"
        @clear="runQuery"
        @keyup.enter="runQuery"
      />
      <el-button type="primary" @click="runQuery">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <el-button v-if="!showAll" @click="showAllEmployees">展示全部</el-button>
      <el-button v-else @click="showDefaultEmployees">仅看本部门</el-button>
      <el-tag v-if="!showAll" type="info" effect="plain">
        仅显示{{ visibleScopeLabel }} · {{ employees.length }} 人
      </el-tag>
      <el-tag v-else type="warning" effect="plain">已展示全部员工 · {{ employees.length }} 人</el-tag>
      <div class="week-nav">
        <el-button @click="moveWeek(-7)">上一周</el-button>
        <el-button @click="moveWeek(0)">本周</el-button>
        <el-button @click="moveWeek(7)">下一周</el-button>
        <strong>{{ weekDates[0] }} 至 {{ weekDates[6] }}</strong>
      </div>
    </div>

    <div v-if="canEdit" class="batch-bar">
      <el-select v-model="batch.date" placeholder="选择日期" style="width: 205px">
        <el-option
          :label="`周一至周五 ${weekDates[0].slice(5)}～${weekDates[4].slice(5)}`"
          :value="WORKDAYS_VALUE"
        />
        <el-option v-for="(day, index) in weekDates" :key="day" :label="`${weekdayLabels[index]} ${day.slice(5)}`" :value="day" />
      </el-select>
      <el-select v-model="batch.shift_code" placeholder="批量班次" style="width: 210px" @change="applyBatchPreset">
        <el-option v-for="option in batchOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-time-select v-if="batch.shift_code === 'custom'" v-model="batch.start_time" start="06:00" step="00:15" end="23:45" placeholder="开始" />
      <el-time-select v-if="batch.shift_code === 'custom'" v-model="batch.end_time" start="06:00" step="00:15" end="23:45" placeholder="结束" />
      <el-input v-if="lockedSelectedRows.length" v-model="batch.note" placeholder="固定班次临时调整原因" style="width: 240px" />
      <el-button type="primary" :disabled="!selectedRows.length" :loading="saving" @click="saveBatch">批量设置</el-button>
    </div>

    <el-table :data="employees" row-key="user_id" border size="small" v-loading="loading" @selection-change="selectedRows = $event">
      <el-table-column v-if="canEdit" type="selection" width="46" fixed="left" />
      <el-table-column prop="name" label="员工" width="130" fixed="left" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.name }}</span>
          <el-tag v-if="row.is_locked" type="warning" size="small" effect="plain" class="fixed-tag">固定</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="department" label="部门" width="100" fixed="left">
        <template #default="{ row }">{{ row.department || '未分部门' }}</template>
      </el-table-column>
      <el-table-column v-for="(scheduleDay, index) in weekDates" :key="scheduleDay" :label="`${weekdayLabels[index]} ${scheduleDay.slice(5)}`" width="164">
        <template #default="{ row }">
          <button v-if="canEdit" class="shift-cell" type="button" @click="openCellEditor(row, scheduleDay)">
            <el-tag :type="tagType(dayOf(row, scheduleDay)?.shift_code)" size="small" effect="plain">
              {{ dayOf(row, scheduleDay)?.shift_label || '未安排' }}
            </el-tag>
            <small v-if="dayTime(dayOf(row, scheduleDay))">{{ dayTime(dayOf(row, scheduleDay)) }}</small>
            <small v-if="dayOf(row, scheduleDay)?.source === 'override'" class="override-mark">临时调整</small>
            <small v-if="dayOf(row, scheduleDay)?.on_leave" class="leave-mark">{{ dayOf(row, scheduleDay)?.leave_type || '请假' }}</small>
          </button>
          <div v-else class="shift-cell readonly">
            <el-tag :type="tagType(dayOf(row, scheduleDay)?.shift_code)" size="small" effect="plain">{{ dayOf(row, scheduleDay)?.shift_label || '未安排' }}</el-tag>
            <small v-if="dayTime(dayOf(row, scheduleDay))">{{ dayTime(dayOf(row, scheduleDay)) }}</small>
            <small v-if="dayOf(row, scheduleDay)?.on_leave" class="leave-mark">{{ dayOf(row, scheduleDay)?.leave_type || '请假' }}</small>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="canEdit" label="常规设置" width="100" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="openTemplate(row)">排班设置</el-button></template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="cellEditorVisible"
      :title="`${activeCell.row?.name || ''} · ${activeCell.date || ''} 班次调整`"
      width="min(420px, calc(100vw - 32px))"
      append-to-body
    >
      <div class="cell-editor">
        <el-alert
          v-if="activeCellDay?.is_locked"
          title="该员工为固定班次，本次保存将作为单日临时调整，不会修改常规模板。"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-checkbox v-if="activeCellDay?.is_locked" v-model="lockedOverrideConfirmed">确认为该日创建临时调整</el-checkbox>
        <el-select v-model="cellDraft.shift_code" style="width: 100%" @change="applyCellPreset">
          <el-option v-for="option in optionsForDate(activeCell.date)" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <div v-if="cellDraft.shift_code === 'custom'" class="custom-times">
          <el-time-select v-model="cellDraft.start_time" start="06:00" step="00:15" end="23:45" placeholder="开始" />
          <el-time-select v-model="cellDraft.end_time" start="06:00" step="00:15" end="23:45" placeholder="结束" />
        </div>
        <el-input v-model="cellDraft.note" :placeholder="activeCellDay?.is_locked ? '固定班次调整原因（必填）' : '临时调整备注（可选）'" />
      </div>
      <template #footer>
        <el-button
          v-if="activeCellDay?.source === 'override'"
          :loading="saving"
          @click="clearActiveOverride"
        >恢复模板</el-button>
        <el-button @click="cellEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveActiveCell">保存调整</el-button>
      </template>
    </el-dialog>

    <EmployeeShiftTemplateDialog
      v-model="templateVisible"
      :employee="templateEmployee"
      :reference-date="weekDates[0]"
      @saved="runQuery"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getEmployeeShifts, saveEmployeeShiftOverrides } from '@/api/schedule'
import { DEPARTMENT_NAMES } from '@/constants/departments'
import EmployeeShiftTemplateDialog from './EmployeeShiftTemplateDialog.vue'

const props = defineProps({ selectedDate: { type: String, default: '' }, canEdit: { type: Boolean, default: false } })
const emit = defineEmits(['update:selectedDate'])
const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const WORKDAYS_VALUE = '__workdays__'
const departments = DEPARTMENT_NAMES
const options = [
  { value: 'early_early', label: '早早班 08:30–18:00', start: '08:30', end: '18:00' },
  { value: 'early', label: '早班 09:00–18:30', start: '09:00', end: '18:30' },
  { value: 'late', label: '晚班 10:30–20:00', start: '10:30', end: '20:00' },
  { value: 'late_late', label: '晚晚班 13:30–21:30', start: '13:30', end: '21:30' },
  { value: 'weekend_duty', label: '周末值班 09:30–18:00', start: '09:30', end: '18:00' },
  { value: 'custom', label: '自定义时间' },
  { value: 'off', label: '休息' },
  { value: 'unassigned', label: '未安排' }
]
const loading = ref(false)
const saving = ref(false)
const cellEditorVisible = ref(false)
const employees = ref([])
const selectedRows = ref([])
const filters = reactive({ department: '', keyword: '' })
const showAll = ref(false)
const effectiveDepartment = ref('')
const currentUserOnly = ref(false)
const cellDraft = reactive({ shift_code: '', start_time: null, end_time: null, note: '' })
const activeCell = reactive({ row: null, date: '' })
const batch = reactive({ date: '', shift_code: '', start_time: null, end_time: null, note: '' })
const templateVisible = ref(false)
const templateEmployee = ref(null)
const lockedOverrideConfirmed = ref(false)
let debounceTimer = null
let controller = null
let requestSequence = 0

const weekDates = computed(() => {
  const base = props.selectedDate ? new Date(`${props.selectedDate}T00:00:00`) : new Date()
  const day = base.getDay() || 7
  base.setDate(base.getDate() - day + 1)
  return Array.from({ length: 7 }, (_, index) => {
    const value = new Date(base)
    value.setDate(base.getDate() + index)
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  })
})
const batchDates = computed(() => {
  if (batch.date === WORKDAYS_VALUE) return weekDates.value.slice(0, 5)
  return batch.date ? [batch.date] : []
})
const batchOptions = computed(() => optionsForDate(
  batch.date === WORKDAYS_VALUE ? weekDates.value[0] : (batch.date || weekDates.value[0])
))
const activeCellDay = computed(() => dayOf(activeCell.row, activeCell.date))
const lockedSelectedRows = computed(() => selectedRows.value.filter(row => (
  batchDates.value.some(scheduleDate => dayOf(row, scheduleDate)?.is_locked)
)))
const visibleScopeLabel = computed(() => {
  if (filters.department === '__unassigned__' || effectiveDepartment.value === '__unassigned__') return '未分部门'
  return effectiveDepartment.value || (currentUserOnly.value ? '本人' : '本部门')
})

function optionsForDate(value) {
  const weekend = value && [0, 6].includes(new Date(`${value}T00:00:00`).getDay())
  return options.filter(option => option.value !== 'weekend_duty' || weekend)
}
function dayOf(row, value) { return row?.dayMap?.[value] }
function dayTime(day) { return day?.start_time && day?.end_time ? `${day.start_time}–${day.end_time}` : '' }
function tagType(code) { return code === 'off' ? 'info' : code === 'unassigned' ? 'warning' : code === 'weekend_duty' ? 'danger' : 'success' }
function applyPreset(target) {
  const preset = options.find(item => item.value === target.shift_code)
  target.start_time = preset?.start || null
  target.end_time = preset?.end || null
}
function applyCellPreset() { applyPreset(cellDraft) }
function applyBatchPreset() { applyPreset(batch) }

async function loadData() {
  controller?.abort()
  controller = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const data = await getEmployeeShifts({
      date_from: weekDates.value[0], date_to: weekDates.value[6],
      department: filters.department || undefined,
      keyword: filters.keyword.trim() || undefined,
      show_all: showAll.value || undefined
    }, controller.signal)
    if (sequence === requestSequence) {
      selectedRows.value = []
      effectiveDepartment.value = data.effective_department || ''
      currentUserOnly.value = Boolean(data.current_user_only)
      employees.value = (data.employees || []).map(employee => ({
        ...employee,
        dayMap: Object.fromEntries((employee.days || []).map(day => [day.date, day]))
      }))
    }
  } catch (error) {
    if (error.code !== 'ERR_CANCELED' && sequence === requestSequence) ElMessage.error(error.detail || '读取员工排班失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
function runQuery() { clearTimeout(debounceTimer); loadData() }
function onKeywordInput(value) { clearTimeout(debounceTimer); if (!value) runQuery(); else debounceTimer = setTimeout(loadData, 400) }
function onDepartmentChange() { showAll.value = false; runQuery() }
function showAllEmployees() { showAll.value = true; filters.department = ''; runQuery() }
function showDefaultEmployees() { showAll.value = false; filters.department = ''; runQuery() }
function resetFilters() { showAll.value = false; filters.department = ''; filters.keyword = ''; runQuery() }
function moveWeek(offset) {
  const base = offset === 0 ? new Date() : new Date(`${weekDates.value[0]}T00:00:00`)
  if (offset) base.setDate(base.getDate() + offset)
  const value = `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, '0')}-${String(base.getDate()).padStart(2, '0')}`
  emit('update:selectedDate', value)
}
function openCellEditor(row, value) {
  const day = dayOf(row, value)
  activeCell.row = row
  activeCell.date = value
  Object.assign(cellDraft, { shift_code: day?.shift_code || 'unassigned', start_time: day?.start_time || null, end_time: day?.end_time || null, note: day?.note || '' })
  lockedOverrideConfirmed.value = false
  cellEditorVisible.value = true
}
function validateCustom(target) { return target.shift_code !== 'custom' || (target.start_time && target.end_time && target.end_time > target.start_time) }
async function saveItems(items) {
  saving.value = true
  try {
    await saveEmployeeShiftOverrides(items)
    ElMessage.success('排班调整已保存')
    await loadData()
    return true
  } catch (error) {
    ElMessage.error(error.detail || '保存排班调整失败')
    return false
  } finally { saving.value = false }
}
async function saveActiveCell() {
  if (!validateCustom(cellDraft)) return ElMessage.warning('自定义班次的结束时间必须晚于开始时间')
  if (activeCellDay.value?.is_locked && !lockedOverrideConfirmed.value) return ElMessage.warning('请先确认本次为单日临时调整')
  if (activeCellDay.value?.is_locked && !cellDraft.note.trim()) return ElMessage.warning('临时调整固定班次必须填写原因')
  const saved = await saveItems([{
    user_id: activeCell.row.user_id,
    schedule_date: activeCell.date,
    action: 'set',
    override_locked: Boolean(activeCellDay.value?.is_locked),
    ...cellDraft
  }])
  if (saved) cellEditorVisible.value = false
}
async function clearActiveOverride() {
  const saved = await saveItems([{ user_id: activeCell.row.user_id, schedule_date: activeCell.date, action: 'clear', shift_code: 'unassigned' }])
  if (saved) cellEditorVisible.value = false
}
async function saveBatch() {
  if (!batch.date || !batch.shift_code) return ElMessage.warning('请选择日期和班次')
  if (!selectedRows.value.length) return ElMessage.warning('请先勾选需要批量设置的员工')
  if (!validateCustom(batch)) return ElMessage.warning('自定义班次的结束时间必须晚于开始时间')
  if (lockedSelectedRows.value.length && !batch.note.trim()) return ElMessage.warning('批量调整包含固定班次员工，请填写调整原因')
  if (lockedSelectedRows.value.length) {
    const names = lockedSelectedRows.value.map(row => row.name).join('、')
    const dateLabel = batch.date === WORKDAYS_VALUE ? '周一至周五' : '所选日期'
    try {
      await ElMessageBox.confirm(`本次批量调整包含固定班次员工：${names}。将为${dateLabel}创建临时调整，是否继续？`, '确认调整固定班次', {
        confirmButtonText: '继续调整', cancelButtonText: '取消', type: 'warning'
      })
    } catch { return }
  }
  await saveItems(selectedRows.value.flatMap(row => batchDates.value.map(scheduleDate => ({
    user_id: row.user_id,
    schedule_date: scheduleDate,
    action: 'set',
    shift_code: batch.shift_code,
    start_time: batch.start_time,
    end_time: batch.end_time,
    note: batch.note || undefined,
    override_locked: Boolean(dayOf(row, scheduleDate)?.is_locked)
  }))))
}
function openTemplate(row) { templateEmployee.value = row; templateVisible.value = true }

watch(() => props.selectedDate, loadData)
watch(() => batch.date, value => {
  if (value === WORKDAYS_VALUE && batch.shift_code === 'weekend_duty') {
    Object.assign(batch, { shift_code: '', start_time: null, end_time: null })
  } else if (value && [0, 6].includes(new Date(`${value}T00:00:00`).getDay())) {
    batch.shift_code = 'weekend_duty'
    applyBatchPreset()
  }
})
onMounted(() => { batch.date = weekDates.value[0]; loadData() })
onBeforeUnmount(() => { clearTimeout(debounceTimer); controller?.abort() })
</script>

<style scoped>
.toolbar, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.week-nav { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.batch-bar { padding: 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-extra-light); }
.shift-cell { width: 100%; min-height: 58px; padding: 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; border: 0; background: transparent; cursor: pointer; }
.shift-cell.readonly { cursor: default; }
.shift-cell small { color: var(--el-text-color-secondary); }
.shift-cell .override-mark { color: var(--el-color-warning); }
.shift-cell .leave-mark { color: var(--el-color-danger); font-weight: 600; }
.fixed-tag { margin-left: 4px; }
.cell-editor { display: flex; flex-direction: column; gap: 10px; }
.custom-times { display: flex; gap: 8px; }
@media (max-width: 900px) { .week-nav { width: 100%; margin-left: 0; } }
</style>
