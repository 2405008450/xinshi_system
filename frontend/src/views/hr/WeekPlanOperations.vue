<template>
  <section class="week-plan-operations">
    <AppForm label-width="90px">
      <el-form-item label="来源周"><el-date-picker v-model="source" type="date" value-format="YYYY-MM-DD" aria-label="来源周" :clearable="false" :disabled="busy" /></el-form-item>
      <el-form-item label="操作"><el-radio-group v-model="operation" :disabled="busy"><el-radio-button value="copy">复制到另一周</el-radio-button><el-radio-button value="move">转移到另一周</el-radio-button><el-radio-button value="swap">两周互换</el-radio-button></el-radio-group></el-form-item>
      <el-form-item label="目标周"><el-date-picker v-model="target" type="date" value-format="YYYY-MM-DD" aria-label="目标周" :clearable="false" :disabled="busy" /></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="operation-preview">
      <template v-if="preview">
        <p>来源：{{shiftWeekTitle(preview.source.week_start)}}，{{count(preview.source)}} 人</p>
        <p>目标：{{shiftWeekTitle(preview.target.week_start)}}，{{count(preview.target)}} 人</p>
        <el-alert :title="effect" type="warning" :closable="false" />
        <p>固定班次按各周原有配置生效，不参与复制、转移或互换；请假按实际日期计算。</p>
        <div class="operation-comparison"><div v-for="(plan,index) in [preview.source,preview.target]" :key="index"><h4>{{index?'目标周原安排':'来源周安排'}}</h4><p v-for="person in plan.assignments.filter(row=>!row.fixed)" :key="person.user_id">{{person.name}} · {{plan.departments.find(row=>row.code===person.department)?.label}} · {{plan.shifts.find(row=>row.code===person.shift)?.label}}</p><p v-if="!count(plan)">暂无非固定安排</p></div></div>
      </template>
    </div>
  </section>
</template>
<script setup>
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getWeeklyShiftPlan,transferWeeklyShiftPlan} from '@/api/monthlyShifts'
import {shiftWeek,shiftWeekTitle} from '@/utils/monthlyShift'
const props=defineProps({sourceWeek:{type:String,required:true},active:Boolean}),emit=defineEmits(['saved','busy','state'])
const source=ref(props.sourceWeek),target=ref(shiftWeek(props.sourceWeek,1)),operation=ref('copy'),preview=ref(null),loading=ref(false),busy=ref(false),error=ref('')
let sequence=0,controller
const count=plan=>plan.assignments.filter(row=>!row.fixed).length
const label=computed(()=>({copy:'确认复制',move:'确认转移',swap:'确认互换'})[operation.value])
const effect=computed(()=>operation.value==='swap'?'两周的非固定班次安排对换。':`${operation.value==='copy'?'保留来源周，将其安排复制到目标周':'清空来源周，将其安排转移到目标周'}，目标周原有的 ${preview.value?count(preview.value.target):0} 人安排被替换。`)
const canSubmit=computed(()=>!!preview.value&&!loading.value&&!busy.value&&!error.value&&(count(preview.value.source)>0||(operation.value==='swap'&&count(preview.value.target)>0)))
watch([canSubmit,label],()=>emit('state',{ready:canSubmit.value,label:label.value}),{immediate:true})
watch(()=>props.sourceWeek,value=>{source.value=value;target.value=shiftWeek(value,1)})
async function load(){
 controller?.abort();const id=++sequence;preview.value=null;error.value='';loading.value=false
 if(!props.active||!source.value||!target.value)return
 if(shiftWeek(target.value)===shiftWeek(source.value)){error.value='请选择不同的两周';return}
 controller=new AbortController();loading.value=true
 try{const [from,to]=await Promise.all([getWeeklyShiftPlan(source.value,{signal:controller.signal}),getWeeklyShiftPlan(target.value,{signal:controller.signal})]);if(id===sequence){preview.value={source:from,target:to};if(!from.ready||!to.ready)error.value='每周班次安排表尚未初始化'}}
 catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取两周排班失败'}finally{if(id===sequence)loading.value=false}
}
watch([source,target,()=>props.active],load,{immediate:true})
async function submit(){
 if(!canSubmit.value)return
 const payload={source_week:preview.value.source.week_start,target_week:preview.value.target.week_start,operation:operation.value,source_revision:preview.value.source.revision,target_revision:preview.value.target.revision}
 const message=`来源：${shiftWeekTitle(payload.source_week)}（${count(preview.value.source)}人）；目标：${shiftWeekTitle(payload.target_week)}（${count(preview.value.target)}人）。${effect.value} 是否继续？`,button=label.value
 busy.value=true;emit('busy',true)
 try{await ElMessageBox.confirm(message,'确认周安排调整',{type:'warning',confirmButtonText:button,cancelButtonText:'取消',closeOnClickModal:false});await transferWeeklyShiftPlan(payload);ElMessage.success('周安排已调整');emit('saved');await load()}
 catch(e){if(e!=='cancel'&&e!=='close'){ElMessage.error(e.detail||'调整失败，请重新预览后重试');await load()}}finally{busy.value=false;emit('busy',false)}
}
defineExpose({submit})
onBeforeUnmount(()=>{controller?.abort();sequence++})
</script>
<style scoped>.operation-preview{min-height:90px;font-size:13px;line-height:1.7}.operation-comparison{display:grid;grid-template-columns:1fr 1fr;gap:16px}.operation-comparison>div{min-width:0;overflow-wrap:anywhere}.operation-comparison p{margin:5px 0}@media(max-width:600px){.operation-comparison{grid-template-columns:1fr}.week-plan-operations :deep(.el-radio-group){gap:6px;flex-wrap:wrap}}</style>
