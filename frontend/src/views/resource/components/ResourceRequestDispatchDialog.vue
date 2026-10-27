<template>
  <DraggableFormDialog :model-value="Boolean(batchId)" :title="data?.label || '需求通知'" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="value=>!value && $emit('close')">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
      <template v-if="data">
        <el-alert v-if="data.cancellation" :title="cancelMine?.confirmedAt ? '已确认收到取消通知' : '该需求通知已取消，请确认收到取消通知'" type="warning" :closable="false" />
        <header class="dispatch-project-header">
          <div class="dispatch-project-summary">
            <h3>{{ data.snapshot.currentProjectName || data.snapshot.sourceProjectNameSnapshot }}</h3>
            <div class="dispatch-identifiers">
              <span>需求编号：<el-popover v-if="requestId" v-model:visible="requestOpen" trigger="click" placement="left" :width="760" :z-index="detailZ" :popper-options="popoverOptions" popper-class="dispatch-request-detail-popover" title="资源需求详情（最新）" @show="loadRequest" @hide="cancelRequest">
                <template #reference><el-button link type="primary" :title="`${data.snapshot.requestNo}（点击查看需求详情）`" @click="raiseDetails">{{data.snapshot.requestNo}}</el-button></template>
                <div class="dispatch-request-detail" v-loading="requestLoading"><el-alert v-if="requestError" :title="requestError" type="warning" :closable="false"><el-button link @click="loadRequest">重新加载</el-button></el-alert><ResourceRequestDetailContent v-if="requestDetail" :request="requestDetail" /></div>
              </el-popover><span v-else>{{data.snapshot.requestNo || '-'}}</span></span>
              <span>订单号：<el-popover v-if="projectTarget" v-model:visible="projectOpen" trigger="click" placement="left" :width="760" :z-index="detailZ" :popper-options="popoverOptions" popper-class="associated-project-popover" @show="loadProject" @hide="projectLoader.cancel()">
                <template #reference><el-button link type="primary" :title="`${orderNo}（点击查看项目详情）`" @click="raiseDetails">{{orderNo}}</el-button></template>
                <AssociatedProjectDetailPanel :source-type="projectTarget.sourceType" :project-id="projectTarget.projectId" :state="projectState" title="项目详情" @retry="loadProject" @close="projectOpen=false" @enter="enterProject" />
              </el-popover><span v-else>{{orderNo}}</span></span>
            </div>
            <p>项目经理：{{ data.snapshot.projectManagers?.map(p=>p.name).join('、') || '尚未登记' }}</p>
          </div>
          <el-button v-if="canEnterChat" type="primary" :disabled="loading||busy" @click="enterChat">进入项目会话</el-button>
        </header>
        <h4>总体需求</h4><ScreenshotText :text="data.snapshot.requestDetail || '暂无说明'" />
        <el-table :data="data.snapshot.items" border><el-table-column label="语种"><template #default="{row}">{{ row.languageLabels?.join(' → ') || '-' }}</template></el-table-column><el-table-column prop="requiredCount" label="需求人数" width="100" /><el-table-column prop="requirementDetail" label="具体要求" /></el-table>
        <ResourceRequestVersions :model-value="data.snapshot.requestContent?.versions || []" />
        <ResourceRequestDispatchNotes :notes="data.snapshot.requestContent?.dispatchNotes || {}" :kind="data.kind" />
        <RequestExecutionChannels v-if="data.kind==='post' && data.canRespond && !data.cancellation" ref="executionForm" :batch-id="batchId" :disabled="!mine?.receivedAt" @replied="data=$event" />
        <template v-if="data.kind==='post'"><h4>平台执行回执</h4><RequestExecutionReplies :rows="data.executionReplies || []" /><p v-if="!data.executionReplies?.length">暂无执行回执</p></template>
        <h4>接收与处理情况</h4>
        <el-table :data="data.recipients" border><el-table-column prop="name" label="人员" width="100" /><el-table-column label="已收到" min-width="130"><template #default="{row}">{{ row.receivedAt ? formatTime(row.receivedAt) : '待确认' }}</template></el-table-column><el-table-column label="已处理" min-width="130"><template #default="{row}">{{ row.processedAt ? formatTime(row.processedAt) : '待处理' }}<small v-if="data.kind==='post' && row.processedAt && !recipientReplies(row.userId).length" class="dispatch-missing-reply">历史回执未填写处理详情</small></template></el-table-column>
          <el-table-column v-if="data.kind==='post'" label="实际发布平台／账号" min-width="180"><template #default="{row}"><div v-for="reply in recipientReplies(row.userId)" :key="reply.id" class="dispatch-execution-detail"><span>{{ reply.platforms.map(p=>(p.parentName ? p.parentName+' / ' : '')+p.name).join('、') }}</span><small>{{ formatTime(reply.createdAt) }}</small></div><span v-if="!recipientReplies(row.userId).length">{{ row.processedAt ? '未登记平台' : '-' }}</span></template></el-table-column>
          <el-table-column v-if="data.kind==='post'" label="具体处理／发布情况" min-width="220"><template #default="{row}"><div v-for="reply in recipientReplies(row.userId)" :key="reply.id" class="dispatch-execution-detail"><ScreenshotText :text="reply.content || '未填写处理说明'" /></div><span v-if="!recipientReplies(row.userId).length">{{ row.processedAt ? '未填写处理说明' : '-' }}</span></template></el-table-column>
        </el-table>
        <template v-if="data.cancellation"><h4>取消通知确认记录</h4><p>{{ data.cancellation.cancelledBy }} · {{ formatTime(data.cancellation.cancelledAt) }}</p><el-table :data="data.cancellation.recipients" border><el-table-column prop="name" label="人员" /><el-table-column label="确认收到取消通知"><template #default="{row}">{{ row.confirmedAt ? formatTime(row.confirmedAt) : '待确认' }}</template></el-table-column></el-table></template>
      </template>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="$emit('close')">关闭</el-button>
      <el-button v-if="cancelMine" type="primary" :loading="busy" :disabled="!!cancelMine.confirmedAt || loading" @click="respond('cancel_received')">{{ cancelMine.confirmedAt ? '已确认收到取消通知' : '确认收到取消通知' }}</el-button>
      <template v-if="data?.canRespond && !data.cancellation">
        <el-button :loading="busy" :disabled="Boolean(mine?.receivedAt) || loading" @click="respond('received')">{{ mine?.receivedAt ? '已确认收到' : '已收到' }}</el-button>
        <el-button v-if="data.kind==='post'" type="primary" :disabled="!mine?.receivedAt || loading" @click="executionForm?.reply()">{{ mine?.processedAt ? '补充处理回执' : '提交处理回执' }}</el-button>
        <el-button v-else type="primary" :loading="busy" :disabled="!mine?.receivedAt || Boolean(mine?.processedAt) || loading" @click="respond('processed')">{{ mine?.processedAt ? '已确认处理' : '已处理' }}</el-button>
      </template>
    </template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, ref, watch, reactive, onBeforeUnmount, nextTick, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import RequestExecutionChannels from './RequestExecutionChannels.vue'
