<template>
  <div class="charge-editor">
    <div class="charge-editor__header">
      <div>
        <strong>客户收费明细</strong>
        <span>计量收费的数量取自当前订单“客户字数”；含税与不含税金额分别维护。</span>
      </div>
      <el-button type="primary" link @click="addItem">新增收费项</el-button>
    </div>

    <el-table v-if="modelValue.length" :data="modelValue" border size="small">
      <el-table-column label="收费项目" min-width="130">
        <template #default="{ row }"><el-input v-model="row.itemName" maxlength="100" /></template>
      </el-table-column>
      <el-table-column label="计价模式" width="108">
        <template #default="{ row }">
          <el-select v-model="row.pricingMode" @change="onModeChange(row)">
            <el-option label="按数量" value="metric" />
            <el-option label="固定收费" value="fixed" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="账单月份" width="145">
        <template #default="{ row }">
          <el-date-picker
            v-model="row.billingMonth"
            type="month"
            value-format="YYYY-MM"
            format="YYYY年MM月"
            placeholder="选择月份"
            style="width: 100%"
          />
        </template>
      </el-table-column>
      <el-table-column label="客户字数口径" min-width="175">
        <template #default="{ row }">
          <el-select
            v-model="row.metricType"
            :disabled="row.pricingMode === 'fixed'"
            @change="onMetricChange(row)"
          >
            <el-option v-for="metric in WORD_COUNT_METRICS" :key="metric.key" :label="metric.label" :value="metric.key" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="数量" width="92" align="right">
        <template #default="{ row }">{{ quantityText(row) }}</template>
      </el-table-column>
      <el-table-column label="每计价单位" width="112">
        <template #default="{ row }">
          <el-input-number
            v-model="row.unitSize"
            :disabled="row.pricingMode === 'fixed'"
            :min="0.0001"
            :precision="4"
            :controls="false"
            @change="fillSuggestedTotals(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="不含税单价" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.unitPriceExclTax"
            :disabled="row.pricingMode === 'fixed'"
            :min="0"
            :precision="4"
            :controls="false"
            @change="fillSuggestedTotal(row, 'excl')"
          />
        </template>
      </el-table-column>
      <el-table-column label="含税单价" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.unitPriceInclTax"
            :disabled="row.pricingMode === 'fixed'"
            :min="0"
            :precision="4"
            :controls="false"
            @change="fillSuggestedTotal(row, 'incl')"
          />
        </template>
      </el-table-column>
      <el-table-column label="不含税总价" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.totalExclTax"
            :min="0"
            :precision="2"
            :controls="false"
            :placeholder="suggestedText(row, 'excl')"
          />
        </template>
      </el-table-column>
      <el-table-column label="含税总价" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.totalInclTax"
            :min="0"
            :precision="2"
            :controls="false"
            :placeholder="suggestedText(row, 'incl')"
          />
        </template>
      </el-table-column>
      <el-table-column label="币种" width="92">
        <template #default="{ row }">
          <el-input v-model="row.currency" maxlength="3" @blur="row.currency = String(row.currency || 'CNY').toUpperCase()" />
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="150">
        <template #default="{ row }"><el-input v-model="row.remarks" maxlength="5000" /></template>
      </el-table-column>
      <el-table-column label="操作" width="64" fixed="right">
        <template #default="{ $index }"><el-button type="danger" link @click="removeItem($index)">删除</el-button></template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无客户收费项" :image-size="48" />
    <div v-if="totalSummary" class="charge-editor__total">含税合计：{{ totalSummary }}</div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { WORD_COUNT_METRICS, normalizeWordCountMatrix } from '@/utils/wordCountMatrix'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  wordCountMatrix: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const customerValues = computed(() => normalizeWordCountMatrix(props.wordCountMatrix).customer)
const defaultUnitSize = (metric) => ['documents', 'pages'].includes(metric) ? 1 : 1000
const lastSuggestions = new WeakMap()

