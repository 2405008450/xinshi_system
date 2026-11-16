<template>
  <component :is="expanded?'section':'details'" v-if="hasChildren" class="invoice-child-orders" @toggle="load($event.currentTarget.open)">
    <summary v-if="!expanded">子订单汇总</summary>
    <div v-loading="loading" class="invoice-child-orders-body">
      <el-alert v-if="error" :title="error" type="error" :closable="false">
        <el-button link @click="load(true)">重试</el-button>
      </el-alert>
      <el-table v-else :data="children" row-key="id" border max-height="320" empty-text="暂无下一级订单">
        <el-table-column label="订单号" min-width="180">
          <template #default="{row}"><TranslationOrderDetailPopover :order="row" /></template>
        </el-table-column>
        <el-table-column prop="projectName" label="项目名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="是否需发票" width="110">
          <template #default="{row}">{{ documentRequirementLabel(special?row.specialInvoiceRequired:invoiceRequirement(row)) }}</template>
        </el-table-column>
        <el-table-column v-for="side in amountColumns" :key="side.total" :label="side.label" min-width="135">
          <template #default="{row}">{{ formatTotals(row[side.total], row[side.adjusted]) }}<OrderPriceDetails :order="row" :side="side.kind" /></template>
        </el-table-column>
        <el-table-column v-if="allowOpen||allowStatement" label="操作" :width="allowStatement?150:100">
          <template #default="{row}">
            <el-button v-if="allowOpen&&!row.fixedPricingFrom" link type="primary" @click="emit('invoice',row)">发票</el-button>
            <template v-if="allowStatement">
              <el-button v-if="row.statementRequired" link type="primary" @click="emit('statement',row)">查看对账单</el-button>
              <span v-else>无需对账单</span>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </component>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getCustomerFinanceProject } from '@/api/translationCustomerFinance'
import { documentRequirementLabel, invoiceRequirement } from '@/utils/documentRequirements'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import TranslationOrderDetailPopover from './TranslationOrderDetailPopover.vue'

const props = defineProps({order:{type:Object,required:true},allowOpen:Boolean,expanded:Boolean,allowStatement:Boolean,special:Boolean})
const emit = defineEmits(['invoice','statement'])
const hasChildren = computed(() => Boolean(props.order.hasChildren || props.order.childOrderCount || props.order.children?.length))
const children = ref([])
const loading = ref(false)
const error = ref('')
let controller
const amountColumns = [
  {label:'不含税总价',kind:'excl',total:'totalsExclTax',adjusted:'adjustedTotalsExclTax'},
  {label:'含税总价',kind:'incl',total:'totalsInclTax',adjusted:'adjustedTotalsInclTax'},
]
function formatTotals(totals, adjusted) {
  return Object.entries(totals || {}).map(([currency,amount]) =>
    `${currency} ${Number(amount).toFixed(2)}${Object.hasOwn(adjusted || {},currency) ? '（调整后）' : ''}`
  ).join('；') || '未填写'
}
function findOrder(node,id) {
  if (!node || node.id === id) return node
  for (const child of node.children || []) {
    const match = findOrder(child,id)
    if (match) return match
  }
}
async function load(open) {
  if (!open || loading.value) return
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const {item} = await getCustomerFinanceProject(props.order.rootId || props.order.id,{
      signal:controller.signal,params:props.special?{special_invoice:true}:undefined,
    })
    const order = findOrder(item,props.order.id)
    if (!order) throw new Error('该订单已变更，请重新打开窗口')
    children.value = order.children || []
  } catch (e) {
    if (!controller.signal.aborted) error.value = getLocalizedErrorMessage(e,'下一级订单加载失败')
  } finally {
    loading.value = false
  }
}
onMounted(()=>{if(props.expanded)void load(true)})
onBeforeUnmount(() => controller?.abort())
</script>

<style scoped>
.invoice-child-orders { margin-bottom:12px; }
.invoice-child-orders summary { cursor:pointer; padding:6px 0; font-weight:600; }
.invoice-child-orders-body { min-height:40px; }
</style>
