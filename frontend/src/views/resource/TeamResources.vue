<template>
  <el-card class="team-resources-page">
    <div class="team-heading"><div><h2>团队资源</h2><span class="team-muted">统一维护团队与企业资源档案</span></div><div class="team-actions">
      <TableColumnSettings v-model="selectedColumns" :columns="teamColumns" title="团队列表字段" @reset="selectedColumns = [...defaultTeamColumns]" />
      <BatchDeleteToolbar v-if="options.can_write" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
      <el-button v-if="options.can_write && !deleteMode" type="primary" @click="openEditor()">新增团队</el-button>
    </div></div>
    <TalentResourceNav />
    <el-alert v-if="moduleError" :title="moduleError" type="warning" :closable="false" show-icon />
    <div class="team-filters">
      <el-input :model-value="filters.keyword" placeholder="团队简称或全称" clearable @update:model-value="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.team_type" placeholder="团队类型" clearable @change="query"><el-option v-for="item in options.team_types" :key="item.value" :label="item.label" :value="item.value" /></el-select>
      <el-select v-model="filters.resource_types" placeholder="资源类型（可多选）" multiple clearable collapse-tags collapse-tags-tooltip @change="query"><el-option v-for="item in options.resource_types" :key="item.value" :label="item.label" :value="item.value" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="team-advanced">
        <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
        <div class="team-advanced-body"><div class="team-advanced-grid">
          <div><label>信实对接人</label><el-select v-model="filters.contact_user_id" filterable clearable @change="query"><el-option v-for="person in options.people" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
          <div><label>信实跟进人</label><el-select v-model="filters.follow_up_user_id" filterable clearable @change="query"><el-option v-for="person in options.people" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
          <div class="team-wide"><label>对接日期范围</label><el-date-picker v-model="filters.contact_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" start-placeholder="开始日期" end-placeholder="结束日期" @change="query" /></div>
        </div><div class="team-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div></div>
      </el-popover>
    </div>
    <el-table ref="tableRef" v-loading="loading" :data="rows" border row-key="id" empty-text="暂无符合条件的团队资源" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" />
      <el-table-column label="序号" width="70"><template #default="{ $index }">{{ (pagination.page - 1) * pagination.limit + $index + 1 }}</template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip><template #default="{ row }">
        <BusinessDetailPopover v-if="column.key === 'contacts'" :row="detailCache[row.id] || {}" :loading="Boolean(detailLoading[row.id])" title="团队对接人详情" popper-class="business-detail-popover team-details team-contacts-popover" @show="loadDetail(row.id)">
          <template #reference><el-button link type="primary">{{ row.contacts?.length ? teamContactSummary(row.contacts) : '查看对接人' }}</el-button></template>
          <template #content><el-alert v-if="detailErrors[row.id]" :title="detailErrors[row.id]" type="error" :closable="false" /><el-button v-if="detailErrors[row.id]" link type="primary" @click="loadDetail(row.id)">重新加载</el-button><TeamContactDetails v-else-if="detailCache[row.id]" :contacts="detailCache[row.id].contacts" :restricted="detailCache[row.id].contact_restricted" /></template>
        </BusinessDetailPopover>
        <template v-else>{{ teamDisplay(row, column.key, options) }}</template>
      </template></el-table-column>
      <el-table-column label="详情" width="110" fixed="right"><template #default="{ row }">
        <BusinessDetailPopover :row="detailCache[row.id] || {}" :items="detailCache[row.id] ? detailItems : []" :loading="Boolean(detailLoading[row.id])" title="团队详情" popper-class="business-detail-popover team-details" @show="loadDetail(row.id)">
          <template #content>
            <template v-if="detailErrors[row.id]"><el-alert :title="detailErrors[row.id]" type="error" :closable="false" /><el-button link type="primary" @click="loadDetail(row.id)">重新加载</el-button></template>
            <el-descriptions v-else-if="detailCache[row.id]" :column="2" border size="small"><el-descriptions-item v-for="item in detailItems" :key="item.key" :label="item.label" :span="item.span"><TeamContactDetails v-if="item.key === 'contacts'" :contacts="detailCache[row.id].contacts" :restricted="detailCache[row.id].contact_restricted" /><span v-else class="business-detail-popover__value">{{ teamDisplay(detailCache[row.id], item.key, options) }}</span></el-descriptions-item></el-descriptions>
          </template>
        </BusinessDetailPopover>
      </template></el-table-column>
      <el-table-column v-if="options.can_write && !deleteMode" label="操作" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openEditor(row)">编辑</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :page-sizes="[10,20,50,100]" :total="pagination.total" layout="total, sizes, prev, pager, next, jumper" @current-change="loadList" @size-change="query" />
    <TeamResourceEditor ref="editorRef" :options="options" @saved="saved" />
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { teamApi } from '@/api/teams'
import { getRawErrorDetail } from '@/utils/errorMessages'
import { cleanTeamColumns, defaultTeamColumns, emptyTeamFilters, personLabel, teamColumns, teamDisplay, teamParams, teamContactSummary } from '@/utils/teamResources'
import TalentResourceNav from './components/TalentResourceNav.vue'
import TeamResourceEditor from './components/TeamResourceEditor.vue'
import TeamContactDetails from './components/TeamContactDetails.vue'

