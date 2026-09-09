<template>
  <div class="charge-editor">
    <div class="charge-editor__header">
      <div>
        <strong>客户收费明细</strong>
        <span>计量收费数量取自本子订单的“客户字数”</span>
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
            <el-option label="按数量" value="metric" /><el-option label="固定收费" value="fixed" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="客户字数口径" min-width="180">
        <template #default="{ row }">
          <el-select v-model="row.metricType" :disabled="row.pricingMode === 'fixed'" @change="onMetricChange(row)">
            <el-option v-for="metric in WORD_COUNT_METRICS" :key="metric.key" :label="metric.label" :value="metric.key" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="数量" width="92" align="right">
        <template #default="{ row }">{{ quantityText(row) }}</template>
      </el-table-column>
      <el-table-column label="每计价单位" width="110">
        <template #default="{ row }"><el-input-number v-model="row.unitSize" :disabled="row.pricingMode === 'fixed'" :min="0.0001" :precision="4" :controls="false" /></template>
      </el-table-column>
      <el-table-column label="单价" width="110">
        <template #default="{ row }"><el-input-number v-model="row.unitPrice" :disabled="row.pricingMode === 'fixed'" :min="0" :precision="4" :controls="false" /></template>
      </el-table-column>
      <el-table-column label="币种" width="92">
        <template #default="{ row }"><el-input v-model="row.currency" maxlength="3" @blur="row.currency = String(row.currency || 'CNY').toUpperCase()" /></template>
      </el-table-column>
      <el-table-column label="计算金额" width="105" align="right">
        <template #default="{ row }">{{ moneyText(calculated(row)) }}</template>
      </el-table-column>
      <el-table-column label="金额覆盖值" width="120">
        <template #default="{ row }">
          <el-input-number v-model="row.amountOverride" :min="0" :precision="2" :controls="false" :placeholder="calculatedText(row)" />
        </template>
      </el-table-column>
      <el-table-column label="最终金额" width="105" align="right">
        <template #default="{ row }">{{ moneyText(finalAmount(row)) }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="140">
        <template #default="{ row }"><el-input v-model="row.remarks" maxlength="5000" /></template>
      </el-table-column>
      <el-table-column label="操作" width="64" fixed="right">
        <template #default="{ $index }"><el-button type="danger" link @click="removeItem($index)">删除</el-button></template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无客户收费项" :image-size="48" />
    <div v-if="totalSummary" class="charge-editor__total">合计：{{ totalSummary }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { WORD_COUNT_METRICS, normalizeWordCountMatrix } from '@/utils/wordCountMatrix'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  wordCountMatrix: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])

const customerValues = computed(() => normalizeWordCountMatrix(props.wordCountMatrix).customer)
const defaultUnitSize = (metric) => ['documents', 'pages'].includes(metric) ? 1 : 1000
const addItem = () => emit('update:modelValue', [...props.modelValue, {
  id: null, sequenceNo: props.modelValue.length + 1, itemName: '翻译费', pricingMode: 'metric',
  metricType: 'words', unitSize: 1000, unitPrice: null, currency: 'CNY', amountOverride: null, remarks: ''
}])
const removeItem = (index) => emit('update:modelValue', props.modelValue.filter((_, itemIndex) => itemIndex !== index))
function onModeChange(row) {
  if (row.pricingMode === 'fixed') {
    row.metricType = null; row.unitSize = null; row.unitPrice = null
  } else {
    row.metricType = row.metricType || 'words'; row.unitSize = defaultUnitSize(row.metricType)
  }
}
function onMetricChange(row) { row.unitSize = defaultUnitSize(row.metricType) }
function quantity(row) { return row.pricingMode === 'metric' ? customerValues.value[row.metricType] : null }
function calculated(row) {
  const count = quantity(row)
  if (count === null || count === undefined || row.unitSize === null || row.unitPrice === null) return null
  return Math.round((Number(count) / Number(row.unitSize) * Number(row.unitPrice) + Number.EPSILON) * 100) / 100
}
function finalAmount(row) { return row.amountOverride ?? calculated(row) }
function quantityText(row) { const value = quantity(row); return value === null || value === undefined ? '-' : Number(value).toLocaleString('zh-CN') }
function moneyText(value) { return value === null || value === undefined ? '-' : Number(value).toFixed(2) }
function calculatedText(row) { const value = calculated(row); return value === null ? '请输入金额' : `计算值 ${value.toFixed(2)}` }
const totalSummary = computed(() => {
  const totals = {}
  props.modelValue.forEach((item) => {
    const value = finalAmount(item)
    if (value === null || value === undefined) return
    const currency = String(item.currency || 'CNY').toUpperCase()
    totals[currency] = (totals[currency] || 0) + Number(value)
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
