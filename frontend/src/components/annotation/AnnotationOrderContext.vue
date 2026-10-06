<template>
  <el-alert v-if="project?.parentProjectId" type="info" :closable="false" class="annotation-order-context">
    <template #title>母订单：{{ project.parentOrderNo }} · {{ project.parentProjectName || '' }} / 子订单：{{ project.orderNo }} <router-link :to="{ name: 'AnnotationProjectDetails', query: { projectId: project.parentProjectId, openEditor: '1' } }">查看母订单</router-link></template>
  </el-alert>
</template>
<script setup>
defineProps({ project: Object })
</script>
<style scoped>
.annotation-order-context { margin-bottom:12px; }
</style>
