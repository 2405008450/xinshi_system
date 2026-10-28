<template>
  <section class="monthly-shift-sections">
    <ShiftEditorDialog v-model="editorDialog" @saved="load" /><FixedShiftDialog v-model="fixedDialog" @saved="load" />
    <el-collapse v-model="expandedSections">
      <el-collapse-item name="shifts">
        <template #title><span>班次安排</span><div class="shift-title-actions" @keydown.stop><el-button size="small" type="primary" @click.stop="editorDialog=true">增加/编辑班次</el-button><el-button size="small" @click.stop="fixedDialog=true">固定班次人员</el-button></div></template>
        <el-card class="common-page-card monthly-shift-management" v-loading="loading">
          <header class="monthly-header"><h3>{{periodTitle}}</h3><div><ShiftPeriodControls v-model:mode="mode" :value="periodValue" :disabled="dutySaving" @update:value="setPeriod" /><el-button @click="load">刷新</el-button></div></header>
          <p class="monthly-hint">此处仅查看班次。调整请点击“增加/编辑班次”。月份视图按周分别展示，跨月周在相邻两个月共用同一份安排。</p>
          <el-alert v-if="error" :title="error" type="error" :closable="false" />
          <el-alert v-if="!plan.ready&&!loading" title="每周班次安排表尚未初始化" type="warning" :closable="false" />
          <MonthlyWeekOverview v-if="mode==='month'" :plans="monthPlans" :month="month" />
          <WeeklyShiftMatrix v-else :plan="plan" :loading="loading" />
          <p v-if="mode==='week'&&plan.updated_at" class="monthly-hint">最近调整：{{plan.updated_by_name}} · {{formatBusinessDateTime(plan.updated_at)}}</p>
        </el-card>
      </el-collapse-item>
      <el-collapse-item name="duty" title="值班安排"><WeekendDutyArrangement v-if="dutyOpened" v-model:month="month" @busy="dutySaving=$event" /></el-collapse-item>
      <el-collapse-item name="holidays"><template #title><strong>节假日安排</strong><el-tag class="holiday-pending" type="info" size="small">待开发</el-tag></template><el-empty description="待开发" :image-size="65" /></el-collapse-item>
    </el-collapse>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import ShiftPeriodControls from '@/components/common/ShiftPeriodControls.vue'
import {getWeeklyShiftPlan} from '@/api/monthlyShifts'
import {currentShiftMonth,shiftMonthTitle,currentShiftWeek,shiftWeek,shiftWeekTitle,shiftMonthWeeks} from '@/utils/monthlyShift'
import {formatBusinessDateTime} from '@/utils/dateTime'
import WeekendDutyArrangement from './WeekendDutyArrangement.vue'
import FixedShiftDialog from './FixedShiftDialog.vue'
import ShiftEditorDialog from './ShiftEditorDialog.vue'
import MonthlyWeekOverview from './MonthlyWeekOverview.vue'
import WeeklyShiftMatrix from './WeeklyShiftMatrix.vue'
const fixedDialog=ref(false),editorDialog=ref(false),monthPlans=ref([])
const expandedSections=ref(['shifts']),dutyOpened=ref(false),dutySaving=ref(false)
watch(expandedSections,value=>{if(value.includes('duty'))dutyOpened.value=true})
const mode=ref('week'),week=ref(currentShiftWeek()),month=ref(currentShiftMonth())
const emptyPlan=()=>({ready:false,assignments:[],shifts:[],departments:[],revision:0})
const plan=ref(emptyPlan()),loading=ref(false),error=ref('')
const periodValue=computed(()=>mode.value==='week'?week.value:month.value)
const periodKey=computed(()=>`${mode.value}:${periodValue.value}`)
const periodTitle=computed(()=>mode.value==='week'?shiftWeekTitle(week.value):shiftMonthTitle(month.value))
let sequence=0,controller,active=true
function setPeriod(value){if(dutySaving.value)return;if(mode.value==='week')week.value=shiftWeek(value);else month.value=value}
async function load(){
 controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';plan.value=emptyPlan();monthPlans.value=[]
 try{const value=mode.value==='week'?await getWeeklyShiftPlan(week.value,{signal:controller.signal}):await Promise.all(shiftMonthWeeks(month.value).map(start=>getWeeklyShiftPlan(start,{signal:controller.signal})));if(active&&id===sequence){if(Array.isArray(value)){monthPlans.value=value;plan.value={...value[0],assignments:[]}}else plan.value=value}}
 catch(e){if(active&&id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取班次安排失败'}finally{if(active&&id===sequence)loading.value=false}
}
watch(periodKey,load);onMounted(load);onBeforeUnmount(()=>{active=false;sequence++;controller?.abort()})
</script>
<style scoped>
.monthly-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.monthly-header h3{margin:0}.monthly-header>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.monthly-header :deep(.el-button+.el-button){margin-left:0}.monthly-hint{font-size:12px;line-height:1.7;color:#64748b}
.monthly-shift-sections{padding:8px 12px}.monthly-shift-sections :deep(.el-collapse){border:0}.monthly-shift-sections :deep(.el-collapse>.el-collapse-item){margin-bottom:12px;border:1px solid #dbe3ec;border-radius:8px;overflow:hidden}.monthly-shift-sections :deep(.el-collapse-item__header){min-height:58px;padding:0 24px;font-size:16px;font-weight:600;background:#fff;box-sizing:border-box}.monthly-shift-sections :deep(.el-collapse-item__content){padding-bottom:0}.monthly-shift-sections :deep(.el-collapse-item__title){display:flex;align-items:center;gap:12px;flex:1;min-width:0}.holiday-pending{margin-left:12px}
.shift-title-actions{display:flex;gap:8px;margin-left:auto;margin-right:14px;flex-wrap:wrap}.shift-title-actions .el-button+.el-button{margin-left:0}@media(max-width:600px){.monthly-shift-sections :deep(.el-collapse-item__header){height:auto;min-height:58px}.shift-title-actions{margin:6px 12px}}
</style>
