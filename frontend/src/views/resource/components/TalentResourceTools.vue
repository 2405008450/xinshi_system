<template>
  <div class="talent-resource-tools"><el-button @click="matchRef.open()">资源匹配</el-button><el-button @click="pathRef.open()">路径筛选</el-button></div>
  <TalentRegionMatchDialog ref="matchRef" />
  <TalentPathFilterDialog ref="pathRef" :can-write="canWrite" @saved="$emit('saved',$event)" />
</template>
<script setup>
import { ref,computed } from 'vue'
import { hasPermission } from '@/utils/permission'
import TalentRegionMatchDialog from './TalentRegionMatchDialog.vue'
import TalentPathFilterDialog from './TalentPathFilterDialog.vue'
defineEmits(['saved'])
const matchRef=ref(),pathRef=ref()
const canWrite=computed(()=>hasPermission(['talents:write','translators:write']))
</script>
<style scoped>.talent-resource-tools{display:flex;align-items:center;gap:8px}.talent-resource-tools>.el-button+.el-button{margin-left:0}</style>
