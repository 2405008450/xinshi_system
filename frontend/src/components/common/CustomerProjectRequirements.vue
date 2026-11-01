<template>
  <el-popover v-if="hasContent" trigger="click" placement="left" :width="640" title="客户要求">
    <template #reference><el-button link type="primary">客户要求</el-button></template>
    <el-descriptions :column="2" border size="small" class="customer-project-requirements"><el-descriptions-item label="客户专业要求" :span="2"><span>{{professional || '-'}}</span></el-descriptions-item><el-descriptions-item label="客户特殊要求" :span="2"><span>{{special || '-'}}</span></el-descriptions-item></el-descriptions>
  </el-popover>
  <span v-else>-</span>
</template>
<script setup>
import {computed} from 'vue'
const props=defineProps({professional:String,special:String})
const hasContent=computed(()=>String(props.professional||'').trim()||String(props.special||'').trim())
</script>
<style scoped>.customer-project-requirements{max-height:560px;overflow-y:auto}.customer-project-requirements span{white-space:pre-wrap;overflow-wrap:anywhere}</style>
