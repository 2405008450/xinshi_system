<template>
  <CustomerStatementWorkspace v-if="projectId" :project-id="projectId" :billing-month="billingMonth" />
  <el-alert v-else title="请先保存项目，再编排对账单" type="info" :closable="false" />
</template>
<script setup>
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
defineProps({projectId:{type:[String,Number],default:''},orderId:{type:[String,Number],default:''},clientId:{type:[String,Number],default:''},billingMonth:String})
</script>
