<template>
  <DraggableFormDialog v-model="reminderVisible" title="状态汇报提醒" width="min(460px, calc(100vw - 32px))" append-to-body>
    <p>请汇报现在的工作/项目状态</p>
    <template #footer><el-button @click="reminderVisible=false">稍后填写</el-button><el-button type="primary" @click="enterReport">进入状态汇报</el-button></template>
  </DraggableFormDialog>
  <AnnotationWorkStatusDialog v-if="loaded" v-model="visible" :request="request" />
</template>
<script setup>
import {defineAsyncComponent, onBeforeUnmount, onMounted, ref} from 'vue'
import {claimAnnotationWorkReminder} from '@/api/projectArrangements'
const AnnotationWorkStatusDialog=defineAsyncComponent(()=>import('./AnnotationWorkStatusDialog.vue'))
const loaded=ref(false),visible=ref(false),request=ref({}),reminderVisible=ref(false)
let timer,checking=false,reminderSlot=''
function open(event){request.value={...event.detail};loaded.value=true;visible.value=true}
function enterReport(){reminderVisible.value=false;open({detail:{mode:'report',slot:reminderSlot}})}
async function check(){
  if(checking||document.visibilityState!=='visible')return
  checking=true
  try{const data=await claimAnnotationWorkReminder();if(data.remind){reminderSlot=data.slot;reminderVisible.value=true}}
  catch{/* 后台提醒暂不可用时，保留手动汇报入口。 */}
  finally{checking=false}
}
onMounted(()=>{window.addEventListener('open-annotation-work-status',open);window.addEventListener('focus',check);timer=setInterval(check,30000);check()})
onBeforeUnmount(()=>{clearInterval(timer);window.removeEventListener('open-annotation-work-status',open);window.removeEventListener('focus',check)})
</script>
