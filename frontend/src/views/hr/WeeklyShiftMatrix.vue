<template>
  <ProjectArrangementLayout :enabled="editable" :can-write="!saving">
    <template #personnel><div class="monthly-roster-return" @dragover.prevent @drop.prevent="returnPeople"><ArrangementPersonnel v-model="selectedPeople" monthly schedule-period="本周" :disabled="saving||loading||!plan.ready" :assigned-ids="assignedIds" :directory-loader="getMonthlyShiftDirectory" :availability-loader="availability" /></div></template>
      <div class="monthly-matrix-scroll" :class="{'is-saving':saving}">
        <table class="monthly-matrix">
          <thead><tr><th>参与部门</th><th v-for="shift in plan.shifts" :key="shift.code"><el-popover trigger="click" placement="bottom" :width="320"><template #reference><el-button link type="primary">{{shift.label}}</el-button></template><strong>{{shift.label}}</strong><p v-for="period in shift.periods" :key="period">{{period}}</p><p>{{shift.description}}</p></el-popover></th></tr></thead>
          <tbody><tr v-for="department in plan.departments" :key="department.code"><th>{{department.label}}</th><td v-for="shift in plan.shifts" :key="shift.code" :data-cell="`${department.code}:${shift.code}`" :class="{'is-unavailable':!validCell(department.code,shift.code)}" @dragover.prevent @drop.stop.prevent="dropPeople($event,department.code,shift.code)">
            <span v-if="!validCell(department.code,shift.code)" class="monthly-hint">仅客户/销售部适用</span>
            <template v-else><el-button v-if="editable&&selectedPeople.length" size="small" :disabled="saving||loading" :aria-label="`安排所选到${department.label}${shift.label}`" @click="placePeople(selectedPeople.map(person=>person.id),department.code,shift.code)">安排所选（{{selectedPeople.length}}人）</el-button><div v-for="person in cellPeople(department.code,shift.code)" :key="person.user_id" class="monthly-person" :draggable="editable&&!saving&&!person.fixed" @dragstart="dragPerson($event,person)"><span>{{person.name}}</span><el-tag v-if="person.fixed" size="small" type="info">固定</el-tag><small v-if="!person.active">已停用</small></div><span v-if="!cellPeople(department.code,shift.code).length" class="monthly-drop-hint">{{editable?'拖入人员':'暂无安排'}}</span></template>
          </td></tr></tbody>
        </table>
      </div>
  </ProjectArrangementLayout>
</template>
<script setup>
import {computed,onBeforeUnmount,ref} from 'vue'
import {ElMessage} from 'element-plus'
import ArrangementPersonnel from '@/components/common/ArrangementPersonnel.vue'
import ProjectArrangementLayout from '@/views/project/translation/components/ProjectArrangementLayout.vue'
import {getMonthlyShiftDirectory,saveWeeklyShiftPlan} from '@/api/monthlyShifts'
const props=defineProps({plan:{type:Object,required:true},editable:Boolean,loading:Boolean})
const emit=defineEmits(['saved','busy','refresh'])
const plan=computed(()=>props.plan),selectedPeople=ref([]),saving=ref(false)
const assignedIds=computed(()=>plan.value.assignments.map(row=>row.user_id))
const availability=async()=>({ready:true})
const validCell=(department,shift)=>shift!=='customer_remote'||department==='customer'
const cellPeople=(department,shift)=>plan.value.assignments.filter(row=>row.department===department&&row.shift===shift)
let active=true
function dragPerson(event,person){if(!props.editable||saving.value||props.loading||person.fixed){event.preventDefault();return}event.dataTransfer.setData('application/x-shift-plan',JSON.stringify({period:plan.value.week_start,user_ids:[person.user_id]}));event.dataTransfer.effectAllowed='move'}
function dragged(event){try{const moved=event.dataTransfer.getData('application/x-shift-plan');if(moved){const data=JSON.parse(moved);return data.period===plan.value.week_start&&Array.isArray(data.user_ids)?data.user_ids:[]}const values=JSON.parse(event.dataTransfer.getData('application/x-project-personnel'));return Array.isArray(values)?values.map(row=>row.id):[]}catch{return []}}
async function persist(values){
 if(!props.editable||saving.value||props.loading||!plan.value.ready)return
 saving.value=true;emit('busy',true)
 try{const result=await saveWeeklyShiftPlan(plan.value.week_start,{revision:plan.value.revision,assignments:values.map(({user_id,department,shift})=>({user_id,department,shift}))});if(active){selectedPeople.value=[];emit('saved',result);ElMessage.success('本周班次已保存')}}
 catch(e){if(active){ElMessage.error(e.detail||'保存失败，原排班保持不变');if(e.response?.status===409)emit('refresh')}}finally{saving.value=false;emit('busy',false)}
}
function placePeople(values,department,shift){
 if(!props.editable||saving.value||props.loading)return
 if(!validCell(department,shift)){ElMessage.warning('此班次仅适用于客户/销售部');return}
 const fixedIds=new Set(plan.value.assignments.filter(row=>row.fixed).map(row=>row.user_id))
 if(values.some(id=>fixedIds.has(id))){ElMessage.warning('固定班次人员请通过“固定班次人员”调整');return}
 const ids=[...new Set(values)];if(!ids.length)return
 persist([...plan.value.assignments.filter(row=>!ids.includes(row.user_id)),...ids.map(user_id=>({user_id,department,shift}))])
}
function dropPeople(event,department,shift){placePeople(dragged(event),department,shift)}
function returnPeople(event){if(!props.editable||!event.dataTransfer.getData('application/x-shift-plan'))return;const ids=dragged(event);if(ids.some(id=>plan.value.assignments.some(row=>row.user_id===id&&row.fixed))){ElMessage.warning('请在“固定班次人员”中取消固定');return}if(ids.some(id=>assignedIds.value.includes(id)))persist(plan.value.assignments.filter(row=>!ids.includes(row.user_id)))}
onBeforeUnmount(()=>{active=false})
</script>
<style scoped>
.monthly-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.monthly-header h3{margin:0}.monthly-header>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.monthly-header :deep(.el-button+.el-button){margin-left:0}.monthly-header :deep(.el-date-editor){width:205px}.monthly-hint{font-size:12px;line-height:1.7;color:#64748b}.monthly-matrix-scroll{overflow-x:auto}.monthly-matrix{border-collapse:collapse;width:100%;min-width:920px;table-layout:fixed}.monthly-matrix th,.monthly-matrix td{border:1px solid #dbe3ec;padding:12px;vertical-align:top}.monthly-matrix th{background:#f8fafc;word-break:break-word}.monthly-matrix th:first-child{width:120px}.monthly-matrix td{height:110px}.monthly-matrix .is-unavailable{background:#f1f5f9}.monthly-person{padding:8px 10px;margin:0 0 6px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;cursor:default;overflow-wrap:anywhere}.monthly-person small{display:block;color:#94a3b8}.monthly-drop-hint{font-size:12px;color:#94a3b8}.is-saving{opacity:.7}.monthly-roster-return{min-width:0}
.monthly-person[draggable="true"]{cursor:grab}</style>
