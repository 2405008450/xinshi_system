<template>
  <section>
    <h2>组织架构</h2>
    <el-tabs v-model="active">
      <el-tab-pane label="部门与人员" name="departments"><Departments /></el-tab-pane>
      <el-tab-pane v-if="canReadUsers" label="人员管理" name="people" lazy><Users /></el-tab-pane>
      <el-tab-pane v-if="canConfigureReports" label="工作报告设置" name="report-settings" lazy><WorkReportSettings /></el-tab-pane>
    </el-tabs>
  </section>
</template>
<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { hasPermission } from '@/utils/permission'
import Departments from './Departments.vue'
import Users from './Users.vue'
import { getReportAccessContext } from '@/api/tasks'
const WorkReportSettings=defineAsyncComponent(()=>import('./WorkReportSettings.vue'))
const canConfigureReports=ref(false)
onMounted(async()=>{try{canConfigureReports.value=(await getReportAccessContext()).can_configure}catch{canConfigureReports.value=false}})
const active=ref('departments')
const canReadUsers=computed(()=>hasPermission('system:users:read'))
</script>
