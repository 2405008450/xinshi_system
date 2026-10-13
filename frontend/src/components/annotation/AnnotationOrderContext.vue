<template>
  <el-alert v-if="project?.parentProjectId" type="info" :closable="false" class="annotation-order-context">
    <template #title>{{ project.orderLevel === 2 ? '子订单' : '订单' }}：{{ project.parentOrderNo }} · {{ project.parentProjectName || '' }} / {{ project.orderLevel === 2 ? '三级订单' : '子订单' }}：{{ project.orderNo }} <router-link :to="{ name: project.orderLevel === 2 ? 'AnnotationChildOrders' : 'AnnotationProjectDetails', query: { projectId: project.parentProjectId, openEditor: '1' } }">查看上级订单</router-link></template>
  </el-alert>
</template>
<script setup>
defineProps({ project: Object })
</script>
<style scoped>
.annotation-order-context { margin-bottom:12px; }
</style>
