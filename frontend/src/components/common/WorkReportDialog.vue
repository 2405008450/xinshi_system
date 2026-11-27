<template>
  <DraggableFormDialog v-if="modelValue" :model-value="modelValue" class="work-report-dialog" width="min(1600px, calc(100vw - 32px))" top="5vh" :z-index="100020" append-to-body :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="我的工作报告" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body"><DailyReportPanel ref="panel" :report-date="date" :footer-target="footer" :annotation-project="project" @update:report-date="date=$event" /></div>
    <template #footer><div ref="footer" class="work-report-dialog__actions" /><el-button @click="close">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {defineAsyncComponent,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {reportBusinessDate} from '@/utils/workReportForm'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
const props=defineProps({modelValue:Boolean,project:{type:Object,default:null}})
const emit=defineEmits(['update:modelValue'])
const DailyReportPanel=defineAsyncComponent(()=>import('@/views/schedule/components/DailyReportPanel.vue'))
const date=ref(reportBusinessDate()),body=ref(),footer=ref(),panel=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
watch(()=>props.modelValue,open=>{if(open){date.value=reportBusinessDate();clearFieldSearch()}},{immediate:true})
function beforeClose(done){if(panel.value?.prepareClose?.()===false){ElMessage.warning('工作报告正在保存或本机备份未成功，请处理提示后再关闭');return}done()}
function close(){beforeClose(()=>emit('update:modelValue',false))}
</script>
<style>
.work-report-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.work-report-dialog>.el-dialog__header,.work-report-dialog>.el-dialog__footer{flex:none}
.work-report-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.work-report-dialog>.el-dialog__footer{display:flex;justify-content:flex-end;align-items:center;flex-wrap:wrap;gap:8px;border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-light)}
.work-report-dialog__actions{display:flex;flex-wrap:wrap;gap:8px}
</style>
