<template>
  <section class="report-feedback" data-screenshot-editor="own" @paste.capture="blockReportImages" @drop.capture="blockReportImages">
    <header><strong>逐项反馈与回复</strong><el-button link :loading="loading" @click="load">刷新沟通</el-button></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!ready" title="报告沟通表待初始化" type="warning" :closable="false" />
    <el-select v-if="targets.length" v-model="selected" filterable placeholder="选择工作项查看或回复" aria-label="沟通工作项"><el-option v-for="target in targets" :key="target.key" :value="target.key" :label="target.label" /></el-select>
    <p v-if="!targets.length" class="muted">暂无反馈。查看人可针对具体工作项发起沟通。</p>
    <template v-if="selected">
      <p class="subject">{{subject}}</p>
      <div class="messages"><article v-for="message in currentMessages" :key="message.id"><header><b>{{message.author_name}}</b><small>{{formatBusinessDateTime(message.created_at)}}</small></header><p>{{message.content}}</p></article><p v-if="!currentMessages.length" class="muted">此项暂无反馈</p></div>
      <AppForm ref="formRef" :model="draft" :rules="rules" label-position="top" @submit.prevent="send"><el-form-item label="反馈 / 回复" prop="content"><el-input v-model="draft.content" type="textarea" :rows="3" maxlength="4000" show-word-limit placeholder="围绕此项工作沟通，可多次来回回复" :disabled="sending||!ready" /></el-form-item><el-button type="primary" :loading="sending" :disabled="!ready" @click="send">发送{{currentMessages.length?'回复':'反馈'}}</el-button></AppForm>
    </template>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {getReportFeedback,addReportFeedback} from '@/api/tasks'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {blockReportImages} from '@/utils/workReportForm'
const props=defineProps({reportId:{type:String,required:true},workItems:{type:Array,default:()=>[]},allowNew:Boolean})
const messages=ref([]),ready=ref(true),loading=ref(false),sending=ref(false),error=ref(''),selected=ref(''),draft=reactive({content:''}),formRef=ref()
const drafts=new Map()
const rules={content:[{required:true,whitespace:true,message:'请输入反馈或回复',trigger:'blur'}]}
const targets=computed(()=>{const map=new Map();if(props.allowNew)props.workItems.forEach((item,index)=>{const key=item.display_metadata?._feedback_key||item.id;if(key)map.set(key,{key,label:`第${index+1}项 ${item.task_name||item.progress_content||item.task_type}`})});messages.value.forEach(message=>{if(!map.has(message.item_key))map.set(message.item_key,{key:message.item_key,label:message.item_snapshot.task_name||message.item_snapshot.progress_content||'原工作项'})});return [...map.values()]})
const currentMessages=computed(()=>messages.value.filter(message=>message.item_key===selected.value))
const subject=computed(()=>currentMessages.value[0]?.item_snapshot?.progress_content||props.workItems.find(item=>(item.display_metadata?._feedback_key||item.id)===selected.value)?.progress_content||'')
watch(selected,(value,previous)=>{if(previous)drafts.set(previous,draft.content);draft.content=drafts.get(value)||'';formRef.value?.clearValidate()})
let sequence=0,timer
async function load(){const current=++sequence;loading.value=true;try{const result=await getReportFeedback(props.reportId);if(current!==sequence)return;messages.value=result.items;ready.value=result.ready;error.value='';if(!selected.value&&targets.value.length)selected.value=targets.value[0].key}catch(e){if(current===sequence){messages.value=[];error.value=e.detail||'读取沟通失败'}}finally{if(current===sequence)loading.value=false}}
async function send(){if(sending.value)return;try{await formRef.value.validate()}catch{return}sending.value=true;try{await addReportFeedback(props.reportId,{item_key:selected.value,content:draft.content.trim()});draft.content='';drafts.delete(selected.value);await load()}catch(e){error.value=e.detail||'发送失败'}finally{sending.value=false}}
function focusItem(key){selected.value=key}
defineExpose({focusItem})
onMounted(()=>{load();timer=setInterval(load,20000);window.addEventListener('focus',load)})
onBeforeUnmount(()=>{sequence++;clearInterval(timer);window.removeEventListener('focus',load)})
</script>
<style scoped>.report-feedback{display:flex;flex-direction:column;gap:12px}.report-feedback>header,.messages header{display:flex;align-items:center;justify-content:space-between;gap:10px}.messages{max-height:300px;overflow-y:auto}.messages article{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:8px;padding:10px}.messages p,.subject{white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0}.messages small,.muted{color:#64748b;font-size:12px}.subject{font-size:13px;color:#475569}.report-feedback :deep(.el-select){width:100%}</style>
