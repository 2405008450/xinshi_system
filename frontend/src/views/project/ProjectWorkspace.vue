<template>
  <div class="project-workspace" :class="{ 'project-workspace--projects': activeSection === 'projects', 'project-workspace--help': activeSection === 'help' }">
    <el-card class="workspace-navigation" shadow="never">
      <el-tabs :model-value="activeSection" :before-leave="handleSectionChange" @tab-click="handleSectionClick">
        <el-tab-pane :label="`${moduleLabel}项目管理`" name="projects" />
        <el-tab-pane v-if="module === 'translation'" label="项目安排" name="arrangements" />
        <el-tab-pane v-if="module === 'translation' && canViewManuscript" label="稿件安排" name="manuscript" />
        <el-tab-pane v-if="module === 'interpretation'" label="财务管理（客户）" name="customer-finance" />
        <el-tab-pane :label="`${moduleLabel}须知`" name="notices" />
        <el-tab-pane v-if="module === 'translation'" label="帮助" name="help" />
      </el-tabs>
    </el-card>
    <keep-alive>
      <component :is="activeComponent" ref="activeView" :key="`${module}:${activeSection}`" v-bind="activeProps" />
    </keep-alive>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { canViewManuscriptArrangements } from '@/utils/permission'

const props = defineProps({ module: { type: String, required: true } })
const route = useRoute()
const router = useRouter()
const activeView=ref(null)
function handleSectionClick(tab){if(props.module==='translation'&&activeSection.value===tab.props.name&&['projects','arrangements'].includes(tab.props.name))activeView.value?.restoreDefaultExclusions?.()}
const labels = { translation: '笔译', interpretation: '口译', recruitment: '招聘' }
const moduleLabel = computed(() => labels[props.module])
const canViewManuscript = computed(() => canViewManuscriptArrangements())
const activeSection = computed(() => {
  const section = route.query.section
  if(section==='notices')return section
  if(props.module==='interpretation'&&section==='customer-finance')return section
  if(props.module==='translation'&&(['help','arrangements'].includes(section)||(section==='manuscript'&&canViewManuscript.value)))return section
  return 'projects'
})
const projects = {
  translation: defineAsyncComponent(() => import('./translation/ProjectDetails.vue')),
  interpretation: defineAsyncComponent(() => import('./interpretation/InterpretationProjectDetails.vue')),
  recruitment: defineAsyncComponent(() => import('./RecruitmentProjects.vue'))
}
const notices = defineAsyncComponent(() => import('./ProjectNotices.vue'))
const arrangements = defineAsyncComponent(() => import('./translation/ProjectArrangements.vue'))
const manuscript = defineAsyncComponent(() => import('../manuscript/ManuscriptArrangements.vue'))
const help = defineAsyncComponent(() => import('./translation/TranslationHelp.vue'))
const interpretationFinance = defineAsyncComponent(() => import('./interpretation/CustomerFinance.vue'))
const sectionViews = {help,manuscript,notices,arrangements,'customer-finance':interpretationFinance}
const activeComponent = computed(() => sectionViews[activeSection.value] || projects[props.module])
const activeProps = computed(() => activeSection.value === 'notices' ? { module: props.module, moduleLabel: moduleLabel.value } : {})

async function handleSectionChange(section) {
  if (section === activeSection.value) return true
  const query = { ...route.query }
  if (section !== 'projects') query.section = section
  else delete query.section
  // 使用路由导航触发公共编辑器的未保存保护，并支持前进、后退。
  await router.push({ path: route.path, query })
  return activeSection.value === section
}
</script>

<style scoped>
.project-workspace{display:flex;flex-direction:column;gap:8px;min-width:0}
.project-workspace--projects,.project-workspace--help{height:100%;min-height:0}
.workspace-navigation{flex:none;border-color:var(--color-border);border-radius:var(--radius-lg)}
.workspace-navigation :deep(.el-card__body){padding:0 20px}
.workspace-navigation :deep(.el-tabs__header){margin:0}
.workspace-navigation :deep(.el-tabs__content){display:none}
.workspace-navigation :deep(.el-tabs__nav-wrap::after){height:1px}
.workspace-navigation :deep(.el-tabs__item){height:36px;font-size:15px}
</style>
