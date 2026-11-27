<template>
  <section class="meeting-board" data-auto-draft="off">
    <div class="meeting-toolbar"><h3>会议安排</h3><el-button type="primary" @click="createVisible=true">新增会议</el-button><el-input v-model="keyword" clearable placeholder="搜索会议编号、主题、类型、地点" @keyup.enter="query" /><el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button><el-button @click="load">刷新</el-button></div>
    <div class="meeting-period"><el-radio-group v-model="period" aria-label="会议时间范围"><el-radio-button value="day">日</el-radio-button><el-radio-button value="week">周</el-radio-button><el-radio-button value="month">月</el-radio-button><el-radio-button value="year">年</el-radio-button></el-radio-group><el-date-picker v-model="anchor" :type="period==='day'?'date':period" value-format="YYYY-MM-DD" :clearable="false" :editable="false" aria-label="选择会议日期" /><span>显示所选时段内所有召开人的会议（UTC+8，周一至周日）；默认按日查看。</span></div>
    <el-button class="meeting-help-entry" @click="helpVisible=true">会议帮助</el-button>
    <MeetingHelp v-model="helpVisible" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border row-key="id">
      <el-table-column label="序号" width="70"><template #default="{ $index }">{{(page-1)*10+$index+1}}</template></el-table-column>
      <el-table-column prop="meeting_no" label="会议编号" width="170" />
      <el-table-column label="会议" min-width="240"><template #default="{row}"><strong>{{row.topic}}</strong><div class="meeting-red" v-if="row.my_response==='pending'">待提交参会回执</div><div class="meeting-red" v-if="row.unread_receipts">{{row.unread_receipts}}份新回执</div><div class="meeting-red">{{meetingCountdown(row,currentTime)}}</div></template></el-table-column>
      <el-table-column label="状态" width="140"><template #default="{row}"><el-select v-if="row.is_organizer" :model-value="row.status" :disabled="!!statusSaving" aria-label="调整会议状态" @change="value=>changeStatus(row,value)"><el-option v-for="(label,value) in statusLabels" :key="value" :value="value" :label="label" /></el-select><span v-else>{{statusLabels[row.status]}}</span></template></el-table-column>
      <el-table-column prop="meeting_type" label="会议类型" width="110" />
      <el-table-column prop="organizer_name" label="召开人" width="110" />
      <el-table-column label="会议时间（UTC+8）" min-width="240"><template #default="{row}">{{formatBusinessDateTime(row.start_at)}}<br>至 {{formatBusinessDateTime(row.end_at)}}</template></el-table-column>
      <el-table-column prop="location" label="地点" min-width="190" />
      <el-table-column label="回执" width="140"><template #default="{row}">{{row.participant_count-row.pending_count}} / {{row.participant_count}} 人已回执</template></el-table-column>
      <el-table-column label="详情" width="115" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" :title="`${row.meeting_no} · 详情`"><div class="meeting-details"><el-descriptions :column="2" border size="small"><el-descriptions-item label="会议编号">{{row.meeting_no}}</el-descriptions-item><el-descriptions-item label="主题">{{row.topic}}</el-descriptions-item><el-descriptions-item label="召开人">{{row.organizer_name}}</el-descriptions-item><el-descriptions-item label="类型">{{row.meeting_type}}</el-descriptions-item><el-descriptions-item label="地点">{{row.location}}</el-descriptions-item><el-descriptions-item label="开始">{{formatBusinessDateTime(row.start_at)}}</el-descriptions-item><el-descriptions-item label="结束">{{formatBusinessDateTime(row.end_at)}}</el-descriptions-item><el-descriptions-item label="关联信息" :span="2">{{associationText(row)}}</el-descriptions-item><el-descriptions-item label="说明" :span="2">{{row.note||'-'}}</el-descriptions-item></el-descriptions></div><template #reference><el-button link type="primary">查看详情</el-button></template></el-popover></template></el-table-column>
      <el-table-column label="操作" width="160" fixed="right"><template #default="{row}"><el-button v-if="row.is_organizer||row.my_response" link type="primary" @click="openDetail(row.id)">{{row.is_organizer?'阅读参会回执':'查看并回执'}}</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <MeetingForm v-model="createVisible" @saved="saved" />
    <DraggableFormDialog v-model="detailVisible" :title="detail?`${detail.meeting_no} · ${detail.topic}`:'会议回执'" class="meeting-receipt-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false">
      <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" />
      <div v-if="detail" v-loading="detailLoading">
        <p>会议编号：{{detail.meeting_no}}</p><p><strong>{{detail.meeting_type}} · {{detail.organizer_name}}</strong></p><p>{{formatBusinessDateTime(detail.start_at)}} 至 {{formatBusinessDateTime(detail.end_at)}}（UTC+8）</p><p>{{detail.location}}</p><p>{{associationText(detail)}}</p>
        <h4>会议议程</h4><div v-for="(agenda,index) in detail.agendas" :key="index" class="meeting-note"><strong>议程{{index+1}}</strong><p>{{agenda.content}}</p><small>参与人员：{{detail.participants.filter(p=>agenda.user_ids.includes(p.user_id)).map(p=>p.name).join('、')}}</small></div>
        <h4>补充说明</h4><p class="meeting-note">{{detail.note||'-'}}</p>
        <el-button v-if="detail.is_organizer&&!detail.confirmed_at" type="success" @click="actualVisible=true">确认正式时间与参与人员，填入工作报告</el-button>
        <el-alert v-if="detail.confirmed_at" :title="`已确认实际会议：${formatBusinessDateTime(detail.actual_start_at)} 至 ${formatBusinessDateTime(detail.actual_end_at)}；${detail.actual_user_ids.length}人已填入报告`" type="success" :closable="false" />
        <AppForm v-if="detail.my_version!=null" ref="receiptForm" :model="response" :rules="receiptRules" label-position="top" @submit.prevent="respond">
          <el-form-item label="我的参会回执" prop="response"><el-radio-group v-model="response.response"><el-radio value="attending">可以参加</el-radio><el-radio value="declined">不能参加</el-radio></el-radio-group></el-form-item>
          <el-form-item v-if="response.response==='declined'" label="不能参加的事由" prop="reason"><el-input v-model="response.reason" type="textarea" :rows="3" maxlength="2000" placeholder="请说明不能参加的事由" /></el-form-item>
          <el-button type="primary" :loading="responding" @click="respond">提交回执</el-button>
        </AppForm>
        <div class="meeting-toolbar"><h4>参与人员及回执（{{detail.participants.length}}人）</h4><el-button v-if="detail.is_organizer" :loading="reading" @click="markReceipts">标记当前回执已读</el-button><el-button @click="openDetail(detail.id)">刷新回执</el-button></div>
        <el-table :data="detail.participants" border size="small" max-height="340"><el-table-column prop="name" label="参与人员" width="140" /><el-table-column label="回执" width="120"><template #default="{row}"><span :class="{'meeting-red':row.response==='pending'||row.response==='declined'}">{{responseLabels[row.response]}}</span></template></el-table-column><el-table-column v-if="detail.is_organizer" prop="reason" label="不能参加的事由" min-width="250" show-overflow-tooltip /><el-table-column label="回执时间" min-width="190"><template #default="{row}">{{formatBusinessDateTime(row.responded_at)}}</template></el-table-column></el-table>
        <MeetingRecords ref="recordsRef" :key="detail.id" :meeting="detail" @saved="openDetail(detail.id)" />
      </div>
      <template #footer><el-button v-if="detail?.is_organizer" type="primary" :loading="recordsRef?.saving" @click="recordsRef?.save()">保存会议记录并发送任务安排</el-button><el-button @click="detailVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
    <MeetingActualForm v-if="detail" v-model="actualVisible" :meeting="detail" @saved="()=>{openDetail(detail.id);load()}" />
  </section>
