<template>
  <section class="home-overtime" v-loading="loading"><h4>公司要求居家加班</h4><p>这是独立类型，无需申请，不占普通居家办公月、季度、半年及年度额度。记录实际工作时间，扣除休息及签退时确认的无效时间后计算加班。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div><el-button type="primary" :disabled="!desktop||!data.can_home_overtime_check_in" @click="mode='in';visible=true">居家加班</el-button><el-button type="primary" :disabled="!desktop||!record||!!record.check_out" @click="mode='out';visible=true">居家加班下班打卡</el-button><el-button @click="load">刷新打卡</el-button></div>
    <p v-if="record">上班：{{formatBusinessDateTime(record.check_in)}}；下班：{{formatBusinessDateTime(record.check_out)}}。</p>
    <AttendanceClockDialog v-model="visible" :mode="mode" :record="record" work-mode="company_home_overtime" />
  </section>
</template>
<script setup>
import {computed,onMounted,onBeforeUnmount,ref} from 'vue'
import {getTodayAttendance} from '@/api/attendance'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {chatClientType} from '@/utils/chatDevice'
import AttendanceClockDialog from './AttendanceClockDialog.vue'
const data=ref({}),loading=ref(false),error=ref(''),visible=ref(false),mode=ref('in'),desktop=chatClientType(navigator)==='desktop'
const record=computed(()=>data.value.home_overtime_record||(data.value.pending_previous?.shift?.overtime_only?data.value.pending_previous:null))
let alive=true,sequence=0
async function load(){const id=++sequence;loading.value=true;error.value='';try{const result=await getTodayAttendance();if(alive&&id===sequence)data.value=result}catch(e){if(alive&&id===sequence)error.value=e.detail||'读取居家加班打卡失败'}finally{if(alive&&id===sequence)loading.value=false}}
onMounted(()=>{load();window.addEventListener('focus',load);window.addEventListener('attendance-clock-changed',load)});onBeforeUnmount(()=>{alive=false;sequence++;window.removeEventListener('focus',load);window.removeEventListener('attendance-clock-changed',load)})
</script>
<style scoped>.home-overtime{border:1px solid #dbe3ec;border-radius:8px;padding:12px;margin:12px 0}.home-overtime h4{margin:0 0 8px}.home-overtime p{font-size:13px;line-height:1.8;color:#64748b}.home-overtime>div{display:flex;gap:8px;flex-wrap:wrap}</style>
