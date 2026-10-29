<template>
  <section class="hr-workspace">
    <RouteSectionNavigation :items="sections" label="人事管理二级导航" />
    <div class="hr-workspace-content"><router-view /></div>
  </section>
</template>

<script setup>
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'
const sections=[{path:'/hr-management/shifts',label:'排班管理'},{path:'/hr-management/attendance',label:'考勤管理'},{path:'/hr-management/kpi',label:'KPI管理'},{path:'/hr-management/salary',label:'薪酬管理'},{path:'/hr-management/onboarding',label:'入职管理'},{path:'/hr-management/offboarding',label:'离职管理'}]
</script>
<style scoped>.hr-workspace{display:flex;flex-direction:column;gap:8px;min-width:0}.hr-workspace-content{min-width:0}</style>
