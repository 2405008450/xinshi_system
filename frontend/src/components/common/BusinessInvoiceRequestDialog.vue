<template>
  <DraggableFormDialog :model-value="modelValue" class="business-invoice-request" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="开票需求／发票回执" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="busy">
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <template v-if="preview&&!request">
        <p>{{preview.client_name}} · {{preview.month}}；接收人：{{preview.recipients.map(row=>row.full_name||row.name||row.username).join('、')||'尚未配置'}}</p>
        <AppForm :model="draft" label-position="top" data-auto-draft="off">
          <el-form-item label="开票主体"><el-select v-model="draft.subject_key"><el-option v-for="row in preview.subjects" :key="row.key" :value="row.key" :label="row.title||row.company||row.name||row.key" /></el-select></el-form-item>
          <el-form-item label="发票类型"><el-select v-model="draft.invoice_type"><el-option v-for="row in types" :key="row.value" v-bind="row" /></el-select></el-form-item>
          <el-form-item v-if="draft.invoice_type.endsWith('_special')" label="税率"><el-select v-model="draft.tax_rate"><el-option v-for="rate in draft.subject_key==='guangzhou'?[6]:[1,3]" :key="rate" :value="rate" :label="rate+'%'" /></el-select></el-form-item>
          <el-form-item v-for="row in buyers" :key="row.buyer_group" :label="row.project_name+' · 客户开票信息'"><el-select v-model="draft.buyer_choices[row.buyer_group]"><el-option v-for="(buyer,index) in row.buyer_options" :key="index" :value="index" :label="buyer.title||'未填写抬头'" /></el-select></el-form-item>
          <el-form-item label="需求说明"><el-input v-model="draft.note" type="textarea" maxlength="2000" /></el-form-item>
        </AppForm>
        <el-table :data="preview.projects" border max-height="280"><el-table-column prop="order_no" label="订单号" min-width="150" /><el-table-column prop="project_name" label="项目名称" min-width="240" /><el-table-column label="含税开票金额" min-width="170"><template #default="{row}">{{money(row.totals)}}</template></el-table-column></el-table>
        <p>发送后保留本次主体、客户开票信息及金额快照；接收人可发送回执并登记发票附件。</p>
      </template>
      <template v-if="request">
        <p>{{request.snapshot.client_name}} · {{request.snapshot.month}} · {{request.snapshot.sender}} · {{formatBusinessDateTime(request.created_at)}}</p>
        <p>开票主体：{{request.snapshot.subject.title||request.snapshot.subject.name}}；{{request.snapshot.invoice_type}}；{{request.completed_by?'已完成开票':'办理中'}}</p>
        <el-table :data="request.snapshot.projects" border><el-table-column prop="order_no" label="订单号" min-width="150" /><el-table-column prop="project_name" label="项目名称" min-width="200" /><el-table-column label="开票金额" min-width="140"><template #default="{row}">{{money(row.totals)}}</template></el-table-column><el-table-column label="客户抬头" min-width="180"><template #default="{row}">{{row.buyer.title}}</template></el-table-column></el-table>
        <AppForm v-if="request.is_recipient" :model="upload" label-position="top" data-auto-draft="off">
          <el-form-item label="登记项目发票"><el-select v-model="upload.project_id"><el-option v-for="row in request.snapshot.projects" :key="row.id" :value="row.id" :label="row.order_no+' · '+row.project_name" /></el-select></el-form-item>
          <el-form-item label="发票附件"><ScreenshotInput v-model="upload.proofs" type="textarea" allow-invoice-files :invoice-order-no="request.snapshot.projects.find(row=>row.id===upload.project_id)?.order_no" @uploading-change="uploading=$event" /></el-form-item>
          <el-button :disabled="uploading||!upload.project_id" @click="act('upload',upload)">登记已开票及附件</el-button>
        </AppForm>
        <p>收到回执：{{Object.values(request.request_receipts).map(row=>row.name+' '+formatBusinessDateTime(row.at)).join('；')||'未收到'}}</p>
      </template>
      <el-table v-if="!request&&history.length" :data="history" max-height="220"><el-table-column label="历史需求"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}} · {{row.completed_by?'已完成':'办理中'}}</template></el-table-column><el-table-column label="查看" width="90"><template #default="{row}"><el-button link @click="request=row">查看</el-button></template></el-table-column></el-table>
    </div>
    <template #footer><el-button :disabled="busy||uploading" @click="emit('update:modelValue',false)">关闭</el-button><el-button v-if="request&&!requestId" @click="request=null">返回发送需求</el-button><el-button v-if="!request" type="primary" :disabled="busy||!preview?.projects.length||!preview?.recipients.length" @click="send">发送开票需求</el-button><el-button v-if="request?.is_recipient" :disabled="busy" @click="act('receive')">发送收到回执</el-button><el-button v-if="request?.is_recipient" type="primary" :disabled="busy" @click="act('complete')">开票完成</el-button><el-button v-if="request?.is_sender&&request.completed_by" :disabled="busy" @click="act('receive_completion')">确认收到发票</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import api from '@/api'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import ScreenshotInput from './ScreenshotInput.vue'
