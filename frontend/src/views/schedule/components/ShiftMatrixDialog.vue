<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="shift-matrix-host"
      :class="{ 'is-modal': !pinned, 'is-pinned': pinned, 'is-collapsed': collapsed }"
      @mousedown.self="handleBackdropClick"
    >
      <el-button
        v-if="pinned && collapsed"
        type="primary"
        class="collapsed-trigger"
        @click="collapsed = false"
      >
        班次矩阵
        <el-badge v-if="onLeaveCount" :value="onLeaveCount" type="danger" />
      </el-button>

      <section
        v-else
        class="shift-matrix-window"
        role="dialog"
        :aria-modal="pinned ? 'false' : 'true'"
        aria-labelledby="shift-matrix-title"
      >
        <header class="window-header">
          <div class="window-heading">
            <strong id="shift-matrix-title">{{ dialogTitle }}</strong>
            <small>{{ pinned ? '已固定，可继续操作工作台' : '部门排班与公司请假' }}</small>
          </div>
          <div class="window-actions">
            <el-tooltip v-if="canPin && !pinned" content="固定到右侧" placement="bottom">
              <el-button :icon="Lock" circle aria-label="固定到右侧" @click="setPinned(true)" />
            </el-tooltip>
            <el-tooltip v-if="pinned" content="收起固定面板" placement="bottom">
              <el-button :icon="Minus" circle aria-label="收起固定面板" @click="collapsed = true" />
            </el-tooltip>
            <el-tooltip v-if="pinned" content="解除固定" placement="bottom">
              <el-button :icon="Unlock" circle aria-label="解除固定" @click="setPinned(false)" />
            </el-tooltip>
            <el-tooltip content="关闭" placement="bottom">
              <el-button :icon="Close" circle aria-label="关闭班次矩阵" @click="closePanel" />
            </el-tooltip>
          </div>
        </header>

        <div class="window-body">
          <el-tabs v-model="activeTab" class="shift-matrix-tabs">
            <el-tab-pane label="部门班次矩阵" name="matrix">
              <div class="matrix-toolbar">
                <div class="scope-search">
                  <el-select
                    v-model="scope"
                    size="small"
                    aria-label="排班查看范围"
                    popper-class="shift-matrix-scope-popper"
                    @change="runQuery"
                  >
                    <el-option label="本部门" value="__default__" />
                    <el-option
                      v-for="option in departmentOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                    <el-option label="全公司" value="__all__" />
                  </el-select>
                  <el-input
                    v-model="keyword"
                    size="small"
                    clearable
                    aria-label="搜索排班员工"
                    placeholder="姓名或用户名"
                    :prefix-icon="Search"
                    @input="onKeywordInput"
                    @keyup.enter="runQuery"
                  />
                  <el-button size="small" type="primary" @click="runQuery">查询</el-button>
                </div>

                <div class="week-nav">
                  <el-button size="small" @click="moveWeek(-7)">上一周</el-button>
                  <el-button size="small" @click="moveWeek(0)">本周</el-button>
                  <el-button size="small" @click="moveWeek(7)">下一周</el-button>
                  <strong class="week-range">{{ weekDates[0] }} 至 {{ weekDates[6] }}</strong>
                  <el-button
                    v-if="isCurrentWeek && pastDayCount"
                    size="small"
                    link
                    type="primary"
                    class="past-days-toggle"
                    @click="showPastDays = !showPastDays"
                  >
                    {{ showPastDays ? '隐藏已过日期' : `显示已过 ${pastDayCount} 天` }}
                  </el-button>
                  <el-tag v-if="scopeLabel" size="small" type="info" effect="plain" class="dept-tag">
                    {{ scopeLabel }} · {{ employees.length }} 人
                  </el-tag>
                </div>
              </div>

              <div v-loading="loading" class="matrix-body">
                <el-table
                  v-if="employees.length"
                  :data="employees"
                  border
                  size="small"
                  max-height="520"
                  class="data-table matrix-table"
                  :row-class-name="rowClassName"
                >
                  <el-table-column prop="name" label="员工" width="132" fixed="left" show-overflow-tooltip>
                    <template #default="{ row }">
                      <div class="employee-cell">
                        <div>
                          <span>{{ row.name }}</span>
                          <el-tag v-if="isMe(row)" size="small" type="primary" effect="plain" class="me-tag">我</el-tag>
                          <el-tag v-else-if="row.is_locked" size="small" type="warning" effect="plain" class="me-tag">固定</el-tag>
                        </div>
                        <small v-if="scope === '__all__'">{{ row.department || '未分部门' }}</small>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column
                    v-for="date in visibleDates"
                    :key="date"
                    :label="`${weekdayLabel(date)} ${date.slice(5)}`"
                    min-width="118"
                    :class-name="isToday(date) ? 'is-today-col' : ''"
                  >
                    <template #default="{ row }">
                      <div class="shift-cell" :class="{ 'is-today': isToday(date) }">
                        <el-tag :type="tagType(dayOf(row, date)?.shift_code)" size="small" effect="plain">
                          {{ dayOf(row, date)?.shift_label || '未安排' }}
                        </el-tag>
                        <small v-if="dayTime(dayOf(row, date))">{{ dayTime(dayOf(row, date)) }}</small>
                        <small v-if="dayOf(row, date)?.source === 'override'" class="override-mark">临时调整</small>
                        <small v-if="dayOf(row, date)?.on_leave" class="leave-mark">
                          {{ dayOf(row, date)?.leave_type || '请假' }}
                        </small>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else-if="!loading" class="empty-tip">当前范围暂无员工排班。</div>
              </div>
            </el-tab-pane>

            <el-tab-pane :label="`公司请假（未来30天 · ${leaveRecords.length}）`" name="leave">
              <el-table
                v-if="leaveRecords.length"
                :data="leaveRecords"
                border
                size="small"
                class="data-table leave-table"
                max-height="520"
              >
                <el-table-column prop="employee_name" label="员工" width="120" />
                <el-table-column label="部门" width="130">
                  <template #default="{ row }">{{ row.department || '-' }}</template>
                </el-table-column>
                <el-table-column label="开始时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
                </el-table-column>
                <el-table-column label="结束时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
                </el-table-column>
                <el-table-column prop="leave_type" label="请假类型" width="110" />
                <el-table-column label="状态" width="96">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'active' ? 'danger' : 'warning'" size="small">
                      {{ row.status === 'active' ? '请假中' : '即将请假' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="reason" label="原因" min-width="170" show-overflow-tooltip />
              </el-table>
              <div v-else class="empty-tip">未来 30 天暂无请假记录。</div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, Lock, Minus, Search, Unlock } from '@element-plus/icons-vue'
import { getEmployeeShifts } from '@/api/schedule'
import { getLeaveOverview } from '@/api/leave'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  referenceDate: { type: String, default: '' },
  onLeaveCount: { type: Number, default: 0 }
})
const emit = defineEmits(['update:modelValue'])

