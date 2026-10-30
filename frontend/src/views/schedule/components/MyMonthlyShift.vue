<template>
  <section v-loading="loading" class="my-monthly-shift">
    <AttendanceOverview /><el-collapse v-model="expandedSections"><el-collapse-item name="shifts" title="班次安排"><div class="my-shift-toolbar"><h3>班次安排</h3><el-radio-group v-model="scope" aria-label="班次查看范围"><el-radio-button value="all">全部人员</el-radio-button><el-radio-button value="mine">仅看自己</el-radio-button></el-radio-group><ShiftPeriodControls v-model:mode="mode" :value="periodValue" :disabled="loading" @update:value="setPeriod" /></div>
    <WeeklyShiftHistoryDialog v-if="historyWeek" v-model="historyVisible" :week="historyWeek" :shifts="data.shifts||monthPlans[0]?.shifts" :departments="data.departments||monthPlans[0]?.departments" />
    <el-button v-if="scope==='mine'&&mode==='week'" link @click="historyWeek=week;historyVisible=true">修改记录</el-button>
    <p>当前查看{{scope==='all'?'全部人员':'本人'}}的已同步班次安排；月度包含每周不同安排，跨月周共用记录。此处仅供查看，调整请联系行政部。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-else-if="data.ready===false" :title="mode==='week'?'每周排班功能尚未初始化':'月度排班功能尚未初始化'" type="info" :closable="false" />
    <template v-else-if="scope==='all'"><MonthlyWeekOverview v-if="mode==='month'" :plans="monthPlans" :month="month" /><WeeklyShiftMatrix v-else :plan="data" :loading="loading" /></template>
    <div v-else-if="mode==='month'" class="my-month-weeks"><el-card v-for="item in monthPlans" :key="item.week_start"><template #header>{{item.week_start}} 至 {{item.week_end}} <el-button link @click="historyWeek=item.week_start;historyVisible=true">修改记录</el-button></template><template v-if="item.assignment"><p>{{item.assignment.name}} · {{item.departments.find(row=>row.code===item.assignment.department)?.label}} · {{item.shifts.find(row=>row.code===item.assignment.shift)?.label}} <el-tag v-if="item.assignment.home_rotation" size="small">居家轮班</el-tag><el-tag v-if="item.assignment.fixed" size="small" type="info">固定</el-tag></p><p v-for="period in item.shifts.find(row=>row.code===item.assignment.shift)?.periods||[]" :key="period">{{period}}</p><p v-if="item.assignment.leave_minutes">请假 {{durationLabel(item.assignment.leave_minutes)}}</p></template><p v-else>本周尚未安排班次</p></el-card></div>
    <el-descriptions v-else-if="data.assignment" :column="1" border>
      <el-descriptions-item :label="mode==='week'?'排班周':'月份'">{{mode==='week'?`${week} 至 ${shiftWeekEnd(week)}`:month}}</el-descriptions-item><el-descriptions-item label="姓名">{{data.assignment.name}}</el-descriptions-item>
      <el-descriptions-item label="排班部门">{{departmentLabel}}</el-descriptions-item><el-descriptions-item label="班次">{{shift?.label}} <el-tag v-if="data.assignment.home_rotation" size="small">居家轮班</el-tag></el-descriptions-item>
      <el-descriptions-item label="工作时段"><p v-for="period in shift?.periods||[]" :key="period">{{period}}</p></el-descriptions-item><el-descriptions-item v-if="data.assignment?.leave_minutes" label="班次内请假"><el-tag type="warning">请假 {{durationLabel(data.assignment.leave_minutes)}}</el-tag><p v-for="leave in data.assignment.leaves" :key="leave.id">{{formatBusinessDateTime(leave.start_at)}} 至 {{formatBusinessDateTime(leave.end_at)}} · {{durationLabel(leave.minutes)}}</p></el-descriptions-item><el-descriptions-item label="班次说明">{{shift?.description}}</el-descriptions-item>
    </el-descriptions>
    <el-empty v-else-if="!loading" :description="mode==='week'?'所选周尚未安排班次':'所选月份尚未安排班次'" :image-size="60" />
    </el-collapse-item><el-collapse-item name="duty" title="值班安排"><p>值班仅展示已同步安排，默认查看全部人员，也可仅看自己。实际完成的周末多值班（含居家）按规则先补班，再申请调休；待审批不等于已批准。</p><WeekendDutyOverview :mode="mode" :week="week" :month="month" :scope="scope" /></el-collapse-item><el-collapse-item name="home-office"><template #title>居家办公申请 <el-tag v-if="homeEligibility.can_apply_qualification" size="small" type="warning">已满3个月，可申请资格</el-tag></template><HomeOfficePanel @eligibility="homeEligibility=$event" /></el-collapse-item></el-collapse>
  </section>
