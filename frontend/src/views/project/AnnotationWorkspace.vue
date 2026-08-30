<template>
  <div class="annotation-workspace" :class="{ 'annotation-workspace--focus': focusMode && activeSection === 'accounts' }">
    <el-card v-show="!(focusMode && activeSection === 'accounts')" class="workspace-navigation" shadow="never">
      <el-tabs v-model="activeSection" @tab-change="handleSectionChange">
        <el-tab-pane v-if="canViewProjects" label="标注项目管理" name="projects" />
        <el-tab-pane v-if="canViewAccounts" label="标注员账号" name="accounts" />
        <el-tab-pane v-if="canViewProjects" label="试标流程" name="trials" />
        <el-tab-pane v-if="canViewProjects" label="标注流程" name="workflow" />
      </el-tabs>
    </el-card>

    <keep-alive>
      <component :is="activeComponent" @focus-mode-change="handleFocusModeChange" />
    </keep-alive>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AnnotationProjects from './AnnotationProjects.vue'
import AnnotationAccounts from './AnnotationAccounts.vue'
import AnnotationTrials from './AnnotationTrials.vue'
import AnnotationWorkflow from './AnnotationWorkflow.vue'
import { hasPermission } from '../../utils/permission'

const route = useRoute()
const router = useRouter()
const activeSection = ref('projects')
const focusMode = ref(false)
const canViewProjects = computed(() => hasPermission('projects:read'))
const canViewAccounts = computed(() => hasPermission(['annotation_accounts:read', 'annotation_accounts:write']))
const availableSections = computed(() => new Set([
  ...(canViewProjects.value ? ['projects', 'trials', 'workflow'] : []),
  ...(canViewAccounts.value ? ['accounts'] : []),
]))
const defaultSection = () => canViewProjects.value ? 'projects' : 'accounts'

const componentMap = {
  projects: AnnotationProjects,
  accounts: AnnotationAccounts,
  trials: AnnotationTrials,
  workflow: AnnotationWorkflow,
}

const activeComponent = computed(() => componentMap[activeSection.value])

watch(
  () => route.query.section,
  (section) => {
    activeSection.value = availableSections.value.has(section) ? section : defaultSection()
    if (activeSection.value !== 'accounts') focusMode.value = false
  },
  { immediate: true },
)

const handleSectionChange = (section) => {
  if (section !== 'accounts') focusMode.value = false
  const nextQuery = { ...route.query }
  if (section === 'projects') delete nextQuery.section
  else nextQuery.section = section
  router.replace({ name: 'AnnotationProjectDetails', query: nextQuery })
}

const handleFocusModeChange = (value) => {
  focusMode.value = Boolean(value)
}
</script>

<style scoped>
.annotation-workspace {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.annotation-workspace--focus {
  gap: 0;
}

.workspace-navigation :deep(.el-card__body) {
  padding: 0 20px;
}

.workspace-navigation :deep(.el-tabs__header) {
  margin: 0;
}

.workspace-navigation :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

.workspace-navigation :deep(.el-tabs__item) {
  height: 48px;
  font-size: 15px;
}
</style>
