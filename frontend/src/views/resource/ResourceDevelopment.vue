<template>
  <el-card class="resource-development-page">
    <div class="development-heading"><div><h2>资源开拓</h2><span class="muted">按日期记录开拓与跟进，添加成功后关联人才总库</span></div><div class="development-actions">
      <el-popover trigger="click" placement="bottom-end" :width="280"><template #reference><el-button>字段设置</el-button></template><div class="development-column-options"><el-checkbox-group v-model="selectedColumns"><el-checkbox v-for="c in developmentColumns" :key="c.key" :value="c.key">{{ c.label }}</el-checkbox></el-checkbox-group></div><el-button text type="primary" @click="selectedColumns = [...defaultDevelopmentColumns]">恢复默认</el-button></el-popover>
      <template v-if="options.can_write"><template v-if="!deleteMode"><el-button @click="settingsRef.open()">平台与选项</el-button><el-button @click="openWork()">每日工作</el-button><el-button type="primary" @click="openEditor()">新增</el-button></template><BatchDeleteToolbar :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /></template>
    </div></div>
    <TalentResourceNav />
    <div class="development-filters">
      <el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" @change="query" />
      <el-input v-model="filters.keyword" clearable placeholder="资源姓名、招呼编号、本人联系方式" @input="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.owner_id" clearable filterable placeholder="开拓人员" @change="commonChanged('owner_id')"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="development-advanced"><template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template><div class="development-advanced-body"><div class="development-form-grid"><div><label>开拓平台</label><el-select v-model="filters.platform_id" clearable filterable @change="commonChanged('platform_id')"><el-option v-for="p in platforms" :key="p.id" :label="p.name" :value="p.id" /></el-select></div><div><label>对接账号</label><el-select v-model="filters.account_id" clearable filterable @change="commonChanged('account_id')"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></div><div><label>添加状态（任一渠道）</label><el-select v-model="filters.state" clearable filterable allow-create @change="query"><el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" /></el-select></div></div><div class="development-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div></div></el-popover>
    </div>
    <div class="development-actions" v-if="activeColumnKeys.length"><el-tag v-for="key in activeColumnKeys" :key="key" closable @close="delete columnFilters[key]; query()">{{ developmentColumns.find(c => c.key === key)?.label }}：已筛选</el-tag><el-button link @click="clearColumns">清空列筛选</el-button></div>
    <div v-loading="loading">
      <el-empty v-if="!days.length" description="所选日期暂无开拓记录，可调整日期查询历史数据" />
      <el-collapse v-model="activeDay" accordion @change="changeDay">
        <el-collapse-item v-for="day in days" :key="day.date" :name="day.date"><template #title><strong>{{ chineseDate(day.date) }}</strong><el-tag class="day-count" effect="plain">{{ day.count }} 条开拓记录</el-tag></template>
          <template v-if="activeDay === day.date">
            <div class="people-summary">
              <span>{{ day.people.length }} 位开拓人 · {{ day.count }} 条记录 · {{ day.people.reduce((n,p) => n + p.duration_minutes, 0) }} 分钟（人员当日总工时）</span>
              <el-popover trigger="click" placement="bottom-start" :width="640" popper-class="development-people" @show="peopleKeyword = ''; peopleSearch = ''">
                <template #reference><el-button link type="primary">人员汇总 / 工时</el-button></template>
                <h4>人员每日汇总</h4><el-input v-model="peopleKeyword" clearable placeholder="搜索开拓人员" @input="searchPeople" @keyup.enter="peopleSearch = peopleKeyword" />
                <el-table :data="day.people.filter(p => p.owner_name.includes(peopleSearch.trim()))" max-height="360" size="small">
                  <el-table-column prop="owner_name" label="开拓人" min-width="110" />
                  <el-table-column prop="count" label="记录数" width="80" />
                  <el-table-column prop="duration_minutes" label="当日工时/分钟" width="110" />
                  <el-table-column label="完成情况" width="110"><template #default="{row}">{{ row.completed === null ? '未填写' : row.completed ? '已完成' : '未完成' }}</template></el-table-column>
                  <el-table-column label="操作" width="110"><template #default="{row}"><el-button v-if="row.can_edit && options.can_write && !deleteMode" link type="primary" @click="openWork(day.date, row.owner_id)">工时 / 截图</el-button><span v-else>只读</span></template></el-table-column>
                </el-table>
              </el-popover>
            </div>
            <el-table :ref="setTableRef" v-loading="recordsLoading" :data="rows" row-key="id" border stripe @selection-change="handleDeleteSelectionChange">
              <el-table-column v-if="deleteMode" type="selection" width="48" :selectable="r => r.can_delete" fixed="left" />
              <el-table-column type="index" label="序号" width="65" />
              <el-table-column v-for="c in visibleColumns" :key="c.key" :prop="c.key" :label="c.label" :min-width="c.width" show-overflow-tooltip><template #header><ConfiguredColumnHeaderFilter :definition="columnDefinition(c)" :model-value="columnFilters[c.key]" @update:model-value="setColumnFilter(c.key, $event)" @text-input="columnTextInput(c.key, $event)" @change="query" @enter="query" @clear="query" /></template><template #default="{row}"><el-button v-if="progressColumnChannel[c.key] && options.can_write && row.can_edit && !deleteMode" link type="primary" class="development-progress" @click="openEditor(row, progressColumnChannel[c.key])">{{ display(row, c.key) }}</el-button><el-button v-else-if="c.key === 'platform_name' && options.can_write && !deleteMode" link type="primary" @click="settingsRef.edit(platforms.find(p => p.id === row.platform_id))">{{ row.platform_name }}</el-button><span v-else>{{ display(row, c.key) }}</span></template></el-table-column>
              <el-table-column label="详情" width="105" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="资源开拓详情" popper-class="development-detail" @show="loadDetail(row)"><template #reference><el-button link type="primary">查看详情</el-button></template><div v-loading="detailLoading[row.id]" class="development-detail-body"><DevelopmentDetailContent v-if="details[row.id]" :record="details[row.id]" :accounts="accounts" /></div></el-popover></template></el-table-column>
              <el-table-column v-if="!deleteMode" label="操作" width="90" fixed="right"><template #default="{row}"><el-button v-if="options.can_write && row.can_edit" link type="primary" @click="openEditor(row)">编辑</el-button><span v-else class="muted">只读</span></template></el-table-column>
            </el-table>
            <el-pagination v-model:current-page="recordPage" :page-size="20" :total="recordTotal" layout="total, prev, pager, next" @current-change="recordPageChanged" />
          </template>
        </el-collapse-item>
      </el-collapse>
      <el-pagination v-if="dayTotal > 7" v-model:current-page="dayPage" :page-size="7" :total="dayTotal" layout="total, prev, pager, next" @current-change="dayPageChanged" />
    </div>
    <DevelopmentRecordEditor ref="editorRef" :options="options" @saved="reload" />
    <DevelopmentWorkEditor ref="workRef" :options="options" @saved="reload" />
    <DevelopmentSettings ref="settingsRef" :options="options" @saved="loadOptions" />
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TalentResourceNav from './components/TalentResourceNav.vue'
import DevelopmentRecordEditor from './components/DevelopmentRecordEditor.vue'
import DevelopmentWorkEditor from './components/DevelopmentWorkEditor.vue'
import DevelopmentSettings from './components/DevelopmentSettings.vue'
import DevelopmentDetailContent from './components/DevelopmentDetailContent.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { developmentColumns, defaultDevelopmentColumns, cleanColumns, recentDays, statusOptions, progressColumnChannel, progressChannels, progressText, progressStatuses } from '@/utils/resourceDevelopment'
const options = reactive({ options: [], users: [], languages: [], user_id: '', is_admin: false, can_write: false })
const editorRef = ref(), workRef = ref(), settingsRef = ref(), tableRef = ref()
const filters = reactive({ range: recentDays(), keyword: '', owner_id: '', platform_id: '', account_id: '', state: '' })
const columnFilters = reactive({}), peopleKeyword = ref(''), peopleSearch = ref('')
let peopleTimer
const searchPeople = value => { clearTimeout(peopleTimer); if (!value) peopleSearch.value = ''; else peopleTimer = setTimeout(() => { peopleSearch.value = value }, 400) }
const activeColumnKeys = computed(() => Object.keys(columnFilters).filter(k => Array.isArray(columnFilters[k]) ? columnFilters[k].length : Boolean(columnFilters[k]?.trim())))
function clearColumns() { Object.keys(columnFilters).forEach(k => delete columnFilters[k]); query() }
function commonChanged(key) { delete columnFilters[{ platform_id: 'platform_name', owner_id: 'owner_name', account_id: 'account_name' }[key]]; query() }
function columnTextInput(key, value) { setColumnFilter(key, value); keywordChanged(value) }
function setColumnFilter(key, value) {
  columnFilters[key] = value
  const common = { platform_name: 'platform_id', owner_name: 'owner_id', account_name: 'account_id' }[key]
  if (common) filters[common] = ''
}
function columnDefinition(c) {
  const selects = { platform_name: platforms.value, owner_name: options.users, account_name: accounts.value, language_names: options.languages }
  const channel = progressColumnChannel[c.key]
  return { key: c.key, label: c.label, type: selects[c.key] || channel ? 'select' : 'text',
    options: channel ? progressStatuses(channel) : selects[c.key], headerWidth: 280,
    placeholder: ['work_date', 'updated_at'].includes(c.key) ? '例如 2026-09-24' : c.key === 'latest_follow_up' ? '操作日期、人员或状态' : `筛选${c.label}` }
}
const days = ref([]), rows = ref([]), activeDay = ref(''), dayPage = ref(1), recordPage = ref(1), dayTotal = ref(0), recordTotal = ref(0), loading = ref(false), recordsLoading = ref(false), advanced = ref(false)
const details = reactive({}), detailLoading = reactive({}), selectedColumns = ref([...defaultDevelopmentColumns])
const visibleColumns = computed(() => developmentColumns.filter(c => selectedColumns.value.includes(c.key)))
const platforms = computed(() => options.options.filter(o => o.kind === 'platform')), accounts = computed(() => options.options.filter(o => o.kind === 'account'))
const advancedCount = computed(() => ['platform_id','account_id','state'].filter(k => filters[k]).length)
const columnKey = () => `resource-development:columns:${options.user_id}`
watch(selectedColumns, value => { if (options.user_id) localStorage.setItem(columnKey(), JSON.stringify(value)) }, { deep: true })
const params = () => ({ column_filters: activeColumnKeys.value.length ? JSON.stringify(Object.fromEntries(activeColumnKeys.value.map(k => [k, columnFilters[k]]))) : undefined, start: filters.range?.[0], end: filters.range?.[1], ...Object.fromEntries(['keyword','owner_id','platform_id','account_id','state'].filter(k => filters[k]).map(k => [k, filters[k]])) })
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({ rows, tableRef, deleteRow: api.remove, getLabel: row => row.full_name, reload: () => reload(true), onDeleted: row => { delete details[row.id] }, entityName: '开拓记录' })
const setTableRef = el => { if (el) tableRef.value = el }
let listController, recordController, listSeq = 0, recordSeq = 0, timer, detailGeneration = 0
const cancelled = e => ['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)
async function loadOptions() { Object.assign(options, await api.options()) }
async function loadRecords() {
  recordController?.abort(); const seq = ++recordSeq
  if (!activeDay.value) { rows.value = []; return }
  recordController = new AbortController(); recordsLoading.value = true
  try {
    const data = await api.records({ ...params(), start: activeDay.value, end: activeDay.value, skip: (recordPage.value - 1) * 20, limit: 20 }, recordController.signal)
    if (seq !== recordSeq) return
    recordTotal.value = data.total
    const last = Math.max(1, Math.ceil(data.total / 20))
    if (recordPage.value > last) { recordPage.value = last; return loadRecords() }
    rows.value = data.items
  } catch (e) { if (!cancelled(e) && seq === recordSeq) ElMessage.error(e.message) } finally { if (seq === recordSeq) recordsLoading.value = false }
}
async function reload(keepDelete = false) {
  clearTimeout(timer); listController?.abort(); recordController?.abort(); ++recordSeq
  const seq = ++listSeq; listController = new AbortController(); loading.value = true
  detailGeneration++; Object.keys(details).forEach(k => delete details[k])
  if (!keepDelete) exitDeleteMode()
  try {
    const data = await api.days({ ...params(), skip: (dayPage.value - 1) * 7, limit: 7 }, listController.signal)
    if (seq !== listSeq) return
    dayTotal.value = data.total
    const last = Math.max(1, Math.ceil(data.total / 7))
    if (dayPage.value > last) { dayPage.value = last; return reload(keepDelete) }
    days.value = data.items
    if (!days.value.some(d => d.date === activeDay.value)) { activeDay.value = days.value[0]?.date || ''; recordPage.value = 1 }
    await loadRecords()
  } catch (e) { if (!cancelled(e) && seq === listSeq) ElMessage.error(e.message) } finally { if (seq === listSeq) loading.value = false }
}
function query() { dayPage.value = 1; recordPage.value = 1; reload() }
function keywordChanged(value) { clearTimeout(timer); listController?.abort(); recordController?.abort(); listSeq++; recordSeq++; if (!value) query(); else timer = setTimeout(query, 400) }
function clearAdvanced() { filters.platform_id = ''; filters.account_id = ''; filters.state = ''; query() }
function reset() { Object.keys(columnFilters).forEach(k => delete columnFilters[k]); Object.assign(filters, { range: recentDays(), keyword: '', owner_id: '', platform_id: '', account_id: '', state: '' }); query() }
function changeDay() { exitDeleteMode(); recordPage.value = 1; rows.value = []; loadRecords() }
function recordPageChanged() { exitDeleteMode(); loadRecords() }
function dayPageChanged() { activeDay.value = ''; reload() }
async function loadDetail(row) { if (details[row.id]) return; const generation = detailGeneration; detailLoading[row.id] = true; try { const data = await api.detail(row.id); if (generation === detailGeneration) details[row.id] = data } catch (e) { ElMessage.error(e.message) } finally { detailLoading[row.id] = false } }
async function openEditor(row, channel) { try { await editorRef.value.open(row, channel) } catch (e) { ElMessage.error(e.message) } }
async function openWork(day, owner) { try { await workRef.value.open(day, owner) } catch (e) { ElMessage.error(e.message) } }
const chineseDate = value => value ? new Date(`${String(value).slice(0,10)}T00:00:00`).toLocaleDateString('zh-CN') : '-'
const chineseTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
const display = (row, key) => progressColumnChannel[key] ? progressText(row, progressColumnChannel[key]) : key === 'work_date' ? chineseDate(row[key]) : key === 'updated_at' ? chineseTime(row[key]) : row[key] || '-'
const accountName = id => accounts.value.find(a => a.id === id)?.name || '-'
onMounted(async () => { try { await loadOptions(); const raw = localStorage.getItem(columnKey()); try { selectedColumns.value = raw ? cleanColumns(JSON.parse(raw)) : [...defaultDevelopmentColumns] } catch { localStorage.removeItem(columnKey()); selectedColumns.value = [...defaultDevelopmentColumns] } await nextTick(); await reload() } catch (e) { ElMessage.error(e.message) } })
onBeforeUnmount(() => { clearTimeout(peopleTimer); clearTimeout(timer); listController?.abort(); recordController?.abort(); listSeq++; recordSeq++; detailGeneration++ })
</script>

<style>
.development-heading,.development-actions,.development-filters,.people-summary,.person-summary,.period-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.development-heading{justify-content:space-between;margin-bottom:18px}.development-heading h2{margin:0 0 5px}.resource-development-page .muted,.development-dialog .muted{color:var(--el-text-color-secondary);font-size:13px}
.development-filters{margin:16px 0}.development-filters>.el-input{width:290px}.development-filters>.el-select{width:150px}.development-filters>.el-date-editor{max-width:330px}
.development-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.development-form-grid .wide{grid-column:1/-1}.development-form-grid .el-select,.development-form-grid .el-date-editor{width:100%}
.development-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.development-dialog>.el-dialog__header,.development-dialog>.el-dialog__footer{flex-shrink:0}.development-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.development-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:#f8fafc;padding:16px}
.development-action{padding:14px;margin:12px 0;border:1px solid var(--el-border-color);border-radius:6px}.development-action>.development-form-grid{margin-top:12px}.development-dialog h3{margin:20px 0 12px}.development-dialog .el-alert{margin:12px 0}
.development-people{max-width:calc(100vw - 32px)!important;max-height:calc(100vh - 100px);overflow:auto}.development-people h4{margin:0 0 10px}.development-people .el-input{margin-bottom:10px}.development-advanced,.development-detail{max-width:calc(100vw - 32px)!important}.development-advanced-body{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.development-advanced-body .development-actions{margin-top:20px;justify-content:flex-end}.development-advanced-body label{display:block;margin:10px 0}
.el-popover.development-detail{padding:18px 20px;border-radius:12px;box-shadow:0 12px 36px #1e293b26}.development-detail>.el-popover__title{font-size:12px;color:#8491a3;margin-bottom:12px}.development-detail-body{height:min(560px,calc(100vh - 140px));max-height:560px;padding-right:8px;scrollbar-gutter:stable;overflow-y:auto;overflow-wrap:anywhere}.development-detail-body .el-descriptions__content{white-space:pre-wrap;overflow-wrap:anywhere}.development-detail-body small{display:block;color:var(--el-text-color-secondary)}.history-line{padding:8px 0;border-bottom:1px solid var(--el-border-color-light)}
.development-progress{white-space:normal;text-align:left;line-height:1.5;height:auto}.development-column-options{max-height:400px;overflow-y:auto}.development-column-options .el-checkbox{display:flex;margin:4px 0}.people-summary{margin-bottom:12px}.person-summary{padding:8px 12px;background:#f1f5f9;border-radius:6px}.day-count{margin-left:12px}.resource-development-page .el-pagination{justify-content:flex-end;margin-top:14px}
.work-periods{width:100%}.period-row{margin-bottom:12px}.period-row>.el-select{width:150px}.platform-chip{margin:5px}.development-dialog input[type=file]{max-width:100%}
@media(max-width:800px){.el-popover.development-detail{position:fixed!important;left:16px!important;right:16px!important;top:72px!important;transform:none!important;width:calc(100vw - 32px)!important;box-sizing:border-box}.development-detail>.el-popper__arrow{display:none}}
@media(max-width:700px){.development-form-grid{grid-template-columns:1fr}.development-heading{align-items:flex-start}.development-filters>.el-input,.development-filters>.el-select{width:100%}.development-actions{gap:6px}}
</style>




