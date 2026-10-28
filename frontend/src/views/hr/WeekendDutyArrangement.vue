<template>
  <el-card class="common-page-card weekend-duty" v-loading="loading">
    <ProjectArrangementLayout enabled :can-write="!saving">
      <template #personnel><div class="duty-roster-return" @dragover.prevent @drop.prevent="returnPeople"><ArrangementPersonnel :key="month" v-model="selectedPeople" monthly default-collapsed :disabled="saving || loading || !plan.ready" :assignment-counts="counts" :directory-loader="getMonthlyShiftDirectory" :availability-loader="availability" /></div></template>
      <header class="duty-header"><h3>{{month.slice(0,4)}}年{{Number(month.slice(5))}}月值班安排</h3><div><el-button :disabled="saving||monthChangeDisabled" @click="chooseMonth(-1)">上月安排</el-button><el-button :disabled="saving||monthChangeDisabled" @click="chooseMonth(0)">本月安排</el-button><el-button :disabled="saving||monthChangeDisabled" @click="chooseMonth(1)">下月安排</el-button><el-date-picker :model-value="month" type="month" value-format="YYYY-MM" aria-label="值班月份" :clearable="false" :disabled="saving||monthChangeDisabled" @update:model-value="value=>$emit('update:month',value)" /><el-button :disabled="saving" @click="load">刷新值班</el-button></div></header>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-alert v-if="!plan.ready && !loading" title="周末值班安排表尚未初始化，暂不能保存。" type="warning" :closable="false" />
      <p class="duty-hint">按本月所有周六、周日安排，参与部门与班次安排相同。人员可在不同日期重复安排，同一天只安排一次；左侧数字为本月已安排次数。拖入自动保存，右侧拖动可调整日期，拖回左侧仅撤销该次安排。</p>
      <div class="duty-matrix-scroll"><table class="duty-matrix"><thead><tr><th class="duty-department">参与部门</th><th v-for="date in plan.dates" :key="date">{{dutyDateLabel(date)}}</th></tr></thead><tbody><tr v-for="department in plan.departments" :key="department.code"><th>{{department.label}}</th><td v-for="date in plan.dates" :key="date" :data-duty-cell="`${department.code}:${date}`" @dragover.prevent @drop.stop.prevent="dropPeople($event,department.code,date)"><div v-for="person in cellPeople(department.code,date)" :key="person.user_id" class="duty-person" :draggable="!saving && !loading" @dragstart="dragPerson($event,person)"><span>{{person.name}}<small v-if="!person.active">已停用</small></span><el-button link type="danger" :disabled="saving" :aria-label="`撤销${person.name}${date}值班`" @click="remove(person)">×</el-button></div><span v-if="!cellPeople(department.code,date).length" class="duty-drop-hint">拖入值班人员</span></td></tr></tbody></table></div>
      <p v-if="plan.updated_at" class="duty-hint">最近调整：{{plan.updated_by_name}} · {{formatBusinessDateTime(plan.updated_at)}}</p>
    </ProjectArrangementLayout>
  </el-card>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import ArrangementPersonnel from '@/components/common/ArrangementPersonnel.vue'
