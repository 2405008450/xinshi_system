<template>
  <section class="aggregate-body">
        <p v-if="order.priceAggregate">调整后金额用于本订单结算和上级汇总。留空时采用下级订单的结算金额。</p>
        <div class="aggregate-totals" data-dialog-field-search-label="不含税总价 含税总价 计算额 调整后金额">
          <div v-for="[label,calculated,effective,kind] in totals" :key="label">
            <strong>{{label}}</strong>
            <template v-if="order.priceAggregate"><small>计算额</small><ReadonlyField :model-value="format(order[calculated])" source="auto" /></template>
            <small>当前结算金额</small><ReadonlyField :model-value="format(order[effective])" source="auto" />
            <div class="aggregate-adjustments">
              <el-form-item :label="label+'折扣'">
                <OrderDiscountField :model-value="kind==='excl'?discountExcl:discountIncl" :disabled="disabled"
                  :label="label+'折扣'" @update:model-value="kind==='excl'?discountExcl=$event:discountIncl=$event" />
              </el-form-item>
              <el-form-item :label="`${label}调整后金额（${order.totalAdjustment?.currency||order.currency||'CNY'}）`">
                <el-input-number :model-value="kind==='excl'?excl:incl" :disabled="disabled" :controls="false" :min="0" :precision="2"
                  :placeholder="order.priceAggregate?'采用下级汇总':order.fixedPricingFrom?'选填':'采用登记金额'"
                  @update:model-value="kind==='excl'?excl=$event:incl=$event" />
              </el-form-item>
            </div>
          </div>
        </div>
  </section>
</template>
<script setup>
import ReadonlyField from './ReadonlyField.vue'
import OrderDiscountField from './OrderDiscountField.vue'
defineProps({order:Object,disabled:Boolean})
const excl=defineModel('excl',{type:Number})
const incl=defineModel('incl',{type:Number})
const discountExcl=defineModel('discountExcl',{type:Number})
const discountIncl=defineModel('discountIncl',{type:Number})
const totals=[['不含税总价','calculatedTotalsExclTax','totalsExclTax','excl'],['含税总价','calculatedTotalsInclTax','totalsInclTax','incl']]
const format=values=>Object.entries(values||{}).map(([currency,amount])=>`${currency} ${Number(amount).toFixed(2)}`).join('；')||'待填写'
</script>
<style scoped>
.aggregate-body{display:grid;gap:16px;padding-top:8px}
p,small{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}small{display:block;margin:8px 0 4px}.aggregate-totals{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;border-top:1px solid var(--el-border-color);padding-top:16px}@media(max-width:680px){.aggregate-totals{grid-template-columns:1fr}}
.aggregate-adjustments {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  align-items: end;
  gap: 12px;
}
.aggregate-adjustments :deep(.el-input-number) { width: 100%; }
</style>