const weekdayLabels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

const activeTab = ref('matrix')
const loading = ref(false)
const employees = ref([])
const leaveRecords = ref([])
const departmentOptions = ref([])
const effectiveDepartment = ref('')
const currentUserOnly = ref(false)
const weekAnchor = ref('')
const scope = ref('__default__')
const keyword = ref('')
const showPastDays = ref(false)
const pinned = ref(false)
const collapsed = ref(false)
const canPin = ref(typeof window !== 'undefined' ? window.innerWidth >= 900 : true)
const currentUserId = (() => {
  try {
    return String(localStorage.getItem('user_id') || '')
  } catch {
    return ''
  }
})()

let debounceTimer = null
let controller = null
let requestSequence = 0
let leaveRequestSequence = 0
let desktopMedia = null

const dialogTitle = computed(() => {
  const base = '班次与请假'
  return props.onLeaveCount ? `${base} · 今日请假 ${props.onLeaveCount} 人` : base
})

const weekDates = computed(() => {
  const base = weekAnchor.value ? new Date(`${weekAnchor.value}T00:00:00`) : new Date()
  const day = base.getDay() || 7
  base.setDate(base.getDate() - day + 1)
  return Array.from({ length: 7 }, (_, index) => {
    const value = new Date(base)
    value.setDate(base.getDate() + index)
    return formatDate(value)
  })
})

const todayValue = computed(() => formatDate(new Date()))
const currentWeekMonday = computed(() => {
  const today = new Date(`${todayValue.value}T00:00:00`)
  const day = today.getDay() || 7
  today.setDate(today.getDate() - day + 1)
  return formatDate(today)
})
const isCurrentWeek = computed(() => weekDates.value[0] === currentWeekMonday.value)
const pastDayCount = computed(() => (
  isCurrentWeek.value ? weekDates.value.filter(date => date < todayValue.value).length : 0
))
const visibleDates = computed(() => {
  if (!isCurrentWeek.value || showPastDays.value) return weekDates.value
  return weekDates.value.filter(date => date >= todayValue.value)
})
const scopeLabel = computed(() => {
  if (scope.value === '__all__') return '全公司'
  if (scope.value === '__unassigned__') return '未分部门'
  if (scope.value !== '__default__') {
    return departmentOptions.value.find(option => option.value === scope.value)?.label || scope.value
  }
  if (effectiveDepartment.value === '__unassigned__') return '未分部门'
  return effectiveDepartment.value || (currentUserOnly.value ? '仅本人' : '本部门')
})

