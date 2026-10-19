<template>
  <el-select class="annotation-progress-track-select" :model-value="modelValue" :disabled="disabled" :validate-event="false" aria-label="进度归属" size="small" @change="$emit('change', $event)">
    <el-option value="project" label="项目进度"><span>项目进度</span><small v-if="projectHasDraft" class="annotation-progress-track-draft">未保存</small></el-option>
    <el-option value="customer" label="客户进度"><span>客户进度</span><small v-if="customerHasDraft" class="annotation-progress-track-draft">未保存</small></el-option>
  </el-select>
</template>

<script setup>
defineProps({ modelValue: { type: String, required: true }, disabled: Boolean, projectHasDraft: Boolean, customerHasDraft: Boolean })
defineEmits(['change'])
</script>

<style>
.annotation-progress-track-select{width:110px;flex:none}
.annotation-progress-track-draft{margin-left:10px;color:var(--el-text-color-secondary);font-size:11px}
.annotation-progress-note-item>.el-form-item__label{height:auto;align-items:flex-start;padding-right:12px}
@media(max-width:600px){
  .annotation-progress-note-item{flex-direction:column}
  .annotation-progress-note-item>.el-form-item__label{width:auto!important;margin-bottom:8px;justify-content:flex-start;padding-right:0}
  .annotation-progress-note-item>.el-form-item__content{width:100%;margin-left:0!important}
}
</style>