</template>
<script setup>
import AttendanceOverview from './AttendanceOverview.vue'
import HomeOfficePanel from './HomeOfficePanel.vue'
import WeekendDutyOverview from '@/views/hr/WeekendDutyOverview.vue'
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {getMyWeeklyShift,getWeeklyShiftOverview} from '@/api/monthlyShifts'
import {currentShiftMonth,currentShiftWeek,shiftWeek,shiftWeekEnd,shiftMonthWeeks} from '@/utils/monthlyShift'
import {durationLabel} from '@/utils/attendance'
import {formatBusinessDateTime} from '@/utils/dateTime'
import ShiftPeriodControls from '@/components/common/ShiftPeriodControls.vue'
import MonthlyWeekOverview from '@/views/hr/MonthlyWeekOverview.vue'
import WeeklyShiftMatrix from '@/views/hr/WeeklyShiftMatrix.vue'
import WeeklyShiftHistoryDialog from '@/views/hr/WeeklyShiftHistoryDialog.vue'
import {subscribe} from '@/utils/realtimeSocket'
const historyWeek=ref(''),historyVisible=ref(false),expandedSections=ref([]),homeEligibility=ref({})
const scope=ref('all'),mode=ref('week'),week=ref(currentShiftWeek()),month=ref(currentShiftMonth()),data=ref({}),monthPlans=ref([]),loading=ref(false),error=ref('')
const periodValue=computed(()=>mode.value==='week'?week.value:month.value),periodKey=computed(()=>`${scope.value}:${mode.value}:${periodValue.value}`)
function setPeriod(value){if(mode.value==='week')week.value=shiftWeek(value);else month.value=value}
const shift=computed(()=>data.value.shifts?.find(row=>row.code===data.value.assignment?.shift))
const departmentLabel=computed(()=>data.value.departments?.find(row=>row.code===data.value.assignment?.department)?.label||'-')
let sequence=0,controller,unsubscribe
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';data.value={};try{monthPlans.value=[];const reader=scope.value==='all'?getWeeklyShiftOverview:getMyWeeklyShift;const value=mode.value==='week'?await reader(week.value,{signal:controller.signal}):await Promise.all(shiftMonthWeeks(month.value).map(start=>reader(start,{signal:controller.signal})));if(id===sequence){if(Array.isArray(value)){monthPlans.value=value;data.value={ready:value.every(row=>row.ready)}}else data.value=value}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取班次安排失败'}finally{if(id===sequence)loading.value=false}}
watch(periodKey,load)
onMounted(()=>{load();window.addEventListener('focus',load);unsubscribe=subscribe('weekly_shift_published',event=>{if(mode.value==='week'?shiftWeek(event.week_start)===week.value:shiftMonthWeeks(month.value).includes(event.week_start))load()})})
onBeforeUnmount(()=>{sequence++;controller?.abort();window.removeEventListener('focus',load);unsubscribe?.()})
</script>
<style scoped>.my-monthly-shift{padding:16px}.my-month-weeks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px;margin-top:12px}.my-shift-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.my-shift-toolbar h3{margin:0 12px 0 0}.my-shift-toolbar :deep(.el-button+.el-button){margin-left:0}.my-shift-toolbar :deep(.el-date-editor){width:205px}.my-monthly-shift>p{color:#64748b;font-size:13px}</style>