function formatDate(value) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}

function weekdayLabel(value) {
  const date = new Date(`${value}T00:00:00`)
  return weekdayLabels[date.getDay()] || ''
}

function dayOf(row, date) { return row?.dayMap?.[date] }
function dayTime(day) { return day?.start_time && day?.end_time ? `${day.start_time}–${day.end_time}` : '' }
function tagType(code) {
  return code === 'off' ? 'info' : code === 'unassigned' ? 'warning' : code === 'weekend_duty' ? 'danger' : 'success'
}
function isMe(row) { return String(row?.user_id) === currentUserId }
function isToday(date) { return date === todayValue.value }
function rowClassName({ row }) { return isMe(row) ? 'is-me-row' : '' }

function moveWeek(offset) {
  const base = offset === 0 ? new Date() : new Date(`${weekDates.value[0]}T00:00:00`)
  if (offset) base.setDate(base.getDate() + offset)
  weekAnchor.value = formatDate(base)
  loadMatrix()
}

function queryParams() {
  const params = {
    date_from: weekDates.value[0],
    date_to: weekDates.value[6],
    keyword: keyword.value.trim() || undefined
  }
  if (scope.value === '__all__') {
    params.show_all = true
  } else if (scope.value !== '__default__') {
    params.department = scope.value
  }
  return params
}

