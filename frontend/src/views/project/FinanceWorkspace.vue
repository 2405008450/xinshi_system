<template>
  <div class="finance-workspace">
    <RouteSectionNavigation :items="sections" label="财务管理分类" />
    <keep-alive>
      <component :is="activeComponent" :key="activeModule" :module="activeModule" />
    </keep-alive>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'

const route = useRoute()
const modules = ['translation', 'interpretation', 'annotation', 'recruitment']
const sections = modules.map((module, index) => ({
  path: `/finance-management/${module}`,
  label: ['笔译', '口译', '标注', '招聘'][index],
}))
const views = {
  translation: defineAsyncComponent(() => import('./translation/CustomerFinance.vue')),
  interpretation: defineAsyncComponent(() => import('./interpretation/CustomerFinance.vue')),
  annotation: defineAsyncComponent(() => import('./ProjectCustomerFinance.vue')),
  recruitment: defineAsyncComponent(() => import('./ProjectCustomerFinance.vue')),
}
const activeModule = computed(() => route.params.module)
const activeComponent = computed(() => views[activeModule.value])
</script>

<style scoped>
.finance-workspace { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
</style>