watch(
  () => props.modelValue,
  (rows) => rows.forEach((row) => {
    if (row.unitPriceExclTax == null && row.unitPrice != null) row.unitPriceExclTax = row.unitPrice
    if (row.totalExclTax == null && row.amountOverride != null) row.totalExclTax = row.amountOverride
    if (!lastSuggestions.has(row)) rememberSuggestedTotals(row)
  }),
  { immediate: true, deep: true },
)

watch(customerValues, () => {
  props.modelValue.forEach(fillSuggestedTotals)
}, { deep: true })

const addItem = () => emit('update:modelValue', [...props.modelValue, {
  id: null,
  sequenceNo: props.modelValue.length + 1,
  itemName: '翻译费',
  pricingMode: 'metric',
  metricType: 'words',
  unitSize: 1000,
  billingMonth: null,
  unitPriceExclTax: null,
  unitPriceInclTax: null,
  totalExclTax: null,
  totalInclTax: null,
  currency: 'CNY',
  remarks: '',
}])
const removeItem = (index) => emit('update:modelValue', props.modelValue.filter((_, itemIndex) => itemIndex !== index))

function onModeChange(row) {
  if (row.pricingMode === 'fixed') {
    row.metricType = null
    row.unitSize = null
    row.unitPriceExclTax = null
    row.unitPriceInclTax = null
  } else {
    row.metricType = row.metricType || 'words'
    row.unitSize = defaultUnitSize(row.metricType)
    fillSuggestedTotals(row)
  }
}
function onMetricChange(row) {
  row.unitSize = defaultUnitSize(row.metricType)
  fillSuggestedTotals(row)
}
function quantity(row) {
  return row.pricingMode === 'metric' ? customerValues.value[row.metricType] : null
}
function suggestedTotal(row, kind) {
  const count = quantity(row)
  const unitPrice = kind === 'incl' ? row.unitPriceInclTax : row.unitPriceExclTax
  if (count == null || row.unitSize == null || unitPrice == null) return null
  return Math.round((Number(count) / Number(row.unitSize) * Number(unitPrice) + Number.EPSILON) * 100) / 100
}
function rememberSuggestedTotals(row) {
  lastSuggestions.set(row, {
    excl: suggestedTotal(row, 'excl'),
    incl: suggestedTotal(row, 'incl'),
  })
}
function sameAmount(left, right) {
  if (left == null || right == null) return left == null && right == null
  return Math.abs(Number(left) - Number(right)) < 0.005
}
function fillSuggestedTotal(row, kind) {
  const key = kind === 'incl' ? 'totalInclTax' : 'totalExclTax'
  const previous = lastSuggestions.get(row)?.[kind] ?? null
  const next = suggestedTotal(row, kind)
  if (row[key] == null || sameAmount(row[key], previous)) row[key] = next
  const state = lastSuggestions.get(row) || {}
  state[kind] = next
  lastSuggestions.set(row, state)
}
function fillSuggestedTotals(row) {
  fillSuggestedTotal(row, 'excl')
  fillSuggestedTotal(row, 'incl')
}
function quantityText(row) {
  const value = quantity(row)
  return value == null ? '-' : Number(value).toLocaleString('zh-CN')
}
function suggestedText(row, kind) {
  const value = suggestedTotal(row, kind)
  return value == null ? '请输入金额' : `建议 ${value.toFixed(2)}`
}

const totalSummary = computed(() => {
  const totals = {}
  props.modelValue.forEach((item) => {
    if (item.totalInclTax == null) return
    const currency = String(item.currency || 'CNY').toUpperCase()
    totals[currency] = (totals[currency] || 0) + Number(item.totalInclTax)
  })
  return Object.entries(totals).map(([currency, value]) => `${currency} ${value.toFixed(2)}`).join('；')
})
</script>

<style scoped>
.charge-editor { width: 100%; min-width: 0; }
.charge-editor__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.charge-editor__header > div { display: flex; flex-direction: column; gap: 2px; }
.charge-editor__header span { color: var(--el-text-color-secondary); font-size: 12px; }
.charge-editor :deep(.el-input-number) { width: 100%; }
.charge-editor__total { margin-top: 8px; text-align: right; font-weight: 600; }
</style>
