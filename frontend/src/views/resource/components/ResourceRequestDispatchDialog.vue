<template>
  <DraggableFormDialog :model-value="Boolean(batchId)" :title="data?.label || '需求通知'" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="value=>!value && $emit('close')">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
      <template v-if="data">
        <h3>{{ data.snapshot.currentProjectName || data.snapshot.sourceProjectNameSnapshot }}</h3>
        <p>需求编号：{{ data.snapshot.requestNo }}　订单号：{{ data.snapshot.currentOrderNo || data.snapshot.sourceOrderNoSnapshot }}</p>
        <p>项目经理：{{ data.snapshot.projectManagers?.map(p=>p.name).join('、') || '尚未登记' }}</p>
        <h4>总体需求</h4><ScreenshotText :text="data.snapshot.requestDetail || '暂无说明'" />
        <el-table :data="data.snapshot.items" border><el-table-column label="语种"><template #default="{row}">{{ row.languageLabels?.join(' → ') || '-' }}</template></el-table-column><el-table-column prop="requiredCount" label="需求人数" width="100" /><el-table-column prop="requirementDetail" label="具体要求" /></el-table>
        <ResourceRequestVersions :model-value="data.snapshot.requestContent?.versions || []" />
        <RequestExecutionChannels v-if="data.kind==='post' && data.canRespond" ref="executionForm" :batch-id="batchId" :disabled="!mine?.receivedAt" @replied="data=$event" />
        <template v-if="data.kind==='post'"><h4>平台执行回执</h4><RequestExecutionReplies :rows="data.executionReplies || []" /><p v-if="!data.executionReplies?.length">暂无执行回执</p></template>
        <h4>接收与处理情况</h4>
        <el-table :data="data.recipients" border><el-table-column prop="name" label="人员" width="100" /><el-table-column label="已收到" min-width="130"><template #default="{row}">{{ row.receivedAt ? formatTime(row.receivedAt) : '待确认' }}</template></el-table-column><el-table-column label="已处理" min-width="130"><template #default="{row}">{{ row.processedAt ? formatTime(row.processedAt) : '待处理' }}<small v-if="data.kind==='post' && row.processedAt && !recipientReplies(row.userId).length" class="dispatch-missing-reply">历史回执未填写处理详情</small></template></el-table-column>
          <el-table-column v-if="data.kind==='post'" label="实际发布平台／账号" min-width="180"><template #default="{row}"><div v-for="reply in recipientReplies(row.userId)" :key="reply.id" class="dispatch-execution-detail"><span>{{ reply.platforms.map(p=>(p.parentName ? p.parentName+' / ' : '')+p.name).join('、') }}</span><small>{{ formatTime(reply.createdAt) }}</small></div><span v-if="!recipientReplies(row.userId).length">{{ row.processedAt ? '未登记平台' : '-' }}</span></template></el-table-column>
          <el-table-column v-if="data.kind==='post'" label="具体处理／发布情况" min-width="220"><template #default="{row}"><div v-for="reply in recipientReplies(row.userId)" :key="reply.id" class="dispatch-execution-detail"><ScreenshotText :text="reply.content || '未填写处理说明'" /></div><span v-if="!recipientReplies(row.userId).length">{{ row.processedAt ? '未填写处理说明' : '-' }}</span></template></el-table-column>
        </el-table>
      </template>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="$emit('close')">关闭</el-button>
      <template v-if="data?.canRespond">
        <el-button :loading="busy" :disabled="Boolean(mine?.receivedAt) || loading" @click="respond('received')">{{ mine?.receivedAt ? '已确认收到' : '已收到' }}</el-button>
        <el-button v-if="data.kind==='post'" type="primary" :disabled="!mine?.receivedAt || loading" @click="executionForm?.reply()">{{ mine?.processedAt ? '补充处理回执' : '提交处理回执' }}</el-button>
        <el-button v-else type="primary" :loading="busy" :disabled="!mine?.receivedAt || Boolean(mine?.processedAt) || loading" @click="respond('processed')">{{ mine?.processedAt ? '已确认处理' : '已处理' }}</el-button>
      </template>
    </template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import RequestExecutionChannels from './RequestExecutionChannels.vue'
import RequestExecutionReplies from './RequestExecutionReplies.vue'
import ResourceRequestVersions from './ResourceRequestVersions.vue'
import { getResourceDispatch, respondResourceDispatch } from '@/api/resourceRequests'
import { formatBusinessDateTime as formatTime } from '@/utils/dateTime'
const props=defineProps({batchId:{type:String,default:''}})
defineEmits(['close'])
const data=ref(null),loading=ref(false),busy=ref(false),error=ref('')
const executionForm=ref()
const repliesByUser=computed(()=>{const result=new Map();for(const reply of data.value?.executionReplies || []){if(!result.has(reply.userId))result.set(reply.userId,[]);result.get(reply.userId).push(reply)}return result})
const recipientReplies=id=>repliesByUser.value.get(id)||[]
const mine=computed(()=>data.value?.recipients.find(p=>p.userId===localStorage.getItem('user_id')))
let sequence=0
async function load(){const seq=++sequence;data.value=null;loading.value=true;error.value='';try{const value=await getResourceDispatch(props.batchId);if(seq===sequence)data.value=value}catch(e){if(seq===sequence)error.value=e.detail||e.message}finally{if(seq===sequence)loading.value=false}}
async function respond(status){if(busy.value)return;busy.value=true;error.value='';try{data.value=await respondResourceDispatch(props.batchId,status)}catch(e){error.value=e.detail||e.message}finally{busy.value=false}}
watch(()=>props.batchId,value=>{if(value)load();else{sequence++;data.value=null}},{immediate:true})
</script>
<style scoped>
.dispatch-execution-detail{white-space:normal;overflow-wrap:anywhere;padding:6px 0}.dispatch-execution-detail+.dispatch-execution-detail{border-top:1px solid #e2e8f0}.dispatch-execution-detail small,.dispatch-missing-reply{display:block;color:#64748b;font-size:12px}
</style>
