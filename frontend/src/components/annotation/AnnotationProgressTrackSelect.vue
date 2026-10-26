<template>
  <el-select class="annotation-progress-track-select" popper-class="annotation-progress-track-popper" :model-value="modelValue" :disabled="disabled" :validate-event="false" aria-label="进度归属" size="small" @change="$emit('change', $event)">
    <el-option value="project" label="项目进度"><span>项目进度</span><small v-if="projectHasDraft" class="annotation-progress-track-draft">未保存</small></el-option>
    <el-option value="customer" label="客户进度"><span>客户进度</span><small v-if="customerHasDraft" class="annotation-progress-track-draft">未保存</small></el-option>
    <el-option value="annotator" label="标注员情况" />
  </el-select>
</template>

<script setup>
defineProps({ modelValue: { type: String, required: true }, disabled: Boolean, projectHasDraft: Boolean, customerHasDraft: Boolean })
defineEmits(['change'])
</script>

<style>
.el-popper.annotation-progress-track-popper,.el-popper.annotation-progress-entry-date-popper{z-index:100030!important}
.annotation-progress-track-select{width:110px;flex:none}
.annotation-progress-track-draft{margin-left:10px;color:var(--el-text-color-secondary);font-size:11px}
.annotation-progress-note-item>.el-form-item__label{height:auto;align-items:flex-start;padding-right:12px}
.el-dialog.annotation-progress-dialog{height:90vh}
.annotation-progress-dialog .progress-entry-panel{padding:12px 14px 4px;border:1px solid var(--el-color-primary-light-7);border-radius:8px;background:var(--el-color-primary-light-9);box-sizing:border-box}
.annotation-progress-dialog .progress-entry-panel__header{height:24px;min-height:24px;margin-bottom:10px;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:12px}
.annotation-progress-dialog .progress-entry-metadata{position:relative;height:88px;overflow:visible;align-content:start}
.annotation-progress-dialog .progress-entry-metadata>.el-col{flex:0 0 50%;max-width:50%}
.annotation-progress-dialog .progress-entry-metadata .el-form-item{position:static}
.annotation-progress-dialog .progress-status-hint{position:absolute;top:36px;left:7px;right:7px;width:auto}
.annotation-progress-dialog .progress-entry-actions{min-height:38px;box-sizing:border-box;display:flex;align-items:center;padding:2px 0 10px}
.annotation-progress-dialog .progress-entry-form .el-form-item{margin-bottom:10px}
.annotation-progress-dialog .annotation-progress-note-item>.el-form-item__label{position:relative;justify-content:flex-start;padding-right:12px!important}
.annotation-progress-dialog .annotation-progress-note-item.is-required>.el-form-item__label:before{position:absolute;left:-10px}
.annotation-progress-dialog .progress-entry-panel__title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:767px){.annotation-progress-dialog .progress-entry-panel__header{flex-direction:row;align-items:center}}
@media(max-width:480px){.annotation-progress-dialog .progress-entry-metadata{height:144px}.annotation-progress-dialog .progress-entry-metadata>.el-col{flex-basis:100%;max-width:100%}.annotation-progress-dialog .progress-status-hint{top:82px}}
@media(max-width:600px){
  .annotation-progress-note-item{flex-direction:column}
  .annotation-progress-note-item>.el-form-item__label{width:auto!important;margin-bottom:8px;justify-content:flex-start;padding-right:0}
  .annotation-progress-note-item>.el-form-item__content{width:100%;margin-left:0!important}
}
</style>