import ProjectArrangementLayout from '@/views/project/translation/components/ProjectArrangementLayout.vue'
import {getMonthlyShiftDirectory,getWeekendDutyPlan,saveWeekendDutyPlan} from '@/api/monthlyShifts'
import {currentShiftMonth,shiftMonth} from '@/utils/monthlyShift'
import {dutyCounts,dutyDateLabel,applyDutyDrop} from '@/utils/weekendDuty'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({month:{type:String,required:true},monthChangeDisabled:Boolean}),emit=defineEmits(['update:month','busy'])
const empty=()=>({ready:false,revision:0,assignments:[],dates:[],departments:[]})
const plan=ref(empty()),selectedPeople=ref([]),loading=ref(false),saving=ref(false),error=ref('')
const counts=computed(()=>dutyCounts(plan.value.assignments))
const availability=async()=>({ready:true})
let sequence=0,controller,active=true
function chooseMonth(offset){if(saving.value||props.monthChangeDisabled)return;emit('update:month',shiftMonth(currentShiftMonth(),offset))}
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';plan.value=empty();selectedPeople.value=[];try{const value=await getWeekendDutyPlan(props.month,{signal:controller.signal});if(active && id===sequence)plan.value=value}catch(e){if(active && id===sequence && e.code!=='ERR_CANCELED')error.value=e.detail||'读取周末值班安排失败'}finally{if(active && id===sequence)loading.value=false}}
const cellPeople=(department,date)=>plan.value.assignments.filter(row=>row.department===department && row.date===date)
function dragPerson(event,person){if(saving.value||loading.value){event.preventDefault();return}event.dataTransfer.setData('application/x-weekend-duty',JSON.stringify({month:props.month,date:person.date,user_ids:[person.user_id]}));event.dataTransfer.effectAllowed='move'}
function dragged(event){try{const moved=event.dataTransfer.getData('application/x-weekend-duty');if(moved){const data=JSON.parse(moved);return data.month===props.month && Array.isArray(data.user_ids)?data:null}const values=JSON.parse(event.dataTransfer.getData('application/x-project-personnel'));return Array.isArray(values)?{user_ids:values.map(row=>row.id)}:null}catch{return null}}
async function persist(values){if(saving.value||loading.value||!plan.value.ready)return;const month=props.month;saving.value=true;emit('busy',true);error.value='';try{const value=await saveWeekendDutyPlan(month,{revision:plan.value.revision,assignments:values.map(({user_id,department,date})=>({user_id,department,date}))});if(active && month===props.month){plan.value=value;selectedPeople.value=[]}ElMessage.success(`${month} 值班安排已保存`)}catch(e){if(active){error.value=e.detail||'保存失败，请重试';ElMessage.error(error.value);if(e.response?.status===409)await load()}}finally{saving.value=false;emit('busy',false)}}
function dropPeople(event,department,date){const data=dragged(event);if(!data?.user_ids.length)return;persist(applyDutyDrop(plan.value.assignments,data.user_ids,date,department,data.date))}
function returnPeople(event){if(!event.dataTransfer.getData('application/x-weekend-duty'))return;const data=dragged(event);if(!data)return;persist(plan.value.assignments.filter(row=>row.date!==data.date||!data.user_ids.includes(row.user_id)))}
function remove(person){persist(plan.value.assignments.filter(row=>row.date!==person.date||row.user_id!==person.user_id))}
watch(()=>props.month,load);onMounted(load);onBeforeUnmount(()=>{active=false;sequence++;controller?.abort()})
</script>
<style scoped>
.duty-header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}.duty-header h3{margin:0}.duty-header>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.duty-header :deep(.el-button+.el-button){margin-left:0}.duty-header :deep(.el-date-editor){width:145px}.duty-hint{font-size:12px;line-height:1.7;color:#64748b}.duty-matrix-scroll{overflow:auto;max-height:70vh}.duty-matrix{border-collapse:separate;border-spacing:0;min-width:100%;table-layout:fixed}.duty-matrix th,.duty-matrix td{border-right:1px solid #dbe3ec;border-bottom:1px solid #dbe3ec;padding:12px;vertical-align:top;min-width:165px}.duty-matrix th{background:#f8fafc;position:sticky;top:0;z-index:2;white-space:nowrap}.duty-matrix th:first-child{left:0;z-index:3;min-width:120px;max-width:120px;white-space:normal;border-left:1px solid #dbe3ec}.duty-matrix thead th{border-top:1px solid #dbe3ec}.duty-matrix tbody th{top:auto;z-index:1}.duty-matrix td{height:105px}.duty-person{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:6px 8px;margin-bottom:6px;border:1px solid #bfdbfe;background:#eff6ff;border-radius:6px;cursor:grab;overflow-wrap:anywhere}.duty-person small{display:block;color:#94a3b8}.duty-drop-hint{font-size:12px;color:#94a3b8}.duty-roster-return{min-width:0}
</style>
