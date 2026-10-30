<template>
  <div class="technology-management">
    <RouteSectionNavigation :items="navigation" label="技术管理二级导航" />
    <router-view />
  </div>
</template>

<script setup>
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'

const navigation = [
  { path: '/technology-management/development', label: '技术开发' }
]
</script>

<style scoped>
.technology-management {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
</style>
