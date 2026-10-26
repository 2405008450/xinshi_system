<template>
  <section class="execution-channels">
    <h4>填写处理回执</h4><p>勾选实际发布的平台／账号，填写具体处理内容、发布链接或结果。提交后自动标记为“已处理”，发送人可查看完整回执。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">刷新平台</el-button></el-alert>
    <div class="execution-tools">
      <el-button :loading="loading" @click="load">刷新平台</el-button><el-button @click="audit.open()">我的渠道操作记录</el-button>
      <template v-if="options.can_write"><BatchDeleteToolbar :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /><el-button v-if="!deleteMode" @click="editor.open()">新增渠道</el-button></template>
    </div>
    <AppForm ref="executionRef" :model="executionModel" :rules="executionRules" label-position="top"><el-form-item label="实际发布平台／账号" prop="platforms"><el-table ref="table" :data="rows" v-loading="loading" border @selection-change="selectionChanged">
      <el-table-column type="selection" width="48" :selectable="()=>!sending" />
      <el-table-column label="平台／账号"><template #default="{row}">{{ row.parent_name ? row.parent_name+' / ' : '' }}{{ row.name }}</template></el-table-column>
      <el-table-column prop="description" label="平台情况说明" show-overflow-tooltip />
      <el-table-column v-if="!deleteMode" label="操作" width="130"><template #default="{row}"><el-button v-if="options.can_write" link type="primary" @click="editor.open(row)">编辑</el-button><el-button link @click="audit.open(row)">记录</el-button></template></el-table-column>
    </el-table></el-form-item>
    <el-form-item v-if="!deleteMode" label="具体处理／发布情况" prop="content"><el-input v-model="content" type="textarea" :rows="3" maxlength="5000" show-word-limit placeholder="填写具体处理／发布情况，例如：已在所选平台发布，附帖子链接、处理结果或截图" :disabled="sending" /></el-form-item></AppForm>
    <template v-if="!deleteMode">
    <el-button type="primary" :loading="sending" :disabled="disabled || loading" @click="reply">提交处理回执</el-button><small v-if="disabled">请先确认“已收到”再回复。</small></template>
    <ChannelEditor ref="editor" :options="options" :default-user-id="options.user_id" @saved="load" /><ChannelAuditDialog ref="audit" />
  </section>
</template>
<script setup>
import {onBeforeUnmount,ref,reactive,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getDispatchChannels,sendDispatchExecution} from '@/api/resourceRequests'
import {createIdempotencyKey} from '@/utils/idempotency'
import {developmentApi as api} from '@/api/resourceDevelopment'
import {useBatchDelete} from '@/composables/useBatchDelete'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import ChannelEditor from './ChannelEditor.vue'
import ChannelAuditDialog from './ChannelAuditDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
const props=defineProps({batchId:{type:String,required:true},disabled:Boolean})
const emit=defineEmits(['replied'])
const rows=ref([]),loading=ref(false),sending=ref(false),error=ref(''),ids=ref([]),content=ref(''),table=ref(null),editor=ref(null),audit=ref(null)
const executionRef=ref()
const executionModel=reactive({get platforms(){return ids.value},get content(){return content.value}})
const executionRules={platforms:[{type:'array',required:true,min:1,message:'请选择实际发布的平台／账号',trigger:'change'}],content:[{required:true,validator:(_rule,value,done)=>String(value||'').trim()?done():done(new Error('请填写具体处理／发布情况')),trigger:'blur'}]}
const options=reactive({users:[],can_write:false,user_id:'',hierarchy_available:false})
let sequence=0,retryKey='',signature=''
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:table,deleteRow:api.removeChannel,getLabel:r=>r.name,reload:load,entityName:'渠道'})
function selectionChanged(values){ids.value=values.map(r=>r.id);handleDeleteSelectionChange(values)}
async function load(){const seq=++sequence;loading.value=true;error.value='';try{const result=await getDispatchChannels(props.batchId);if(seq!==sequence)return;rows.value=result.items;options.user_id=result.user_id;options.hierarchy_available=result.hierarchy_available;options.can_write=result.can_manage;ids.value=[];if(result.can_manage){const people=await api.channelPeople();if(seq===sequence)options.users=people}}catch(e){if(seq===sequence)error.value=e.detail||e.message}finally{if(seq===sequence)loading.value=false}}
async function reply(){if(sending.value||props.disabled||loading.value)return;if(deleteMode.value){ElMessage.warning('请先退出渠道删除管理');return}if(!await executionRef.value?.validate().catch(()=>false))return;sending.value=true;error.value='';try{const next=JSON.stringify([props.batchId,[...ids.value].sort(),content.value]);if(next!==signature){signature=next;retryKey=createIdempotencyKey()}const result=await sendDispatchExecution(props.batchId,{platform_ids:ids.value,content:content.value,idempotency_key:retryKey});retryKey='';signature='';content.value='';table.value?.clearSelection();emit('replied',result);ElMessage.success('执行回执已发送并标记已处理')}catch(e){error.value=e.detail||e.message}finally{sending.value=false}}
defineExpose({reply})
watch(()=>props.batchId,()=>{content.value='';retryKey='';signature='';load()},{immediate:true})
onBeforeUnmount(()=>{sequence++})
</script>
<style scoped>.execution-channels{border:1px solid #dbe3ef;border-radius:8px;padding:14px;margin:16px 0}.execution-channels p,.execution-channels small{font-size:12px;color:#64748b}.execution-tools{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.execution-channels .el-textarea{margin:12px 0}.execution-channels small{margin-left:8px}</style>
