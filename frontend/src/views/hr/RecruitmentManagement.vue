<template>
  <section class="hr-recruitment-management"><el-collapse v-model="sections"><el-collapse-item name="requirements" title="招聘需求"><RecruitmentRequirements @changed="version++" /></el-collapse-item><el-collapse-item name="process" title="招聘过程"><RecruitmentProcess v-if="sections.includes('process')" :requirement-version="version" /></el-collapse-item></el-collapse></section>
</template>
<script setup>
import {ref,defineAsyncComponent} from 'vue'
import RecruitmentRequirements from './RecruitmentRequirements.vue'
const RecruitmentProcess=defineAsyncComponent(()=>import('./RecruitmentProcess.vue'))
const sections=ref(['requirements']),version=ref(0)
</script>
