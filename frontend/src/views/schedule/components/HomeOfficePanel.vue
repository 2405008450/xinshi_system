<template>
  <section v-loading="loading" class="home-office-panel">
    <header><div><strong>{{admin?'公司居家办公申请':'居家办公申请'}}</strong><el-tag type="info">审批：待开发</el-tag></div><div><AttendanceRulesPopover /><el-button :disabled="saving" @click="load">刷新</el-button></div></header>
    <p v-if="!desktop">手机端可查看记录；排班考勤仅请假和延迟上班申请支持手机操作，其他操作请使用电脑端。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <HomeOvertimePanel v-if="!admin" />
    <template v-if="admin"><h4>{{data.year}}年已居家天数补录</h4><p>仅补录普通居家的系统外历史天数，不计公司要求居家加班，不要重复计入下方系统申请。可登记0天；未补录时本人不能申请。今年年度占用＝补录＋系统内待审批及已批准申请。历史数据超过额度时据实记录，禁止新增申请。</p>
      <el-table :data="data.usage_people||[]" border><el-table-column prop="name" label="人员" min-width="120" /><el-table-column label="补录已居家" min-width="120"><template #default="{row}">{{row.manual_used_days??'待补录'}}</template></el-table-column><el-table-column prop="system_used_days" label="系统申请" width="105" /><el-table-column prop="annual_used" label="年度已用" width="105" /><el-table-column prop="annual_limit" label="年度上限" width="105" /><el-table-column label="剩余额度" width="110"><template #default="{row}">{{Math.max(0,row.annual_limit-row.annual_used)}}天</template></el-table-column><el-table-column label="详情" width="100" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="usage-history"><h4>{{row.name}} · 补录记录</h4><el-descriptions :column="2" border size="small"><el-descriptions-item label="年度">{{data.year}}</el-descriptions-item><el-descriptions-item label="年度占用">{{row.annual_used}}天</el-descriptions-item></el-descriptions><p v-if="!row.history?.length">尚未补录</p><p v-for="(entry,index) in row.history||[]" :key="index">{{entry.actor_name}} · {{formatBusinessDateTime(entry.at)}}：{{entry.before??'未登记'}} → {{entry.after}}天。{{entry.note}}</p></div></el-popover></template></el-table-column><el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="!desktop" @click="editUsage(row)">补录 / 修改</el-button></template></el-table-column></el-table>
    </template>
    <template v-if="!admin">
      <el-alert :title="data.qualification_hint||'正在读取居家资格'" :type="data.qualified?'success':'info'" :closable="false" />
      <p>入职时间：{{annualLeaveDateLabel(data.hire_date)}}；满3个月可申请：{{annualLeaveDateLabel(data.qualification_apply_on)}}；满6个月自动获得资格：{{annualLeaveDateLabel(data.automatic_on)}}。</p>
      <div class="home-office-actions"><el-button type="primary" :disabled="!desktop||!data.ready||!data.can_apply_qualification||saving" @click="open('qualification')">申请居家办公资格</el-button><span>批准人：总经理 赵震锋；资格申请理由必填。</span></div>
      <div class="home-office-actions"><span>申请日期</span><el-date-picker v-model="requestedDate" type="date" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" :clearable="false" :disabled="saving" aria-label="居家办公申请日期" /><el-button type="primary" :disabled="!desktop||!data.ready||!data.qualified||!data.quota_available||saving||loading" @click="open('application')">居家办公申请</el-button></div>
      <p>{{requestedDate}} 所属自然周期额度（含待审批申请）：月 {{data.month_used||0}} / 2；季度 {{data.quarter_used||0}} / 4；半年 {{data.half_used||0}} / 8；年度 {{data.annual_used||0}} / {{data.annual_limit??'-'}}。</p>
      <p>{{requestedDate.slice(0,4)}}年补录已居家：{{data.manual_used_days==null?'待行政部补录':`${data.manual_used_days}天`}}；系统内申请：{{data.system_used_days||0}}天；年度剩余：{{data.annual_remaining??0}}天。补录仅扣年度额度，未提供具体日期时不分摊到月、季度或半年。</p>
      <el-alert v-if="data.limit_message" :title="data.limit_message" type="warning" :closable="false" />
      <p>每次申请1个工作日，提交后通知行政部。未获批准前，请勿把待审批记录视为已获准居家。</p>
    </template>
    <template v-if="admin"><h4>公司要求居家加班记录（最近500条，不占普通居家额度）</h4><el-table :data="data.company_overtime||[]" border><el-table-column prop="name" label="人员" min-width="110" /><el-table-column label="日期" min-width="140"><template #default="{row}">{{annualLeaveDateLabel(row.day)}}</template></el-table-column><el-table-column label="上班打卡" min-width="175"><template #default="{row}">{{formatBusinessDateTime(row.check_in)}}</template></el-table-column><el-table-column label="下班打卡" min-width="175"><template #default="{row}">{{formatBusinessDateTime(row.check_out)}}</template></el-table-column><el-table-column prop="invalid_minutes" label="无效分钟" width="100" /><el-table-column prop="invalid_reason" label="扣除说明" min-width="160" show-overflow-tooltip /></el-table></template>
    <h4>{{admin?'最近500条居家日期申请' :'我的居家日期申请'}}</h4>
    <el-table :data="data.applications||[]" border><el-table-column v-if="admin" prop="name" label="申请人" min-width="100" /><el-table-column label="申请日期" min-width="150"><template #default="{row}">{{annualLeaveDateLabel(row.requested_date)}}</template></el-table-column><el-table-column prop="reason" label="说明" min-width="180" show-overflow-tooltip /><el-table-column label="状态" width="110"><template #default="{row}">{{statusLabel(row.status)}}</template></el-table-column><el-table-column label="提交时间" min-width="170"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column></el-table>
    <h4>{{admin?'最近500条资格申请':'我的资格申请'}}</h4>
    <el-table :data="data.qualification_requests||[]" border><el-table-column v-if="admin" prop="name" label="申请人" min-width="100" /><el-table-column prop="reason" label="申请理由" min-width="180" show-overflow-tooltip /><el-table-column label="批准人" min-width="160">总经理 赵震锋</el-table-column><el-table-column label="状态" width="110"><template #default="{row}">{{statusLabel(row.status)}}</template></el-table-column><el-table-column label="提交时间" min-width="170"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column></el-table>
    <DraggableFormDialog v-model="visible" :title="kind==='qualification'?'申请居家办公资格':'居家办公申请'" append-to-body width="min(720px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item v-if="kind==='application'" label="申请日期"><ReadonlyField :model-value="annualLeaveDateLabel(requestedDate)" source="locked" /></el-form-item>
        <el-form-item :label="kind==='qualification'?'申请理由':'申请说明（可选）'" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="4" maxlength="1000" show-word-limit :disabled="saving" /></el-form-item>
        <p>接收部门：行政部。<template v-if="kind==='qualification'">批准人：总经理 赵震锋。</template>审批：待开发。</p>
      </AppForm>
      <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交并通知行政部</el-button></template>
    </DraggableFormDialog>
    <DraggableFormDialog v-model="usageVisible" :title="`补录今年已居家天数 · ${usageTarget?.name||''}`" append-to-body width="min(650px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="closeUsage">
      <AppForm ref="usageFormRef" :model="usageForm" :rules="usageRules" label-position="top"><el-form-item label="今年已居家天数（普通居家、系统外历史）" prop="used_days"><el-input-number v-model="usageForm.used_days" :min="0" :max="366" :precision="0" :disabled="saving" /></el-form-item><el-form-item label="补录说明（可选）"><el-input v-model="usageForm.note" type="textarea" :rows="3" maxlength="500" :disabled="saving" /></el-form-item><p>不计公司要求居家加班，请勿重复包含系统已有申请。保存后立即反映在本人工作台，并保留修改记录。</p></AppForm>
      <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" /><template #footer><el-button :disabled="saving" @click="usageVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveUsage">保存补录</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,onMounted,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getHomeOffice,getCompanyHomeOffice,applyHomeOfficeQualification,applyHomeOffice,saveHomeOfficeUsage} from '@/api/attendance'
