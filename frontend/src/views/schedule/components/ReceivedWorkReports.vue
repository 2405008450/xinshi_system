<template>
  <section class="received-reports">
    <div class="filters"><el-input v-model="keyword" clearable placeholder="搜索姓名或账号，可输入多个关键词" aria-label="搜索报告姓名" @keyup.enter="query" /><el-select v-model="departmentId" filterable clearable placeholder="部门" aria-label="筛选报告部门" @change="query"><el-option v-for="department in directory.departments" :key="department.id" :value="department.id" :label="department.name" /></el-select><el-select v-model="senderId" filterable clearable placeholder="指定人员" aria-label="筛选发送报告人" @change="query"><el-option v-for="person in directory.people" :key="person.id" :value="person.id" :label="`${person.name}（${person.username}）`" /></el-select><el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button></div>
    <el-tabs v-model="active"><el-tab-pane label="工作报告列表" name="reports">
      <div class="report-actions"><el-date-picker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" @change="query" /><el-button :disabled="!selectedRows.length" @click="selectedRows.forEach(open)">打开所选报告（{{selectedRows.length}}）</el-button><el-switch v-model="parallel" active-text="并排查看" aria-label="并排查看报告" /><el-button v-if="windows.length" @click="windows=[]">关闭全部窗口（{{windows.length}}）</el-button></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-alert v-if="idleOverLimitCount" :title="`当前范围内有 ${idleOverLimitCount} 份报告的每日空闲时间超过 60 分钟`" type="error" show-icon :closable="false" class="report-idle-warning" />
      <el-table :data="rows" v-loading="loading" border row-key="id" empty-text="当前范围内暂无有权查看的已确认报告" @selection-change="value=>selectedRows=value"><el-table-column type="selection" width="45" /><el-table-column prop="user_name" label="姓名" min-width="140" /><el-table-column prop="report_date" label="报告日期" width="140" /><el-table-column label="合计耗时" width="120"><template #default="{row}">{{durationLabel(row.duration_minutes)}}</template></el-table-column><el-table-column label="当日空闲" width="125"><template #default="{row}"><strong :class="{'idle-danger':row.idle_minutes>60}">{{row.idle_minutes==null?'未填写':row.idle_minutes+'分钟'}}</strong></template></el-table-column>
      <el-table-column label="本周空闲合计" width="140"><template #default="{row}"><span :title="row.week_date_from+' 至 '+row.week_date_to">{{row.week_idle_minutes==null?'暂无已填数据':row.week_idle_minutes+'分钟'}}</span></template></el-table-column>
      <el-table-column label="本月空闲合计" width="140"><template #default="{row}"><span :title="row.month_date_from+' 至 '+row.month_date_to">{{row.month_idle_minutes==null?'暂无已填数据':row.month_idle_minutes+'分钟'}}</span></template></el-table-column>
      <el-table-column label="日报提示" min-width="235"><template #default="{row}"><div class="report-daily-flags"><el-tag v-if="row.idle_minutes>60" type="danger">空闲超过60分钟</el-tag><el-tag v-if="row.has_lunch_work" type="primary" class="lunch-work-tag">有中午工作</el-tag><span v-if="!(row.idle_minutes>60)&&!row.has_lunch_work">—</span></div></template></el-table-column>
      <el-table-column label="最近保存时间" min-width="180"><template #default="{row}">{{formatBusinessDateTime(row.saved_at)}}</template></el-table-column><el-table-column label="提交时间" min-width="180"><template #default="{row}">{{formatBusinessDateTime(row.finalized_at)}}</template></el-table-column><el-table-column label="详情" width="110" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="工作报告详情" :popper-style="{maxWidth:'calc(100vw - 32px)'}" @show="loadDetail(row.id)" @hide="clearDetail(row.id)"><div class="report-detail" v-loading="detailLoading[row.id]"><el-alert v-if="detailErrors[row.id]" :title="detailErrors[row.id]" type="error" :closable="false" /><ReportSnapshot v-if="details[row.id]" :report="details[row.id]" /></div><template #reference><el-button link type="primary">查看详情</el-button></template></el-popover></template></el-table-column><el-table-column label="对比 / 反馈" width="140" fixed="right"><template #default="{row}"><el-button link type="primary" @click="open(row)">打开报告窗口</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50]" :total="total" layout="total,sizes,prev,pager,next" @current-change="load" @size-change="query" />
    </el-tab-pane><el-tab-pane label="空闲时间统计" name="idle-statistics" lazy><ReportIdleStatistics :department-id="departmentId" :keyword="appliedKeyword" :sender-id="senderId" /></el-tab-pane><el-tab-pane :label="directory.can_supervise?'全部报告沟通':'报告沟通'" name="communications" lazy><ReportCommunicationInbox /></el-tab-pane><el-tab-pane v-if="directory.can_statistics" label="工作日缺报统计" name="statistics" lazy><ReportStatistics :department-id="departmentId" :keyword="appliedKeyword" :sender-id="senderId" /></el-tab-pane></el-tabs>
    <ReportReviewWindow v-for="(identity,index) in windows" :key="identity.id" :identity="identity" :index="index" :parallel="parallel" @close="windows=windows.filter(row=>row.id!==identity.id)" />
  </section>