const props=defineProps({modelValue:Boolean,projectId:String,requestId:String,module:{type:String,default:'interpretation'}}),emit=defineEmits(['update:modelValue','saved'])
const body=ref(),busy=ref(false),uploading=ref(false),error=ref(''),preview=ref(null),request=ref(null),history=ref([])
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const draft=reactive({subject_key:'guangzhou',invoice_type:'electronic_normal',tax_rate:6,buyer_choices:{},note:''}),upload=reactive({project_id:'',proofs:'',invoice_status:'issued'})
const types=[{value:'electronic_normal',label:'电子普通发票'},{value:'electronic_special',label:'电子专用发票'},{value:'paper_normal',label:'纸质普通发票'},{value:'paper_special',label:'纸质专用发票'}]
const buyers=computed(()=>[...new Map((preview.value?.projects||[]).map(row=>[row.buyer_group,row])).values()])
const money=value=>Object.entries(value||{}).map(([code,total])=>code+' '+total).join(' / ')||'含税金额待补'
const path='/interpretation-customer-finance/invoice-requests'
let key
async function perform(fn){busy.value=true;error.value='';try{await fn()}catch(e){error.value=getLocalizedErrorMessage(e,'开票需求操作失败')}finally{busy.value=false}}
async function send(){await perform(async()=>{request.value=await api.post(`${path}/project/${props.projectId}/send`,{...draft,tax_rate:draft.invoice_type.endsWith('_special')?draft.tax_rate:null,settings_revision:preview.value.settings_revision,expected_user_ids:preview.value.recipients.map(row=>row.id),project_revisions:Object.fromEntries(preview.value.projects.map(row=>[row.id,row.revision])),idempotency_key:key},{params:{module:props.module}});emit('saved')})}
async function act(action,data={}){await perform(async()=>{request.value=await api.post(`${path}/request/${request.value.id}`,{revision:request.value.revision,action,...data},{params:{module:request.value.module||props.module}});emit('saved')})}
watch(()=>[props.modelValue,props.projectId,props.requestId],async([open])=>{if(!open)return;clearFieldSearch();request.value=null;preview.value=null;history.value=[];key=crypto.randomUUID();await perform(async()=>{if(props.requestId){request.value=await api.get(`${path}/request/${props.requestId}`);return}const [data,old]=await Promise.all([api.get(`${path}/project/${props.projectId}/preview`,{params:{module:props.module}}),api.get(`${path}/project/${props.projectId}/history`,{params:{module:props.module}})]);preview.value=data;history.value=old.items;draft.buyer_choices=Object.fromEntries(data.projects.map(row=>[row.buyer_group,0]));draft.note=''})},{immediate:true})
</script>
<style>.business-invoice-request{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.business-invoice-request>.el-dialog__header,.business-invoice-request>.el-dialog__footer{flex:none}.business-invoice-request>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.business-invoice-request>.el-dialog__footer{border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}</style>
