<template>
  <section class="chat-managed-projects">
    <el-config-provider :z-index="10000"><component :is="views[module]" embedded :my-projects="myProjects" /></el-config-provider>
  </section>
</template>
<script setup>
import {defineAsyncComponent} from 'vue'
defineProps({module:{type:String,required:true},myProjects:Boolean})
const views={
  translation:defineAsyncComponent(()=>import('@/views/project/translation/ProjectDetails.vue')),
  interpretation:defineAsyncComponent(()=>import('@/views/project/interpretation/InterpretationProjectDetails.vue')),
  consultation:defineAsyncComponent(()=>import('@/views/client/Consultations.vue')),
}
</script>
<style scoped>
.chat-managed-projects{height:100%;min-height:0;overflow:auto}.chat-managed-projects :deep(.el-card){min-height:100%}
</style>
