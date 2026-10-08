<template>
  <el-card class="referral-development-page">
    <div class="referral-heading"><div><h2>推荐拓展</h2><p class="referral-muted">按推荐人与日期记录推广奖励、凭证和付款情况</p></div><div class="referral-actions">
      <el-popover trigger="click" placement="bottom-end" :width="280"><template #reference><el-button>字段设置</el-button></template><div class="referral-column-options"><el-checkbox-group v-model="selectedColumns"><el-checkbox v-for="column in referralColumns" :key="column.key" :value="column.key">{{ column.label }}</el-checkbox></el-checkbox-group></div><el-button text type="primary" @click="selectedColumns = [...defaultReferralColumns]">恢复默认</el-button></el-popover>
      <el-button v-if="options.can_write && !deleteMode" type="primary" @click="editorRef.open()">新增</el-button>
      <BatchDeleteToolbar v-if="options.can_write" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
    </div></div>
    <TalentResourceNav />
    <div class="referral-filters">
      <el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="推广开始日期" end-placeholder="推广结束日期" @change="query" />
      <el-input v-model="filters.keyword" clearable placeholder="推荐人姓名、微信" @input="keywordChanged" @keyup.enter="query" />
      <el-select v-model="filters.payment_status" clearable placeholder="付款状态" @change="query"><el-option label="未支付" value="unpaid" /><el-option label="已支付" value="paid" /></el-select>
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="referral-advanced"><template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
        <div class="referral-advanced-body"><div class="referral-advanced-grid">
          <div><label>录入人</label><el-select v-model="filters.creator_id" clearable filterable @change="query"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></div>
          <div><label>最近操作人</label><el-select v-model="filters.operator_id" clearable filterable @change="query"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></div>
          <div class="referral-wide"><label>付款日期</label><el-date-picker v-model="filters.paid_range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="付款开始日期" end-placeholder="付款结束日期" @change="query" /></div>
        </div><div class="referral-advanced-footer"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced = false">关闭</el-button></div></div>
      </el-popover>
    </div>
    <el-table ref="tableRef" v-loading="loading" :data="rows" row-key="id" border @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" :selectable="row => row.can_delete" />
      <el-table-column label="序号" type="index" width="65" :index="index => (pagination.page - 1) * pagination.limit + index + 1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip>
        <template #default="{ row }"><el-tag v-if="column.key === 'payment_status'" :type="row.payment_status === 'paid' ? 'success' : 'warning'" effect="plain">{{ displayReferralValue(row, column.key) }}</el-tag><span v-else>{{ displayReferralValue(row, column.key) }}</span></template>
      </el-table-column>
      <el-table-column label="详情" fixed="right" width="105"><template #default="{ row }">
        <el-popover trigger="click" placement="left" :width="760" title="推荐拓展详情" popper-class="referral-detail-popover" @show="loadDetail(row.id)">
          <div v-loading="detailLoading[row.id]" class="referral-detail-wrapper"><ReferralDetailContent v-if="details[row.id]" :record="details[row.id]" /><el-button v-else-if="detailErrors[row.id]" @click="loadDetail(row.id)">加载失败，点击重试</el-button><p v-else>正在加载详情…</p></div>
          <template #reference><el-button link type="primary">查看详情</el-button></template>
        </el-popover>
      </template></el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" fixed="right" width="185"><template #default="{ row }"><el-button v-if="row.can_edit" link type="primary" @click="editorRef.open(row)">编辑</el-button><el-button v-if="row.can_edit" link type="primary" @click="editorRef.open(row, 'payment')">{{ row.payment_status === 'paid' ? '更正付款' : '登记付款' }}</el-button><span v-if="!row.can_edit" class="referral-muted">只读</span></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :page-sizes="[10,20,50,100]" :total="pagination.total" layout="total, sizes, prev, pager, next, jumper" @current-change="pageChanged" @size-change="sizeChanged" />
    <ReferralRecordEditor ref="editorRef" @saved="recordSaved" />
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TalentResourceNav from './components/TalentResourceNav.vue'
import ReferralDetailContent from './components/ReferralDetailContent.vue'
import ReferralRecordEditor from './components/ReferralRecordEditor.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { referralApi as api } from '@/api/referralDevelopment'
import { referralColumns, defaultReferralColumns, cleanReferralColumns, displayReferralValue } from '@/utils/referralDevelopment'
const options = reactive({ user_id: '', users: [], can_write: false })
const rows = ref([]), tableRef = ref(), editorRef = ref(), loading = ref(false), advanced = ref(false)
const filters = reactive({ range: null, keyword: '', payment_status: '', creator_id: '', operator_id: '', paid_range: null })
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const selectedColumns = ref([...defaultReferralColumns])
const visibleColumns = computed(() => referralColumns.filter(c => selectedColumns.value.includes(c.key)))
const advancedCount = computed(() => [filters.creator_id, filters.operator_id, filters.paid_range?.length ? true : false].filter(Boolean).length)
const columnKey = () => `referral-development:columns:${options.user_id}`
watch(selectedColumns, value => { if (options.user_id) { try { localStorage.setItem(columnKey(), JSON.stringify(value)) } catch { /* 浏览器存储不可用时仍可切换字段。 */ } } }, { deep: true })
const details = reactive({}), detailLoading = reactive({}), detailErrors = reactive({}), detailControllers = new Map()
function invalidateDetail(id) { detailControllers.get(id)?.abort(); detailControllers.delete(id); delete details[id]; delete detailErrors[id]; delete detailLoading[id] }
const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({ rows, tableRef, pagination, deleteRow: api.remove, getLabel: row => row.full_name, reload: () => reload(true), onDeleted: row => invalidateDetail(row.id), entityName: '推荐拓展记录' })
let controller, sequence = 0, timer
const cancelled = e => ['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)
const params = () => ({ start: filters.range?.[0] || undefined, end: filters.range?.[1] || undefined, keyword: filters.keyword.trim() || undefined, payment_status: filters.payment_status || undefined, creator_id: filters.creator_id || undefined, operator_id: filters.operator_id || undefined, paid_start: filters.paid_range?.[0] || undefined, paid_end: filters.paid_range?.[1] || undefined })
async function reload(keepDelete = false) {
  clearTimeout(timer); controller?.abort(); const seq = ++sequence; controller = new AbortController(); loading.value = true
  if (!keepDelete) exitDeleteMode()
  try {
    const data = await api.records({ ...params(), skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit }, controller.signal)
    if (seq !== sequence) return
    pagination.total = data.total
    const last = Math.max(1, Math.ceil(data.total / pagination.limit))
    if (pagination.page > last) { pagination.page = last; return reload(keepDelete) }
    rows.value = data.items
  } catch (e) { if (!cancelled(e) && seq === sequence) ElMessage.error(e.message) } finally { if (seq === sequence) loading.value = false }
}
function query() { pagination.page = 1; reload() }
function keywordChanged(value) {
  clearTimeout(timer); controller?.abort(); ++sequence; loading.value = false
  if (!value.trim()) query(); else timer = setTimeout(query, 400)
}
function reset() { Object.assign(filters, { range: null, keyword: '', payment_status: '', creator_id: '', operator_id: '', paid_range: null }); query() }
function clearAdvanced() { filters.creator_id = ''; filters.operator_id = ''; filters.paid_range = null; query() }
function pageChanged() { reload() }
function sizeChanged() { pagination.page = 1; reload() }
async function loadDetail(id) {
  if (details[id] || detailLoading[id]) return
  const current = new AbortController(); detailControllers.set(id, current); detailLoading[id] = true; delete detailErrors[id]
  try { const data = await api.detail(id, current.signal); if (detailControllers.get(id) === current) details[id] = data }
  catch (e) { if (!cancelled(e) && detailControllers.get(id) === current) detailErrors[id] = e.message }
  finally { if (detailControllers.get(id) === current) { detailLoading[id] = false; detailControllers.delete(id) } }
}
function recordSaved(id) { invalidateDetail(id); reload() }
onMounted(async () => {
  try {
    Object.assign(options, await api.options())
    try { const stored = localStorage.getItem(columnKey()); if (stored !== null) { selectedColumns.value = cleanReferralColumns(JSON.parse(stored)); localStorage.setItem(columnKey(), JSON.stringify(selectedColumns.value)) } }
    catch { selectedColumns.value = [...defaultReferralColumns]; try { localStorage.removeItem(columnKey()) } catch { /* 当前浏览器不允许存储。 */ } }
    await reload()
  } catch (e) { ElMessage.error(e.message) }
})
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); ++sequence; detailControllers.forEach(c => c.abort()) })
</script>

