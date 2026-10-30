<template>
  <section>
    <h2>组织架构</h2>
    <el-tabs v-model="active">
      <el-tab-pane label="部门与人员" name="departments"><Departments /></el-tab-pane>
      <el-tab-pane v-if="canReadUsers" label="人员管理" name="people" lazy><Users :office-city-id="typeof route.query.office_city_id==='string'?route.query.office_city_id:''" :office-active-only="route.query.active_only==='true'" @clear-office-filter="clearOfficeFilter" /></el-tab-pane>
      <el-tab-pane v-if="canConfigureReports" label="工作报告与任务查看设置" name="report-settings" lazy><WorkReportSettings /></el-tab-pane>
      <el-tab-pane v-if="canReadUsers||canWriteUsers" label="办公室管理" name="offices" lazy><OfficeManagement @people="openOfficePeople" /></el-tab-pane>
    </el-tabs>
  </section>
</template>
<script setup>
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { hasPermission } from '@/utils/permission'
import Departments from './Departments.vue'
import Users from './Users.vue'
import {useRoute,useRouter} from 'vue-router'
const OfficeManagement=defineAsyncComponent(()=>import('./OfficeManagement.vue'))
const route=useRoute(),router=useRouter()
import { getReportAccessContext } from '@/api/tasks'
const WorkReportSettings=defineAsyncComponent(()=>import('./WorkReportSettings.vue'))
const canConfigureReports=ref(false)
onMounted(async()=>{try{canConfigureReports.value=(await getReportAccessContext()).can_configure}catch{canConfigureReports.value=false}})
const active=ref(typeof route.query.tab==='string'?route.query.tab:'departments')
const canReadUsers=computed(()=>hasPermission('system:users:read'))
const canWriteUsers=computed(()=>hasPermission('system:users:write'))
watch(()=>route.query.tab,value=>{active.value=typeof value==='string'?value:'departments'})
watch(active,value=>{if(route.query.tab!==value)router.replace({query:{...route.query,tab:value}})})
function openOfficePeople(office){router.push({path:'/users',query:{tab:'people',office_city_id:office.id,active_only:'true'}})}
function clearOfficeFilter(){const query={...route.query,tab:'people'};delete query.office_city_id;delete query.active_only;router.replace({query})}
</script>
