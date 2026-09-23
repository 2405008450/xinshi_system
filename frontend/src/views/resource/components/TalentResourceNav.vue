<template>
  <nav class="resource-nav" aria-label="人才资源分类">
    <div class="resource-nav__primary">
      <el-button
        v-for="item in TALENT_RESOURCE_VIEWS"
        :key="item.path"
        class="resource-nav__item"
        :class="{ 'is-current': isActiveView(item) }"
        :aria-current="route.path === item.path ? 'page' : undefined"
        text
        @click="router.push(item.path)"
      >
        {{ item.label }}
      </el-button>
    </div>
    <div v-if="activeChildren.length" class="resource-nav__secondary" role="group" aria-label="人才总库资源分类">
      <el-button
        v-for="item in activeChildren"
        :key="item.path"
        class="resource-nav__item"
        :class="{ 'is-current': route.path === item.path }"
        :aria-current="route.path === item.path ? 'page' : undefined"
        text
        @click="router.push(item.path)"
      >
        {{ item.label }}
      </el-button>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TALENT_RESOURCE_VIEWS } from '@/config/talentResourceViews'

const route = useRoute()
const router = useRouter()
const isActiveView = item => route.path === item.path || item.children?.some(child => route.path === child.path)
const activeChildren = computed(() => TALENT_RESOURCE_VIEWS.find(isActiveView)?.children ?? [])
</script>

<style scoped>
.resource-nav {
  margin: -4px 0 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.resource-nav__primary,
.resource-nav__secondary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.resource-nav__secondary {
  margin-top: 8px;
  margin-left: 16px;
  padding-left: 12px;
  border-left: 2px solid var(--el-border-color-lighter);
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
    min-width: 0;
  }

  .resource-nav__secondary {
    margin-left: 8px;
    padding-left: 8px;
  }
}
</style>
