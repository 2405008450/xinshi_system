<template>
  <div class="project-workspace" :class="{ 'project-workspace--projects': activeSection === 'projects' }">
    <el-card class="workspace-navigation" shadow="never">
      <el-tabs :model-value="activeSection" :before-leave="handleSectionChange">
        <el-tab-pane :label="`${moduleLabel}项目管理`" name="projects" />
        <el-tab-pane :label="`${moduleLabel}须知`" name="notices" />
      </el-tabs>
    </el-card>
    <keep-alive>
      <component :is="activeComponent" :key="`${module}:${activeSection}`" v-bind="activeProps" />
    </keep-alive>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({ module: { type: String, required: true } })
const route = useRoute()
const router = useRouter()
const labels = { translation: '笔译', interpretation: '口译', recruitment: '招聘' }
const moduleLabel = computed(() => labels[props.module])
const activeSection = computed(() => route.query.section === 'notices' ? 'notices' : 'projects')
const projects = {
  translation: defineAsyncComponent(() => import('./translation/ProjectDetails.vue')),
  interpretation: defineAsyncComponent(() => import('./interpretation/InterpretationProjectDetails.vue')),
  recruitment: defineAsyncComponent(() => import('./RecruitmentProjects.vue'))
}
const notices = defineAsyncComponent(() => import('./ProjectNotices.vue'))
const activeComponent = computed(() => activeSection.value === 'notices' ? notices : projects[props.module])
const activeProps = computed(() => activeSection.value === 'notices' ? { module: props.module, moduleLabel: moduleLabel.value } : {})

async function handleSectionChange(section) {
  if (section === activeSection.value) return true
  const query = { ...route.query }
  if (section === 'notices') query.section = 'notices'
  else delete query.section
  // 使用路由导航触发公共编辑器的未保存保护，并支持前进、后退。
  await router.push({ path: route.path, query })
  return activeSection.value === section
}
</script>

<style scoped>
.project-workspace{display:flex;flex-direction:column;gap:8px;min-width:0}
.project-workspace--projects{height:100%;min-height:0}
.workspace-navigation{flex:none;border-color:var(--color-border);border-radius:var(--radius-lg)}
.workspace-navigation :deep(.el-card__body){padding:0 20px}
.workspace-navigation :deep(.el-tabs__header){margin:0}
.workspace-navigation :deep(.el-tabs__content){display:none}
.workspace-navigation :deep(.el-tabs__nav-wrap::after){height:1px}
.workspace-navigation :deep(.el-tabs__item){height:36px;font-size:15px}
</style>
