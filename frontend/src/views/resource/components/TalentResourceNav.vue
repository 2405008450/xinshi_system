<template>
  <nav class="resource-nav" aria-label="人才资源分类">
    <el-button
      v-for="item in visibleViews"
      :key="item.path"
      class="resource-nav__item"
      :class="{ 'is-current': route.path === item.path }"
      :aria-current="route.path === item.path ? 'page' : undefined"
      text
      @click="router.push(item.path)"
    >
      {{ item.label }}
    </el-button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TALENT_RESOURCE_VIEWS } from '@/config/talentResourceViews'
import { hasPermission } from '@/utils/permission'

const route = useRoute()
const router = useRouter()
const visibleViews = computed(() => (
  TALENT_RESOURCE_VIEWS.filter(item => hasPermission(item.permissions))
))
</script>

<style scoped>
.resource-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -4px 0 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.resource-nav__item {
  margin-left: 0 !important;
  border: 1px solid transparent !important;
  border-radius: var(--el-border-radius-base);
  color: var(--el-text-color-regular);
  font-weight: 500;
  transition: color .2s ease, background-color .2s ease, border-color .2s ease, box-shadow .2s ease;
}

.resource-nav__item:hover {
  border-color: var(--el-color-primary-light-8) !important;
  background: var(--el-color-primary-light-9) !important;
  color: var(--el-color-primary-dark-2) !important;
}

.resource-nav__item.is-current {
  border-color: var(--el-color-primary-light-7) !important;
  background: var(--el-color-primary-light-9) !important;
  color: var(--el-color-primary-dark-2) !important;
  font-weight: 600;
  box-shadow: inset 0 -2px 0 var(--el-color-primary);
}

@media (max-width: 768px) {
  .resource-nav {
    align-items: flex-start;
    overflow-x: auto;
  }
}
</style>
