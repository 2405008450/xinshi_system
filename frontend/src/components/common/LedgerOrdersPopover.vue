<template>
  <el-popover trigger="click" placement="left" :width="760" :title="title" @show="load">
    <template #reference><el-button link type="primary">{{label||'查看明细'}}</el-button></template>
    <div v-loading="loading" class="ledger-orders-details"><el-alert v-if="error" :title="error" type="error" :closable="false" /><el-table :data="displayRows" border size="small" max-height="480"><el-table-column prop="settlementLabel" label="结算单元" min-width="150" /><el-table-column prop="orderNo" label="订单号" min-width="160" /><el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip /><el-table-column label="项目计费金额"><template #default="{row}">{{money(row.amounts)}}</template></el-table-column></el-table><p v-if="totals">小计：{{money(totals)}}</p></div>
  </el-popover>
</template>
<script setup>
import {computed,ref} from 'vue'
import api from '@/api'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({label:String,title:{type:String,default:'订单明细'},orders:{type:Array,default:()=>[]},clientId:String,months:Array,managerQuery:Object})
const rows=ref(null),totals=ref(null),loading=ref(false),error=ref('')
const displayRows=computed(()=>rows.value||props.orders)
const money=value=>Object.entries(value||{}).map(([currency,total])=>`${currency} ${total}`).join(' / ')||'待补'
async function load(){if(!props.clientId){rows.value=null;return}loading.value=true;error.value='';try{const data=await api.get(`/translation-statement-workspaces/${props.clientId}/ledger-orders`,{params:{...props.managerQuery,months:props.months?.length?props.months:undefined},paramsSerializer:{indexes:null},timeout:60000});rows.value=data.items.map(row=>({orderNo:row.order_no,projectName:row.project_name,amounts:row.amounts,settlementLabel:row.settlement_label}));totals.value=data.summary.billing_totals}catch(e){error.value=getLocalizedErrorMessage(e,'客户订单明细加载失败')}finally{loading.value=false}}
</script>
<style scoped>.ledger-orders-details{max-height:560px;overflow:auto;overflow-wrap:anywhere}</style>
