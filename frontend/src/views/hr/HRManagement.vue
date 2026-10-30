<template>
  <section class="hr-workspace">
    <RouteSectionNavigation :items="sections" label="人事管理二级导航" />
    <div class="hr-workspace-content"><router-view /></div>
  </section>
</template>

<script setup>
import {computed} from 'vue'
import {canAccessRoute} from '@/utils/permission'
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'
const allSections=[{path:'/hr-management/organization',label:'组织架构',organization:true},{path:'/hr-management/shifts',label:'排班管理'},{path:'/hr-management/attendance',label:'考勤管理'},{path:'/hr-management/kpi',label:'KPI管理'},{path:'/hr-management/salary',label:'薪酬管理'},{path:'/hr-management/recruitment',label:'招聘管理'},{path:'/hr-management/onboarding',label:'入职管理'},{path:'/hr-management/offboarding',label:'离职管理'}]
const sections=computed(()=>allSections.filter(item=>canAccessRoute({meta:item.organization?{organizationManagement:true}:{hrManagement:true}})))
</script>
<style scoped>.hr-workspace{display:flex;flex-direction:column;gap:8px;min-width:0}.hr-workspace-content{min-width:0}</style>