import RequestExecutionReplies from './RequestExecutionReplies.vue'
import ResourceRequestVersions from './ResourceRequestVersions.vue'
import ResourceRequestDispatchNotes from './ResourceRequestDispatchNotes.vue'
import ResourceRequestDetailContent from './ResourceRequestDetailContent.vue'
import { getResourceDispatch, respondResourceDispatch, getResourceRequest } from '@/api/resourceRequests'
import { associatedProject, createAssociatedProjectLoader } from '@/utils/associatedProjectDetail'
import { fetchAssociatedProject } from '@/api/associatedProjectDetail'
import { arrangementProjectRoute } from '@/utils/resourceArrangements'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { formatBusinessDateTime as formatTime } from '@/utils/dateTime'
const props=defineProps({batchId:{type:String,default:''}})
const emit=defineEmits(['close'])
const data=ref(null),loading=ref(false),busy=ref(false),error=ref('')
const AssociatedProjectDetailPanel=defineAsyncComponent(()=>import('@/components/project/AssociatedProjectDetailPanel.vue'))
const router=useRouter(),dock=useProjectChatDock()
const projectTarget=computed(()=>associatedProject(data.value?.snapshot))
const requestId=computed(()=>data.value?.snapshot?.id)
const orderNo=computed(()=>data.value?.snapshot?.currentOrderNo||data.value?.snapshot?.sourceOrderNoSnapshot||'-')
const canEnterChat=computed(()=>['annotation','translation'].includes(projectTarget.value?.sourceType))
const projectOpen=ref(false),requestOpen=ref(false),detailZ=ref(2100),requestDetail=ref(null),requestLoading=ref(false),requestError=ref('')
const projectState=reactive({loading:false,detail:null,error:'',extras:{}})
const projectLoader=createAssociatedProjectLoader(fetchAssociatedProject,value=>Object.assign(projectState,value))
const popoverOptions={modifiers:[{name:'preventOverflow',options:{rootBoundary:'viewport',altAxis:true,tether:false,padding:16}}]}
let requestSequence=0,requestController
function raiseDetails(event){detailZ.value=chatOverlayZIndex(event.currentTarget)}
function cancelRequest(){requestSequence++;requestController?.abort();requestLoading.value=false}
function closeDetails(){projectOpen.value=false;requestOpen.value=false;projectLoader.cancel();cancelRequest();requestDetail.value=null}
function loadProject(){requestOpen.value=false;if(projectTarget.value)projectLoader.load(projectTarget.value)}
async function loadRequest(){projectOpen.value=false;cancelRequest();const current=requestSequence;requestController=new AbortController();requestLoading.value=true;requestError.value='';requestDetail.value=null;try{const value=await getResourceRequest(requestId.value,{signal:requestController.signal});if(current===requestSequence)requestDetail.value=value}catch(e){if(current===requestSequence&&e.code!=='ERR_CANCELED')requestError.value=e.detail||e.message||'读取需求详情失败'}finally{if(current===requestSequence)requestLoading.value=false}}
function enterProject(){if(!projectTarget.value)return;const target=projectTarget.value;closeDetails();emit('close');router.push(arrangementProjectRoute({source_type:target.sourceType,project_id:target.projectId}))}
async function enterChat(){if(!canEnterChat.value)return;const target=projectTarget.value;const session={projectId:target.projectId,projectType:target.sourceType,title:data.value.snapshot.currentProjectName||data.value.snapshot.sourceProjectNameSnapshot,subtitle:orderNo.value,projectStatus:data.value.snapshot.currentProjectStatus||data.value.snapshot.sourceStatusSnapshot||'',syncSidebar:true};closeDetails();emit('close');await nextTick();dock.openChat(session)}
const executionForm=ref()
const repliesByUser=computed(()=>{const result=new Map();for(const reply of data.value?.executionReplies || []){if(!result.has(reply.userId))result.set(reply.userId,[]);result.get(reply.userId).push(reply)}return result})
const recipientReplies=id=>repliesByUser.value.get(id)||[]
const mine=computed(()=>data.value?.recipients.find(p=>p.userId===localStorage.getItem('user_id')))
const cancelMine=computed(()=>data.value?.cancellation?.recipients.find(p=>p.userId===localStorage.getItem('user_id')))
let sequence=0
async function load(){closeDetails();const seq=++sequence;data.value=null;loading.value=true;error.value='';try{const value=await getResourceDispatch(props.batchId);if(seq===sequence)data.value=value}catch(e){if(seq===sequence)error.value=e.detail||e.message}finally{if(seq===sequence)loading.value=false}}
async function respond(status){if(busy.value)return;busy.value=true;error.value='';try{await respondResourceDispatch(status==='cancel_received' ? data.value.cancellation.id : props.batchId,status);await load()}catch(e){error.value=e.detail||e.message}finally{busy.value=false}}
watch(()=>props.batchId,value=>{if(value)load();else{closeDetails();sequence++;data.value=null}},{immediate:true})
onBeforeUnmount(()=>{sequence++;closeDetails()})
</script>
<style scoped>
.dispatch-execution-detail{white-space:normal;overflow-wrap:anywhere;padding:6px 0}.dispatch-execution-detail+.dispatch-execution-detail{border-top:1px solid #e2e8f0}.dispatch-execution-detail small,.dispatch-missing-reply{display:block;color:#64748b;font-size:12px}
.dispatch-project-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin:16px 0}.dispatch-project-summary{min-width:0;overflow-wrap:anywhere}.dispatch-project-summary h3{margin:0 0 4px}.dispatch-project-summary p{margin:4px 0}.dispatch-identifiers{display:flex;align-items:center;gap:8px 20px;flex-wrap:wrap}.dispatch-project-header>.el-button{flex-shrink:0}.dispatch-request-detail{max-height:min(560px,calc(100vh - 140px));overflow-y:auto;overflow-wrap:anywhere}@media(max-width:600px){.dispatch-project-header{flex-wrap:wrap;gap:10px}}
</style>
<style>.dispatch-request-detail-popover{width:min(760px,calc(100vw - 32px))!important;max-width:calc(100vw - 32px)}</style>
