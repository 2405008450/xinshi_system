<template>
  <el-button v-if="canRead" text :icon="Document" @click="open">工作报告</el-button>
  <DraggableFormDialog v-if="visible" :model-value="visible" class="finance-work-report-dialog" width="min(1600px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="visible=$event">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="工作报告" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body"><DailyReportPanel ref="panel" :report-date="date" :footer-target="footer" @update:report-date="date=$event" /></div>
    <template #footer><div ref="footer" class="finance-work-report-actions" /><el-button @click="close">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,defineAsyncComponent,ref} from 'vue'
import {Document} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'
import {hasPermission} from '@/utils/permission'
import {reportBusinessDate} from '@/utils/workReportForm'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
const DailyReportPanel=defineAsyncComponent(()=>import('@/views/schedule/components/DailyReportPanel.vue'))
const visible=ref(false),date=ref(''),body=ref(),footer=ref(),panel=ref()
const canRead=computed(()=>hasPermission('reports:read')||hasPermission('reports:write'))
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
function open(){date.value=reportBusinessDate();clearFieldSearch();visible.value=true}
function beforeClose(done){if(panel.value?.prepareClose?.()===false){ElMessage.warning('工作报告正在保存或本机备份未成功，请处理提示后再关闭');return}done()}
function close(){beforeClose(()=>visible.value=false)}
</script>
<style>
.finance-work-report-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.finance-work-report-dialog>.el-dialog__header,.finance-work-report-dialog>.el-dialog__footer{flex:none}
.finance-work-report-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.finance-work-report-dialog>.el-dialog__footer{display:flex;justify-content:flex-end;align-items:center;gap:8px;border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-light)}
.finance-work-report-actions{display:flex;flex-wrap:wrap;gap:8px}
</style>
