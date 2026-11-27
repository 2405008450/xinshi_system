<template>
  <el-button v-if="canRead" text :icon="Document" @click="visible=true">工作报告</el-button>
  <WorkReportDialog v-if="visible" v-model="visible" />
</template>
<script setup>
import {computed,defineAsyncComponent,ref} from 'vue'
import {Document} from '@element-plus/icons-vue'
import {hasPermission} from '@/utils/permission'
const WorkReportDialog=defineAsyncComponent(()=>import('./WorkReportDialog.vue'))
const visible=ref(false)
const canRead=computed(()=>hasPermission('reports:read')||hasPermission('reports:write'))
</script>
