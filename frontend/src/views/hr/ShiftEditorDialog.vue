<template>
  <DraggableFormDialog :model-value="modelValue" title="增加/编辑班次" width="min(1500px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="增加/编辑班次" placeholder="搜索月份、排班周、部门等" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBodyRef" class="shift-editor-body">
      <el-tabs v-model="tab" :before-leave="()=>!busy">
        <el-tab-pane label="班次编辑" name="edit">
          <AppForm inline label-width="80px" class="editor-period-form">
            <el-form-item label="编辑方式"><el-radio-group :model-value="mode" :disabled="busy" @update:model-value="setMode"><el-radio-button value="month">按月分周编辑</el-radio-button><el-radio-button value="week">按周编辑</el-radio-button></el-radio-group></el-form-item>
            <el-form-item v-if="mode==='month'" label="排班月份"><el-date-picker v-model="month" type="month" value-format="YYYY-MM" :clearable="false" :disabled="busy" aria-label="编辑月份" /></el-form-item>
            <el-form-item v-else label="排班周"><el-date-picker v-model="week" type="date" value-format="YYYY-MM-DD" :clearable="false" :disabled="busy" aria-label="编辑周" /><el-button :disabled="busy" @click="week=currentShiftWeek()">本周</el-button></el-form-item>
          </AppForm>
          <p class="editor-hint">各周独立编辑，拖入、调班或拖回人员后自动保存，仅影响操作的这一周。跨月周在相邻两个月均显示，共用同一份安排。</p>
          <el-alert v-if="error" :title="error" type="error" :closable="false" />
          <div v-loading="loading">
            <el-collapse :model-value="expanded" @update:model-value="value=>{if(!busy)expanded=value}">
              <el-collapse-item v-for="plan in plans" :key="plan.week_start" :name="plan.week_start" :data-editor-week="plan.week_start" data-dialog-field-search-group>
                <template #title><span data-dialog-field-search-group-title>{{shiftWeekTitle(plan.week_start)}}</span><el-tag v-if="crossMonth(plan)" type="info" size="small">跨月周</el-tag><span class="week-count">{{plan.assignments.length}} 人</span></template>
                <div :data-dialog-field-search-label="`${plan.week_start} 部门班次安排`">
                  <el-alert v-if="!plan.ready" title="每周班次安排表尚未初始化，暂不能保存" type="warning" :closable="false" />
                  <div class="week-actions"><el-button :disabled="busy||loading||!plan.ready" @click="openOperations(plan.week_start)">复制 / 转移 / 互换</el-button></div>
                  <WeeklyShiftMatrix :plan="plan" editable :loading="busy||loading" @busy="matrixBusy=$event" @saved="savedPlan" @refresh="load" />
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-tab-pane>
        <el-tab-pane label="复制 / 转移 / 互换" name="operations"><WeekPlanOperations ref="operationsRef" :source-week="operationSource" :active="modelValue&&tab==='operations'" @busy="operationBusy=$event" @state="operationState=$event" @saved="operationSaved" /></el-tab-pane>
      </el-tabs>
    </div>
    <template #footer><span class="editor-footer-hint">{{busy?'正在保存，请稍候…':'班次调整自动保存'}}</span><el-button :disabled="busy" @click="close()">完成</el-button><el-button v-if="tab==='operations'" type="primary" :loading="operationBusy" :disabled="!operationState.ready||busy" @click="operationsRef?.submit()">{{operationState.label}}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getWeeklyShiftPlan} from '@/api/monthlyShifts'
import {currentShiftMonth,currentShiftWeek,shiftMonth,shiftMonthWeeks,shiftWeek,shiftWeekTitle} from '@/utils/monthlyShift'
import WeeklyShiftMatrix from './WeeklyShiftMatrix.vue'
import WeekPlanOperations from './WeekPlanOperations.vue'
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue','saved'])
const editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const mode=ref('month'),month=ref(shiftMonth(currentShiftMonth(),1)),week=ref(currentShiftWeek()),tab=ref('edit'),expanded=ref([]),plans=ref([]),loading=ref(false),error=ref('')
const matrixBusy=ref(false),operationBusy=ref(false),busy=computed(()=>matrixBusy.value||operationBusy.value),operationsRef=ref(null),operationSource=ref(currentShiftWeek()),operationState=ref({ready:false,label:'确认复制'})
const periodKey=computed(()=>`${mode.value}:${mode.value==='month'?month.value:shiftWeek(week.value)}`)
let sequence=0,controller
function close(done){if(busy.value)return;if(typeof done==='function')done();else emit('update:modelValue',false)}
function setMode(value){if(busy.value)return;mode.value=value;if(value==='week')week.value=currentShiftWeek()}
const crossMonth=plan=>plan.week_start.slice(0,7)!==plan.week_end.slice(0,7)
function openOperations(start){operationSource.value=start;tab.value='operations'}
async function load(){
 controller?.abort();const id=++sequence;if(!props.modelValue)return
 controller=new AbortController();loading.value=true;error.value='';plans.value=[]
 const starts=mode.value==='month'?shiftMonthWeeks(month.value):[shiftWeek(week.value)]
 try{const result=await Promise.all(starts.map(start=>getWeeklyShiftPlan(start,{signal:controller.signal})));if(id===sequence){plans.value=result;const retained=expanded.value.filter(start=>starts.includes(start));expanded.value=retained.length?retained:[starts[0]];if(tab.value==='edit')operationSource.value=expanded.value[0]}}
 catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取排班失败'}finally{if(id===sequence)loading.value=false}
}
function savedPlan(value){plans.value=plans.value.map(plan=>plan.week_start===value.week_start?value:plan);emit('saved')}
async function operationSaved(){emit('saved');await load()}
watch(periodKey,load)
watch(()=>props.modelValue,value=>{if(value){mode.value='month';month.value=shiftMonth(currentShiftMonth(),1);week.value=currentShiftWeek();tab.value='edit';expanded.value=[];clearFieldSearch();load()}else{controller?.abort();sequence++;plans.value=[]}},{immediate:true})
onBeforeUnmount(()=>{controller?.abort();sequence++})
</script>
<style scoped>.editor-period-form{display:flex;flex-wrap:wrap;gap:0 12px}.editor-period-form :deep(.el-form-item){margin-right:0}.editor-period-form :deep(.el-date-editor){max-width:100%}.editor-hint,.editor-footer-hint{font-size:12px;color:#64748b;line-height:1.7}.editor-footer-hint{margin-right:auto}.week-actions{display:flex;justify-content:flex-end;margin:8px 0}.week-count{font-size:12px;color:#64748b;margin-left:10px}.shift-editor-body :deep(.el-collapse-item__title){display:flex;flex-wrap:wrap;align-items:center;gap:8px}.shift-editor-body :deep(.el-collapse-item__content){padding-bottom:12px}.shift-editor-body :deep(.el-tabs__content){overflow:visible}.shift-editor-body{min-width:0}@media(max-width:600px){.editor-period-form{display:block}.editor-period-form :deep(.el-radio-group){flex-wrap:wrap;gap:6px}.editor-footer-hint{display:none}}</style>
