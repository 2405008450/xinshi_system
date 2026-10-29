<template>
  <div class="development-notices">
    <el-card shadow="never" class="common-page-card development-notices-navigation"><TalentResourceNav /></el-card>
    <ProjectNotices module="development" module-label="开拓" route-section="" :write-permission="['talents:write','translators:write']" />
  </div>
</template>
<script setup>
import TalentResourceNav from './components/TalentResourceNav.vue'
import ProjectNotices from '@/views/project/ProjectNotices.vue'
</script>
<style scoped>
.development-notices-navigation{margin-bottom:12px}.development-notices-navigation :deep(.el-card__body){padding:12px 16px}.development-notices-navigation :deep(.resource-nav){margin:0;padding-bottom:0;border-bottom:0}
</style>
