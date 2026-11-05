<template>
  <div class="aggregate-prices" :class="{'is-compact':compact}">
    <el-tag size="small" type="info">子订单累计</el-tag>
    <div v-for="(price,index) in prices||[]" :key="price.aggregateKey||index" class="aggregate-price">
      <strong>{{price.languagePair}} · {{price.pricingMode==='fixed'?'固定收费':metricName(price.quantityMetric)}}</strong>
      <span v-if="price.pricingMode==='fixed'">不含税 {{price.fixedExclTotal??'待填写'}}／含税 {{price.fixedInclTotal??'待填写'}} {{price.currency}}</span>
      <span v-else>{{taxPriceSummary(price.taxPrices,price.currency,`${price.unitSize||1}${metricName(price.quantityMetric)}`,false)||'单价待填写'}}</span>
      <small v-if="price.quantity!=null">累计数量：{{price.quantity}} {{metricName(price.quantityMetric)}}</small>
      <el-popover v-if="compact" title="单价来源订单" trigger="click" placement="left-start" :width="360">
        <template #reference><el-button link type="primary">来源 {{price.sourceOrders?.length||0}} 个订单</el-button></template>
        <p v-for="order in price.sourceOrders||[]" :key="order.id"><el-button link :disabled="!canEdit" @click="emit('edit-order',order.id)">{{order.orderNo}}</el-button> · {{order.quantity??'待填'}} {{metricName(order.metric)}}</p>
      </el-popover>
      <div v-else class="aggregate-sources"><el-button v-for="order in price.sourceOrders||[]" :key="order.id" link type="primary" :disabled="!canEdit" @click="emit('edit-order',order.id)">{{order.orderNo}} · 到此订单填写</el-button></div>
    </div>
    <small v-if="!prices?.length">请在末级子订单登记统计及单价。</small>
  </div>
</template>
<script setup>
import {metricName} from '@/utils/translationQuantityBasis'
import {taxPriceSummary} from '@/utils/taxPrices'
defineProps({prices:Array,compact:Boolean,canEdit:{type:Boolean,default:true}})
const emit=defineEmits(['edit-order'])
</script>
<style scoped>
.aggregate-prices{display:grid;gap:10px}.aggregate-price{display:grid;gap:5px;border-top:1px solid var(--el-border-color-lighter);padding-top:8px}.aggregate-price span{white-space:pre-line}.aggregate-price strong{font-size:13px}.aggregate-price small{font-size:12px;color:var(--el-text-color-secondary)}.aggregate-sources{display:flex;gap:12px;flex-wrap:wrap}.is-compact{gap:6px;font-size:11px}.is-compact .aggregate-price strong,.is-compact .aggregate-price small{font-size:11px}.aggregate-prices .el-button{margin-left:0;white-space:normal;height:auto}
</style>