import {annualLeaveDateLabel} from '@/utils/annualLeave'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AttendanceRulesPopover from '@/components/common/AttendanceRulesPopover.vue'
import {subscribe} from '@/utils/realtimeSocket'
import {chatClientType} from '@/utils/chatDevice'
import HomeOvertimePanel from './HomeOvertimePanel.vue'
const props=defineProps({admin:Boolean}),emit=defineEmits(['eligibility']),desktop=chatClientType(navigator)==='desktop'
const requestedDate=ref(businessDateTimeInputValue(new Date()).slice(0,10)),data=ref({}),loading=ref(false),saving=ref(false),error=ref(''),visible=ref(false),kind=ref('qualification'),formRef=ref(),submitError=ref('')
const form=reactive({id:'home-office-qualification',reason:'',client_id:''})
const usageVisible=ref(false),usageTarget=ref(null),usageFormRef=ref(),usageForm=reactive({id:'',used_days:null,note:''}),usageRules={used_days:[{required:true,message:'请输入已居家天数，可填0天',trigger:'change'}]}
const rules=computed(()=>({reason:kind.value==='qualification'?[{required:true,whitespace:true,message:'请填写申请理由',trigger:'blur'}]:[]}))
const statusLabel=value=>({pending:'待审批',approved:'已批准',rejected:'已驳回'})[value]||value
let controller,sequence=0,alive=true,unsubscribe
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';try{const value=props.admin?await getCompanyHomeOffice():await getHomeOffice(requestedDate.value,{signal:controller.signal});if(alive&&id===sequence){data.value=value;emit('eligibility',value)}}catch(e){if(alive&&id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取居家办公申请失败'}finally{if(alive&&id===sequence)loading.value=false}}
function open(value){kind.value=value;Object.assign(form,{id:`home-office-${value}`,reason:'',client_id:crypto.randomUUID()});submitError.value='';visible.value=true}
function close(done){if(saving.value)return;done()}
async function submit(){if(saving.value)return;if(!await formRef.value.validate().catch(()=>false))return;saving.value=true;submitError.value='';try{const payload={client_id:form.client_id,reason:form.reason};const result=kind.value==='qualification'?await applyHomeOfficeQualification(payload):await applyHomeOffice({...payload,requested_date:requestedDate.value});ElMessage.success(result.message);data.value=result;emit('eligibility',result);visible.value=false}catch(e){submitError.value=typeof e.detail==='string'?e.detail:'申请未提交成功，请重试'}finally{saving.value=false}}
function editUsage(row){usageTarget.value=row;Object.assign(usageForm,{id:`home-usage:${row.user_id}:${data.value.year}`,used_days:row.manual_used_days,note:''});submitError.value='';usageVisible.value=true}
function closeUsage(done){if(!saving.value)done()}
async function saveUsage(){if(saving.value||!await usageFormRef.value.validate().catch(()=>false))return;saving.value=true;submitError.value='';try{const result=await saveHomeOfficeUsage({user_id:usageTarget.value.user_id,year:data.value.year,used_days:usageForm.used_days,revision:usageTarget.value.revision,note:usageForm.note});ElMessage.success(result.message);usageVisible.value=false;await load()}catch(e){submitError.value=typeof e.detail==='string'?e.detail:'补录未保存成功'}finally{saving.value=false}}
watch(requestedDate,load);onMounted(()=>{load();window.addEventListener('focus',load);unsubscribe=subscribe('home_office_usage_changed',load)});onBeforeUnmount(()=>{alive=false;sequence++;controller?.abort();unsubscribe?.();window.removeEventListener('focus',load)})
</script>
<style scoped>.home-office-panel{font-size:13px;line-height:1.8;min-width:0}.home-office-panel header,.home-office-panel header>div,.home-office-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.home-office-panel header{justify-content:space-between;margin-bottom:12px}.home-office-actions{margin:12px 0}.home-office-panel p{color:#64748b}.home-office-panel h4{margin-bottom:8px}.home-office-panel .el-table{margin-bottom:16px}.usage-history{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}</style>
