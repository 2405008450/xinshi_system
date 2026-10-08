<template>
  <el-card class="resource-development-page">
    <div class="development-heading"><div><h2>资源开拓</h2><span class="muted">按日期记录开拓与跟进，添加成功后关联人才总库</span></div><div class="development-actions">
      <el-popover trigger="click" placement="bottom-end" :width="280"><template #reference><el-button>字段设置</el-button></template><div class="development-column-options"><el-checkbox-group v-model="selectedColumns"><el-checkbox v-for="c in developmentColumns" :key="c.key" :value="c.key">{{ c.label }}</el-checkbox></el-checkbox-group></div><el-button text type="primary" @click="selectedColumns = [...defaultDevelopmentColumns]">恢复默认</el-button></el-popover>
      <el-button v-if="!deleteMode" @click="friendPanelRef.open(activeDay || filters.range?.[1])">新增统计</el-button><template v-if="options.can_write"><template v-if="!deleteMode"><el-button @click="settingsRef.open()">平台与选项</el-button><el-button @click="openWork()">每日工作</el-button><el-button type="primary" @click="openEditor()">新增</el-button></template><BatchDeleteToolbar :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /></template>
    </div></div>
    <TalentResourceNav />
    <div class="development-filters">
      <el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" clearable @change="query" />
      <el-input v-model="filters.keyword" clearable placeholder="姓名、招呼编号、联系方式、语种/方言、开拓平台" @input="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.owner_id" clearable filterable placeholder="开拓人员" @change="commonChanged('owner_id')"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="development-advanced"><template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template><div class="development-advanced-body"><div class="development-form-grid"><div><label>开拓平台</label><el-select v-model="filters.platform_id" clearable filterable @change="commonChanged('platform_id')"><el-option v-for="p in platforms" :key="p.id" :label="p.name" :value="p.id" /></el-select></div><div><label>交换账号</label><el-select v-model="filters.account_id" clearable filterable @change="commonChanged('account_id')"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></div><div><label>添加状态（任一渠道）</label><el-select v-model="filters.state" clearable filterable allow-create @change="query"><el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" /></el-select></div></div><div class="development-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div></div></el-popover>
      <div v-if="!deleteMode" class="development-status-entry"><el-button @click="statusRecordsRef.open('未处理')">未处理</el-button><el-button @click="statusRecordsRef.open('一次请求')">一次请求</el-button></div>
    </div>
    <div class="development-actions" v-if="activeColumnKeys.length"><el-tag v-for="key in activeColumnKeys" :key="key" closable @close="delete columnFilters[key]; query()">{{ developmentColumns.find(c => c.key === key)?.label }}：已筛选</el-tag><el-button link @click="clearColumns">清空列筛选</el-button></div>
    <DevelopmentFriendDailyPanel ref="friendPanelRef" />
    <div v-loading="loading">
      <el-empty v-if="!days.length" :description="filters.range?.length ? '所选日期暂无开拓记录，可调整或清空日期查询历史数据' : '暂无符合条件的开拓记录'" />
      <el-collapse v-model="activeDay" accordion @change="changeDay">
        <el-collapse-item v-for="day in days" :key="day.date" :name="day.date"><template #title><el-button link type="primary" :aria-label="`${chineseDate(day.date)}新增微信/企微好友统计`" @click.stop="friendPanelRef.open(day.date)">{{ chineseDate(day.date) }}</el-button><el-tag class="day-count" effect="plain">{{ day.count }} 条开拓记录</el-tag></template>
          <template v-if="activeDay === day.date">
            <div class="people-summary">
              <span>{{ day.people.length }} 位开拓人 · {{ day.count }} 条记录 · {{ day.people.reduce((n,p) => n + p.duration_minutes, 0) }} 分钟（人员当日总工时）</span>
            </div>
            <div class="development-pagination"><span class="muted">当日开拓记录</span><el-pagination v-model:current-page="recordPage" v-model:page-size="recordPageSize" :page-sizes="[10, 20, 50, 100]" :total="recordTotal" layout="total, sizes, prev, pager, next, jumper" @size-change="recordSizeChanged" @current-change="recordPageChanged" /></div>
            <DevelopmentRecordsTable :ref="setTableRef" :rows="rows" :loading="recordsLoading" :options="options" :selected-columns="selectedColumns" :column-filters="columnFilters" :page="recordPage" :page-size="recordPageSize" :delete-mode="deleteMode"
              @selection-change="handleDeleteSelectionChange" @column-filter="setColumnFilter" @text-input="columnTextInput" @query="query" @edit="openEditor" @saved="recordSaved" @platform="id => settingsRef.edit(platforms.find(p => p.id === id))" @work="openWork" @statistic="day => friendPanelRef.open(day)" />
            <el-pagination v-model:current-page="recordPage" :page-size="recordPageSize" :total="recordTotal" layout="total, prev, pager, next" @current-change="recordPageChanged" />
          </template>
        </el-collapse-item>
      </el-collapse>
      <div v-if="dayTotal > 3" class="development-pagination development-day-pagination">
        <span class="muted">共 {{ dayTotal }} 个日期</span>
        <div class="development-day-controls">
          <el-select v-model="dayPageSize" aria-label="每页显示日期数" @change="daySizeChanged">
            <el-option v-for="size in [3, 7, 14, 31]" :key="size" :label="`${size} 天/页`" :value="size" />
          </el-select>
          <el-pagination v-model:current-page="dayPage" :page-size="dayPageSize" :total="dayTotal" layout="prev, pager, next" :pager-count="5" @current-change="dayPageChanged" />
        </div>
      </div>
    </div>
    <DevelopmentStatusRecordsDialog ref="statusRecordsRef" :options="options" @edit="openEditor" @saved="recordSaved" />
    <DevelopmentRecordEditor ref="editorRef" :options="options" @saved="recordSaved" />
    <DevelopmentWorkEditor ref="workRef" :options="options" @saved="reload" />
    <DevelopmentSettings ref="settingsRef" :options="options" @saved="loadOptions" />
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TalentResourceNav from './components/TalentResourceNav.vue'
import DevelopmentFriendDailyPanel from './components/DevelopmentFriendDailyPanel.vue'
import DevelopmentRecordEditor from './components/DevelopmentRecordEditor.vue'
import DevelopmentWorkEditor from './components/DevelopmentWorkEditor.vue'
import DevelopmentSettings from './components/DevelopmentSettings.vue'
import DevelopmentRecordsTable from './components/DevelopmentRecordsTable.vue'
import DevelopmentStatusRecordsDialog from './components/DevelopmentStatusRecordsDialog.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useDevelopmentFilters } from '@/composables/useDevelopmentFilters'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { developmentColumns, defaultDevelopmentColumns, cleanColumns, statusOptions } from '@/utils/resourceDevelopment'
const options = reactive({ options: [], users: [], languages: [], user_id: '', is_admin: false, can_write: false })
const editorRef = ref(), workRef = ref(), settingsRef = ref(), tableRef = ref(), friendPanelRef = ref(), statusRecordsRef = ref()
// 默认不限定日期，自动展开最近有开拓记录的日期。
const { filters, columnFilters, activeColumnKeys, params, setColumnFilter, clearCommonColumn, resetFilters } = useDevelopmentFilters()
function clearColumns() { Object.keys(columnFilters).forEach(k => delete columnFilters[k]); query() }
function commonChanged(key) { clearCommonColumn(key); query() }
function columnTextInput(key, value) { setColumnFilter(key, value); keywordChanged(value) }
const days = ref([]), rows = ref([]), activeDay = ref(''), dayPage = ref(1), recordPage = ref(1), dayTotal = ref(0), recordTotal = ref(0), loading = ref(false), recordsLoading = ref(false), advanced = ref(false)
const dayPageSize = ref(3), recordPageSize = ref(10)
const selectedColumns = ref([...defaultDevelopmentColumns])
const platforms = computed(() => options.options.filter(o => o.kind === 'platform')), accounts = computed(() => options.options.filter(o => o.kind === 'account'))
const advancedCount = computed(() => ['platform_id','account_id','state'].filter(k => filters[k]).length)
const columnKey = () => `resource-development:columns:${options.user_id}`
watch(selectedColumns, value => { if (options.user_id) localStorage.setItem(columnKey(), JSON.stringify(value)) }, { deep: true })
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({ rows, tableRef, deleteRow: api.remove, getLabel: row => row.full_name, reload: () => reload(true), onDeleted: () => { tableRef.value?.invalidateDetails() }, entityName: '开拓记录' })
const setTableRef = el => { if (el) tableRef.value = el }
let listController, recordController, listSeq = 0, recordSeq = 0, timer
const cancelled = e => ['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)
async function loadOptions() { Object.assign(options, await api.options()) }
async function loadRecords() {
  recordController?.abort(); const seq = ++recordSeq
  if (!activeDay.value) { rows.value = []; recordTotal.value = 0; recordsLoading.value = false; return }
  recordController = new AbortController(); recordsLoading.value = true
  try {
    const data = await api.records({ ...params(), start: activeDay.value, end: activeDay.value, skip: (recordPage.value - 1) * recordPageSize.value, limit: recordPageSize.value }, recordController.signal)
    if (seq !== recordSeq) return
    recordTotal.value = data.total
    const last = Math.max(1, Math.ceil(data.total / recordPageSize.value))
    if (recordPage.value > last) { recordPage.value = last; return loadRecords() }
    rows.value = data.items
  } catch (e) { if (!cancelled(e) && seq === recordSeq) ElMessage.error(e.message) } finally { if (seq === recordSeq) recordsLoading.value = false }
}
async function reload(keepDelete = false) {
  clearTimeout(timer); listController?.abort(); recordController?.abort(); ++recordSeq
  const seq = ++listSeq; listController = new AbortController(); loading.value = true
  tableRef.value?.invalidateDetails()
  if (!keepDelete) exitDeleteMode()
  try {
    const data = await api.days({ ...params(), skip: (dayPage.value - 1) * dayPageSize.value, limit: dayPageSize.value }, listController.signal)
    if (seq !== listSeq) return
    dayTotal.value = data.total
    const last = Math.max(1, Math.ceil(data.total / dayPageSize.value))
    if (dayPage.value > last) { dayPage.value = last; return reload(keepDelete) }
    days.value = data.items
    if (!days.value.some(d => d.date === activeDay.value)) { activeDay.value = days.value[0]?.date || ''; recordPage.value = 1 }
    await loadRecords()
  } catch (e) { if (!cancelled(e) && seq === listSeq) ElMessage.error(e.message) } finally { if (seq === listSeq) loading.value = false }
}
function query() { activeDay.value = ''; dayPage.value = 1; recordPage.value = 1; reload() }
function keywordChanged(value) { clearTimeout(timer); listController?.abort(); recordController?.abort(); listSeq++; recordSeq++; if (!value) query(); else timer = setTimeout(query, 400) }
function clearAdvanced() { filters.platform_id = ''; filters.account_id = ''; filters.state = ''; query() }
function reset() { resetFilters(); query() }
function changeDay() { exitDeleteMode(); recordPage.value = 1; rows.value = []; loadRecords() }
function recordPageChanged() { exitDeleteMode(); rows.value = []; loadRecords() }
function recordSizeChanged() { recordPage.value = 1; recordPageChanged() }
function daySizeChanged() { dayPage.value = 1; dayPageChanged() }
function dayPageChanged() { activeDay.value = ''; reload() }
async function recordSaved() { await Promise.all([reload(), statusRecordsRef.value?.reload()]) }
async function openEditor(row, channel, status) { try { await editorRef.value.open(row, channel, status) } catch (e) { ElMessage.error(e.message) } }
async function openWork(day, owner) { try { await workRef.value.open(day, owner) } catch (e) { ElMessage.error(e.message) } }
const chineseDate = value => value ? new Date(`${String(value).slice(0,10)}T00:00:00`).toLocaleDateString('zh-CN') : '-'
onMounted(async () => { try { await loadOptions(); const raw = localStorage.getItem(columnKey()); try { selectedColumns.value = raw ? cleanColumns(JSON.parse(raw)) : [...defaultDevelopmentColumns] } catch { localStorage.removeItem(columnKey()); selectedColumns.value = [...defaultDevelopmentColumns] } await nextTick(); await reload() } catch (e) { ElMessage.error(e.message) } })
onBeforeUnmount(() => { clearTimeout(timer); listController?.abort(); recordController?.abort(); listSeq++; recordSeq++ })
</script>

<style>
.development-heading,.development-actions,.development-filters,.people-summary,.person-summary,.period-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.development-pagination{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0}.development-pagination>.el-pagination{max-width:100%;overflow-x:auto;margin-top:0}
.development-heading{justify-content:space-between;margin-bottom:18px}.development-heading h2{margin:0 0 5px}.resource-development-page .muted,.development-dialog .muted{color:var(--el-text-color-secondary);font-size:13px}
.development-day-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;max-width:100%}.development-day-controls>.el-select{width:110px}.resource-development-page .development-day-controls>.el-pagination{margin-top:0;max-width:100%;overflow-x:auto}
.development-filters{margin:16px 0}.development-filters>.el-input{width:290px}.development-filters>.el-select{width:150px}.development-filters>.el-date-editor{max-width:330px}
.development-status-entry{display:flex;gap:10px;margin-left:auto}.development-status-entry .el-button+.el-button{margin-left:0}
.development-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.development-form-grid .wide{grid-column:1/-1}.development-form-grid .el-select,.development-form-grid .el-date-editor{width:100%}
.development-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.development-dialog>.el-dialog__header,.development-dialog>.el-dialog__footer{flex-shrink:0}.development-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.development-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:#f8fafc;padding:16px}
.development-action{padding:14px;margin:12px 0;border:1px solid var(--el-border-color);border-radius:6px}.development-action>.development-form-grid{margin-top:12px}.development-dialog h3{margin:20px 0 12px}.development-dialog .el-alert{margin:12px 0}
.development-advanced,.development-detail{max-width:calc(100vw - 32px)!important}.development-advanced-body{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.development-advanced-body .development-actions{margin-top:20px;justify-content:flex-end}.development-advanced-body label{display:block;margin:10px 0}
.el-popover.development-detail{padding:18px 20px;border-radius:12px;box-shadow:0 12px 36px #1e293b26}.development-detail>.el-popover__title{font-size:12px;color:#8491a3;margin-bottom:12px}.development-detail-body{height:min(560px,calc(100vh - 140px));max-height:560px;padding-right:8px;scrollbar-gutter:stable;overflow-y:auto;overflow-wrap:anywhere}.development-detail-body .el-descriptions__content{white-space:pre-wrap;overflow-wrap:anywhere}.development-detail-body small{display:block;color:var(--el-text-color-secondary)}.history-line{padding:8px 0;border-bottom:1px solid var(--el-border-color-light)}
.development-progress{white-space:normal;text-align:left;line-height:1.5;height:auto}.development-column-options{max-height:400px;overflow-y:auto}.development-column-options .el-checkbox{display:flex;margin:4px 0}.people-summary{margin-bottom:12px}.person-summary{padding:8px 12px;background:#f1f5f9;border-radius:6px}.day-count{margin-left:12px}.resource-development-page .el-pagination{justify-content:flex-end;margin-top:14px}
.work-periods{width:100%}.period-row{margin-bottom:12px}.period-row>.el-select{width:150px}.platform-chip{margin:5px}.development-dialog input[type=file]{max-width:100%}
@media(max-width:800px){.el-popover.development-detail{position:fixed!important;left:16px!important;right:16px!important;top:72px!important;transform:none!important;width:calc(100vw - 32px)!important;box-sizing:border-box}.development-detail>.el-popper__arrow{display:none}}
@media(max-width:700px){.development-form-grid{grid-template-columns:1fr}.development-heading{align-items:flex-start}.development-filters>.el-input,.development-filters>.el-select{width:100%}.development-actions{gap:6px}}
</style>
