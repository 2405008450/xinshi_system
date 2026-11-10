<template>
  <section class="source-analysis">
    <el-empty v-if="customerMode && !clientId" description="请先保存客户，再查看关联的新咨询来源" />
    <template v-else>
      <div class="source-controls">
        <el-radio-group v-model="granularity" aria-label="统计周期">
          <el-radio-button v-if="!confirmedOnly" value="day">按日</el-radio-button>
          <el-radio-button value="week">按周</el-radio-button>
          <el-radio-button value="month">按月</el-radio-button>
        </el-radio-group>
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" />
        <el-button type="primary" :loading="loading" @click="refresh">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-if="!customerMode && ['source', 'keyword'].includes(dimension)" :disabled="loading" @click="aiVisible = !aiVisible">{{ aiVisible ? '收起 AI 分析' : 'AI 分析与分类' }}</el-button>
      </div>
      <p v-if="confirmedOnly" class="source-note">仅统计当前咨询状态为“已确认”的记录，同一客户多次已确认咨询分别计数；按咨询时间（UTC+8）归属周/月，周一为每周起点。未填写的分类字段归为“未知”。</p>
      <p v-else class="source-note">按新咨询记录统计，同一客户多次咨询分别计数；使用咨询时间（UTC+8），周一为每周起点。未填写的分析字段归为“未知”。<template v-if="dimension === 'keyword'">关键词按原始字段完整内容分组。</template></p>
      <el-alert v-if="summaryError" :title="summaryError" type="error" :closable="false" show-icon />
      <CustomerSourceAiPanel v-if="aiVisible && !customerMode && ['source', 'keyword'].includes(dimension)" :dimension="dimension" :stats="stats" :start="dateRange?.[0]" :end="dateRange?.[1]" :granularity="granularity" :loading="loading" />
      <div v-loading="loading">
        <div class="source-totals">
          <span>{{ confirmedOnly ? '成交数量（已确认）' : '咨询记录' }} <strong>{{ stats.total }}</strong></span>
          <span>{{ confirmedOnly ? '成交客户' : '关联客户' }} <strong>{{ stats.client_count }}</strong></span>
          <span>{{ dimensionTitle }}种类 <strong>{{ stats.sources.length }}</strong></span>
        </div>
        <el-alert v-if="stats.undated_count" :title="`${stats.undated_count} 条记录未填写咨询时间，已计入${confirmedOnly ? '成交汇总' : '分类汇总'}，未计入日期趋势。`" type="info" :closable="false" />
        <h4>{{ dimensionTitle }}{{ confirmedOnly ? '成交分布' : '分布' }} <small>点击分类查看{{ confirmedOnly ? '成交明细' : '咨询记录' }}</small></h4>
        <el-table :data="stats.sources" stripe max-height="360" empty-text="暂无咨询统计数据">
          <el-table-column :label="dimensionTitle" min-width="180">
            <template #default="{ row }"><el-button link type="primary" :disabled="loading" @click="selectSource(row.source)">{{ dimensionLabel(row.source) }}</el-button></template>
          </el-table-column>
          <el-table-column prop="count" :label="confirmedOnly ? '成交数量' : '咨询数量'" width="105" />
          <el-table-column prop="client_count" label="客户数量" width="105" />
          <el-table-column label="占比" min-width="150"><template #default="{ row }"><el-progress :percentage="percentage(row.count)" :stroke-width="10" /></template></el-table-column>
        </el-table>
        <template v-if="dimension === 'type_status'">
          <h4>咨询类型与状态交叉统计 <small>点击数量查看对应咨询</small></h4>
          <el-table :data="combinationTypes" stripe max-height="360">
            <el-table-column prop="type" label="咨询类型" min-width="150" fixed />
            <el-table-column v-for="status in combinationStatuses" :key="status" :label="statusLabel(status)" min-width="110">
              <template #default="{ row }"><el-button link type="primary" :disabled="loading || !combinationCount(row.type, status)" @click="selectSource(JSON.stringify([row.type, status]))">{{ combinationCount(row.type, status) }}</el-button></template>
            </el-table-column>
          </el-table>
        </template>
        <h4>{{ dimensionTitle }}{{ confirmedOnly ? '成交趋势' : '趋势' }} <small>{{ periodHint }}，点击数量查看当期明细<span v-if="stats.sources.length > 10">；趋势展示数量前 10 类，合计包含全部分类</span></small></h4>
        <el-table :data="stats.periods" stripe max-height="360" empty-text="暂无可按日期统计的数据">
          <el-table-column label="统计周期" width="190" fixed><template #default="{ row }">{{ periodLabel(row.period) }}</template></el-table-column>
          <el-table-column label="合计" width="90"><template #default="{ row }"><el-button link type="primary" :disabled="loading" @click="selectPeriod(row.period)">{{ row.count }}</el-button></template></el-table-column>
          <el-table-column v-for="item in stats.sources.slice(0, 10)" :key="item.source" :label="dimensionLabel(item.source)" min-width="125" show-overflow-tooltip>
            <template #default="{ row }"><el-button link type="primary" :disabled="loading || !periodCount(row, item.source)" @click="selectPeriod(row.period, item.source)">{{ periodCount(row, item.source) }}</el-button></template>
          </el-table-column>
        </el-table>
      </div>
      <div class="source-record-heading"><h4>{{ confirmedOnly ? '成交明细（已确认）' : '咨询明细' }} · {{ selectedSource === null ? '全部分类' : dimensionLabel(selectedSource) }}<small v-if="selectedPeriod"> · {{ periodLabel(selectedPeriod) }}</small></h4><el-button v-if="selectedSource !== null || selectedPeriod" link type="primary" @click="clearSelection">查看全部</el-button></div>
      <el-alert v-if="recordsError" :title="recordsError" type="error" :closable="false" show-icon />
      <el-table v-loading="recordsLoading" :data="items" stripe max-height="430" empty-text="暂无关联的新咨询记录">
        <el-table-column prop="consultation_code" label="咨询编号" min-width="145" />
        <el-table-column label="咨询时间" min-width="175"><template #default="{ row }">{{ formatBusinessDateTimeMinute(row.consultation_time) }}</template></el-table-column>
        <el-table-column v-if="!customerMode" label="客户" min-width="170" show-overflow-tooltip><template #default="{ row }">{{ row.client_name || row.client_short_name || '未关联客户' }}</template></el-table-column>
        <el-table-column prop="client_source" label="客户来源" min-width="140" show-overflow-tooltip />
        <el-table-column v-if="dimension === 'method'" label="咨询方式" min-width="120"><template #default="{ row }">{{ methodLabel(row.consultation_method) }}</template></el-table-column>
        <el-table-column v-if="['type', 'type_status', 'type_confirmed'].includes(dimension)" prop="consultation_type" :label="confirmedOnly ? '项目类型' : '咨询类型'" min-width="130" />
        <el-table-column v-if="confirmedOnly || ['status', 'type_status'].includes(dimension)" label="咨询状态" min-width="110"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
        <el-table-column prop="source_keyword" label="来源关键词" min-width="170" show-overflow-tooltip><template #default="{ row }">{{ row.source_keyword || '-' }}</template></el-table-column>
        <el-table-column label="详情" width="100" fixed="right">
          <template #default="{ row }">
            <el-popover trigger="click" placement="left" :width="760" title="咨询记录详情" popper-class="customer-source-detail">
              <template #reference><el-button link type="primary">查看详情</el-button></template>
              <div><div class="source-detail-scroll">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item v-for="field in detailFields" :key="field.key" :label="field.label">{{ detailValue(row, field.key) }}</el-descriptions-item>
                </el-descriptions>
              </div></div>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="loadRecords" />
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import CustomerSourceAiPanel from './CustomerSourceAiPanel.vue'
import { getCustomerSourceRecords, getCustomerSourceSummary } from '@/api/customerSources'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'