<style>
.referral-heading{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:16px}.referral-heading h2{margin:0 0 5px}.referral-heading p{margin:0}.referral-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.referral-actions>.el-button+.el-button{margin-left:0}.referral-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:20px}.referral-filters>.el-input{width:230px}.referral-filters>.el-select{width:140px}.referral-filters>.el-date-editor{width:310px;flex-grow:0}.referral-development-page .el-pagination{margin-top:20px;justify-content:flex-end;max-width:100%;overflow-x:auto}.referral-column-options{max-height:400px;overflow-y:auto}.referral-column-options .el-checkbox{display:flex;margin:4px 0}.referral-advanced.el-popover{max-width:calc(100vw - 32px);box-sizing:border-box}.referral-advanced-body{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.referral-advanced-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.referral-advanced-grid label{display:block;margin-bottom:8px}.referral-advanced-grid .el-select,.referral-advanced-grid .el-date-editor{width:100%;box-sizing:border-box}.referral-wide{grid-column:1/-1}.referral-advanced-footer{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}.referral-detail-popover.el-popover{max-width:calc(100vw - 32px);box-sizing:border-box}.referral-detail-wrapper{min-height:60px;max-height:560px;overflow-y:auto}@media(max-width:640px){.referral-filters>.el-date-editor,.referral-filters>.el-input,.referral-filters>.el-select{width:100%;min-width:0}.referral-advanced-grid{grid-template-columns:1fr}}
</style>
