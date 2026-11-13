<template>
  <DraggableFormDialog
    :model-value="true"
    :title="context.boardName ? `对账单项目 · ${context.boardName}` : isStatement ? '需对账单的项目' : '订单汇总付款'"
    width="min(840px, calc(100vw - 32px))"
    top="8vh"
    append-to-body
    @update:model-value="$emit('close')"
  >
    <el-table v-if="context.statementProjects" :data="context.statementProjects" row-key="id" border max-height="min(48vh, 460px)">
      <el-table-column prop="orderNo" label="订单号" min-width="145" />
      <el-table-column prop="projectName" label="项目名称" min-width="190" show-overflow-tooltip />
      <el-table-column prop="billingMonth" label="账单月份" width="125" />
    </el-table>
    <template v-else>
    <AppForm inline :model="filters">
      <el-form-item label="客户"><span>{{ context.clientName || '未关联客户' }}</span></el-form-item>
      <el-form-item label="账单月份">
        <el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" :clearable="false" @change="search" />
      </el-form-item>
    </AppForm>
    <p v-if="!isStatement" class="monthly-payment-help">同一客户在同一账单月份内无需对账单的项目，可勾选后汇总付款。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load">重新加载</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" row-key="id" border max-height="min(48vh, 460px)" empty-text="该客户在所选月份没有项目">
      <el-table-column prop="orderNo" label="订单号" min-width="145" />
      <el-table-column prop="projectName" label="项目名称" min-width="190" show-overflow-tooltip />
      <el-table-column label="对账单" width="90">
        <template #default="{row}">
          <CustomerStatementRequiredToggle v-if="isStatement" :row="row" :prepare="prepare" @saved="load" />
          <template v-else>{{ row.statementRequired ? '需' : '无需' }}</template>
        </template>
      </el-table-column>
      <el-table-column v-if="!isStatement" label="订单汇总付款" min-width="160">
        <template #default="{row}">
          <el-checkbox
            :model-value="row.paymentMethod === 'monthly'"
            :disabled="!canWrite || loading || saving.has(row.id)"
            :aria-label="`${row.orderNo} 是否纳入订单汇总付款`"
            @change="setMonthly(row, $event)"
          >{{ row.paymentMethod === 'monthly' ? '已纳入' : '是否纳入？' }}</el-checkbox>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="total > pageSize" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="load" />
    </template>
    <template #footer><el-button @click="$emit('close')">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getCustomerFinancePage } from '@/api/translationCustomerFinance'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import AppForm from './AppForm.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import CustomerStatementRequiredToggle from './CustomerStatementRequiredToggle.vue'

const props = defineProps({ context: Object, canWrite: Boolean, saveMethod: Function, prepare: Function })
defineEmits(['close'])

const isStatement = props.context.type === 'statement'
const [year, month] = businessDateTimeInputValue().slice(0, 7).split('-').map(Number)
const previousMonth = `${month === 1 ? year - 1 : year}-${String(month === 1 ? 12 : month - 1).padStart(2, '0')}`
const filters = reactive({ month: props.context.month || previousMonth })
const pageSize = 20
const page = ref(1)
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const saving = reactive(new Set())
let controller

async function load() {
  controller?.abort()
  const request = new AbortController()
  controller = request
  loading.value = true
  error.value = ''
  try {
    const result = await getCustomerFinancePage({
      client_ids: [props.context.clientId], billing_month: filters.month,
      skip: (page.value - 1) * pageSize, limit: pageSize,
    }, { signal: request.signal })
    if (request.signal.aborted) return
    rows.value = result.items || []
    total.value = result.total || 0
  } catch (reason) {
    if (request.signal.aborted) return
    rows.value = []
    total.value = 0
    error.value = getLocalizedErrorMessage(reason, '汇总付款项目加载失败')
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

function search() {
  page.value = 1
  rows.value = []
  void load()
}

async function setMonthly(row, checked) {
  if (saving.has(row.id)) return
  saving.add(row.id)
  try {
    const item = await props.saveMethod(row, checked)
    if (item) {
      rows.value = rows.value.map(project => project.id === item.id ? item : project)
      if (loading.value) void load()
    }
  } finally {
    saving.delete(row.id)
  }
}

onMounted(()=>{if(!props.context.statementProjects)void load()})
onBeforeUnmount(() => controller?.abort())
</script>

<style scoped>
.monthly-payment-help { margin: 0 0 12px; color: var(--el-text-color-secondary); }
.el-pagination { margin-top: 12px; }
</style>
