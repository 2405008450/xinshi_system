<template>
  <el-card class="common-page-card compact-list-card resource-channels-page">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">渠道管理</span>
          <p class="page-subtitle">集中维护开拓平台资料、用途与人员分工</p>
        </div>
        <div class="header-actions">
          <TableColumnSettings settings-key="resource-channels"
            v-model="selectedColumns"
            :columns="channelColumns"
            :column-count="2"
            title="渠道列表字段"
            @reset="selectedColumns = [...defaultChannelColumns]"
          />
          <BatchDeleteToolbar v-if="options.can_write" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /><el-button @click="auditRef.open()">我的操作记录</el-button>
          <el-button v-if="options.can_write && !deleteMode" type="primary" @click="openEditor()">新增渠道</el-button>
        </div>
      </div>
    </template>
    <TalentResourceNav />
    <div class="channel-filters search-bar">
      <el-input v-model="filters.keyword" clearable maxlength="255" placeholder="平台名称、账号名称、平台用途" @input="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.category" clearable placeholder="平台性质" @change="query"><el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <AdvancedFilterPopover v-model:visible="advanced" :count="advancedCount" popper-class="channel-advanced" @clear="clearAdvanced" @reset="reset">
        <div class="channel-advanced-grid">
          <div><label>维护人</label><el-select v-model="filters.maintainer_ids" multiple filterable clearable placeholder="选择维护人" @change="query"><el-option v-for="person in filterPeople" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
          <div><label>使用人</label><el-select v-model="filters.user_ids" multiple filterable clearable placeholder="选择使用人" @change="query"><el-option v-for="person in filterPeople" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
        </div>
      </AdvancedFilterPopover>
    </div>
    <el-table ref="tableRef" v-loading="loading" :data="rows" :expand-row-keys="expandedIds" border row-key="id" empty-text="暂无符合条件的渠道" @expand-change="expandedChanged" @selection-change="handleDeleteSelectionChange">