const options = reactive({ team_types: [], resource_types: [], people: [], user_id: '', can_write: false, can_view_contacts: false })
const filters = reactive(emptyTeamFilters()), pagination = reactive({ page: 1, limit: 20, total: 0 })
const rows = ref([]), loading = ref(false), advanced = ref(false), moduleError = ref(''), tableRef = ref(null), editorRef = ref(null)
const selectedColumns = ref([...defaultTeamColumns]), detailCache = reactive({}), detailErrors = reactive({}), detailLoading = reactive({})
const detailRequests = new Map()
const visibleColumns = computed(() => teamColumns.filter(column => selectedColumns.value.includes(column.key)))
const detailItems = teamColumns.map(column => ({ ...column, span: ['contacts', 'introduction', 'resource_situation', 'remarks', 'other_resource_description'].includes(column.key) ? 2 : 1 }))
const advancedCount = computed(() => Number(Boolean(filters.contact_user_id)) + Number(Boolean(filters.follow_up_user_id)) + Number(Boolean(filters.contact_dates?.length)))
const columnKey = () => `resource-teams:columns:${options.user_id}`
let columnsReady = false, request, sequence = 0, timer, optionsRequest
const cancelled = error => ['ERR_CANCELED', 'CanceledError', 'AbortError'].includes(error.code || error.name)
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({ rows, tableRef, pagination, deleteRow: teamApi.delete, getLabel: row => row.short_name, reload: loadList, onDeleted: row => invalidateDetail(row.id), entityName: '团队' })
watch(selectedColumns, value => { if (columnsReady) { try { localStorage.setItem(columnKey(), JSON.stringify(value)) } catch { /* 存储不可用时仍允许本次调整。 */ } } }, { deep: true })
function invalidateDetail(id) { detailRequests.get(id)?.abort(); detailRequests.delete(id); delete detailCache[id]; delete detailErrors[id]; delete detailLoading[id] }
async function loadDetail(id) {
  if (detailCache[id] || detailLoading[id]) return
  const controller = new AbortController(); detailRequests.set(id, controller); detailLoading[id] = true; delete detailErrors[id]
  try { const row = await teamApi.detail(id, controller.signal); if (detailRequests.get(id) === controller) detailCache[id] = row }
  catch (error) { if (!cancelled(error) && detailRequests.get(id) === controller) detailErrors[id] = error.message }
  finally { if (detailRequests.get(id) === controller) { detailLoading[id] = false; detailRequests.delete(id) } }
}
async function loadList() {
  clearTimeout(timer); request?.abort(); request = new AbortController(); const seq = ++sequence; loading.value = true
  try {
    const data = await teamApi.list(teamParams(filters, pagination.page, pagination.limit), request.signal)
    if (seq !== sequence) return
    moduleError.value = ''; pagination.total = data.total
    const last = Math.max(1, Math.ceil(data.total / pagination.limit))
    if (pagination.page > last) { pagination.page = last; return loadList() }
    rows.value = data.items
  } catch (error) {
    if (!cancelled(error) && seq === sequence) {
      if (getRawErrorDetail(error)?.code === 'team_module_uninitialized') moduleError.value = error.message
      else ElMessage.error(error.message)
    }
  } finally { if (seq === sequence) loading.value = false }
}
function query() { exitDeleteMode(); pagination.page = 1; loadList() }
function keywordChanged(value) { filters.keyword = value; clearTimeout(timer); request?.abort(); sequence++; loading.value = false; exitDeleteMode(); if (!value.trim()) query(); else timer = setTimeout(query, 400) }
function clearAdvanced() { filters.contact_user_id = ''; filters.follow_up_user_id = ''; filters.contact_dates = []; query() }
function reset() { Object.assign(filters, emptyTeamFilters()); query() }
function openEditor(row) { editorRef.value.open(row) }
async function saved(row) {
  invalidateDetail(row.id); await loadList()
  try { await loadOptions(false) } catch (error) { if (!cancelled(error)) ElMessage.error(error.message) }
}
async function loadOptions(restoreColumns = true) {
  optionsRequest?.abort(); optionsRequest = new AbortController()
  const data = await teamApi.options(optionsRequest.signal); Object.assign(options, data)
  if (restoreColumns) {
    try { const stored = localStorage.getItem(columnKey()); selectedColumns.value = stored === null ? [...defaultTeamColumns] : cleanTeamColumns(JSON.parse(stored)); if (stored !== null) localStorage.setItem(columnKey(), JSON.stringify(selectedColumns.value)) }
    catch { selectedColumns.value = [...defaultTeamColumns]; try { localStorage.removeItem(columnKey()) } catch { /* 忽略不可用存储。 */ } }
    columnsReady = true
  }
}
onMounted(async () => {
  try { await loadOptions() } catch (error) { if (cancelled(error)) return; if (getRawErrorDetail(error)?.code === 'team_module_uninitialized') moduleError.value = error.message; else ElMessage.error(error.message) }
  await loadList()
})
onBeforeUnmount(() => { clearTimeout(timer); request?.abort(); optionsRequest?.abort(); sequence++; detailRequests.forEach(controller => controller.abort()); detailRequests.clear() })
</script>

