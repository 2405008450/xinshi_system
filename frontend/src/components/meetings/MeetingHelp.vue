<template>
  <DraggableFormDialog v-model="visible" title="会议与工作台帮助" width="min(1200px, calc(100vw - 32px))" top="5vh" class="meeting-help-dialog" append-to-body destroy-on-close><ProjectOperationHelp title="会议安排、工作报告与任务协作" intro="按入口、填写、通知、回执和会后落实顺序查阅。" :updated-at="meetingWorkbenchHelpUpdatedAt" module-label="会议与工作台" :sections="meetingWorkbenchHelpSections" id-prefix="meeting-help-" /><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog>
</template>
<script setup>
import {computed} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ProjectOperationHelp from '@/components/common/ProjectOperationHelp.vue'
import {meetingWorkbenchHelpSections,meetingWorkbenchHelpUpdatedAt} from '@/utils/meetingWorkbenchHelp'
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
</script>
<style>.meeting-help-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.meeting-help-dialog .el-dialog__header,.meeting-help-dialog .el-dialog__footer{flex-shrink:0}.meeting-help-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.meeting-help-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
