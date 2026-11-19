<template>
  <el-popover trigger="click" placement="left" width="min(760px, calc(100vw - 32px))"
    :title="`${row.client_name} · ${periodLabel}订单明细`" @show="show" @hide="hide">
    <template #reference>
      <el-button link type="primary" class="revenue-order-amount"
        :aria-label="`查看 ${row.client_name} 本期订单明细，营收 ${revenueAmount(row.amount)}`">
        {{ revenueAmount(row.amount) }}
      </el-button>
    </template>
    <el-alert v-if="error" type="error" :closable="false" :title="error">
      <el-button link @click="load">重试</el-button>
    </el-alert>
    <el-table v-else v-loading="loading" :data="orders || []" row-key="id" border size="small"
      max-height="min(540px, calc(100vh - 140px))" :empty-text="loading ? '正在加载订单…' : '该客户本期没有订单'">
      <el-table-column label="订单" min-width="190">
        <template #default="{ row: order }">
          <div class="revenue-order-cell" :style="{ paddingInlineStart: `${Math.min(order.depth, 4) * 10}px` }">
            <strong>{{ order.order_no || '未登记订单号' }}</strong>
            <div>{{ order.project_name || '—' }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="date" label="归属日期" width="100" />
      <el-table-column label="单价" min-width="190">
        <template #default="{ row: order }">
          <div v-for="(price, index) in order.prices" :key="index" class="revenue-order-rate">
            <strong v-if="price.label">{{ price.label }}</strong>
            <div v-if="price.excl != null">不含税 {{ formatUnitPrice(price.excl, price) }}</div>
            <div v-if="price.incl != null">含税 {{ formatUnitPrice(price.incl, price) }}</div>
            <div v-if="price.legacy != null">{{ formatUnitPrice(price.legacy, price) }}</div>
          </div>
          <span v-if="!order.prices.length">{{ order.pricing_mode === 'fixed' ? '固定收费' : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="总价" min-width="198">
        <template #default="{ row: order }">
          <div>不含税 {{ moneyText(order.totals_excl_tax) }}</div>
          <div>含税 {{ moneyText(order.totals_incl_tax) }}</div>
          <div>项目计费金额 {{ moneyText(order.billing_totals) }}</div>
        </template>
      </el-table-column>
    </el-table>
  </el-popover>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { getTranslationRevenue } from '@/api/translationRevenue'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { revenueAmount } from '@/utils/revenueStatistics'
import { metricName } from '@/utils/translationQuantityBasis'

const props = defineProps({
  row: { type: Object, required: true },
  query: { type: Object, required: true },
  periodLabel: { type: String, required: true },
})
const orders = ref(null)
const loading = ref(false)
const error = ref('')
const unitPriceFormatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 8 })
let visible = false
let controller

function formatUnitPrice(value, price) {
  const unit = price.unit ? ` / ${price.unit_size === '1' ? '' : price.unit_size}${metricName(price.unit)}` : ''
  return `${price.currency} ${unitPriceFormatter.format(value)}${unit}`
}

function moneyText(amounts) {
  return Object.entries(amounts || {})
    .map(([currency, amount]) => `${currency} ${revenueAmount(amount)}`)
    .join('、') || '—'
}

async function load() {
  controller?.abort()
  const request = new AbortController()
  controller = request
  loading.value = true
  error.value = ''
  try {
    const result = await getTranslationRevenue({ ...props.query, detail_client: props.row.key }, { signal: request.signal })
    if (!request.signal.aborted) orders.value = result.items
  } catch (reason) {
    if (!request.signal.aborted) error.value = getLocalizedErrorMessage(reason, '订单明细加载失败')
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

function show() {
  visible = true
  if (!orders.value) void load()
}

function hide() {
  visible = false
  controller?.abort()
  loading.value = false
}

watch(() => props.query, () => {
  orders.value = null
  error.value = ''
  if (visible) void load()
})
onBeforeUnmount(hide)
</script>

<style scoped>
.revenue-order-amount { line-height: inherit; }
.revenue-order-cell { overflow-wrap: anywhere; }
.revenue-order-rate + .revenue-order-rate { margin-top: 6px; }
</style>
