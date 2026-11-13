<template>
  <div class="aggregate-prices" :class="{'is-compact':compact}">
    <el-tag v-if="!compact" size="small" type="info">子订单累计</el-tag>
    <component :is="compact ? 'div' : 'details'" v-for="(price,index) in prices||[]" :key="price.aggregateKey||index" class="aggregate-price">
      <component :is="compact ? 'strong' : 'summary'" class="aggregate-price-heading">
        {{price.languagePair}} · {{price.pricingMode==='fixed'?'固定收费':metricName(price.quantityMetric)}}
      </component>
      <div class="aggregate-price-content">
        <span v-if="price.pricingMode==='fixed'">不含税 {{price.fixedExclTotal??'待填写'}}／含税 {{price.fixedInclTotal??'待填写'}} {{price.currency}}</span>
        <span v-else>{{taxPriceSummary(price.taxPrices,price.currency,`${price.unitSize||1}${metricName(price.quantityMetric)}`,false)||'单价待填写'}}</span>
        <small v-if="price.quantity!=null">累计数量：{{price.quantity}} {{metricName(price.quantityMetric)}}</small>
        <details v-if="compact && price.sourceOrders?.length" @toggle="openedSources[index]=$event.target.open">
          <summary>来源 {{price.sourceOrders.length}} 个订单</summary>
          <ul v-if="openedSources[index]" class="aggregate-source-list">
            <li v-for="order in price.sourceOrders" :key="order.id"><el-button v-if="canEdit" link type="primary" @click="emit('edit-order',order.id)">{{order.orderNo}}</el-button><span v-else>{{order.orderNo}}</span> · {{order.quantity??'待填'}} {{metricName(order.metric)}}</li>
          </ul>
        </details>
        <div v-else-if="!compact" class="aggregate-sources"><el-button v-for="order in price.sourceOrders||[]" :key="order.id" link type="primary" :disabled="!canEdit" @click="emit('edit-order',order.id)">{{order.orderNo}} · 到此订单填写</el-button></div>
      </div>
    </component>
    <small v-if="!prices?.length">请在末级子订单登记统计及单价。</small>
  </div>
</template>
<script setup>
import {ref} from 'vue'
import {metricName} from '@/utils/translationQuantityBasis'
import {taxPriceSummary} from '@/utils/taxPrices'
defineProps({prices:Array,compact:Boolean,canEdit:{type:Boolean,default:true}})
const emit=defineEmits(['edit-order'])
const openedSources=ref({})
</script>
<style scoped>
.aggregate-price summary{cursor:pointer;color:var(--el-color-primary)}.aggregate-source-list{margin:4px 0 0;padding-inline-start:1.4em}.aggregate-source-list li{margin-block:3px;overflow-wrap:anywhere}
.aggregate-price-content{display:grid;gap:5px}.aggregate-price[open]>.aggregate-price-content{padding:6px 0 4px 16px}.aggregate-price>.aggregate-price-heading{font-weight:600}
.aggregate-prices{display:grid;gap:10px}.aggregate-price{display:grid;gap:5px;border-top:1px solid var(--el-border-color-lighter);padding-top:8px}.aggregate-price span{white-space:pre-line}.aggregate-price strong{font-size:13px}.aggregate-price small{font-size:12px;color:var(--el-text-color-secondary)}.aggregate-sources{display:flex;gap:12px;flex-wrap:wrap}.is-compact{gap:6px;font-size:11px}.is-compact .aggregate-price strong,.is-compact .aggregate-price small{font-size:11px}.aggregate-prices .el-button{margin-left:0;white-space:normal;height:auto}
</style>