<OrderedTableColumns settings-key="resource-channels">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="expand" width="1" class-name="channel-expand-column" label-class-name="channel-expand-column">
        <template #default="{ row }">
          <div v-if="row.accounts?.length" class="channel-account-panel">
            <div class="channel-account-heading"><strong>{{ row.name }} · 账号明细</strong><el-button v-if="options.can_write && !deleteMode" link type="primary" @click="openEditor(null, row)">新增账号</el-button></div>
            <el-table :data="row.accounts" row-key="id" border size="small">
              <el-table-column label="账号名称" min-width="160"><template #default="{ row: account }">{{ account.name }}</template></el-table-column>
              <el-table-column label="维护人" min-width="150"><template #default="{ row: account }">{{ channelMembersText(account.maintainers) }}</template></el-table-column>
              <el-table-column label="使用人" min-width="150"><template #default="{ row: account }">{{ channelMembersText(account.users) }}</template></el-table-column>
              <el-table-column label="账号情况说明" min-width="260"><template #default="{ row: account }"><ChannelTextPreview :text="account.description" :name="account.name" /></template></el-table-column>
              <el-table-column label="详情" :width="compactViewport ? 70 : 110" fixed="right"><template #default="{ row: account }"><ChannelDetailPopover :row="account" /></template></el-table-column>
              <el-table-column v-if="options.can_write && !deleteMode" label="操作" :width="compactViewport ? 80 : 90" fixed="right"><template #default="{ row: account }"><el-button link type="primary" @click="openEditor(account)">编辑账号</el-button></template></el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="序号" :width="fittedViewport ? 70 : 80"><template #default="{ row, $index }"><div class="channel-index-cell"><span>{{ (page - 1) * pageSize + $index + 1 }}</span><TableExpandButton v-if="row.accounts?.length" :expanded="expandedIds.includes(row.id)" expand-label="展开账号" collapse-label="收起账号" @click="toggleAccounts(row)" /></div></template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="columnWidth(column)" :show-overflow-tooltip="!['description','maintainers','users'].includes(column.key)">
        <template #default="{ row }">
          <ChannelTextPreview v-if="column.key === 'description'" :text="row.description" :name="row.name" />
          <div v-else-if="column.key === 'name'" class="channel-name-cell"><span>{{ row.name }}</span><el-button v-if="row.accounts?.length" link type="primary" @click="toggleAccounts(row)">{{ row.accounts.length }}个账号</el-button></div>
          <span v-else :class="{ 'channel-members-text': ['maintainers','users'].includes(column.key) }">{{ displayValue(row, column.key) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" :width="compactViewport ? 70 : fittedViewport ? 80 : 110" fixed="right">
        <template #default="{ row }">
          <ChannelDetailPopover :row="row" />
        </template>
      </el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" :width="compactViewport ? 80 : fittedViewport ? 90 : 120" fixed="right"><template #default="{ row }"><template v-if="options.can_write && !deleteMode"><el-button link type="primary" @click="openEditor(row)">编辑</el-button><el-button v-if="options.hierarchy_available" link type="primary" @click="openEditor(null, row)">新增账号</el-button></template><span v-else class="channel-muted">-</span></template></el-table-column>
    </OrderedTableColumns>
</el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50,100]" :total="total" layout="total, sizes, prev, pager, next, jumper" @current-change="loadList" @size-change="query" />
    <ChannelAuditDialog ref="auditRef" /><ChannelEditor ref="editorRef" :options="options" @saved="saved" />
  </el-card>
</template>

<script setup>
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import {useBatchDelete} from '@/composables/useBatchDelete'
import ChannelAuditDialog from './components/ChannelAuditDialog.vue'
import TalentResourceNav from './components/TalentResourceNav.vue'
import ChannelEditor from './components/ChannelEditor.vue'
import ChannelTextPreview from './components/ChannelTextPreview.vue'
import ChannelDetailPopover from './components/ChannelDetailPopover.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'
import { channelColumns, defaultChannelColumns, cleanChannelColumns, channelMembersText, channelDateTime, channelParams } from '@/utils/resourceChannels'

const options = reactive({ users: [], can_write: false, user_id: '', hierarchy_available: false })
const filters = reactive({ keyword: '', category: '', maintainer_ids: [], user_ids: [] })
const rows = ref([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), advanced = ref(false), filterPeople = ref([]), editorRef = ref(null), tableRef = ref(null), expandedIds = ref([])
const auditRef=ref(null)
const deletionPagination=reactive({get page(){return page.value},set page(value){page.value=value},get limit(){return pageSize.value},get total(){return total.value}})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination:deletionPagination,deleteRow:api.removeChannel,getLabel:r=>r.name,reload:loadList,entityName:'渠道'})
const selectedColumns = ref([...defaultChannelColumns])
const viewportQuery = window.matchMedia('(max-width: 640px)')
const compactViewport = ref(viewportQuery.matches)
const updateViewport = event => { compactViewport.value = event.matches }
const fittedQuery = window.matchMedia('(max-width: 1280px)')
const fittedViewport = ref(fittedQuery.matches)
const updateFittedViewport = event => { fittedViewport.value = event.matches }
const fittedWidths = { name: 120, category: 100, purpose: 100, maintainers: 70, users: 70, description: 200 }
const columnWidth = column => fittedViewport.value ? fittedWidths[column.key] || column.width : column.width
const visibleColumns = computed(() => channelColumns.filter(column => selectedColumns.value.includes(column.key)))
const advancedCount = computed(() => Number(Boolean(filters.maintainer_ids.length)) + Number(Boolean(filters.user_ids.length)))
const columnKey = () => `resource-channels:columns:${options.user_id}`
let columnsReady = false, request, sequence = 0, timer
const cancelled = error => ['ERR_CANCELED','CanceledError','AbortError'].includes(error.code || error.name)
const personLabel = person => `${person.name}${person.is_active === false ? '（已停用）' : ''}`
function displayValue(row, key) {
  if (key === 'category') return categoryOptions.find(item => item.value === row.category)?.label || '-'
  if (['maintainers', 'users'].includes(key)) return channelMembersText(row[key])
  if (key.endsWith('_at')) return channelDateTime(row[key])
  return row[key] || '-'
}
watch(selectedColumns, value => { if (columnsReady) { try { localStorage.setItem(columnKey(), JSON.stringify(value)) } catch { /* 存储不可用时仍可调整字段。 */ } } }, { deep: true })
async function loadOptions() {
  const [data, people] = await Promise.all([api.options(), api.channelPeople()])
  Object.assign(options, data); filterPeople.value = people
}
async function loadList() {
  clearTimeout(timer); request?.abort(); const seq = ++sequence; request = new AbortController(); loading.value = true
  try {
    const data = await api.channels(channelParams(filters, page.value, pageSize.value), request.signal)
    if (seq !== sequence) return
    total.value = data.total
    const last = Math.max(1, Math.ceil(data.total / pageSize.value))
    if (page.value > last) { page.value = last; return loadList() }
    rows.value = data.items
    options.hierarchy_available = Boolean(data.hierarchy_available)
    expandedIds.value = rows.value.filter(row => row.accounts?.length && (row.expand_accounts || expandedIds.value.includes(row.id))).map(row => row.id)
  } catch (error) { if (!cancelled(error) && seq === sequence) ElMessage.error(error.message) }
  finally { if (seq === sequence) loading.value = false }
}
function query() { page.value = 1; expandedIds.value = []; loadList() }
function toggleAccounts(row) { tableRef.value?.toggleRowExpansion(row, !expandedIds.value.includes(row.id)) }
function expandedChanged(_row, expanded) { expandedIds.value = expanded.map(row => row.id) }
function keywordChanged(value) { clearTimeout(timer); request?.abort(); sequence++; loading.value = false; if (!value) query(); else timer = setTimeout(query, 400) }
function clearAdvanced() { filters.maintainer_ids = []; filters.user_ids = []; query() }
function reset() { Object.assign(filters, { keyword: '', category: '', maintainer_ids: [], user_ids: [] }); query() }
async function openEditor(row, parent) { try { await loadOptions(); await editorRef.value.open(row, '', parent) } catch (error) { ElMessage.error(error.message) } }
async function saved() { await Promise.all([loadOptions(), loadList()]).catch(error => ElMessage.error(error.message)) }
onMounted(async () => {
  viewportQuery.addEventListener('change', updateViewport)
  fittedQuery.addEventListener('change', updateFittedViewport)
  try {
    await loadOptions()
    try {
      const raw = localStorage.getItem(columnKey())
      selectedColumns.value = raw ? cleanChannelColumns(JSON.parse(raw)) : [...defaultChannelColumns]
      // 原列表说明默认藏在独立编辑按钮中；首次升级补入预览，之后继续尊重个人设置。
      const previewKey = `${columnKey()}:preview-v2`
      if (!localStorage.getItem(previewKey)) {
        if (raw && selectedColumns.value.length && !selectedColumns.value.includes('description')) selectedColumns.value.push('description')
        localStorage.setItem(previewKey, '1')
      }
      if (raw) localStorage.setItem(columnKey(), JSON.stringify(selectedColumns.value))
    } catch { selectedColumns.value = [...defaultChannelColumns]; try { localStorage.removeItem(columnKey()) } catch { /* 使用默认字段。 */ } }
    columnsReady = true; await loadList()
  } catch (error) { ElMessage.error(error.message) }
})
onBeforeUnmount(() => { viewportQuery.removeEventListener('change', updateViewport); fittedQuery.removeEventListener('change', updateFittedViewport); clearTimeout(timer); request?.abort(); sequence++ })
</script>

