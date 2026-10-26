<template><section v-if="history.length" class="revision-history"><el-alert title="此报告已使用一次修改机会，下方保留修改前后记录。" type="warning" :closable="false" /><p>修改时间：{{formatBusinessDateTime(history[0].created_at)}}</p><el-collapse><el-collapse-item title="修改前的报告" name="before"><ReportSnapshot :report="history[0].before" /></el-collapse-item><el-collapse-item title="修改后的报告" name="after"><ReportSnapshot :report="history[0].after" /></el-collapse-item></el-collapse></section><el-alert v-else-if="error" :title="error" type="error" :closable="false" /></template>
<script setup>
import {onMounted,onBeforeUnmount,ref,watch} from 'vue'
import {getReportRevisionHistory} from '@/api/tasks'
import {formatBusinessDateTime} from '@/utils/dateTime'
import ReportSnapshot from './ReportSnapshot.vue'
const props=defineProps({reportId:String,version:Boolean})
const history=ref([]),error=ref('');let sequence=0
async function load(){const current=++sequence;if(!props.reportId){history.value=[];return}try{const result=await getReportRevisionHistory(props.reportId);if(current===sequence){history.value=result;error.value=''}}catch(e){if(current===sequence)error.value=e.detail||'读取修改记录失败'}}
watch(()=>[props.reportId,props.version],load);onMounted(load);onBeforeUnmount(()=>sequence++)
</script>
<style scoped>.revision-history{margin-top:16px}.revision-history>p{font-size:12px;color:#64748b}</style>
