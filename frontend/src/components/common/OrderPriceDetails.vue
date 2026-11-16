<template>
  <small v-for="entry in details" :key="entry.kind" class="order-price-detail">
    {{ entry.label }}{{ entry.description }}
  </small>
</template>

<script setup>
import {computed} from 'vue'

const props=defineProps({order:Object,side:String})
const details=computed(()=>{
  const order=props.order||{}
  const rules=order.totalAdjustment||order.total_adjustment||{}
  const discountedTotals=order.discountedTotals||order.discounted_totals||{}
  const pricingMode=order.pricingMode||order.pricing_mode
  return [['excl','不含税',order.adjustedTotal??order.adjusted_total],['incl','含税',order.adjustedTotalInclTax??order.adjusted_total_incl_tax]]
    .filter(([kind])=>!props.side||kind===props.side)
    .flatMap(([kind,label,legacy])=>{
      const discount=rules[kind+'Discount']??rules[kind+'_discount']
      const adjusted=rules[kind+'Tax']??rules[kind+'_tax']??(pricingMode==='metric'?legacy:null)
      const currency=rules.currency||order.currency||'CNY'
      const format=amount=>`${currency} ${Number(amount).toFixed(2)}`
      const parts=[]
      if(discount!=null){
        const discounted=discountedTotals[kind+'Tax']??discountedTotals[kind+'_tax']
        parts.push(String(discount).padStart(2,'0')+' 折'+(discounted==null?'':' · 折后 '+format(discounted)))
      }
      if(adjusted!=null)parts.push('调整后 '+format(adjusted))
      return parts.length?[{kind,label:props.side?'':label+'：',description:parts.join('；')}]:[]
    })
})
</script>

<style scoped>
.order-price-detail{display:block;color:var(--el-text-color-secondary);line-height:1.5}
</style>