async function loadMatrix() {
  controller?.abort()
  controller = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const data = await getEmployeeShifts(queryParams(), controller.signal)
    if (sequence !== requestSequence) return
    departmentOptions.value = Array.isArray(data.department_options) ? data.department_options : []
    effectiveDepartment.value = data.effective_department || ''
    currentUserOnly.value = Boolean(data.current_user_only)
    const meFirst = (data.employees || []).map(employee => ({
      ...employee,
      dayMap: Object.fromEntries((employee.days || []).map(day => [day.date, day]))
    }))
    meFirst.sort((a, b) => Number(isMe(b)) - Number(isMe(a)))
    employees.value = meFirst
  } catch (error) {
    if (error.code !== 'ERR_CANCELED' && sequence === requestSequence) {
      employees.value = []
      ElMessage.error(error.detail || '读取员工班次失败')
    }
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function runQuery() {
  clearTimeout(debounceTimer)
  loadMatrix()
}

function onKeywordInput(value) {
  clearTimeout(debounceTimer)
  if (!value) {
    loadMatrix()
    return
  }
  debounceTimer = setTimeout(loadMatrix, 400)
}

function formatDateTimeValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

async function loadLeave() {
  const sequence = ++leaveRequestSequence
  const now = new Date()
  const nextMonth = new Date(now)
  nextMonth.setMonth(nextMonth.getMonth() + 1)
  try {
    const res = await getLeaveOverview({
      start_date: formatDateTimeValue(now),
      end_date: formatDateTimeValue(nextMonth)
    })
    if (sequence === leaveRequestSequence) {
      leaveRecords.value = Array.isArray(res) ? res : []
    }
  } catch {
    if (sequence === leaveRequestSequence) leaveRecords.value = []
  }
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function syncBodyScroll() {
  if (typeof document === 'undefined') return
  document.body.classList.toggle('shift-matrix-modal-open', visible.value && !pinned.value)
}

function setPinned(value) {
  if (value && !canPin.value) return
  pinned.value = value
  collapsed.value = false
  syncBodyScroll()
}

function closePanel() {
  clearTimeout(debounceTimer)
  controller?.abort()
  visible.value = false
}

function handleBackdropClick() {
  if (!pinned.value) closePanel()
}

function handleKeydown(event) {
  if (event.key === 'Escape' && visible.value && !pinned.value) closePanel()
}

function handleDesktopChange(event) {
  canPin.value = event.matches
  if (!event.matches && pinned.value) setPinned(false)
}

function onOpen() {
  activeTab.value = 'matrix'
  weekAnchor.value = props.referenceDate || formatDate(new Date())
  scope.value = '__default__'
  keyword.value = ''
  showPastDays.value = false
  pinned.value = false
  collapsed.value = false
  loadMatrix()
  loadLeave()
}

watch(() => props.modelValue, value => {
  if (value) onOpen()
  else {
    pinned.value = false
    collapsed.value = false
  }
  syncBodyScroll()
}, { immediate: true })

onMounted(() => {
  desktopMedia = window.matchMedia('(min-width: 900px)')
  canPin.value = desktopMedia.matches
  desktopMedia.addEventListener('change', handleDesktopChange)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  controller?.abort()
  leaveRequestSequence += 1
  desktopMedia?.removeEventListener('change', handleDesktopChange)
  window.removeEventListener('keydown', handleKeydown)
  document.body.classList.remove('shift-matrix-modal-open')
})
</script>

<style scoped>
.shift-matrix-host {
  position: fixed;
  inset: 0;
  z-index: 2200;
}

:global(.shift-matrix-scope-popper) {
  z-index: 2300 !important;
}

.shift-matrix-host.is-modal {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 5vh 16px 16px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(1px);
}

.shift-matrix-host.is-pinned {
  pointer-events: none;
}

.shift-matrix-window {
  display: flex;
  flex-direction: column;
  width: min(1080px, calc(100vw - 32px));
  max-height: 90vh;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
  pointer-events: auto;
}

.is-pinned .shift-matrix-window {
  position: absolute;
  top: 72px;
  right: 12px;
  bottom: 12px;
  width: clamp(560px, 48vw, 920px);
  max-height: none;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: -10px 12px 36px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(12px);
}

.window-header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.window-heading {
  display: grid;
  gap: 2px;
}

.window-heading strong {
  color: var(--el-text-color-primary);
  font-size: 17px;
}

.window-heading small {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.window-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.window-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.window-body {
  flex: 1;
  min-height: 0;
  padding: 6px 14px 14px;
  overflow: auto;
}

.shift-matrix-tabs :deep(.el-tabs__header) {
  margin-bottom: 10px;
}

.matrix-toolbar {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}

.scope-search,
.week-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.scope-search :deep(.el-select) {
  width: 150px;
}

.scope-search :deep(.el-input) {
  width: 190px;
}

.week-range {
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.past-days-toggle {
  padding-inline: 2px;
}

.dept-tag {
  margin-left: auto;
}

.matrix-body {
  min-height: 120px;
  max-width: 100%;
  overflow: hidden;
}

.employee-cell {
  display: grid;
  gap: 2px;
}

.employee-cell small {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.me-tag {
  margin-left: 4px;
}

.shift-cell {
  display: flex;
  min-height: 54px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 2px 0;
}

.shift-cell small {
  color: var(--el-text-color-secondary);
}

.shift-cell .override-mark {
  color: var(--el-color-warning);
}

.shift-cell .leave-mark {
  color: var(--el-color-danger);
  font-weight: 600;
}

.shift-cell.is-today {
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
}

.data-table {
  width: 100%;
  margin-bottom: 4px;
}

.empty-tip {
  padding: 28px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
}

.matrix-body :deep(.el-table__empty-block) {
  min-height: 48px;
}

.matrix-body :deep(.is-me-row) {
  background: var(--el-color-primary-light-9);
}

.matrix-body :deep(.is-today-col) {
  background: var(--el-fill-color-lighter);
}

.collapsed-trigger {
  position: fixed;
  top: 116px;
  right: 0;
  min-height: 44px;
  border-radius: 8px 0 0 8px;
  pointer-events: auto;
  box-shadow: -4px 6px 18px rgba(15, 23, 42, 0.18);
}

.collapsed-trigger :deep(.el-badge) {
  margin-left: 6px;
}

@media (max-width: 899px) {
  .shift-matrix-host.is-modal {
    padding: 8px;
  }

  .shift-matrix-window {
    width: calc(100vw - 16px);
    max-height: calc(100vh - 16px);
  }

  .window-header {
    padding: 10px 12px;
  }

  .window-body {
    padding: 4px 10px 10px;
  }

  .scope-search :deep(.el-select),
  .scope-search :deep(.el-input) {
    width: calc(50% - 4px);
    min-width: 140px;
  }

  .week-range {
    width: 100%;
  }

  .dept-tag {
    margin-left: 0;
  }
}

@media (max-width: 520px) {
  .window-heading small {
    display: none;
  }

  .scope-search :deep(.el-select),
  .scope-search :deep(.el-input) {
    width: 100%;
  }
}
</style>

<style>
body.shift-matrix-modal-open {
  overflow: hidden;
}
</style>
