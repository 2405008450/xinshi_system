<template>
  <DraggableFormDialog :model-value="modelValue" :title="mode==='in'?(workMode==='company_home_overtime'?'居家加班上班打卡':'上班打卡'):'下班打卡确认'" append-to-body width="min(800px, calc(100vw - 32px))" top="5vh" :before-close="close" @update:model-value="$emit('update:modelValue',$event)">
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" data-auto-draft="off">
      <template v-if="mode==='in'"><p v-if="workMode==='company_home_overtime'" class="clock-notice">本次为公司要求的居家加班，无需居家申请，不占普通居家办公次数和年度12天额度。请确认本次实际工作由公司要求，并如实打卡。</p><p class="clock-notice">员工不得在工位进食早餐。如需进食，可在会议室进行；在会议室进食后，须打开会议室窗户通风，遇中雨、大雨等恶劣天气时除外。上班打卡须在早餐后完成。</p><p>点击“打卡”即确认已阅读上述提示并完成上班打卡。</p></template>
      <template v-else>
        <p v-if="record">{{formatBusinessDateTime(record.check_in)}} 上班 · {{record.shift?.label}}<span v-if="record.shift?.code==='customer_remote'"> · 第{{(record.segment||0)+1}}段</span></p>
        <el-form-item v-if="!record?.shift?.overtime_only&&!record?.shift?.flexible" prop="early_work_confirmed" label="1. 请确认你提前到达公司的一段时间，已经在工作。"><el-radio-group v-model="form.early_work_confirmed"><el-radio :value="true">是，提前时间计加班</el-radio><el-radio :value="false">否，提前时间不计加班</el-radio></el-radio-group></el-form-item>
        <el-form-item prop="breakfast_after_eating" label="2. 请确认你没有在进食早餐前打卡。"><el-radio-group v-model="form.breakfast_after_eating"><el-radio :value="true">是</el-radio><el-radio :value="false">否</el-radio></el-radio-group></el-form-item>
        <el-alert v-if="form.breakfast_after_eating===false" title="将记录15分钟早餐时间，抵扣加班，并记违纪一次；抵扣过程可在每日明细中查看。" type="warning" :closable="false" />
        <el-form-item v-if="askDinner" prop="dinner_eaten" label="3. 今天有无进食晚餐？"><el-radio-group v-model="form.dinner_eaten"><el-radio :value="true">有</el-radio><el-radio :value="false">无</el-radio></el-radio-group></el-form-item>
        <p v-if="!remote&&record?.shift?.fixed" class="clock-note">固定班次每天扣除一次20分钟晚餐时间，不与晚餐选择重复扣除。</p>
        <p v-else-if="askDinner" class="clock-note">选择“有”扣除20分钟；当天加班不足的部分继续抵扣当月累计加班。</p>
        <p v-if="record?.shift?.flexible" class="clock-note">灵活班次不设预定上下班时间，不判迟到；本次打卡时长可查，不自动将全部工作时间计为加班。</p><p class="clock-warning">郑重提示：<br>弄虚作假一经查实，公司有权视情节每次处以 50—200 元绩效扣款，并给予警告或通报批评等纪律处分</p>
        <template v-if="atHome"><p v-if="record?.shift?.home_office_approval_status==='pending'" class="clock-note">居家申请仍待审批；此打卡声明不代表已获准居家。</p><p class="clock-warning">郑重提示：<br>请确认下班打卡之前的时间，均为真实、有效的工作时间。弄虚作假一经查实，公司有权视情节每次处以 50—200 元绩效扣款，并给予警告或通报批评等纪律处分。如需减去中间的无效时间，请选择是</p>
          <el-form-item prop="deduct_invalid_time" label="是否扣除中间的无效时间？"><el-radio-group v-model="form.deduct_invalid_time"><el-radio :value="true">是</el-radio><el-radio :value="false">否</el-radio></el-radio-group></el-form-item>
          <template v-if="form.deduct_invalid_time===true"><el-form-item prop="invalid_minutes" label="扣除时间（分钟）"><el-input-number v-model="form.invalid_minutes" :min="0.01" :max="1440" :precision="2" /></el-form-item><el-form-item prop="invalid_reason" label="情况说明"><el-input v-model="form.invalid_reason" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item></template>
        </template>
      </template>
      <template v-if="mode==='out'&&record?.requires_cross_day_reason"><el-alert title="已超过下次预定上班时间。请说明原因并填写后续上班时间，系统将以该时间及15分钟宽限判断下一次迟到，行政部可查全过程。" type="warning" :closable="false" /><el-form-item label="跨日/跨组签退原因" prop="cross_day_reason"><el-input v-model="form.cross_day_reason" type="textarea" :rows="3" maxlength="2000" /></el-form-item><el-form-item label="第二天/第二次上班时间" prop="next_start"><el-date-picker v-model="form.next_start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY年MM月DD日 HH:mm:ss" /></el-form-item></template>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button type="primary" :loading="saving" @click="submit">打卡</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {checkIn,checkOut} from '@/api/attendance'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({modelValue:Boolean,mode:String,record:Object,segment:{type:Number,default:0},workMode:{type:String,default:'scheduled'}}),emit=defineEmits(['update:modelValue','saved'])