const props = defineProps({ clientId: { type: String, default: null }, customerMode: Boolean, dimension: { type: String, default: 'source' } })
const confirmedOnly = computed(() => ['type_confirmed', 'source_confirmed'].includes(props.dimension))
const dimensionTitle = computed(() => ({ source: '客户来源', method: '咨询方式', type: '咨询类型', keyword: '来源关键词', status: '咨询状态', type_status: '类型与状态组合', type_confirmed: '项目类型', source_confirmed: '客户来源' }[props.dimension]))
const statusLabel = value => ({ pending: '待处理', following: '跟进中', emphasis: '重点跟进', success: '已确认', failed: '未成交' }[value] || value || '未知')
const methodLabel = value => ({ phone: '电话', email: '邮件', online: '在线咨询', onsite: '上门', other: '其他' }[value] || value || '-')
function dimensionLabel(value) {
  if (props.dimension === 'status') return statusLabel(value)
  if (props.dimension === 'type_status') { try { const pair = JSON.parse(value); return `${pair[0]} / ${statusLabel(pair[1])}` } catch { return value } }
  return value
}
const granularity = ref(confirmedOnly.value ? 'month' : 'day')
const aiVisible = ref(false)
const dateRange = ref(null)
const emptyStats = () => ({ total: 0, client_count: 0, sources: [], periods: [], undated_count: 0 })
const stats = ref(emptyStats())
const combinationTypes = computed(() => [...new Set(stats.value.sources.map(item => item.values[0]))].map(type => ({ type })))
const combinationStatuses = computed(() => [...new Set(stats.value.sources.map(item => item.values[1]))])
const combinationCount = (type, status) => stats.value.sources.find(item => item.values[0] === type && item.values[1] === status)?.count || 0
const loading = ref(false)
const recordsLoading = ref(false)
const summaryError = ref('')
const recordsError = ref('')
const selectedSource = ref(null)
const selectedPeriod = ref('')
const items = ref([])
const page = ref(1)
const total = ref(0)
let summaryController, recordsController, summarySequence = 0, recordsSequence = 0
const periodHint = computed(() => ({ day: '每天', week: '每周（周一起）', month: '每月' }[granularity.value]))
const detailFields = [
  { key: 'consultation_code', label: '咨询编号' }, { key: 'consultation_time', label: '咨询时间' },
  { key: 'client_name', label: '客户全称' }, { key: 'client_short_name', label: '客户简称' },
  { key: 'client_source', label: '客户来源' }, { key: 'source_keyword', label: '来源关键词' },
  { key: 'contact_name', label: '联系人' }, { key: 'consultation_type', label: '咨询类型' },
  { key: 'consultation_method', label: '咨询方式' }, { key: 'consultation_method_detail', label: '方式说明' },
  { key: 'status', label: '咨询状态' }, { key: 'handling_method', label: '处理方式' },
  { key: 'failure_reason', label: '未成交原因' },
  { key: 'consultation_description', label: '咨询描述' }, { key: 'follow_up_remarks', label: '跟进备注' },
]
function detailValue(row, key) {
  if (key === 'failure_reason') return row[key] ? `${row[key].reason}${row[key].details ? `：${row[key].details}` : ''}` : '-'
  if (key === 'consultation_time') return formatBusinessDateTimeMinute(row[key])
  if (key === 'status') return statusLabel(row[key])
  if (key === 'consultation_method') return methodLabel(row[key])
  return row[key] || '-'
}
const percentage = count => stats.value.total ? Math.round(count * 10000 / stats.value.total) / 100 : 0
const periodCount = (row, key) => Object.hasOwn(row.sources, key) ? row.sources[key] : 0
const periodLabel = value => granularity.value === 'month' ? value.slice(0, 7) : granularity.value === 'week' ? `${value} 起一周` : value
const baseParams = () => ({ ...(!props.customerMode ? { dimension: props.dimension } : {}), ...(dateRange.value?.length === 2 ? { start: dateRange.value[0], end: dateRange.value[1] } : {}) })
function recordParams() {
  const params = { ...baseParams(), page: page.value, page_size: 20 }
  if (selectedSource.value !== null) params.source = selectedSource.value
  if (selectedPeriod.value) {
    const start = selectedPeriod.value
    const endDate = new Date(`${start}T00:00:00Z`)
    if (granularity.value === 'month') endDate.setUTCMonth(endDate.getUTCMonth() + 1)
    else endDate.setUTCDate(endDate.getUTCDate() + (granularity.value === 'week' ? 7 : 1))
    endDate.setUTCDate(endDate.getUTCDate() - 1)
    const end = endDate.toISOString().slice(0, 10)
    params.start = params.start && params.start > start ? params.start : start
    params.end = params.end && params.end < end ? params.end : end
  }
  return params
}
const cancelled = error => error?.code === 'ERR_CANCELED' || error?.name === 'AbortError'
async function loadRecords() {
  recordsController?.abort()
  const sequence = ++recordsSequence
  recordsController = new AbortController()
  recordsLoading.value = true
  recordsError.value = ''
  items.value = []
  try {
    const result = await getCustomerSourceRecords(props.clientId, recordParams(), { signal: recordsController.signal })
    if (sequence !== recordsSequence) return
    items.value = result.items
    total.value = result.total
    page.value = result.page
  } catch (error) {
    if (sequence === recordsSequence && !cancelled(error)) { total.value = 0; recordsError.value = '咨询明细加载失败，请点击查询重试' }
  } finally {
    if (sequence === recordsSequence) recordsLoading.value = false
  }
}
async function refresh() {
  summaryController?.abort()
  recordsController?.abort()
  ++recordsSequence
  const sequence = ++summarySequence
  items.value = []; total.value = 0; stats.value = emptyStats(); recordsLoading.value = false
  selectedSource.value = null; selectedPeriod.value = ''; page.value = 1
  summaryError.value = ''; recordsError.value = ''
  if (props.customerMode && !props.clientId) { loading.value = false; return }
  summaryController = new AbortController()
  loading.value = true
  try {
    const result = await getCustomerSourceSummary(props.clientId, { ...baseParams(), granularity: granularity.value }, { signal: summaryController.signal })
    if (sequence !== summarySequence) return
    stats.value = result
    await loadRecords()
  } catch (error) {
    if (sequence === summarySequence && !cancelled(error)) summaryError.value = '咨询统计加载失败，请点击查询重试'
  } finally {
    if (sequence === summarySequence) loading.value = false
  }
}
function selectSource(source) { selectedSource.value = source; selectedPeriod.value = ''; page.value = 1; loadRecords() }
function selectPeriod(period, source = null) { selectedSource.value = source; selectedPeriod.value = period; page.value = 1; loadRecords() }
function clearSelection() { selectedSource.value = null; selectedPeriod.value = ''; page.value = 1; loadRecords() }
function reset() {
  const defaultGranularity = confirmedOnly.value ? 'month' : 'day'
  if (granularity.value === defaultGranularity && !dateRange.value) refresh()
  else { granularity.value = defaultGranularity; dateRange.value = null }
}
watch([() => props.clientId, () => props.dimension, granularity, dateRange], refresh, { immediate: true })
onBeforeUnmount(() => { ++summarySequence; ++recordsSequence; summaryController?.abort(); recordsController?.abort() })
</script>

<style scoped>
.source-analysis { min-width: 0; }
.source-analysis :deep(.el-button.is-link) { max-width: 100%; white-space: normal; overflow-wrap: anywhere; }
.source-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.source-controls :deep(.el-date-editor) { max-width: 100%; flex: 0 1 330px; }
.source-note, h4 small { color: var(--el-text-color-secondary); font-size: 12px; font-weight: normal; }
.source-note { line-height: 1.7; }
.source-totals { display: flex; flex-wrap: wrap; gap: 24px; margin: 20px 0; }
.source-totals strong { font-size: 24px; margin-left: 10px; }
.source-record-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.source-detail-scroll { max-height: 560px; overflow-y: auto; overflow-wrap: anywhere; }
.source-detail-scroll :deep(.el-descriptions__cell) { word-break: break-word; white-space: pre-wrap; }
.el-pagination { margin-top: 16px; max-width: 100%; overflow-x: auto; }
@media (max-width: 600px) { .source-totals { gap: 12px; } .source-totals strong { font-size: 20px; } }
</style>
<style>
.customer-source-detail { max-width: calc(100vw - 32px); }
</style>
