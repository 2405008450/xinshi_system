<template>
  <DraggableFormDialog v-model="visible" :title="`${entryState} · 跨日期开拓记录`" width="min(1380px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="development-status-dialog" @close="stopRequests">
    <div class="status-filter-area">
      <div class="development-filters">
        <el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期（全部日期）" end-placeholder="结束日期" clearable @change="query" />
        <el-input v-model="filters.keyword" clearable placeholder="姓名、招呼编号、联系方式、语种/方言、开拓平台" @input="keywordChanged" @keyup.enter="query" />
        <el-select v-model="filters.state" clearable filterable allow-create aria-label="添加状态（任一渠道）" placeholder="添加状态（任一渠道）" @change="query"><el-option v-for="state in statusOptions" :key="state" :label="state" :value="state" /></el-select>
        <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
        <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="development-advanced development-status-advanced">
          <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
          <div ref="advancedBody" class="development-advanced-body">
            <div class="development-form-grid">
              <div v-for="condition in advancedConditions" :key="condition.key"><label>{{ condition.label }}</label><el-select v-model="filters[condition.key]" clearable filterable :append-to="advancedBody?.parentElement" :aria-label="condition.label" @change="commonChanged(condition.key)"><el-option v-for="option in condition.options" :key="option.id" :label="option.name" :value="option.id" /></el-select></div>
            </div>
            <div class="development-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div>
          </div>
        </el-popover>
        <el-popover trigger="click" placement="bottom-end" :width="280" popper-class="development-status-columns">
          <template #reference><el-button>字段设置</el-button></template>
          <div class="development-column-options"><el-checkbox-group v-model="selectedColumns"><el-checkbox v-for="column in developmentColumns" :key="column.key" :value="column.key">{{ column.label }}</el-checkbox></el-checkbox-group></div>
          <el-button text type="primary" @click="selectedColumns = [...defaultColumns]">恢复默认</el-button>
        </el-popover>
      </div>
      <div class="development-actions status-shortcuts"><span class="muted">开拓日期：{{ filters.range?.length ? filters.range.join(' 至 ') : '全部日期' }}</span><el-tooltip v-for="shortcut in developmentDateShortcuts" :key="shortcut.key" :content="shortcut.hint"><el-button size="small" @click="chooseRange(shortcut.key)">{{ shortcut.label }}</el-button></el-tooltip></div>
      <div v-if="activeColumnKeys.length" class="development-actions status-column-tags"><el-tag v-for="key in activeColumnKeys" :key="key" closable @close="delete columnFilters[key]; query()">{{ developmentColumns.find(column => column.key === key)?.label }}：已筛选</el-tag><el-button link @click="clearColumns">清空列筛选</el-button></div>
    </div>
    <div class="status-records-area">
      <DevelopmentRecordsTable ref="tableRef" :rows="rows" :options="options" :selected-columns="selectedColumns" :column-filters="columnFilters" :page="page" :page-size="pageSize" :loading="loading" height="100%" cross-date
        @column-filter="setColumnFilter" @text-input="columnTextInput" @query="query" @edit="(row, channel, status) => $emit('edit', row, channel, status)" @saved="$emit('saved')" />
    </div>
    <template #footer><div class="status-records-footer"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next, jumper" @size-change="sizeChanged" @current-change="pageChanged" /><el-button @click="visible = false">关闭</el-button></div></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DevelopmentRecordsTable from './DevelopmentRecordsTable.vue'
import { useDevelopmentFilters } from '@/composables/useDevelopmentFilters'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { developmentColumns, defaultDevelopmentColumns, cleanColumns, statusOptions, developmentDateShortcuts, developmentDateRange } from '@/utils/resourceDevelopment'

