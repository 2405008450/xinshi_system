<template>
  <DraggableFormDialog :model-value="true" :title="`${identity.user_name} · ${identity.report_date} 工作报告`" :width="parallel?'min(620px, calc(50vw - 24px))':'min(860px, calc(100vw - 32px))'" top="7vh" :style="initialStyle" class="report-review-window" modal-class="report-review-overlay" non-modal :modal="false" :lock-scroll="false" :close-on-click-modal="false" append-to-body destroy-on-close @update:model-value="value=>{if(!value)$emit('close')}">
    <template #header><span class="is-copyable-title" style="user-select:text;cursor:text" @mousedown.stop>{{identity.user_name}} · {{identity.report_date}} 工作报告</span></template>
    <div v-loading="loading"><el-alert v-if="error" :title="error" type="error" :closable="false" /><template v-if="report"><el-tabs v-model="tab"><el-tab-pane label="工作明细" name="report"><ReportSnapshot :report="report" feedback @feedback="feedback" /></el-tab-pane><el-tab-pane label="逐项沟通" name="feedback"><ReportFeedbackPanel ref="feedbackRef" :report-id="identity.id" :work-items="report.items" allow-new /></el-tab-pane><el-tab-pane label="修改记录" name="history"><ReportRevisionHistory :report-id="identity.id" :version="report.amendment_used" /></el-tab-pane></el-tabs></template></div>
    <template #footer><el-button :loading="loading" @click="load">刷新报告</el-button><el-button @click="$emit('close')">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,onMounted,ref} from 'vue'
import {getReceivedReport} from '@/api/tasks'
import {subscribe} from '@/utils/realtimeSocket'
import ReportSnapshot from './ReportSnapshot.vue'
import ReportFeedbackPanel from './ReportFeedbackPanel.vue'
import ReportRevisionHistory from './ReportRevisionHistory.vue'
const props=defineProps({identity:{type:Object,required:true},index:{type:Number,default:0},parallel:Boolean})
defineEmits(['close'])
const report=ref(),loading=ref(false),error=ref(''),tab=ref('report'),feedbackRef=ref()
const initialStyle=computed(()=>props.parallel?{position:'fixed',left:props.index%2?'calc(50vw + 8px)':'16px',marginLeft:0}:{marginLeft:`${20+(props.index%5)*32}px`})
let sequence=0
async function load(){const current=++sequence;loading.value=true;try{const result=await getReceivedReport(props.identity.id);if(current===sequence){report.value=result;error.value=''}}catch(e){if(current===sequence){report.value=null;error.value=e.detail||'报告不存在或无权查看'}}finally{if(current===sequence)loading.value=false}}
async function feedback(key){tab.value='feedback';await nextTick();feedbackRef.value?.focusItem(key)}
const stopUpdates=subscribe('daily_report_updated',event=>{if(event.report_id===props.identity.id)load()})
onMounted(load);onBeforeUnmount(()=>{stopUpdates();sequence++})
</script>
<style>.report-review-overlay,.report-review-overlay .el-overlay-dialog{pointer-events:none}.report-review-overlay .el-dialog{pointer-events:auto}.report-review-window{display:flex;flex-direction:column;max-height:88vh;overflow:hidden}.report-review-window .el-dialog__header,.report-review-window .el-dialog__footer{flex-shrink:0}.report-review-window .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.report-review-window .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}@media(max-width:760px){.report-review-window{width:calc(100vw - 32px)!important;left:16px!important;margin-left:0!important}}</style>
