<template>
  <ProjectArrangementLayout :enabled="editable" :can-write="canEdit&&!saving">
    <template #personnel><div class="monthly-roster-return" @dragover.prevent @drop.prevent="returnPeople"><ArrangementPersonnel v-model="selectedPeople" monthly schedule-period="本周" :disabled="!canEdit||saving||loading||!plan.ready" :assigned-ids="assignedIds" :directory-loader="getMonthlyShiftDirectory" :availability-loader="availability" /></div></template>
      <el-alert v-if="recovery" title="有上次未保存到服务器的本机排班草稿" type="warning" :closable="false"><el-button size="small" :disabled="!canEdit" @click="restoreLocal">恢复草稿</el-button><el-button size="small" @click="discardLocal">放弃本机草稿</el-button></el-alert>
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false"><el-button size="small" :disabled="saving" @click="saveDraft">重试保存</el-button></el-alert>
      <div class="monthly-matrix-scroll" :class="{'is-saving':saving}">
        <table class="monthly-matrix">
          <thead><tr><th>参与部门</th><th v-for="shift in plan.shifts" :key="shift.code"><el-popover trigger="click" placement="bottom" :width="320"><template #reference><el-button link type="primary">{{shift.label}}</el-button></template><strong>{{shift.label}}</strong><p v-for="period in shift.periods" :key="period">{{period}}</p><p>{{shift.description}}</p></el-popover></th></tr></thead>
          <tbody><tr v-for="department in plan.departments" :key="department.code"><th>{{department.label}}</th><td v-for="shift in plan.shifts" :key="shift.code" :data-cell="`${department.code}:${shift.code}`" :class="{'is-unavailable':!validCell(department.code,shift.code)}" @dragover.prevent @drop.stop.prevent="dropPeople($event,department.code,shift.code)">
            <span v-if="!validCell(department.code,shift.code)" class="monthly-hint">仅客户/销售部适用</span>
            <template v-else><el-button v-if="canEdit&&selectedPeople.length" size="small" :disabled="saving||loading" :aria-label="`安排所选到${department.label}${shift.label}`" @click="placePeople(selectedPeople.map(person=>person.id),department.code,shift.code)">安排所选（{{selectedPeople.length}}人）</el-button><div v-for="person in cellPeople(department.code,shift.code)" :key="person.user_id" class="monthly-person" :draggable="canEdit&&!saving&&!person.fixed" @dragstart="dragPerson($event,person)"><span>{{person.name}}</span><el-tag v-if="person.fixed" size="small" type="info">固定</el-tag><el-tag v-if="person.leave_minutes" type="warning" size="small">请假 {{durationLabel(person.leave_minutes)}}</el-tag><small v-if="!person.active">已停用</small></div><span v-if="!cellPeople(department.code,shift.code).length" class="monthly-drop-hint">{{editable?'拖入人员':'暂无安排'}}</span></template>
          </td></tr></tbody>
        </table>
      </div>
      <div class="weekly-sync-bar">
        <span v-if="editable" class="weekly-save-state">{{saving?'草稿保存中…':dirty?'草稿待自动保存（400毫秒）':basePlan.updated_at?`草稿已保存 · ${formatBusinessDateTime(basePlan.updated_at)}`:'尚无草稿修改'}}</span>
        <div class="weekly-sync-actions"><el-button v-if="basePlan.week_start" link @click="historyVisible=true">修改记录</el-button><template v-if="editable"><el-button :disabled="saving||dirty||!basePlan.published||basePlan.can_edit" @click="enableEdit">修改</el-button><el-button :type="basePlan.needs_sync||dirty?'warning':'primary'" :class="{'needs-sync':basePlan.needs_sync||dirty}" :loading="syncing" :disabled="saving||syncing||!basePlan.sync_ready||(!basePlan.needs_sync&&!dirty&&!basePlan.can_edit)" @click="syncPlan">{{!basePlan.published?'同步（尚未同步）':basePlan.needs_sync||dirty?'同步（有未同步修改）':basePlan.can_edit?'同步':'已同步'}}</el-button></template></div>
      </div>
  </ProjectArrangementLayout>
  <WeeklyShiftHistoryDialog v-if="basePlan.week_start" v-model="historyVisible" :week="basePlan.week_start" :public="!editable" :shifts="basePlan.shifts" :departments="basePlan.departments" />
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import ArrangementPersonnel from '@/components/common/ArrangementPersonnel.vue'
import ProjectArrangementLayout from '@/views/project/translation/components/ProjectArrangementLayout.vue'
import {getMonthlyShiftDirectory,saveWeeklyShiftPlan,syncWeeklyShiftPlan,enableWeeklyShiftEdit} from '@/api/monthlyShifts'
import {durationLabel} from '@/utils/attendance'
import {formatBusinessDateTime} from '@/utils/dateTime'
import WeeklyShiftHistoryDialog from './WeeklyShiftHistoryDialog.vue'
const props=defineProps({plan:{type:Object,required:true},editable:Boolean,loading:Boolean})
const emit=defineEmits(['saved','busy','refresh','pending'])
const basePlan=ref(props.plan),draft=ref(props.plan.assignments||[]),selectedPeople=ref([]),saving=ref(false),syncing=ref(false),dirty=ref(false),saveError=ref(''),historyVisible=ref(false),recovery=ref(null)
const plan=computed(()=>({...basePlan.value,assignments:draft.value}))
const canEdit=computed(()=>props.editable&&basePlan.value.can_edit!==false&&basePlan.value.sync_ready===true&&!syncing.value)
const assignedIds=computed(()=>draft.value.map(row=>row.user_id))
const availability=async()=>({ready:true})
const validCell=(department,shift)=>shift!=='customer_remote'||department==='customer'
const cellPeople=(department,shift)=>draft.value.filter(row=>row.department===department&&row.shift===shift)
let active=true,timer=null
const key=()=>`xinshi.weekly-draft.v1:${localStorage.getItem('user_id')||'anonymous'}:${basePlan.value.week_start}`
const compact=values=>values.map(({user_id,department,shift})=>({user_id,department,shift}))
function checkRecovery(){if(!props.editable)return;try{const value=JSON.parse(localStorage.getItem(key())||'null');recovery.value=value&&Array.isArray(value.assignments)?value:null}catch{recovery.value=null}}
watch(()=>props.plan,value=>{if(!dirty.value&&!saving.value){basePlan.value=value;draft.value=value.assignments||[];checkRecovery()}},{immediate:true})
function backup(){try{localStorage.setItem(key(),JSON.stringify({assignments:draft.value,revision:basePlan.value.revision,savedAt:new Date(Date.now()+28800000).toISOString().replace('Z','+08:00')}))}catch{saveError.value='本机草稿备份失败，请确认服务器保存成功后再离开'}}
function discardLocal(){localStorage.removeItem(key());recovery.value=null}
function restoreLocal(){if(!recovery.value||!canEdit.value)return;if(recovery.value.revision!==basePlan.value.revision){ElMessage.warning('服务器草稿版本已变化，请先核对修改记录，不能直接覆盖');return}queueSave(recovery.value.assignments);recovery.value=null}
function applySaved(value,clearBackup=true){basePlan.value=value;draft.value=value.assignments||[];dirty.value=false;saveError.value='';if(clearBackup)discardLocal();if(active){selectedPeople.value=[];emit('saved',value)}}
function queueSave(values){if(!canEdit.value||saving.value||props.loading)return;draft.value=values;dirty.value=true;emit('pending',true);saveError.value='';backup();clearTimeout(timer);timer=setTimeout(()=>void saveDraft(),400)}
async function saveDraft(){
 clearTimeout(timer);timer=null
 if(!dirty.value)return basePlan.value
 if(saving.value||!basePlan.value.sync_ready)return null
 const start=basePlan.value.week_start,backupKey=key(),values=compact(draft.value)
 saving.value=true;emit('busy',true)
 try{const result=await saveWeeklyShiftPlan(start,{revision:basePlan.value.revision,assignments:values});if(active)applySaved(result);else localStorage.removeItem(backupKey);return result}
 catch(e){if(active){saveError.value=e.detail||'自动保存失败，本机草稿已保留；请重试或重新载入核对版本';ElMessage.error(saveError.value)}return null}finally{saving.value=false;emit('busy',false);emit('pending',false)}
}
const version=value=>({revision:value.revision,publication_revision:value.publication_revision||0,fixed_revision:value.fixed_revision||0})
async function enableEdit(){if(saving.value)return;try{applySaved(await enableWeeklyShiftEdit(basePlan.value.week_start,version(basePlan.value)),false);ElMessage.success('可继续修改；自动保存后仍需点击同步')}catch(e){ElMessage.error(e.detail||'开启修改失败，请刷新重试')}}
async function syncPlan(){
 if(syncing.value||saving.value)return
 const value=await saveDraft();if(!value)return
 syncing.value=true;emit('busy',true)
 try{applySaved(await syncWeeklyShiftPlan(value.week_start,version(value)));ElMessage.success('本周班次及修改记录已同步到全部人员工作台')}
 catch(e){ElMessage.error(e.detail||'同步失败，草稿已保留')}finally{syncing.value=false;emit('busy',false)}
}
function dragPerson(event,person){if(!canEdit.value||saving.value||props.loading||person.fixed){event.preventDefault();return}event.dataTransfer.setData('application/x-shift-plan',JSON.stringify({period:plan.value.week_start,user_ids:[person.user_id]}));event.dataTransfer.effectAllowed='move'}
let draggedNames=new Map()
function dragged(event){try{const moved=event.dataTransfer.getData('application/x-shift-plan');if(moved){const data=JSON.parse(moved);return data.period===plan.value.week_start&&Array.isArray(data.user_ids)?data.user_ids:[]}const values=JSON.parse(event.dataTransfer.getData('application/x-project-personnel'));if(!Array.isArray(values))return [];draggedNames=new Map(values.map(row=>[row.id,row.name]));return values.map(row=>row.id)}catch{return []}}
function placePeople(values,department,shift){
 if(!canEdit.value||saving.value||props.loading)return
 if(!validCell(department,shift)){ElMessage.warning('此班次仅适用于客户/销售部');return}
 const fixedIds=new Set(draft.value.filter(row=>row.fixed).map(row=>row.user_id))
 if(values.some(id=>fixedIds.has(id))){ElMessage.warning('固定班次人员请通过“固定班次人员”调整');return}
 const ids=[...new Set(values)];if(!ids.length)return
 const old=new Map(draft.value.map(row=>[row.user_id,row]))
 queueSave([...draft.value.filter(row=>!ids.includes(row.user_id)),...ids.map(user_id=>({user_id,department,shift,name:old.get(user_id)?.name||selectedPeople.value.find(row=>row.id===user_id)?.name||draggedNames.get(user_id)||'待保存人员',active:old.get(user_id)?.active??true}))])
}
function dropPeople(event,department,shift){placePeople(dragged(event),department,shift)}
function returnPeople(event){if(!canEdit.value||!event.dataTransfer.getData('application/x-shift-plan'))return;const ids=dragged(event);if(ids.some(id=>draft.value.some(row=>row.user_id===id&&row.fixed))){ElMessage.warning('请在“固定班次人员”中取消固定');return}if(ids.some(id=>assignedIds.value.includes(id)))queueSave(draft.value.filter(row=>!ids.includes(row.user_id)))}
onBeforeUnmount(()=>{active=false;emit('pending',false);clearTimeout(timer);if(dirty.value&&!saving.value)void saveDraft()})
</script>
<style scoped>
.monthly-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.monthly-header h3{margin:0}.monthly-header>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.monthly-header :deep(.el-button+.el-button){margin-left:0}.monthly-header :deep(.el-date-editor){width:205px}.monthly-hint{font-size:12px;line-height:1.7;color:#64748b}.monthly-matrix-scroll{max-height:min(75vh,720px);overflow-x:auto;overflow-y:scroll;scrollbar-gutter:stable;overscroll-behavior:contain}.monthly-roster-return :deep(.arrangement-personnel){max-height:min(75vh,720px);overflow-y:scroll;scrollbar-gutter:stable;overscroll-behavior:contain}.monthly-matrix thead{position:sticky;top:0;z-index:1}.monthly-matrix{border-collapse:collapse;width:100%;min-width:920px;table-layout:fixed}.monthly-matrix th,.monthly-matrix td{border:1px solid #dbe3ec;padding:12px;vertical-align:top}.monthly-matrix th{background:#f8fafc;word-break:break-word}.monthly-matrix th:first-child{width:120px}.monthly-matrix td{height:110px}.monthly-matrix .is-unavailable{background:#f1f5f9}.monthly-person{padding:8px 10px;margin:0 0 6px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;cursor:default;overflow-wrap:anywhere}.monthly-person small{display:block;color:#94a3b8}.monthly-drop-hint{font-size:12px;color:#94a3b8}.is-saving{opacity:.7}.monthly-roster-return{min-width:0}
.monthly-person[draggable="true"]{cursor:grab}</style>
<style scoped>.monthly-matrix{font-size:14px}.monthly-roster-return :deep(.arrangement-personnel){font-size:14px;--el-font-size-base:14px;--el-collapse-header-font-size:14px}.monthly-roster-return :deep(.arrangement-personnel .el-collapse-item__header),.monthly-roster-return :deep(.personnel-heading strong),.monthly-roster-return :deep(.el-checkbox__label){font-size:14px}.monthly-roster-return :deep(.el-collapse-item__header){padding-inline:8px!important}.monthly-roster-return :deep(.arrangement-personnel){padding:8px;gap:8px}</style>

<style scoped>.weekly-sync-bar{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 0;font-size:12px;color:#64748b}.weekly-sync-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap;margin-left:auto}.weekly-sync-actions .el-button+.el-button{margin-left:0}.needs-sync{font-weight:600;box-shadow:0 0 0 2px var(--el-color-warning-light-7)}.weekly-save-state{overflow-wrap:anywhere}</style>