const formRef=ref(),saving=ref(false),error=ref('')
const defaults=()=>({early_work_confirmed:null,breakfast_after_eating:null,dinner_eaten:null,deduct_invalid_time:null,invalid_minutes:0,invalid_reason:'',cross_day_reason:'',next_start:null})
const form=reactive(defaults()),remote=computed(()=>props.record?.shift?.code==='customer_remote'||props.record?.shift?.home_rotation),atHome=computed(()=>remote.value||props.record?.shift?.home_office_day),askDinner=computed(()=>!remote.value&&['late','late_late'].includes(props.record?.shift?.code))
const choice=(needed)=>({validator:(_rule,value,done)=>done(!needed()||typeof value==='boolean'?undefined:new Error('请选择是或否')),trigger:'change'})
const rules=computed(()=>({cross_day_reason:props.record?.requires_cross_day_reason?[{required:true,whitespace:true,message:'请说明跨日/跨组签退原因',trigger:'blur'}]:[],next_start:props.record?.requires_cross_day_reason?[{required:true,message:'请填写后续上班时间',trigger:'change'}]:[],early_work_confirmed:[choice(()=>props.mode==='out'&&!props.record?.shift?.overtime_only&&!props.record?.shift?.flexible)],breakfast_after_eating:[choice(()=>props.mode==='out')],dinner_eaten:[choice(()=>props.mode==='out'&&askDinner.value)],deduct_invalid_time:[choice(()=>props.mode==='out'&&atHome.value)],invalid_minutes:[{validator:(_r,v,done)=>done(!form.deduct_invalid_time||Number(v)>0?undefined:new Error('请填写大于零的扣除分钟数')),trigger:'change'}],invalid_reason:[{validator:(_r,v,done)=>done(!form.deduct_invalid_time||v?.trim()?undefined:new Error('请填写情况说明')),trigger:'blur'}]}))
watch(()=>props.modelValue,value=>{if(value){Object.assign(form,defaults());error.value=''}})
watch(()=>form.deduct_invalid_time,value=>{if(value!==true){form.invalid_minutes=0;form.invalid_reason=''}})
function close(done){if(saving.value)return;if(typeof done==='function')done();else emit('update:modelValue',false)}
async function submit(){if(saving.value)return;if(props.mode==='out'&&!await formRef.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{const value=props.mode==='in'?await checkIn({segment:props.segment,breakfast_notice_accepted:true,work_mode:props.workMode}):await checkOut({...form,next_start:form.next_start?`${form.next_start}+08:00`:null,record_id:props.record.id});ElMessage.success(value.message);window.dispatchEvent(new Event('attendance-clock-changed'));emit('saved',value.record);emit('update:modelValue',false)}catch(e){error.value=e.detail||'打卡未确认成功，请重试'}finally{saving.value=false}}
</script>
<style scoped>p{line-height:1.8;font-size:14px}.clock-notice,.clock-warning{padding:14px;border:1px solid #fed7aa;background:#fff7ed;border-radius:8px}.clock-warning{font-weight:600}.clock-note{color:#64748b;font-size:13px}.el-radio-group{display:flex;gap:12px;flex-wrap:wrap}.el-radio{margin-right:0}</style>