</template>
<script setup>
import {onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {getReceivedReports,getReceivedReport,getReportReviewDirectory} from '@/api/tasks'
import {durationLabel,reportBusinessDate} from '@/utils/workReportForm'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {subscribe} from '@/utils/realtimeSocket'
import ReportSnapshot from './ReportSnapshot.vue'
import ReportReviewWindow from './ReportReviewWindow.vue'
import ReportCommunicationInbox from './ReportCommunicationInbox.vue'
import ReportStatistics from './ReportStatistics.vue'
import ReportIdleStatistics from './ReportIdleStatistics.vue'
const directory=reactive({people:[],departments:[],can_statistics:false,can_supervise:false})
const rows=ref([]),senderId=ref(''),departmentId=ref(''),keyword=ref(''),appliedKeyword=ref(''),dates=ref([reportBusinessDate(),reportBusinessDate()]),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),active=ref('reports'),selectedRows=ref([]),windows=ref([]),parallel=ref(false)
const details=reactive({}),detailErrors=reactive({}),detailLoading=reactive({}),versions={}
let controller,sequence=0,timer
const pageSize=ref(20)
const idleOverLimitCount=ref(0)
function params(){return {sender_id:senderId.value||undefined,department_id:departmentId.value||undefined,keyword:appliedKeyword.value||undefined,date_from:dates.value?.[0],date_to:dates.value?.[1],page:page.value,page_size:pageSize.value}}
async function load(){controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;error.value='';selectedRows.value=[];for(const id of Object.keys(versions))clearDetail(id);try{const result=await getReceivedReports(params(),{signal:controller.signal});if(current===sequence){rows.value=result.items;total.value=result.total;idleOverLimitCount.value=result.idle_over_limit_count||0}}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED'){rows.value=[];total.value=0;idleOverLimitCount.value=0;error.value=e.detail||'读取报告失败'}}finally{if(current===sequence)loading.value=false}}
function query(){clearTimeout(timer);appliedKeyword.value=keyword.value.trim();page.value=1;load()}
watch(keyword,value=>{clearTimeout(timer);if(!value)query();else timer=setTimeout(query,400)})
function reset(){senderId.value='';departmentId.value='';keyword.value='';dates.value=[];query()}
function open(row){if(!windows.value.some(item=>item.id===row.id))windows.value.push({...row})}
function clearDetail(id){versions[id]=(versions[id]||0)+1;delete details[id];delete detailErrors[id];delete detailLoading[id]}
async function loadDetail(id){clearDetail(id);const current=versions[id];detailLoading[id]=true;try{const report=await getReceivedReport(id);if(versions[id]===current)details[id]=report}catch(e){if(versions[id]===current)detailErrors[id]=e.detail||'报告不存在或已无权查看'}finally{if(versions[id]===current)detailLoading[id]=false}}
onMounted(async()=>{window.addEventListener('work-report-lunch-changed',load);window.addEventListener('focus',load);load();try{Object.assign(directory,await getReportReviewDirectory())}catch{directory.people=[]}})
const stopUpdates=subscribe('daily_report_updated',load)
onBeforeUnmount(()=>{window.removeEventListener('work-report-lunch-changed',load);window.removeEventListener('focus',load);stopUpdates();sequence++;controller?.abort();clearTimeout(timer);for(const id of Object.keys(versions))clearDetail(id)})
</script>
<style scoped>.received-reports{display:flex;flex-direction:column;gap:14px}.filters,.report-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.filters>.el-input{width:280px}.filters>.el-select{width:180px}.report-actions{margin-bottom:14px}.report-actions :deep(.el-date-editor){max-width:100%}.report-detail{max-height:560px;min-height:80px;overflow-y:auto}.received-reports :deep(.el-pagination){margin-top:14px}</style>

<style scoped>
.idle-danger{color:#b91c1c;font-weight:700}.report-daily-flags{display:flex;gap:6px;flex-wrap:wrap}.report-idle-warning{margin-bottom:12px}.lunch-work-tag{--el-tag-text-color:#1d4ed8;--el-tag-bg-color:#eff6ff;--el-tag-border-color:#bfdbfe}
</style>
