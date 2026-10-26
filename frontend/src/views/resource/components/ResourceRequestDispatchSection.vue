<template>
  <section class="request-dispatch">
    <el-checkbox v-model="enabled" :disabled="disabled || sending">{{ label }}</el-checkbox>
    <p class="request-dispatch__defaults">默认接收人：{{ loading ? '加载中…' : defaultNames || '未设置' }}</p>
    <div v-if="enabled" class="request-dispatch__body">
      <div class="request-dispatch__quick"><el-button v-for="p in kind==='circle' ? defaultPeople : []" :key="p.id" size="small" :disabled="disabled || sending || loading" @click="ids=[p.id]">仅选 {{ p.name }}</el-button><el-button size="small" :disabled="disabled || sending || loading" @click="loadDefaults">恢复默认名单</el-button></div>
      <el-select v-model="ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="kind==='circle' ? 2 : 3" :placeholder="kind==='post' ? '选择全公司人员（可多选）' : '选择标注项目部人员（可多选）'" :disabled="disabled || sending" :loading="loading"><el-option v-for="p in people" :key="p.id" :value="p.id" :label="p.name" /></el-select>
      <el-button type="primary" :loading="sending" :disabled="disabled || !ids.length || loading || historyLoading || records.length >= 5" @click="send">{{ records.length >= 5 ? '已达到5次上限' : records.length ? '再次发送'+label : '发送'+label }}</el-button>
      <p>接收人可在会话左侧“通知”中查看完整需求并反馈“已收到”“已处理”。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </div>
    <el-alert v-if="error && !enabled" :title="error" type="error" :closable="false" />
    <ResourceRequestSendHistory :records="records" />
  </section>
</template>
<script setup>
import { computed,ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { sendResourceRequest } from '@/api/resourceRequests'
import { createIdempotencyKey } from '@/utils/idempotency'
import ResourceRequestSendHistory from './ResourceRequestSendHistory.vue'
const props=defineProps({kind:{type:String,required:true},label:{type:String,required:true},prepare:{type:Function,required:true},disabled:Boolean,active:{type:Boolean,default:true},records:{type:Array,default:()=>[]},historyLoading:Boolean})
const emit=defineEmits(['busy','sent'])
const enabled=ref(false),ids=ref([]),people=ref([]),defaultIds=ref([]),loading=ref(false),sending=ref(false),error=ref('')
const defaultPeople=computed(()=>defaultIds.value.map(id=>people.value.find(p=>p.id===id)).filter(Boolean))
const defaultNames=computed(()=>defaultPeople.value.map(p=>p.name).join('、'))
let retryKey='',retrySignature=''
let defaultsSequence=0
async function loadDefaults(){const seq=++defaultsSequence;loading.value=true;error.value='';try{const result=await api.get(`/resource-requests/dispatch-defaults/${props.kind}`);if(seq!==defaultsSequence)return;people.value=result.users;defaultIds.value=result.user_ids;ids.value=[...defaultIds.value]}catch(e){if(seq===defaultsSequence)error.value=e.detail||e.message}finally{if(seq===defaultsSequence)loading.value=false}}
watch(()=>[props.kind,props.active],([kind,active])=>{if(active){enabled.value=false;loadDefaults()}else{defaultsSequence++;loading.value=false}},{immediate:true})

async function send(){
  if(sending.value||props.disabled||props.historyLoading||props.records.length>=5||!ids.value.length)return
  sending.value=true;emit('busy',true);error.value=''
  try{
    const saved=await props.prepare()
    if(!saved?.id)throw new Error('请先保存有效的资源需求')
    const signature=JSON.stringify([saved.id,saved.updatedAt,props.kind,[...ids.value].sort()])
    if(signature!==retrySignature){retryKey=createIdempotencyKey();retrySignature=signature}
    const result = props.kind === 'development'
      ? await sendResourceRequest(saved.id,retryKey,ids.value)
      : await api.post(`/resource-requests/${saved.id}/dispatch`,{kind:props.kind,user_ids:ids.value,idempotency_key:retryKey})
    retryKey='';retrySignature='';emit('sent',result);ElMessage.success(`${props.label}已发送，接收人将收到业务通知`)
  }catch(e){error.value=e.detail||e.message||'发送失败，请重试';emit('sent')}finally{sending.value=false;emit('busy',false)}
}
</script>
<style scoped>
.request-dispatch__quick{display:flex;flex-wrap:wrap;gap:6px;width:100%}.request-dispatch__defaults{font-size:12px;color:#64748b}.request-dispatch{border:1px solid #dbe3ef;border-radius:8px;padding:14px;margin:16px 0}.request-dispatch__body{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}.request-dispatch__body>.el-select{flex:1;min-width:220px}.request-dispatch p{width:100%;margin:0;font-size:12px;color:#64748b}.request-dispatch .el-alert{width:100%}
</style>
