<template>
  <DraggableFormDialog v-model="visible" :title="dispatchId?'项目经理安排 · 收到及已完成回执':'简单需求 · 收到及已完成回执'" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="done=>{if(!saving)done()}" @closed="emit('close')">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div v-loading="loading"><template v-if="item"><p class="requirement-project">{{item.order_no}} · {{item.project_name}}</p><p>项目当前状态：{{status(item.current_status)}}</p><p>客户回稿时间：{{time(dispatchId?item.current_customer_deadline_time:item.customer_deadline_time)}}</p><TranslationRequirementDispatchRecord v-if="dispatchId" :item="item" /><TranslationSimpleRequirementRecord v-else :item="item" />
      <AppForm v-if="canReply||canComplete" ref="formRef" :model="form" :rules="rules" label-position="top" class="requirement-reply"><el-form-item v-if="canReply" label="收到回复" prop="reply"><el-input v-model="form.reply" type="textarea" :rows="2" maxlength="500" show-word-limit :disabled="saving" /></el-form-item><el-form-item v-if="canComplete" label="已完成回执" prop="completion_reply"><el-input v-model="form.completion_reply" type="textarea" :rows="2" maxlength="500" show-word-limit :disabled="saving" /></el-form-item></AppForm>
    </template></div>
    <template #footer><el-button :loading="loading" :disabled="saving" @click="load">刷新</el-button><el-button :disabled="saving" @click="visible=false">关闭</el-button><el-button v-if="canReply" type="primary" :loading="saving" @click="respond('received')">回复收到</el-button><el-button v-if="item?.is_recipient&&!item.my_completed_at" type="primary" :loading="saving" :disabled="!canComplete||loading" :title="canComplete?'发送已完成回执':'请先回复收到'" @click="respond('completed')">回复已完成</el-button><el-tag v-if="item?.my_completed_at" type="success">已完成回执已发送</el-tag></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {formatBusinessDateTime as time} from '@/utils/dateTime'
import TranslationSimpleRequirementRecord from './TranslationSimpleRequirementRecord.vue'
import TranslationRequirementDispatchRecord from './TranslationRequirementDispatchRecord.vue'
const props=defineProps({requirementId:{type:String,default:''},dispatchId:{type:String,default:''}}),emit=defineEmits(['close'])
const visible=ref(true),loading=ref(false),saving=ref(false),error=ref(''),item=ref(),formRef=ref(),form=reactive({reply:'收到',completion_reply:'已完成'})
const required=(_r,value,done)=>String(value||'').trim()?done():done(new Error('请填写回执内容'))
const rules={reply:[{required:true,validator:required,trigger:'blur'}],completion_reply:[{required:true,validator:required,trigger:'blur'}]}
const status=value=>getProjectStatusLabel('translation',value),canReply=computed(()=>Boolean(item.value?.can_reply)),canComplete=computed(()=>Boolean(item.value?.can_complete))
const endpoint=computed(()=>props.dispatchId?`/translation-simple-requirements/dispatches/${props.dispatchId}`:`/translation-simple-requirements/${props.requirementId}`)
let sequence=0,controller
async function load(){if(!props.dispatchId&&!props.requirementId)return;const request=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await api.get(endpoint.value,{signal:controller.signal});if(request===sequence)item.value=data}catch{if(request===sequence)error.value='需求或安排加载失败，请刷新重试'}finally{if(request===sequence)loading.value=false}}
async function respond(step){if(saving.value||loading.value||!(step==='received'?canReply.value:canComplete.value)||!await formRef.value?.validate().catch(()=>false))return;if(saving.value)return;saving.value=true;const target=endpoint.value;try{const data=await api.post(`${target}/${step}`,{reply:(step==='received'?form.reply:form.completion_reply).trim()});if(target===endpoint.value){item.value=data;ElMessage.success(step==='received'?'已回复收到':'已发送已完成回执')}}catch(error){ElMessage.error(error?.detail||'回执保存失败，请重试')}finally{saving.value=false}}
watch(()=>[props.requirementId,props.dispatchId],()=>{item.value=undefined;Object.assign(form,{reply:'收到',completion_reply:'已完成'});load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.requirement-project{font-weight:600;overflow-wrap:anywhere}.requirement-reply{margin-top:16px}</style>
