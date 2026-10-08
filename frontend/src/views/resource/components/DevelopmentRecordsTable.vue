<template>
  <el-table ref="tableRef" v-loading="loading" :data="rows" :height="height" row-key="id" border stripe @selection-change="$emit('selection-change', $event)">
    <el-table-column v-if="deleteMode" type="selection" width="48" :selectable="row => row.can_delete" fixed="left" />
    <el-table-column type="index" :index="index => (page - 1) * pageSize + index + 1" label="序号" width="65" />
    <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip>
      <template #header>
        <ConfiguredColumnHeaderFilter :definition="columnDefinition(column)" :model-value="columnFilters[column.key]"
          @update:model-value="$emit('column-filter', column.key, $event)" @text-input="$emit('text-input', column.key, $event)"
          @change="$emit('query')" @enter="$emit('query')" @clear="$emit('query')" />
      </template>
      <template #default="{ row }">
        <DevelopmentGroupProgress v-if="isGroupChannel(progressColumnChannel[column.key])" :row="row" :channel="progressColumnChannel[column.key]" :editable="editable(row)" @saved="$emit('saved')" @edit="(record, channel, status) => $emit('edit', record, channel, status)" />
        <el-button v-else-if="progressColumnChannel[column.key] && editable(row)" link type="primary" class="development-progress" @click="$emit('edit', row, progressColumnChannel[column.key])">{{ display(row, column.key) }}</el-button>
        <el-button v-else-if="!crossDate && column.key === 'platform_name' && options.can_write && !deleteMode" link type="primary" @click="$emit('platform', row.platform_id)">{{ row.platform_name }}</el-button>
        <el-button v-else-if="!crossDate && column.key === 'owner_name' && editable(row)" link type="primary" :aria-label="`填写${row.owner_name}的每日工时`" @click="$emit('work', row.work_date, row.owner_id)">{{ display(row, column.key) }}</el-button>
        <el-button v-else-if="!crossDate && column.key === 'work_date'" link type="primary" @click="$emit('statistic', row.work_date)">{{ display(row, column.key) }}</el-button>
        <el-button v-else-if="column.key === 'latest_follow_up' && editable(row)" link type="primary" class="development-progress" :title="row.latest_follow_up || row.follow_up || ''" @click="$emit('edit', row, 'follow_up')">{{ followUpText(row) || '填写后续跟进情况' }}</el-button>
        <span v-else>{{ display(row, column.key) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="详情" width="105" fixed="right">
      <template #default="{ row }">
        <el-popover trigger="click" placement="left" :width="760" title="资源开拓详情" popper-class="development-detail" @show="loadDetail(row)">
          <template #reference><el-button link type="primary">查看详情</el-button></template>
          <div v-loading="detailLoading[row.id]" class="development-detail-body"><DevelopmentDetailContent v-if="details[row.id]" :record="details[row.id]" :accounts="accounts" /></div>
        </el-popover>
      </template>
    </el-table-column>
    <el-table-column v-if="!deleteMode" label="操作" width="90" fixed="right">
      <template #default="{ row }"><el-button v-if="editable(row)" link type="primary" @click="$emit('edit', row)">编辑</el-button><span v-else class="muted">只读</span></template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import DevelopmentDetailContent from './DevelopmentDetailContent.vue'
import DevelopmentGroupProgress from './DevelopmentGroupProgress.vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { developmentColumns, progressColumnChannel, progressText, progressStatuses, isGroupChannel, followUpText } from '@/utils/resourceDevelopment'

const props = defineProps({
  rows: { type: Array, required: true }, options: { type: Object, required: true },
  selectedColumns: { type: Array, required: true }, columnFilters: { type: Object, required: true },
  page: { type: Number, default: 1 }, pageSize: { type: Number, default: 10 },
  loading: Boolean, deleteMode: Boolean, crossDate: Boolean, height: [String, Number],
})
defineEmits(['selection-change', 'column-filter', 'text-input', 'query', 'edit', 'platform', 'work', 'statistic', 'saved'])
const tableRef = ref()
const details = reactive({}), detailLoading = reactive({}), controllers = new Map()
let generation = 0
const visibleColumns = computed(() => {
  const columns = developmentColumns.filter(column => props.selectedColumns.includes(column.key))
  // 跨日结果优先显示业务日期，用户无需横向滚动就能区分记录来源日期。
  return props.crossDate ? [...columns.filter(column => column.key === 'work_date'), ...columns.filter(column => column.key !== 'work_date')] : columns
})
const platforms = computed(() => props.options.options.filter(option => option.kind === 'platform'))
const accounts = computed(() => props.options.options.filter(option => option.kind === 'account'))
const editable = row => props.options.can_write && row.can_edit && !props.deleteMode
function columnDefinition(column) {
  const selects = { platform_name: platforms.value, owner_name: props.options.users, account_name: accounts.value, language_names: props.options.languages }
  const channel = progressColumnChannel[column.key]
  return { key: column.key, label: column.label, type: selects[column.key] || channel ? 'select' : 'text',
    options: channel ? progressStatuses(channel) : selects[column.key], headerWidth: 280,
    placeholder: ['work_date', 'updated_at'].includes(column.key) ? '例如 2026-09-24' : column.key === 'latest_follow_up' ? '跟进内容、操作人或操作日期' : `筛选${column.label}` }
}
const chineseDate = value => value ? new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString('zh-CN') : '-'
const chineseTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
const display = (row, key) => key === 'latest_follow_up' ? followUpText(row) || '-' : progressColumnChannel[key] ? progressText(row, progressColumnChannel[key]) : key === 'work_date' ? chineseDate(row[key]) : key === 'updated_at' ? chineseTime(row[key]) : row[key] || '-'
function invalidateDetails() {
  generation++
  controllers.forEach(controller => controller.abort()); controllers.clear()
  Object.keys(details).forEach(key => delete details[key])
  Object.keys(detailLoading).forEach(key => delete detailLoading[key])
}
async function loadDetail(row) {
  if (details[row.id] || controllers.has(row.id)) return
  const current = generation, controller = new AbortController()
  controllers.set(row.id, controller); detailLoading[row.id] = true
  try {
    const data = await api.detail(row.id, controller.signal)
    if (current === generation) details[row.id] = data
  } catch (error) {
    if (current === generation && !controller.signal.aborted) ElMessage.error(error.message)
  } finally {
    if (current === generation) { controllers.delete(row.id); detailLoading[row.id] = false }
  }
}
onBeforeUnmount(invalidateDetails)
defineExpose({ invalidateDetails, clearSelection: () => tableRef.value?.clearSelection(), toggleRowSelection: (...args) => tableRef.value?.toggleRowSelection(...args) })
</script>
