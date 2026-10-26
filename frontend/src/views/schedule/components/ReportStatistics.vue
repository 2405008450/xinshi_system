<template>
  <section class="report-statistics" v-loading="loading">
    <div class="stat-filter"><el-select v-model="period" aria-label="统计周期" @change="load"><el-option label="按日" value="day" /><el-option label="按周" value="week" /><el-option label="按月" value="month" /></el-select><el-date-picker v-model="anchor" :type="period==='day'?'date':period==='week'?'week':'month'" value-format="YYYY-MM-DD" :clearable="false" aria-label="统计日期" @change="load" /><el-button @click="load">刷新统计</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="result"><el-alert :title="result.basis" type="info" :closable="false" /><div class="stat-counters"><span>{{result.date_from}} 至 {{result.date_to||'尚未开始'}}</span><strong>{{result.days.length}} 个工作日</strong><strong>缺报 {{result.people.reduce((sum,person)=>sum+person.missing_dates.length,0)}} 人次</strong></div>
      <h4>每日完成情况</h4><el-table :data="result.days" border empty-text="此期间暂无应统计的工作日"><el-table-column prop="date" label="工作日" width="140" /><el-table-column prop="expected_count" label="应写人数" width="110" /><el-table-column label="已写人数 / 名单"><template #default="{row}"><el-popover trigger="click" placement="bottom" :width="400"><div class="name-list">{{names(row.written_ids)}}</div><template #reference><el-button link type="success">{{row.written_ids.length}} 人已写</el-button></template></el-popover></template></el-table-column><el-table-column label="未写人数 / 名单"><template #default="{row}"><el-popover trigger="click" placement="bottom" :width="400"><div class="name-list">{{names(row.missing_ids)}}</div><template #reference><el-button link :type="row.missing_ids.length?'danger':'info'">{{row.missing_ids.length}} 人未写</el-button></template></el-popover></template></el-table-column></el-table>
      <h4>每人缺报工作日</h4><el-table :data="result.people" border><el-table-column prop="name" label="姓名" width="150" /><el-table-column prop="expected_count" label="应写天数" width="100" /><el-table-column label="缺报天数" width="100"><template #default="{row}">{{row.missing_dates.length}}</template></el-table-column><el-table-column label="具体缺报工作日" min-width="300"><template #default="{row}"><span class="missing-dates">{{row.missing_dates.join('、')||'无缺报'}}</span></template></el-table-column></el-table>
      <small>日历来源：<a v-for="source in result.calendar_sources" :key="source" :href="source" target="_blank" rel="noopener noreferrer">国务院节假日及调休安排</a></small>
    </template>
  </section>
</template>
<script setup>
import {onMounted,onBeforeUnmount,ref,watch} from 'vue'
import {getReportStatistics} from '@/api/tasks'
import {reportBusinessDate} from '@/utils/workReportForm'
const props=defineProps({departmentId:String,keyword:String,senderId:String})
const period=ref('day'),anchor=ref(reportBusinessDate()),result=ref(),loading=ref(false),error=ref('')
let controller,sequence=0
function names(ids){return ids.map(id=>result.value.people.find(person=>person.id===id)?.name||'-').join('、')||'无'}
async function load(){controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;try{const data=await getReportStatistics({anchor:anchor.value,period:period.value,department_id:props.departmentId||undefined,keyword:props.keyword||undefined,sender_id:props.senderId||undefined},{signal:controller.signal});if(current===sequence){result.value=data;error.value=''}}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED'){result.value=null;error.value=e.detail||'读取统计失败'}}finally{if(current===sequence)loading.value=false}}
watch(()=>[props.departmentId,props.keyword,props.senderId],load);onMounted(load);onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.report-statistics{display:flex;flex-direction:column;gap:14px}.stat-filter,.stat-counters{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.stat-filter>.el-select{width:120px}.report-statistics h4{margin:12px 0 0}.stat-counters{background:#f8fafc;padding:14px}.name-list{max-height:300px;overflow-y:auto;white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere}.missing-dates{white-space:normal;line-height:1.8}.report-statistics small{color:#64748b}.report-statistics a{margin-left:10px;color:#2563eb}</style>
