<template>
  <el-card class="resource-channels-page">
    <div class="channel-heading">
      <div><h2>渠道管理</h2><span class="channel-muted">集中维护开拓平台资料、用途与人员分工</span></div>
      <div class="channel-actions">
        <el-popover trigger="click" placement="bottom-end" :width="280">
          <template #reference><el-button>字段设置</el-button></template>
          <div class="channel-column-options"><el-checkbox-group v-model="selectedColumns"><el-checkbox v-for="column in channelColumns" :key="column.key" :value="column.key">{{ column.label }}</el-checkbox></el-checkbox-group></div>
          <el-button text type="primary" @click="selectedColumns = [...defaultChannelColumns]">恢复默认</el-button>
        </el-popover>
        <el-button v-if="options.can_write" type="primary" @click="openEditor()">新增渠道</el-button>
      </div>
    </div>
    <TalentResourceNav />
    <div class="channel-filters">
      <el-input v-model="filters.keyword" clearable maxlength="255" placeholder="渠道／平台名称、平台用途" @input="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.category" clearable placeholder="平台性质" @change="query"><el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="channel-advanced">
        <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
        <div class="channel-advanced-body">
          <div class="channel-advanced-grid">
            <div><label>维护人</label><el-select v-model="filters.maintainer_ids" multiple filterable clearable placeholder="选择维护人" @change="query"><el-option v-for="person in filterPeople" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
            <div><label>使用人</label><el-select v-model="filters.user_ids" multiple filterable clearable placeholder="选择使用人" @change="query"><el-option v-for="person in filterPeople" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select></div>
          </div>
          <div class="channel-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div>
        </div>
      </el-popover>
    </div>
    <el-table v-loading="loading" :data="rows" border row-key="id" empty-text="暂无符合条件的渠道">
      <el-table-column label="序号" width="70"><template #default="{ $index }">{{ (page - 1) * pageSize + $index + 1 }}</template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip><template #default="{ row }">{{ displayValue(row, column.key) }}</template></el-table-column>
      <el-table-column label="情况说明" width="135" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="descriptionRef.open(row)">{{ options.can_write ? '编辑情况说明' : '查看情况说明' }}</el-button></template></el-table-column>
      <el-table-column label="详情" width="110" fixed="right">
        <template #default="{ row }">
          <el-popover trigger="click" placement="left" :width="760" title="渠道详情" popper-class="channel-details">
            <template #reference><el-button link type="primary">查看详情</el-button></template>
            <div class="channel-details-body"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="column in channelColumns" :key="column.key" :label="column.label" :span="['purpose', 'description'].includes(column.key) ? 2 : 1">{{ displayValue(row, column.key) }}</el-descriptions-item></el-descriptions></div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button v-if="options.can_write" link type="primary" @click="openEditor(row)">编辑</el-button><span v-else class="channel-muted">-</span></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50,100]" :total="total" layout="total, sizes, prev, pager, next, jumper" @current-change="loadList" @size-change="query" />
    <ChannelEditor ref="editorRef" :options="options" @saved="saved" />
    <ChannelDescriptionEditor ref="descriptionRef" :can-write="options.can_write" @saved="saved" />
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TalentResourceNav from './components/TalentResourceNav.vue'
import ChannelEditor from './components/ChannelEditor.vue'
import ChannelDescriptionEditor from './components/ChannelDescriptionEditor.vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'
import { channelColumns, defaultChannelColumns, cleanChannelColumns, channelMembersText, channelDateTime, channelParams } from '@/utils/resourceChannels'

const options = reactive({ users: [], can_write: false, user_id: '' })
const filters = reactive({ keyword: '', category: '', maintainer_ids: [], user_ids: [] })
const rows = ref([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), advanced = ref(false), filterPeople = ref([]), editorRef = ref(null), descriptionRef = ref(null)
const selectedColumns = ref([...defaultChannelColumns])
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
  } catch (error) { if (!cancelled(error) && seq === sequence) ElMessage.error(error.message) }
  finally { if (seq === sequence) loading.value = false }
}
function query() { page.value = 1; loadList() }
function keywordChanged(value) { clearTimeout(timer); request?.abort(); sequence++; loading.value = false; if (!value) query(); else timer = setTimeout(query, 400) }
function clearAdvanced() { filters.maintainer_ids = []; filters.user_ids = []; query() }
function reset() { Object.assign(filters, { keyword: '', category: '', maintainer_ids: [], user_ids: [] }); query() }
async function openEditor(row) { try { await loadOptions(); await editorRef.value.open(row) } catch (error) { ElMessage.error(error.message) } }
async function saved() { await Promise.all([loadOptions(), loadList()]).catch(error => ElMessage.error(error.message)) }
onMounted(async () => {
  try {
    await loadOptions()
    try {
      const raw = localStorage.getItem(columnKey())
      selectedColumns.value = raw ? cleanChannelColumns(JSON.parse(raw)) : [...defaultChannelColumns]
      if (raw) localStorage.setItem(columnKey(), JSON.stringify(selectedColumns.value))
    } catch { selectedColumns.value = [...defaultChannelColumns]; try { localStorage.removeItem(columnKey()) } catch { /* 使用默认字段。 */ } }
    columnsReady = true; await loadList()
  } catch (error) { ElMessage.error(error.message) }
})
onBeforeUnmount(() => { clearTimeout(timer); request?.abort(); sequence++ })
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
.channel-details-body { max-height:560px; overflow-y:auto; }
.channel-details .el-descriptions__table { table-layout:fixed; width:100%; }
.channel-details .el-descriptions__cell { white-space:pre-wrap; overflow-wrap:anywhere; }
.resource-channels-page .el-pagination { justify-content:flex-end; margin-top:16px; max-width:100%; overflow-x:auto; }
@media(max-width:640px) { .channel-advanced-grid { grid-template-columns:minmax(0,1fr); } }
</style>