<style>
.channel-heading,.channel-actions,.channel-filters { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.channel-heading { justify-content:space-between; margin-bottom:18px; }
.channel-heading h2 { margin:0 0 5px; }
.channel-muted { color:var(--el-text-color-secondary); font-size:13px; }
.channel-filters { margin:16px 0; }
.channel-filters>.el-input { width:300px; max-width:100%; }
.channel-filters>.el-select { width:160px; }
.channel-column-options { max-height:min(400px,calc(100vh - 120px)); overflow-y:auto; }
.channel-column-options .el-checkbox { display:flex; margin:4px 0; }
.channel-advanced,.channel-details { max-width:calc(100vw - 32px); box-sizing:border-box; }
.channel-advanced-body { max-height:min(560px,calc(100vh - 120px)); overflow-y:auto; }
.channel-advanced-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-bottom:16px; }
.channel-advanced-grid label { display:block; margin-bottom:8px; }
.channel-advanced-grid .el-select { width:100%; }
.channel-expand-column { padding:0 !important; }
.channel-expand-column .cell { padding:0 !important; }
.channel-expand-column .el-table__expand-icon { display:none; }
.channel-index-cell { display:flex; align-items:center; gap:5px; }
.channel-name-cell { display:flex; flex-direction:column; align-items:flex-start; }
.channel-members-text { white-space:normal; overflow-wrap:anywhere; }
.channel-account-panel { padding:12px 20px 16px 50px; background:var(--el-fill-color-lighter); }
.channel-account-heading { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.resource-channels-page .el-pagination { justify-content:flex-end; margin-top:16px; max-width:100%; overflow-x:auto; }
@media(max-width:640px) { .channel-advanced-grid { grid-template-columns:minmax(0,1fr); } .channel-account-panel { padding:12px 10px; } }
</style>