const props = defineProps({ options: { type: Object, required: true } })
defineEmits(['edit', 'saved'])
const visible = ref(false), entryState = ref('未处理'), advanced = ref(false), tableRef = ref()
// 下拉浮层属于高级筛选；使用挂载后的实际节点，避免目标尚未挂载或误判为外部点击。
const advancedBody = ref()
const rows = ref([]), total = ref(0), page = ref(1), pageSize = ref(10), loading = ref(false)
const { filters, columnFilters, activeColumnKeys, params, setColumnFilter, clearCommonColumn, resetFilters } = useDevelopmentFilters()
const defaultColumns = [...defaultDevelopmentColumns, 'work_date'], selectedColumns = ref([...defaultColumns])
const columnKey = () => `resource-development:status-records:columns:${props.options.user_id}`
const advancedConditions = computed(() => [
  { key: 'owner_id', label: '开拓人员', options: props.options.users },
  { key: 'platform_id', label: '开拓平台', options: props.options.options.filter(option => option.kind === 'platform') },
  { key: 'account_id', label: '交换账号', options: props.options.options.filter(option => option.kind === 'account') },
])
const advancedCount = computed(() => advancedConditions.value.filter(condition => filters[condition.key]).length)
watch(selectedColumns, value => { if (props.options.user_id) localStorage.setItem(columnKey(), JSON.stringify(value)) }, { deep: true })
let controller, sequence = 0, timer
function stopRequests() {
  clearTimeout(timer); controller?.abort(); sequence++; loading.value = false; advanced.value = false
  tableRef.value?.invalidateDetails()
}
async function reload() {
  if (!visible.value) return
  clearTimeout(timer); controller?.abort()
  const current = ++sequence
  controller = new AbortController(); loading.value = true
  tableRef.value?.invalidateDetails()
  try {
    const data = await api.records({ ...params(), skip: (page.value - 1) * pageSize.value, limit: pageSize.value }, controller.signal)
    if (current !== sequence) return
    total.value = data.total
    const last = Math.max(1, Math.ceil(data.total / pageSize.value))
    if (page.value > last) { page.value = last; return reload() }
    rows.value = data.items
  } catch (error) {
    if (current === sequence && !['ERR_CANCELED', 'CanceledError', 'AbortError'].includes(error.code || error.name)) ElMessage.error(error.message)
  } finally { if (current === sequence) loading.value = false }
}
function query() { page.value = 1; rows.value = []; total.value = 0; reload() }
function keywordChanged(value) {
  clearTimeout(timer); controller?.abort(); sequence++
  if (!value) query()
  else timer = setTimeout(query, 400)
}
function columnTextInput(key, value) { setColumnFilter(key, value); keywordChanged(value) }
function commonChanged(key) { clearCommonColumn(key); query() }
function clearColumns() { Object.keys(columnFilters).forEach(key => delete columnFilters[key]); query() }
function clearAdvanced() { advancedConditions.value.forEach(condition => { filters[condition.key] = '' }); query() }
function reset() { resetFilters(); query() }
function chooseRange(key) { filters.range = developmentDateRange(key); query() }
function pageChanged() { rows.value = []; reload() }
function sizeChanged() { page.value = 1; pageChanged() }
async function open(state) {
  stopRequests(); resetFilters(state); entryState.value = state; page.value = 1; pageSize.value = 10; rows.value = []; total.value = 0
  try {
    const raw = localStorage.getItem(columnKey())
    const saved = raw ? JSON.parse(raw) : null
    if (raw && !Array.isArray(saved)) localStorage.removeItem(columnKey())
    selectedColumns.value = cleanColumns(saved, defaultColumns)
  } catch {
    localStorage.removeItem(columnKey()); selectedColumns.value = [...defaultColumns]
  }
  visible.value = true
  await nextTick(); await reload()
}
onBeforeUnmount(stopRequests)
defineExpose({ open, reload })
</script>

<style>
.development-status-dialog{display:flex;flex-direction:column;height:90vh;max-height:90vh;overflow:hidden}
.development-status-dialog>.el-dialog__header,.development-status-dialog>.el-dialog__footer{flex:none}
.development-status-dialog>.el-dialog__body{display:flex;flex:1;min-height:0;flex-direction:column;overflow:hidden;padding-top:0}
.development-status-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:#f8fafc;padding:12px 16px}
.status-filter-area{flex:none;max-height:45vh;overflow-y:auto;padding-bottom:12px}
.development-status-dialog .development-filters{margin:8px 0 12px;gap:8px}
.development-status-dialog .development-filters>.el-input{width:270px}
.development-status-dialog .development-filters>.el-select{width:175px}
.status-shortcuts,.status-column-tags{gap:8px;margin-top:10px}
.status-shortcuts .el-button+.el-button{margin-left:0}
.status-records-area{flex:1;min-height:0}
.status-records-footer{display:flex;align-items:center;justify-content:space-between;gap:12px}
.status-records-footer>.el-pagination{min-width:0;max-width:100%;overflow-x:auto;margin:0}
.development-status-dialog .muted{color:var(--el-text-color-secondary);font-size:13px}
.development-status-columns{max-width:calc(100vw - 32px)!important}
@media(max-width:700px){.development-status-dialog .development-filters>.el-input,.development-status-dialog .development-filters>.el-select{width:100%}.status-records-footer{align-items:flex-end}.status-records-footer>.el-pagination{flex:1}}
</style>
