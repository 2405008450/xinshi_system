<template>
  <section class="finance-aggregate-summary">
    <div class="aggregate-heading"><strong>父级订单收费汇总</strong><el-tag>子订单累计 · 只读</el-tag><el-button v-if="order.rootId" @click="emit('payment')">打开付款情况</el-button></div>
    <p>单价在末级订单填写，逐级同步到上级；父级显示单价和总价，不重复计算父级统计。</p>
    <div data-dialog-field-search-label="单价 子订单累计"><CustomerAggregatePrices :prices="order.prices" :can-edit="canEdit" @edit-order="emit('edit-order',$event)" /></div>
    <div class="aggregate-totals" data-dialog-field-search-label="不含税总价 含税总价 计算额 调整后金额">
      <div v-for="[label,calculated,effective] in totals" :key="label"><strong>{{label}}</strong><small>计算额</small><ReadonlyField :model-value="format(order[calculated])" source="auto" /><small>调整后金额（下级累计）</small><ReadonlyField :model-value="format(order[effective])" source="auto" /></div>
    </div>
    <div class="aggregate-totals"><div><small>内部说明</small><ReadonlyField :model-value="order.explanation||'—'" source="auto" /></div><div><small>客户说明</small><ReadonlyField :model-value="order.customerExplanation||'—'" source="auto" /></div></div>
    <el-alert v-if="order.incomplete" title="部分子订单的数量或单价待补录，当前仅汇总已计算金额。" type="warning" :closable="false" />
    <p v-if="order.recordedPricingMode==='fixed'||order.recordedAdjustedTotal!=null||order.recordedAdjustedTotalInclTax!=null">父级原收费记录保留；当前总价按子订单累计，请在末级登记实际收费。</p>
  </section>
</template>
<script setup>
import CustomerAggregatePrices from './CustomerAggregatePrices.vue'
import ReadonlyField from './ReadonlyField.vue'
defineProps({order:Object,canEdit:Boolean})
const emit=defineEmits(['edit-order','payment'])
const totals=[['不含税总价','calculatedTotalsExclTax','totalsExclTax'],['含税总价','calculatedTotalsInclTax','totalsInclTax']]
const format=values=>Object.entries(values||{}).map(([currency,amount])=>`${currency} ${Number(amount).toFixed(2)}`).join('；')||'待填写'
</script>
<style scoped>
.finance-aggregate-summary{display:grid;gap:16px}.aggregate-heading{display:flex;gap:12px;align-items:center;flex-wrap:wrap}p,small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}small{display:block;margin:8px 0 4px}.aggregate-totals{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;border-top:1px solid var(--el-border-color);padding-top:16px}@media(max-width:680px){.aggregate-totals{grid-template-columns:1fr}}
</style>
