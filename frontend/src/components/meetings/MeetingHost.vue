<template>
  <el-config-provider :z-index="50000">
  <div v-if="reminders.length" class="meeting-countdown-host"><el-button v-for="meeting in reminders" :key="meeting.id" type="danger" @click="open(meeting.id)">第{{meeting.number}}个会议 · {{meetingCountdown(meeting,clock)}} · {{meeting.topic}}</el-button></div>
  <DraggableFormDialog v-model="visible" title="会议安排" width="min(1450px, calc(100vw - 32px))" top="5vh" class="meeting-center-dialog" append-to-body destroy-on-close :close-on-click-modal="false"><MeetingBoard v-if="visible" :initial-id="selectedId" /><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog>
  </el-config-provider>
</template>
<script setup>
import {computed,defineAsyncComponent,onBeforeUnmount,onMounted,ref} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {meetingSummary} from '@/api/meetings'
import {subscribe} from '@/utils/realtimeSocket'
import {meetingCountdown} from '@/utils/meetingTime'
const MeetingBoard=defineAsyncComponent(()=>import('./MeetingBoard.vue'))
const emit=defineEmits(['badge-change'])
const visible=ref(false),selectedId=ref(''),upcoming=ref([]),clock=ref(Date.now());let timer,tick,unsubscribe,pending=false,offset=0,stopped=false
const reminders=computed(()=>upcoming.value.filter(row=>meetingCountdown(row,clock.value)))
function open(id=''){selectedId.value=id;visible.value=true}
function eventOpen(event){open(event.detail?.meetingId||'')}
async function refresh(){if(pending||document.hidden)return;pending=true;const sent=Date.now();try{const result=await meetingSummary();if(stopped)return;offset=Date.parse(result.server_now)-(sent+Date.now())/2;upcoming.value=result.upcoming;emit('badge-change',result.pending+result.unread_receipts+(result.unread_notifications||0))}catch{/* 入口始终保留，弹窗内显示读取错误。 */}finally{pending=false}}
function wake(){refresh()}
onMounted(()=>{unsubscribe=subscribe('notification',payload=>{if(payload?.notification?.notification_type?.startsWith('meeting_'))refresh()});refresh();timer=setInterval(refresh,30000);tick=setInterval(()=>{clock.value=Date.now()+offset},1000);window.addEventListener('meeting-open',eventOpen);window.addEventListener('meetings-changed',wake);window.addEventListener('focus',wake);document.addEventListener('visibilitychange',wake)})
onBeforeUnmount(()=>{stopped=true;unsubscribe?.();clearInterval(timer);clearInterval(tick);window.removeEventListener('meeting-open',eventOpen);window.removeEventListener('meetings-changed',wake);window.removeEventListener('focus',wake);document.removeEventListener('visibilitychange',wake)})
</script>
<style scoped>.meeting-countdown-host{position:fixed;right:24px;bottom:24px;z-index:1800;display:flex;flex-direction:column;gap:6px;max-width:min(520px,calc(100vw - 48px))}.meeting-countdown-host .el-button{margin:0;white-space:normal;height:auto;min-height:38px;text-align:left}</style>
<style>.meeting-center-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.meeting-center-dialog .el-dialog__header,.meeting-center-dialog .el-dialog__footer{flex-shrink:0}.meeting-center-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.meeting-center-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
