<template>
  <section class="requirement-dispatch-panel">
    <div class="dispatch-heading"><strong>项目经理安排及回执</strong><el-button :loading="loading" :disabled="sending" @click="load">刷新安排</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="dispatch-history"><el-empty v-if="!items.length&&!loading&&!error" description="暂无项目经理安排" :image-size="40" /><TranslationRequirementDispatchRecord v-for="item in items" :key="item.id" :item="item" /></div>
    <el-pagination v-if="total>10" v-model:current-page="page" :total="total" :page-size="10" layout="prev,pager,next,total" small @current-change="load" />
    <details v-if="changesTotal" class="settings-history"><summary>项目状态 / 客户回稿时间调整记录（{{changesTotal}}）</summary><article v-for="entry in changes" :key="entry.id"><strong>{{entry.actor_name}}</strong> · {{time(entry.created_at)}}<p>项目状态：{{status(entry.before.project_status)}} → {{status(entry.after.project_status)}}</p><p>客户回稿时间：{{time(entry.before.customer_deadline_time)}} → {{time(entry.after.customer_deadline_time)}}</p></article><el-pagination v-if="changesTotal>10" v-model:current-page="changePage" :total="changesTotal" :page-size="10" layout="prev,pager,next,total" small @current-change="load" /></details>
    <DraggableFormDialog v-model="composeVisible" title="项目经理安排" width="min(760px, calc(100vw - 32px))" top="5vh" append-to-body class="requirement-dispatch-compose" :close-on-click-modal="false" :close-on-press-escape="!sending" :before-close="done=>{if(!sending)done()}">
      <p>客户回稿时间：{{time(customerDeadlineTime)}}</p><p>安排内容与回执共同可见。原文、译文若有修改，请先保存需求。</p>
      <details v-if="sourceRequirement"><summary>本次关联的已保存简单需求</summary><TranslationSimpleRequirementRecord :item="sourceRequirement" :show-receipts="false" /></details>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="被安排人（笔译项目部，可多选）" prop="recipient_ids"><el-select v-model="form.recipient_ids" multiple filterable placeholder="请选择笔译项目部人员" :disabled="sending"><el-option v-for="person in people" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item><el-form-item label="安排具体内容（共同可见）" prop="content"><el-input v-model="form.content" type="textarea" :rows="5" maxlength="10000" show-word-limit :disabled="sending" /></el-form-item></AppForm>
      <template #footer><el-button :disabled="sending" @click="composeVisible=false">取消</el-button><el-button type="primary" :loading="sending" @click="send">发送</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {formatBusinessDateTime as time} from '@/utils/dateTime'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import TranslationRequirementDispatchRecord from '@/components/common/TranslationRequirementDispatchRecord.vue'
import TranslationSimpleRequirementRecord from '@/components/common/TranslationSimpleRequirementRecord.vue'
const props=defineProps({projectId:String,projectUpdatedAt:[String,Date],customerDeadlineTime:String,latestRequirement:Object,people:{type:Array,default:()=>[]},canWrite:Boolean,active:Boolean,blocked:Boolean})
const loading=ref(false),sending=ref(false),error=ref(''),items=ref([]),total=ref(0),page=ref(1),changes=ref([]),changesTotal=ref(0),changePage=ref(1),composeVisible=ref(false),formRef=ref(),sourceRequirement=ref(null)
const form=reactive({recipient_ids:[],content:''}),rules={recipient_ids:[{required:true,type:'array',min:1,message:'请选择被安排人',trigger:'change'}],content:[{required:true,validator:(_r,value,done)=>String(value||'').trim()?done():done(new Error('请填写安排具体内容')),trigger:'blur'}]}
const status=value=>getProjectStatusLabel('translation',value)
let sequence=0,controller,attempt
async function load(){if(!props.active||!props.projectId)return;const request=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await api.get(`/translation-simple-requirements/projects/${props.projectId}/dispatches`,{params:{skip:(page.value-1)*10,limit:10,change_skip:(changePage.value-1)*10},signal:controller.signal});if(request!==sequence)return;items.value=data.items||[];total.value=data.total||0;changes.value=data.changes||[];changesTotal.value=data.changes_total||0}catch{if(request===sequence)error.value='安排记录加载失败，请刷新重试'}finally{if(request===sequence)loading.value=false}}
async function openCompose(){if(props.blocked||!props.canWrite||sending.value)return;sourceRequirement.value=props.latestRequirement||null;composeVisible.value=true;await nextTick();formRef.value?.clearValidate()}
async function send(){if(sending.value||!props.canWrite||!await formRef.value?.validate().catch(()=>false))return;if(sending.value)return;sending.value=true;const projectId=props.projectId,payload={content:form.content.trim(),recipient_ids:[...form.recipient_ids],requirement_id:sourceRequirement.value?.id||null,expected_updated_at:props.projectUpdatedAt||null},signature=JSON.stringify({projectId,...payload});if(attempt?.signature!==signature)attempt={signature,request_id:crypto.randomUUID()};try{await api.post(`/translation-simple-requirements/projects/${projectId}/dispatches`,{...payload,request_id:attempt.request_id});if(projectId!==props.projectId)return;composeVisible.value=false;form.content='';attempt=undefined;page.value=1;await load();ElMessage.success('安排已发送，可查看收到和已完成回执')}catch(error){ElMessage.error(error?.detail||error?.response?.data?.detail||'发送安排失败，请重试')}finally{sending.value=false}}
watch(()=>[props.active,props.projectId],()=>{sequence++;controller?.abort();if(props.active){page.value=1;changePage.value=1;load()}else loading.value=false},{immediate:true})
watch(()=>props.projectId,()=>{composeVisible.value=false;form.content='';form.recipient_ids=[];items.value=[];changes.value=[];total.value=0;changesTotal.value=0;attempt=undefined})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
defineExpose({reload:load,openCompose})
</script>
<style scoped>.requirement-dispatch-panel{margin-top:18px;border-top:1px solid var(--el-border-color-lighter);padding-top:12px}.dispatch-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.dispatch-history{max-height:360px;overflow-y:auto}.settings-history{margin:12px 0}.settings-history article{font-size:12px;padding:10px 0;border-bottom:1px solid var(--el-border-color-lighter)}.settings-history p{margin:5px 0}</style>
