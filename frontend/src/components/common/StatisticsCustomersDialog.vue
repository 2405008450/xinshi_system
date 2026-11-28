<template><DraggableFormDialog v-model="visible" :title="title+' · 客户明细'" width="min(1000px, calc(100vw - 32px))" top="6vh" append-to-body><p>共 {{customers.length}} 个客户，每页10条</p><StatisticsTable :rows="customers" :columns="columns" :page-size="10"><template #cell="{row,column,value}"><ClientManagementLink v-if="column.key==='client_short_name'" :row="row" :value="value"/><StatisticsOrderDetails v-else-if="column.key==='order_count'" :orders="row.orders" :label="value" :show-money="false"/><span v-else>{{value}}</span></template></StatisticsTable><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog></template>
<script setup>
import {ref} from 'vue'
import StatisticsTable from './StatisticsTable.vue'
import StatisticsOrderDetails from './StatisticsOrderDetails.vue'
import ClientManagementLink from './ClientManagementLink.vue'
const visible=ref(false),title=ref(''),customers=ref([])
const columns=[{key:'client_short_name',label:'客户简称'},{key:'client_name',label:'客户全称',width:240},{key:'order_count',label:'订单数'},{key:'cohort',label:'新老客户',format:row=>({new:'新客户',old:'老客户'}[row.cohort]||'—')}]
function open(label,rows){const grouped=new Map();for(const row of rows){const key=row.client_id||row.key||row.id||row.order_no;if(!grouped.has(key))grouped.set(key,{...row,client_short_name:row.client_short_name||row.client_name||'未关联客户',orders:[],order_count:0});const item=grouped.get(key);item.order_count+=Number(row.order_count??1);item.orders.push(...(row.orders||[row]))}title.value=label;customers.value=[...grouped.values()];visible.value=true}
defineExpose({open})
</script>
