<template>
  <section v-loading="loading" class="my-monthly-shift">
    <div class="my-shift-toolbar"><h3>班次安排</h3><el-radio-group v-model="scope" aria-label="班次查看范围"><el-radio-button value="all">全部人员</el-radio-button><el-radio-button value="mine">仅看自己</el-radio-button></el-radio-group><ShiftPeriodControls v-model:mode="mode" :value="periodValue" :disabled="loading" @update:value="setPeriod" /></div>
    <p>当前查看{{scope==='all'?'全部人员':'本人'}}的班次安排；此处仅供查看，调整请联系行政部。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-else-if="data.ready===false" :title="mode==='week'?'每周排班功能尚未初始化':'月度排班功能尚未初始化'" type="info" :closable="false" />
    <template v-else-if="scope==='all'"><MonthlyWeekOverview v-if="mode==='month'" :plans="monthPlans" :month="month" /><WeeklyShiftMatrix v-else :plan="data" :loading="loading" /></template>
    <div v-else-if="mode==='month'" class="my-month-weeks"><el-card v-for="item in monthPlans" :key="item.week_start"><template #header>{{item.week_start}} 至 {{item.week_end}}</template><template v-if="item.assignment"><p>{{item.assignment.name}} · {{item.departments.find(row=>row.code===item.assignment.department)?.label}} · {{item.shifts.find(row=>row.code===item.assignment.shift)?.label}} <el-tag v-if="item.assignment.fixed" size="small" type="info">固定</el-tag></p><p v-for="period in item.shifts.find(row=>row.code===item.assignment.shift)?.periods||[]" :key="period">{{period}}</p></template><p v-else>本周尚未安排班次</p></el-card></div>
    <el-descriptions v-else-if="data.assignment" :column="1" border>
      <el-descriptions-item :label="mode==='week'?'排班周':'月份'">{{mode==='week'?`${week} 至 ${shiftWeekEnd(week)}`:month}}</el-descriptions-item><el-descriptions-item label="姓名">{{data.assignment.name}}</el-descriptions-item>
      <el-descriptions-item label="排班部门">{{departmentLabel}}</el-descriptions-item><el-descriptions-item label="班次">{{shift?.label}}</el-descriptions-item>
      <el-descriptions-item label="工作时段"><p v-for="period in shift?.periods||[]" :key="period">{{period}}</p></el-descriptions-item><el-descriptions-item label="班次说明">{{shift?.description}}</el-descriptions-item>
    </el-descriptions>
    <el-empty v-else-if="!loading" :description="mode==='week'?'所选周尚未安排班次':'所选月份尚未安排班次'" :image-size="60" />
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {getMyWeeklyShift,getWeeklyShiftOverview} from '@/api/monthlyShifts'
import {currentShiftMonth,currentShiftWeek,shiftWeek,shiftWeekEnd,shiftMonthWeeks} from '@/utils/monthlyShift'
import {formatBusinessDateTime} from '@/utils/dateTime'
import ShiftPeriodControls from '@/components/common/ShiftPeriodControls.vue'
import MonthlyWeekOverview from '@/views/hr/MonthlyWeekOverview.vue'
import WeeklyShiftMatrix from '@/views/hr/WeeklyShiftMatrix.vue'
const scope=ref('all'),mode=ref('week'),week=ref(currentShiftWeek()),month=ref(currentShiftMonth()),data=ref({}),monthPlans=ref([]),loading=ref(false),error=ref('')
const periodValue=computed(()=>mode.value==='week'?week.value:month.value),periodKey=computed(()=>`${scope.value}:${mode.value}:${periodValue.value}`)
function setPeriod(value){if(mode.value==='week')week.value=shiftWeek(value);else month.value=value}
const shift=computed(()=>data.value.shifts?.find(row=>row.code===data.value.assignment?.shift))
const departmentLabel=computed(()=>data.value.departments?.find(row=>row.code===data.value.assignment?.department)?.label||'-')
let sequence=0,controller
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';data.value={};try{monthPlans.value=[];const reader=scope.value==='all'?getWeeklyShiftOverview:getMyWeeklyShift;const value=mode.value==='week'?await reader(week.value,{signal:controller.signal}):await Promise.all(shiftMonthWeeks(month.value).map(start=>reader(start,{signal:controller.signal})));if(id===sequence){if(Array.isArray(value)){monthPlans.value=value;data.value={ready:value.every(row=>row.ready)}}else data.value=value}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取班次安排失败'}finally{if(id===sequence)loading.value=false}}
watch(periodKey,load)
onMounted(()=>{load();window.addEventListener('focus',load)})
onBeforeUnmount(()=>{sequence++;controller?.abort();window.removeEventListener('focus',load)})
</script>
<style scoped>.my-monthly-shift{padding:16px}.my-month-weeks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px;margin-top:12px}.my-shift-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.my-shift-toolbar h3{margin:0 12px 0 0}.my-shift-toolbar :deep(.el-button+.el-button){margin-left:0}.my-shift-toolbar :deep(.el-date-editor){width:205px}.my-monthly-shift>p{color:#64748b;font-size:13px}</style>
