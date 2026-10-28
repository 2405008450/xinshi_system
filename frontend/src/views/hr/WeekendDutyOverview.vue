<template>
  <section v-loading="loading" class="duty-overview"><h3>值班安排</h3>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p>仅显示已同步的值班安排。</p>
    <el-button v-for="item in plans" :key="item.month" link @click="historyMonth=item.month;historyVisible=true">{{item.month}} 修改记录</el-button>
    <div class="duty-overview-scroll"><table><thead><tr><th>参与部门</th><th v-for="day in dates" :key="day">{{dutyDateLabel(day)}}</th></tr></thead><tbody><tr v-for="department in departments" :key="department.code"><th>{{department.label}}</th><td v-for="day in dates" :key="day"><p v-for="person in people(department.code,day)" :key="person.user_id">{{person.name}} <el-tag v-if="person.fixed" size="small" type="info">固定</el-tag></p><span v-if="!people(department.code,day).length">暂无安排</span></td></tr></tbody></table></div>
    <WeeklyShiftHistoryDialog v-if="historyMonth" v-model="historyVisible" kind="duty" :week="historyMonth" :departments="departments" />
  </section>
</template>
<script setup>
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {getWeekendDutyOverview} from '@/api/monthlyShifts'
import {shiftWeekEnd} from '@/utils/monthlyShift'
import {dutyDateLabel} from '@/utils/weekendDuty'
import {subscribe} from '@/utils/realtimeSocket'
import WeeklyShiftHistoryDialog from './WeeklyShiftHistoryDialog.vue'
const props=defineProps({mode:String,week:String,month:String,scope:String})
const plans=ref([]),loading=ref(false),error=ref(''),historyMonth=ref(''),historyVisible=ref(false)
const months=computed(()=>props.mode==='week'?[...new Set([props.week.slice(0,7),shiftWeekEnd(props.week).slice(0,7)])]:[props.month])
const dates=computed(()=>plans.value.flatMap(plan=>plan.dates||[]).filter(day=>props.mode!=='week'||(day>=props.week&&day<=shiftWeekEnd(props.week))))
const departments=computed(()=>plans.value[0]?.departments||[])
const people=(department,day)=>plans.value.flatMap(plan=>plan.assignments||[]).filter(person=>person.date===day&&person.department===department&&(props.scope!=='mine'||person.user_id===plans.value[0]?.current_user_id))
let sequence=0,controller,unsubscribe
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';plans.value=[];try{const result=await Promise.all(months.value.map(month=>getWeekendDutyOverview(month,{signal:controller.signal})));if(id===sequence)plans.value=result}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取值班安排失败'}finally{if(id===sequence)loading.value=false}}
watch([months,()=>props.week],load,{immediate:true})
onMounted(()=>{unsubscribe=subscribe('weekend_duty_published',event=>{if(months.value.includes(event.month))load()});window.addEventListener('focus',load)})
onBeforeUnmount(()=>{sequence++;controller?.abort();unsubscribe?.();window.removeEventListener('focus',load)})
</script>
<style scoped>.duty-overview{margin-top:20px}.duty-overview>p{font-size:12px;color:#64748b}.duty-overview-scroll{overflow:auto;max-height:65vh}table{border-collapse:collapse;font-size:14px;min-width:100%}th,td{border:1px solid #dbe3ec;padding:12px;min-width:130px;vertical-align:top}th{background:#f8fafc;position:sticky;top:0}td>p{margin:0 0 8px}td>span{color:#94a3b8;font-size:12px}</style>
