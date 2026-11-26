<template>
  <DraggableFormDialog v-model="visible" :title="helpTitle" width="min(1200px, calc(100vw - 32px))" top="5vh" class="meeting-help-dialog" append-to-body destroy-on-close><ProjectOperationHelp :title="helpTitle" :intro="workbench ? '查阅工作报告、个人任务与日常协作的操作说明。' : '按填写、通知、回执、会议记录和会后确认顺序查阅。'" :updated-at="meetingWorkbenchHelpUpdatedAt" :module-label="workbench ? '工作台' : '会议'" :sections="sections" :id-prefix="workbench ? 'workbench-help-' : 'meeting-help-'" /><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog>
</template>
<script setup>
import {computed} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ProjectOperationHelp from '@/components/common/ProjectOperationHelp.vue'
import {meetingWorkbenchHelpSections,meetingWorkbenchHelpUpdatedAt} from '@/utils/meetingWorkbenchHelp'
const props=defineProps({modelValue:Boolean,workbench:Boolean}),emit=defineEmits(['update:modelValue'])
const helpTitle=computed(()=>props.workbench?'工作台帮助':'会议帮助')
const sections=computed(()=>meetingWorkbenchHelpSections.filter(section=>props.workbench?section.group!=='会议安排':section.group==='会议安排'))
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
</script>
<style>.meeting-help-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.meeting-help-dialog .el-dialog__header,.meeting-help-dialog .el-dialog__footer{flex-shrink:0}.meeting-help-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.meeting-help-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
