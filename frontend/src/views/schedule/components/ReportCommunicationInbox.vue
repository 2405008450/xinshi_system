<template><section><el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button :loading="loading" @click="load">刷新沟通记录</el-button><el-table :data="rows" v-loading="loading" border empty-text="暂无沟通记录"><el-table-column prop="user_name" label="被评价人" /><el-table-column prop="report_date" label="报告日期" /><el-table-column label="沟通记录"><template #default="{row}"><el-button link type="primary" @click="open(row)">查看 / 回复</el-button></template></el-table-column></el-table><el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total,prev,pager,next" @current-change="load" /><DraggableFormDialog v-model="visible" :title="`${current?.user_name||''} · ${current?.report_date||''} 工作报告沟通`" width="min(760px, calc(100vw - 32px))" top="5vh" class="report-review-window" append-to-body destroy-on-close><ReportFeedbackPanel v-if="visible&&current" :key="current.report_id" :report-id="current.report_id" /><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog></section></template>
<script setup>
import {onMounted,onBeforeUnmount,ref} from 'vue'
import {getReportFeedbackInbox} from '@/api/tasks'
import ReportFeedbackPanel from './ReportFeedbackPanel.vue'
const rows=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),visible=ref(false),current=ref();let sequence=0
async function load(){const value=++sequence;loading.value=true;try{const data=await getReportFeedbackInbox({page:page.value,page_size:20});if(value===sequence){rows.value=data.items;total.value=data.total;error.value=''}}catch(e){if(value===sequence)error.value=e.detail||'读取沟通记录失败'}finally{if(value===sequence)loading.value=false}}
function open(row){current.value=row;visible.value=true}
onMounted(load);onBeforeUnmount(()=>sequence++)
</script>
