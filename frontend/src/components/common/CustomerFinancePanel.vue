<template>
  <section>
    <el-tabs v-model="active">
      <el-tab-pane label="笔译" name="translation"><template v-if="active==='translation'"><CustomerTranslationRates :client-id="clientId" :can-write="canWrite" @saved="revision++" /><CustomerRateDifferences v-if="clientId" module="translation" :client-id="clientId" :revision="revision" @saved="revision++" /><TranslationFinance v-if="clientId&&canViewProjects" :key="`${clientId}:${revision}`" :client-id="clientId" @saved="revision++" /><p v-else-if="!clientId">请先保存客户，再维护财务信息。</p></template></el-tab-pane>
      <el-tab-pane label="口译" name="interpretation"><template v-if="active==='interpretation'"><InterpretationFinanceEditor scope="client" :target-id="clientId" :can-write="canWrite" @saved="revision++" /><CustomerRateDifferences v-if="clientId" module="interpretation" :client-id="clientId" :revision="revision" @saved="revision++" /><InterpretationFinance v-if="clientId" :key="`${clientId}:${revision}`" :client-id="clientId" @saved="revision++" /></template></el-tab-pane>
      <el-tab-pane label="标注" name="annotation"><el-empty description="暂无标注财务配置" /></el-tab-pane>
      <el-tab-pane label="招聘" name="recruitment"><el-empty description="暂无招聘财务配置" /></el-tab-pane>
    </el-tabs>
  </section>
</template>
<script setup>
import {ref,defineAsyncComponent} from 'vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import InterpretationFinanceEditor from './InterpretationFinanceEditor.vue'
import {hasPermission} from '@/utils/permission'
const TranslationFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const InterpretationFinance=defineAsyncComponent(()=>import('@/views/project/interpretation/CustomerFinance.vue'))
defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const revision=ref(0),active=ref('translation'),canViewProjects=hasPermission('projects:read')||hasPermission('projects:write')
</script>
