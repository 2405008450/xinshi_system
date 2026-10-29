<template>
  <section class="monthly-shift-sections">
    <WeekPlanOperationsDialog v-model="operationsDialog" :source-week="operationSource" @saved="load" @busy="operationBusy=$event" /><FixedShiftDialog v-model="fixedDialog" @saved="load" />
    <el-collapse v-model="expandedSections">
      <el-collapse-item name="shifts">
        <template #title><span>班次安排</span><div class="shift-title-actions" @keydown.stop><el-button size="small" type="primary" :disabled="navigationBusy||loading" @click.stop="openOperations()">复制 / 转移 / 互换</el-button><el-button size="small" :disabled="navigationBusy" @click.stop="fixedDialog=true">固定班次人员</el-button></div></template>
        <el-card class="common-page-card monthly-shift-management" v-loading="loading">
          <header class="monthly-header"><h3>{{periodTitle}}</h3><div><ShiftPeriodControls v-model:mode="mode" :value="periodValue" week-label="进行排班" :show-picker="mode==='month'" :disabled="navigationBusy||dutySaving" @update:value="setPeriod" /><el-button :disabled="navigationBusy" @click="load">刷新</el-button></div></header>
          <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button size="small" @click="load">重新加载班次</el-button></el-alert>
          <template v-if="mode==='week'">
            <AppForm inline label-width="80px" class="planning-period-form">
              <el-form-item label="编辑方式"><el-radio-group v-model="editingMode" :disabled="navigationBusy"><el-radio-button value="week">按周编辑</el-radio-button><el-radio-button value="month">按月分周编辑</el-radio-button></el-radio-group></el-form-item>
              <el-form-item v-if="editingMode==='month'" label="排班月份"><el-date-picker v-model="month" type="month" value-format="YYYY-MM" :clearable="false" :disabled="navigationBusy" aria-label="编辑月份" /></el-form-item>
              <el-form-item v-else label="排班周"><el-date-picker v-model="week" type="date" value-format="YYYY-MM-DD" :clearable="false" :disabled="navigationBusy" aria-label="编辑周" /><el-button :disabled="navigationBusy" @click="week=currentShiftWeek()">本周</el-button></el-form-item>
            </AppForm>
            <p class="monthly-hint">各周独立编辑，停止操作400毫秒后自动保存草稿；点击“同步”才更新全部人员工作台。已同步周请先点“修改”。其他周可折叠，跨月周共用同一份安排。</p>
            <el-collapse :model-value="expandedWeeks" @update:model-value="value=>{if(!busy)expandedWeeks=value}">
              <el-collapse-item v-for="plan in plans" :key="plan.week_start" :name="plan.week_start" :data-editor-week="plan.week_start">
                <template #title><span>{{shiftWeekTitle(plan.week_start)}}</span><el-tag v-if="plan.week_start.slice(0,7)!==plan.week_end.slice(0,7)" type="info" size="small">跨月周</el-tag><span class="week-count">{{plan.assignments.length}} 人</span></template>
                <el-alert v-if="!plan.ready" title="每周班次安排表尚未初始化，暂不能保存" type="warning" :closable="false" />
                <div class="week-actions"><el-button :disabled="navigationBusy||loading||!plan.ready" @click="openOperations(plan.week_start)">复制 / 转移 / 互换</el-button></div>
                <WeeklyShiftMatrix :plan="plan" editable :loading="busy||loading" @busy="matrixBusy=$event" @pending="value=>setPending(plan.week_start,value)" @saved="savedPlan" @refresh="load" />
                <p v-if="plan.updated_at" class="monthly-hint">最近调整：{{plan.updated_by_name}} · {{formatBusinessDateTime(plan.updated_at)}}</p>
              </el-collapse-item>
            </el-collapse>
          </template>
          <template v-else><p class="monthly-hint">月份视图仅供查看；请切换“进行排班”调整。各周独立保存，跨月周在相邻两个月共用同一份安排。</p><MonthlyWeekOverview :plans="plans" :month="month" :public="false" /></template>
        </el-card>
      </el-collapse-item>
      <el-collapse-item name="duty" title="值班安排"><WeekendDutyArrangement v-if="dutyOpened" v-model:month="month" :month-change-disabled="navigationBusy" @busy="dutySaving=$event" /></el-collapse-item>
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
import WeekPlanOperationsDialog from './WeekPlanOperationsDialog.vue'
import MonthlyWeekOverview from './MonthlyWeekOverview.vue'
import WeeklyShiftMatrix from './WeeklyShiftMatrix.vue'
const fixedDialog=ref(false),operationsDialog=ref(false),operationBusy=ref(false),matrixBusy=ref(false),busy=computed(()=>matrixBusy.value||operationBusy.value)
const pendingWeeks=ref(new Set()),navigationBusy=computed(()=>busy.value||pendingWeeks.value.size>0||dutySaving.value)
function setPending(start,value){const next=new Set(pendingWeeks.value);if(value)next.add(start);else next.delete(start);pendingWeeks.value=next}
const operationSource=ref(currentShiftWeek()),expandedWeeks=ref([]),plans=ref([])
const expandedSections=ref(['shifts']),dutyOpened=ref(false),dutySaving=ref(false)
watch(expandedSections,value=>{if(value.includes('duty'))dutyOpened.value=true})
const mode=ref('week'),editingMode=ref('week'),week=ref(currentShiftWeek()),month=ref(currentShiftMonth())
const loading=ref(false),error=ref('')
const singleWeek=computed(()=>mode.value==='week'&&editingMode.value==='week')
const periodValue=computed(()=>singleWeek.value?week.value:month.value)
const periodKey=computed(()=>`${mode.value}:${editingMode.value}:${periodValue.value}`)
const periodTitle=computed(()=>singleWeek.value?shiftWeekTitle(week.value):shiftMonthTitle(month.value))
let sequence=0,controller,active=true
function setPeriod(value){if(navigationBusy.value||dutySaving.value)return;if(mode.value==='week'){editingMode.value='week';week.value=shiftWeek(value)}else month.value=value}
function openOperations(start){if(navigationBusy.value)return;operationSource.value=start||expandedWeeks.value[0]||plans.value[0]?.week_start||week.value;operationsDialog.value=true}
function savedPlan(value){plans.value=plans.value.map(plan=>plan.week_start===value.week_start?value:plan)}
async function load(){
 controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';plans.value=[]
 const starts=singleWeek.value?[shiftWeek(week.value)]:shiftMonthWeeks(month.value)
 try{const result=await Promise.all(starts.map(start=>getWeeklyShiftPlan(start,{signal:controller.signal})));if(active&&id===sequence){plans.value=result;const retained=expandedWeeks.value.filter(start=>starts.includes(start));expandedWeeks.value=retained.length?retained:[starts.includes(currentShiftWeek())?currentShiftWeek():starts[0]]}}
 catch(e){if(active&&id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取班次安排失败'}finally{if(active&&id===sequence)loading.value=false}
}
watch(periodKey,load);onMounted(load);onBeforeUnmount(()=>{active=false;sequence++;controller?.abort()})
</script>
<style scoped>
.monthly-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.monthly-header h3{margin:0}.monthly-header>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.monthly-header :deep(.el-button+.el-button){margin-left:0}.monthly-hint{font-size:12px;line-height:1.7;color:#64748b}
.monthly-shift-sections{padding:8px 6px;margin-inline:-12px}.monthly-shift-sections :deep(.el-collapse){border:0}.monthly-shift-sections :deep(.el-collapse>.el-collapse-item){margin-bottom:12px;border:1px solid #dbe3ec;border-radius:8px;overflow:hidden}.monthly-shift-sections :deep(.el-collapse-item__header){min-height:58px;padding:0 24px;font-size:16px;font-weight:600;background:#fff;box-sizing:border-box}.monthly-shift-sections :deep(.el-collapse-item__content){padding-bottom:0}.monthly-shift-sections :deep(.el-collapse-item__title){display:flex;align-items:center;gap:12px;flex:1;min-width:0}.holiday-pending{margin-left:12px}
.shift-title-actions{display:flex;gap:8px;margin-left:auto;margin-right:14px;flex-wrap:wrap}.shift-title-actions .el-button+.el-button{margin-left:0}@media(max-width:600px){.monthly-shift-sections :deep(.el-collapse-item__header){height:auto;min-height:58px}.shift-title-actions{margin:6px 12px}}
.planning-period-form{display:flex;flex-wrap:wrap;gap:0 12px}.planning-period-form :deep(.el-form-item){margin-right:0}.week-actions{display:flex;justify-content:flex-end;margin:8px 0}.week-count{font-size:12px;color:#64748b}.planning-period-form :deep(.el-date-editor){max-width:100%}.monthly-shift-sections :deep([data-editor-week]>.el-collapse-item__header .el-collapse-item__title){flex-wrap:wrap}@media(max-width:600px){.planning-period-form{display:block}.planning-period-form :deep(.el-radio-group){flex-wrap:wrap;gap:6px}}</style>

<style scoped>@media(max-width:768px){.monthly-shift-sections{margin-inline:-6px}}</style>

<style scoped>.monthly-shift-sections :deep([data-editor-week]>.el-collapse-item__header){font-size:14px;font-weight:500;min-height:44px}.monthly-shift-sections :deep([data-editor-week]>.el-collapse-item__header .el-collapse-item__title),.monthly-shift-sections :deep([data-editor-week]>.el-collapse-item__header .el-tag),.monthly-shift-sections :deep([data-editor-week] .week-count){font-size:14px}</style>