<style>
.team-heading,.team-actions,.team-filters { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.team-heading { justify-content:space-between; margin-bottom:18px; }
.team-heading h2 { margin:0 0 5px; font-size:20px; }
.team-muted { color:var(--el-text-color-secondary); font-size:13px; }
.team-filters { margin:16px 0; }
.team-filters>.el-input { width:260px; max-width:100%; }
.team-filters>.el-select { width:180px; max-width:100%; }
.team-advanced,.team-details { max-width:calc(100vw - 32px); box-sizing:border-box; }
.team-advanced-body { max-height:min(560px,calc(100vh - 120px)); overflow-y:auto; }
.team-advanced-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-bottom:16px; }
.team-advanced-grid label { display:block; margin-bottom:8px; }
.team-advanced-grid .el-select,.team-advanced-grid .el-date-editor { width:100%; max-width:100%; }
.team-details .business-detail-popover__content { min-height:64px; }
.team-details .el-descriptions__table { table-layout:fixed; width:100%; }
.team-details .el-descriptions__cell { vertical-align:top; white-space:pre-wrap; overflow-wrap:anywhere; }
.team-details .business-detail-popover__value { white-space:pre-wrap; }
.team-resources-page .el-pagination { justify-content:flex-end; margin-top:16px; max-width:100%; overflow-x:auto; }
@media(max-width:640px) { .team-advanced-grid { grid-template-columns:minmax(0,1fr); } }
</style>
