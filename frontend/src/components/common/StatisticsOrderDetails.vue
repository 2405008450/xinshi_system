<template><el-popover trigger="click" placement="left" :width="760" :popper-style="{maxWidth:'calc(100vw - 32px)'}"><template #reference><el-button link type="primary">{{label}}</el-button></template><strong>{{title||'订单项目明细'}}</strong><StatisticsTable :rows="orders" :columns="columns" :height="400"/></el-popover></template>
<script setup>
import {computed} from 'vue'
import StatisticsTable from './StatisticsTable.vue'
const props=defineProps({showMoney:{type:Boolean,default:true},orders:{type:Array,default:()=>[]},label:{type:[String,Number],default:'查看订单'},title:String})
const allColumns=[{key:'order_no',label:'订单号',width:150},{key:'project_name',label:'项目名称',width:230},{key:'order_date',label:'订单日期',width:125},{key:'amounts',label:'项目金额',width:180,format:row=>Object.entries(row.amounts||{}).map(([code,amount])=>code+' '+Number(amount).toFixed(2)).join('；')||'金额未登记'},{key:'amount_complete',label:'计价完整性',format:row=>row.amount_complete?'金额完整':'待补充'}]
const columns=computed(()=>props.showMoney?allColumns:allColumns.filter(column=>!['amounts','amount_complete'].includes(column.key)))
</script>