</template>
<script setup>
import {onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import MeetingForm from './MeetingForm.vue'
import MeetingActualForm from './MeetingActualForm.vue'
import MeetingRecords from './MeetingRecords.vue'
import MeetingHelp from './MeetingHelp.vue'
import {meetingList,meetingDetail,respondMeeting,readMeetingReceipts,updateMeetingStatus} from '@/api/meetings'
import {meetingCountdown} from '@/utils/meetingTime'
import {formatBusinessDateTime,businessDateTimeInputValue} from '@/utils/dateTime'
const props=defineProps({initialId:{type:String,default:''}})
const period=ref('day'),anchor=ref(businessDateTimeInputValue().slice(0,10))
const rows=ref([]),total=ref(0),page=ref(1),keyword=ref(''),loading=ref(false),error=ref(''),createVisible=ref(false),currentTime=ref(Date.now())
const detail=ref(null),detailVisible=ref(false),detailLoading=ref(false),detailError=ref(''),responding=ref(false),reading=ref(false),receiptForm=ref(),response=reactive({response:'',reason:''})
const statusLabels={pending:'待开始',in_progress:'进行中',ended:'已结束',cancelled:'已取消'},statusSaving=ref('')
async function changeStatus(row,status){if(statusSaving.value||row.status===status)return;statusSaving.value=row.id;try{const changed=await updateMeetingStatus(row.id,{status,version:row.status_version});if(changed.server_now){clockOffset=Date.parse(changed.server_now)-Date.now();currentTime.value=Date.now()+clockOffset}row.status=changed.status;row.status_version=changed.status_version;row.status_started_at=changed.status_started_at;if(detail.value?.id===row.id)detail.value=changed;window.dispatchEvent(new Event('meetings-changed'));ElMessage.success('会议状态已调整为'+statusLabels[status]);load()}catch(e){ElMessage.error(e.detail||'状态调整失败，请刷新后重试');load()}finally{statusSaving.value=''}}
const responseLabels={pending:'待回执',attending:'可以参加',declined:'不能参加'}
const recordsRef=ref(null)
const actualVisible=ref(false)
const helpVisible=ref(false)
const receiptRules={response:[{required:true,message:'请选择是否参加',trigger:'change'}],reason:[{validator:(_r,v,done)=>done(response.response!=='declined'||v.trim()?undefined:new Error('请说明不能参加的事由')),trigger:'blur'}]}
function associationText(row){const a=row.association||{};return [a.project&&`${a.project.project_type} · ${a.project.order_no} · ${a.project.project_name}`,a.department_names?.join('、'),a.clients?.map(c=>c.name).join('、'),a.task_name].filter(Boolean).join('；')||'未关联项目/客户'}
let clockOffset=0,sequence=0,controller,timer,tick,detailSequence=0
async function load(){controller?.abort();controller=new AbortController();const id=++sequence,sent=Date.now();loading.value=true;error.value='';try{const data=await meetingList({keyword:keyword.value,page:page.value,page_size:10,period:period.value,anchor:anchor.value},controller.signal);if(id===sequence){if(data.server_now){clockOffset=Date.parse(data.server_now)-(sent+Date.now())/2;currentTime.value=Date.now()+clockOffset}rows.value=data.items;total.value=data.total}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'会议安排加载失败，请重试'}finally{if(id===sequence)loading.value=false}}
function query(){clearTimeout(timer);page.value=1;load()}
function reset(){keyword.value='';period.value='day';anchor.value=businessDateTimeInputValue().slice(0,10);query()}
watch(keyword,value=>{clearTimeout(timer);controller?.abort();sequence++;loading.value=false;if(!value)query();else timer=setTimeout(query,400)})
async function openDetail(id){const version=++detailSequence;detailError.value='';detailLoading.value=true;try{const data=await meetingDetail(id);if(version!==detailSequence)return;detail.value=data;Object.assign(response,{response:data.my_response==='pending'?'':data.my_response||'',reason:data.my_reason||''});detailVisible.value=true}catch(e){detailError.value=e.detail||'会议回执读取失败';ElMessage.error(detailError.value)}finally{if(version===detailSequence)detailLoading.value=false}}
async function respond(){if(responding.value)return;try{await receiptForm.value.validate()}catch{return}responding.value=true;try{const result=await respondMeeting(detail.value.id,{...response,version:detail.value.my_version});detail.value=result;ElMessage.success('回执已提交');window.dispatchEvent(new Event('meetings-changed'));load()}catch(e){detailError.value=e.detail||'回执提交失败'}finally{responding.value=false}}
async function markReceipts(){reading.value=true;try{await readMeetingReceipts(detail.value.id,Object.fromEntries(detail.value.participants.map(p=>[p.user_id,p.response_version])));ElMessage.success('当前回执已标记已读');window.dispatchEvent(new Event('meetings-changed'));load()}catch(e){detailError.value=e.detail||'标记失败'}finally{reading.value=false}}
function saved(data){load();openDetail(data.id)}
watch([period,anchor],query)
watch(()=>props.initialId,id=>{if(id)openDetail(id)})
function focus(){load();if(detailVisible.value&&detail.value)openDetail(detail.value.id)}
onMounted(()=>{load();if(props.initialId)openDetail(props.initialId);tick=setInterval(()=>{currentTime.value=Date.now()+clockOffset},1000);window.addEventListener('focus',focus)})
onBeforeUnmount(()=>{controller?.abort();sequence++;detailSequence++;clearTimeout(timer);clearInterval(tick);window.removeEventListener('focus',focus)})
</script>
<style scoped>.meeting-period{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px}.meeting-period span{color:#64748b;font-size:13px}.meeting-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.meeting-toolbar h3,.meeting-toolbar h4{margin:0 auto 0 0}.meeting-toolbar .el-input{max-width:300px}.meeting-red{color:#dc2626;font-weight:600}.meeting-details{max-height:560px;overflow-y:auto;overflow-wrap:anywhere;white-space:pre-wrap}.meeting-note{white-space:pre-wrap;overflow-wrap:anywhere}.el-pagination{margin-top:12px;justify-content:flex-end;overflow-x:auto}</style>
<style>.meeting-receipt-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.meeting-receipt-dialog .el-dialog__header,.meeting-receipt-dialog .el-dialog__footer{flex-shrink:0}.meeting-receipt-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.meeting-receipt-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
