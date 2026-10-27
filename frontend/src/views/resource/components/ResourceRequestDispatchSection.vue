<template>
  <section class="request-dispatch" data-dialog-field-search-group :data-dialog-field-search-group-title="label">
    <el-checkbox v-model="enabled" :disabled="disabled || sending">{{ label }}</el-checkbox>
    <el-form-item label="说明" :prop="`requestContent.dispatchNotes.${kind}`" :data-dialog-field-search-aliases="`${label}说明`" class="request-dispatch__note">
      <el-input v-model="note" type="textarea" :rows="3" maxlength="10000" show-word-limit :aria-label="`${label}说明`" placeholder="可填写补充说明，也可留空" :disabled="disabled || sending" />
    </el-form-item>
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
    <el-button v-if="records.some(item=>!item.cancellation)" type="danger" plain :loading="sending" :disabled="cancelDisabled || historyLoading || sending" @click="cancel">取消{{ label }}</el-button>
  </section>
</template>
<script setup>
import { computed,ref,watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { sendResourceRequest, cancelResourceDispatches } from '@/api/resourceRequests'
import { createIdempotencyKey } from '@/utils/idempotency'
import ResourceRequestSendHistory from './ResourceRequestSendHistory.vue'
const props=defineProps({modelValue:{type:String,default:''},requestId:String,cancelDisabled:Boolean,kind:{type:String,required:true},label:{type:String,required:true},prepare:{type:Function,required:true},disabled:Boolean,active:{type:Boolean,default:true},records:{type:Array,default:()=>[]},historyLoading:Boolean})
const emit=defineEmits(['update:modelValue','busy','sent','cancel'])
const note=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const enabled=ref(false),ids=ref([]),people=ref([]),defaultIds=ref([]),loading=ref(false),sending=ref(false),error=ref('')
const defaultPeople=computed(()=>defaultIds.value.map(id=>people.value.find(p=>p.id===id)).filter(Boolean))
const defaultNames=computed(()=>defaultPeople.value.map(p=>p.name).join('、'))
let retryKey='',retrySignature=''
let defaultsSequence=0
async function cancel(){
  if(sending.value || props.cancelDisabled || props.historyLoading)return
  if(props.kind==='development'){emit('cancel');return}
  if(!props.requestId)return
  try{await ElMessageBox.confirm(`取消所有尚未取消的${props.label}发送记录，并通知原接收人确认收到。是否继续？`,'取消需求通知',{type:'warning',confirmButtonText:'确认取消',cancelButtonText:'返回'})}catch{return}
  sending.value=true;emit('busy',true);error.value=''
  try{await cancelResourceDispatches(props.requestId,props.kind);ElMessage.success('已发送取消通知，接收人确认后你将收到回执通知')}
  catch(e){error.value=e.detail||e.message||'取消失败，请重试'}
  finally{emit('sent');sending.value=false;emit('busy',false)}
}
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
.request-dispatch__note{margin-top:12px}
</style>
