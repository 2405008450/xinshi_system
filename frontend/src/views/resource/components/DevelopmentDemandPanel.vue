<template>
  <section class="development-demand-panel">
    <div class="development-demand-heading">
      <h3>需求管理 <span class="muted">共 {{ total }} 项</span></h3>
      <div class="development-demand-search">
        <el-input v-model="keyword" clearable placeholder="订单号、项目名称、需求编号" @input="keywordChanged" @keyup.enter="query" />
        <el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      </div>
    </div>
    <p class="muted">已发送的需求可分配到多个平台账号；默认每页显示 5 项。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border row-key="id" class="development-demand-table" empty-text="暂无已发送的需求">
      <el-table-column label="订单号" prop="order_no" width="160" show-overflow-tooltip><template #default="{row}">{{ row.order_no || '-' }}</template></el-table-column>
      <el-table-column label="需求项目" min-width="200">
        <template #default="{row}">
          <el-popover trigger="click" placement="left" :width="760" :popper-options="popoverOptions" title="需求项目详情" popper-class="development-detail" @show="loadDetail(row)">
            <template #reference><el-button link type="primary" class="arrangement-project-link">{{ row.project_name || row.request_no }}</el-button></template>
            <div v-loading="detailLoading[row.id]" class="development-detail-body">
              <el-alert v-if="detailErrors[row.id]" :title="detailErrors[row.id]" type="error" :closable="false" />
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="订单号">{{ row.order_no || '-' }}</el-descriptions-item>
                <el-descriptions-item label="项目名称">{{ row.project_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="需求编号">{{ row.request_no }}</el-descriptions-item>
                <el-descriptions-item label="需求状态">{{ detailCache[row.id]?.demand_status === 'cancelled' ? '已取消' : '已发送' }}</el-descriptions-item>
                <el-descriptions-item label="语种／方言" :span="2">{{ (detailCache[row.id]?.languages || row.languages || []).join('、') || '-' }}</el-descriptions-item>
                <el-descriptions-item label="需求说明" :span="2">{{ detailCache[row.id]?.request_detail || row.request_detail || '-' }}</el-descriptions-item>
              </el-descriptions>
              <RequestArrangementHistory :items="detailCache[row.id]?.arrangements || row.arrangements || []" />
            </div>
          </el-popover>
          <small class="muted">{{ row.request_no }}</small>
        </template>
      </el-table-column>
      <el-table-column label="已安排平台" min-width="180"><template #default="{row}"><span>{{ platformNames(row) || '暂未安排' }}</span></template></el-table-column>
      <el-table-column v-if="options.can_delegate" label="操作" fixed="right" width="100"><template #default="{row}"><el-button link type="primary" @click="editorRef.open(row, defaultDate)">每日安排</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-if="total > 5" v-model:current-page="page" :page-size="5" :total="total" layout="total, prev, pager, next" @current-change="reload" />
    <RequestArrangementDialog ref="editorRef" :options="options" @saved="day => emit('saved', day)" />
  </section>
</template>
<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementPopoverOptions as popoverOptions } from '@/utils/resourceArrangements'
import RequestArrangementDialog from './RequestArrangementDialog.vue'
import RequestArrangementHistory from './RequestArrangementHistory.vue'
defineProps({ options: { type: Object, required: true }, defaultDate: { type: String, default: '' } })
const emit = defineEmits(['saved'])
const rows = ref([]), total = ref(0), page = ref(1), keyword = ref(''), loading = ref(false), error = ref(''), editorRef = ref()
const detailCache = reactive({}), detailLoading = reactive({}), detailErrors = reactive({})
const detailControllers = new Map()
let controller, sequence = 0, timer
const cancelled = e => ['ERR_CANCELED', 'CanceledError', 'AbortError'].includes(e.code || e.name)
const platformNames = row => [...new Set((row.arrangements || []).map(item => item.platform_name))].join('、')
function clearDetails() {
  for (const value of detailControllers.values()) value.abort()
  detailControllers.clear()
  for (const map of [detailCache, detailLoading, detailErrors]) for (const key of Object.keys(map)) delete map[key]
}
async function reload() {
  clearTimeout(timer); controller?.abort(); clearDetails()
  const seq = ++sequence, current = new AbortController(); controller = current; loading.value = true; error.value = ''
  try {
    const result = await api.arrangementRequests({ keyword: keyword.value || undefined, skip: (page.value - 1) * 5, limit: 5 }, current.signal)
    if (seq !== sequence) return
    total.value = result.total || 0
    const last = Math.max(1, Math.ceil(total.value / 5))
    if (page.value > last) { page.value = last; return reload() }
    rows.value = result.items || []
  } catch (e) { if (seq === sequence && !cancelled(e)) { rows.value = []; error.value = e.message } }
  finally { if (seq === sequence) loading.value = false }
}
function query() { page.value = 1; reload() }
function keywordChanged(value) { clearTimeout(timer); controller?.abort(); sequence++; if (!value) query(); else timer = setTimeout(query, 400) }
function reset() { keyword.value = ''; query() }
async function loadDetail(row) {
  if (detailCache[row.id] || detailLoading[row.id]) return
  const current = new AbortController(); detailControllers.set(row.id, current)
  detailLoading[row.id] = true; delete detailErrors[row.id]
  try {
    const value = await api.arrangementRequest(row.id, current.signal)
    if (!current.signal.aborted) detailCache[row.id] = value
  } catch (e) { if (!current.signal.aborted && !cancelled(e)) detailErrors[row.id] = e.message }
  finally { if (detailControllers.get(row.id) === current) { detailLoading[row.id] = false; detailControllers.delete(row.id) } }
}
onMounted(reload)
onBeforeUnmount(() => { clearTimeout(timer); sequence++; controller?.abort(); clearDetails() })
defineExpose({ reload })
</script>
<style>
.development-demand-panel{padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid var(--el-border-color-light)}
.development-demand-heading,.development-demand-search{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.development-demand-heading{justify-content:space-between}.development-demand-heading h3{margin:0}.development-demand-heading h3>span{margin-left:8px;font-weight:normal}.development-demand-search>.el-input{width:270px}.development-demand-table small{display:block}.development-demand-table .cell{overflow-wrap:anywhere}.development-demand-panel>.el-alert{margin:12px 0}
@media(max-width:600px){.development-demand-search{width:100%}.development-demand-search>.el-input{width:100%}}
</style>
