<template>
  <DraggableFormDialog :model-value="true" :title="title" append-to-body
    width="min(1060px, calc(100vw - 32px))" top="6vh" @update:model-value="$emit('close')">
    <el-table :data="orders" row-key="id" :expand-row-keys="expanded" border max-height="55vh"
      @expand-change="toggleExpanded">
      <el-table-column label="订单号" prop="orderNo" min-width="190" />
      <el-table-column label="项目名称" prop="projectName" min-width="160" show-overflow-tooltip />
      <el-table-column label="单价" min-width="175">
        <template #default="{row}">
          <div v-for="(price,index) in row.prices" :key="price.id||index">
            {{price.languagePair}} {{taxPriceSummary(price.taxPrices,price.currency,`${price.unitSize || 1} ${basisLabel(price.metric)}`,false) ||
              (price.amount==null?'待填写':`${price.currency} ${price.amount} / ${price.unitSize || 1} ${basisLabel(price.metric)}`)}}
          </div>
          <span v-if="!row.prices?.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="计费金额" min-width="125">
        <template #default="{row}"><span class="match-amount">{{formatMatchTotals(row.billingTotals)}}</span></template>
      </el-table-column>
      <el-table-column label="匹配" width="74" fixed="right">
        <template #default="{row}">
          <el-checkbox :model-value="selected.has(row.id)" :disabled="!canSelect(row)"
            :aria-label="`匹配 ${row.orderNo}`" @change="toggleSelected(row.id,$event)" />
        </template>
      </el-table-column>
    </el-table>
    <p>已选 {{selected.size}} 笔 · 计费合计 {{formatMatchTotals(totals)}}</p>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" @click="$emit('apply',[...selected])">确定</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed,ref} from 'vue'
import {taxPriceSummary} from '@/utils/taxPrices'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {collectMatchTotals,formatMatchTotals,isMatchableOrder} from '@/utils/paymentOrderMatching'

const props=defineProps({title:String,orders:Array,orderIds:Array,currency:String})
defineEmits(['close','apply'])
const expanded=ref([])
const nodes=new Map()
const parents=new Map()
function indexOrders(orders,parent){
  for(const order of orders){
    nodes.set(order.id,order)
    if(parent)parents.set(order.id,parent)
    indexOrders(order.children||[],order.id)
  }
}
indexOrders(props.orders)
const selected=ref(new Set(props.orderIds.filter(id=>nodes.has(id))))
const totals=computed(()=>collectMatchTotals(props.orders,selected.value))
function toggleExpanded(row,open){
  expanded.value=open?[...new Set([...expanded.value,row.id])]:expanded.value.filter(id=>id!==row.id)
}
function isAncestor(ancestor,id){
  for(let parent=parents.get(id);parent;parent=parents.get(parent)){
    if(parent===ancestor)return true
  }
  return false
}
function canSelect(row){
  if(selected.value.has(row.id))return true
  return isMatchableOrder(row,props.currency)&&
    ![...selected.value].some(id=>isAncestor(id,row.id)||isAncestor(row.id,id))
}
function toggleSelected(id,checked){
  if(checked)selected.value.add(id)
  else selected.value.delete(id)
}
</script>

<style scoped>
.match-amount{white-space:pre-line}
</style>
