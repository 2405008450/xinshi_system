<template>
  <section><el-tabs :model-value="$route.path" @update:model-value="$router.push($event)"><el-tab-pane label="排班管理" name="/hr-management/shifts" /><el-tab-pane label="考核管理" name="/hr-management/attendance" /><el-tab-pane label="KPI管理" name="/hr-management/kpi" /><el-tab-pane label="薪酬管理" name="/hr-management/salary" /><el-tab-pane label="入职管理" name="/hr-management/onboarding" /><el-tab-pane label="离职管理" name="/hr-management/offboarding" /></el-tabs><router-view /></section>
</template>
