<template>
  <div class="finance-workspace">
    <RouteSectionNavigation :items="sections" label="财务管理分类"><template #actions><el-button link type="primary" @click="helpVisible=true">帮助</el-button></template></RouteSectionNavigation>
    <FinanceWorkflowHelp v-model="helpVisible" />
    <keep-alive>
      <component :is="activeComponent" v-if="activeComponent" :key="activeModule">
        <template v-if="activeModule === 'translation'" #project-type-filter>
          <el-form-item label="项目类型">
            <el-select model-value="translation" aria-label="项目类型" style="width: 160px">
              <el-option v-for="type in projectTypes" :key="type.value" :value="type.value"
                :label="type.label" :disabled="!type.available" />
            </el-select>
          </el-form-item>
        </template>
      </component>
    </keep-alive>
    <el-card v-if="activeProjectType && !activeProjectType.available" shadow="never">
      <el-empty :description="activeProjectType.label" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute } from 'vue-router'
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'
import FinanceWorkflowHelp from '@/components/common/FinanceWorkflowHelp.vue'

const route = useRoute()
const helpVisible=ref(false)
const projectTypes = [
  { value: 'translation', label: '笔译', available: true },
  { value: 'interpretation', label: '口译（待开发）', available: false },
  { value: 'annotation', label: '标注（待开发）', available: false },
  { value: 'recruitment', label: '招聘（待开发）', available: false },
]
const sections = projectTypes.map(type => ({
  path: `/finance-management/${type.value}`,
  label: type.label,
}))
const views = {
  permissions:defineAsyncComponent(()=>import('../finance/StatementPermissions.vue')),
  translation: defineAsyncComponent(() => import('./translation/CustomerFinance.vue')),
}
const activeModule = computed(() => route.params.module)
const activeProjectType = computed(() => projectTypes.find(type => type.value === activeModule.value))
const activeComponent = computed(() => views[activeModule.value])
</script>

<style scoped>
.finance-workspace { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
:global(.main-content:has(.finance-workspace)) { padding-bottom: 0; }
</style>
