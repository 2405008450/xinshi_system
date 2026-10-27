<template>
  <div class="progress-record-actions">
    <template v-if="!deleted">
      <el-button link type="primary" size="small" :disabled="disabled || saving || !editingReady" :title="editingReady ? '编辑本条记录' : '等待进度编辑留痕初始化'" @click="open('edit')">编辑</el-button>
      <el-button link type="danger" size="small" :disabled="disabled || saving" @click="open('delete')">删除</el-button>
    </template>
    <el-popover trigger="click" placement="left" :width="760" popper-class="progress-record-audits" @show="loadAudits">
      <template #reference><el-button link size="small">查看编辑 / 删除记录</el-button></template>
      <div class="progress-record-audits-body" v-loading="loading">
        <h4>本条进度的编辑 / 删除记录</h4>
        <el-alert v-if="auditError" :title="auditError" type="error" :closable="false"><el-button link @click="loadAudits">重试</el-button></el-alert>
        <el-empty v-else-if="!loading && !audits.length" description="暂无编辑或删除记录" :image-size="50" />
        <el-descriptions v-for="item in audits" :key="item.id" :column="2" border size="small" class="record-audit-entry">
          <el-descriptions-item label="操作">{{ item.action === 'edit' ? '编辑' : '删除' }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ item.actorName }}</el-descriptions-item>
          <el-descriptions-item label="操作时间" :span="2">{{ dateTime(item.occurredAt) }}</el-descriptions-item>
          <el-descriptions-item label="原节点时间" :span="2">{{ dateTime(item.before?.effectiveOn) }}</el-descriptions-item>
          <el-descriptions-item label="原内容" :span="2"><div class="record-audit-note">{{ item.before?.changeNote || '-' }}</div></el-descriptions-item>
          <el-descriptions-item v-if="item.action === 'edit'" label="修改后时间" :span="2">{{ dateTime(item.after?.effectiveOn) }}</el-descriptions-item>
          <el-descriptions-item v-if="item.action === 'edit'" label="修改后内容" :span="2"><div class="record-audit-note">{{ item.after?.changeNote || '-' }}</div></el-descriptions-item>
          <el-descriptions-item label="原因" :span="2"><div class="record-audit-note">{{ item.reason || '-' }}</div></el-descriptions-item>
        </el-descriptions>
      </div>
    </el-popover>
    <DraggableFormDialog v-model="visible" :title="mode === 'edit' ? '编辑项目进度' : '删除项目进度'" width="min(760px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="progress-record-editor" :before-close="beforeClose" :close-on-click-modal="!saving">
      <el-alert v-if="mode === 'delete'" title="删除后保留原内容、操作人和删除原因，可在本条记录下查看。" type="warning" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving">
        <el-form-item label="节点时间" prop="effectiveOn">
          <el-date-picker v-if="mode === 'edit' && !statusNote" v-model="form.effectiveOn" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
          <ReadonlyField v-else :model-value="dateTime(record.effectiveOn)" source="auto" />
        </el-form-item>
        <el-form-item label="内容" prop="changeNote"><el-input v-if="mode === 'edit'" v-model="form.changeNote" type="textarea" :rows="6" maxlength="10000" show-word-limit /><div v-else class="record-audit-note">{{ record.changeNote }}</div></el-form-item>
        <el-form-item :label="mode === 'delete' ? '删除原因' : '修改原因（选填）'" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="2" maxlength="500" show-word-limit /></el-form-item>
      </AppForm>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button :type="mode === 'delete' ? 'danger' : 'primary'" :loading="saving" @click="save">{{ mode === 'delete' ? '确认删除' : '保存修改' }}</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { businessDateTimeInputValue, formatBusinessDateTime } from '@/utils/dateTime'
import { getProgressRecordCapabilities, getProgressRecordAudits, updateStatusHistoryProgress, deleteStatusHistoryProgress } from '@/api/annotationOps'
const props=defineProps({projectId:{type:String,required:true},record:{type:Object,required:true},disabled:Boolean})
const emit=defineEmits(['updated','busy'])
const visible=ref(false),mode=ref('edit'),saving=ref(false),error=ref(''),formRef=ref(),loading=ref(false),auditError=ref(''),audits=ref([])
const editingReady=ref(false)
const form=reactive({effectiveOn:'',changeNote:'',reason:''})
const statusNote=computed(()=>props.record.kind==='status-note')
const deleted=computed(()=>props.record.isDeleted || props.record.noteDeleted)
const dateTime=value=>formatBusinessDateTime(value)
const rules=computed(()=>({effectiveOn:[{required:true,message:'请选择节点时间',trigger:'change'}],changeNote:[{required:mode.value==='edit',validator:(_r,v,cb)=>cb(mode.value==='edit'&&!String(v||'').trim()?new Error('请填写进度内容'):undefined),trigger:'blur'}],reason:[{required:mode.value==='delete',validator:(_r,v,cb)=>cb(mode.value==='delete'&&!String(v||'').trim()?new Error('请填写删除原因'):undefined),trigger:'blur'}]}))
let controller,sequence=0
function open(action){mode.value=action;form.effectiveOn=businessDateTimeInputValue(props.record.effectiveOn);form.changeNote=props.record.changeNote||'';form.reason='';error.value='';visible.value=true}
function beforeClose(done){if(!saving.value)done()}
async function save(){
  if(saving.value||!await formRef.value?.validate().catch(()=>false))return
  saving.value=true;emit('busy',true);error.value=''
  try{
    const data={expectedUpdatedAt:props.record.updatedAt||props.record.changedAt,recordPart:statusNote.value?'status_note':'progress',reason:form.reason.trim()||null}
    const rows=mode.value==='delete'?await deleteStatusHistoryProgress(props.record.id,data):await updateStatusHistoryProgress(props.record.id,{...data,effectiveOn:form.effectiveOn,changeNote:form.changeNote.trim()})
    visible.value=false;audits.value=[];emit('updated',rows);ElMessage.success(mode.value==='delete'?'进度已删除，删除记录已保留':'进度已修改，修改前后内容已保留')
  }catch(e){error.value=e.detail||e.message||'操作失败';await formRef.value?.applyServerErrors(e)}
  finally{saving.value=false;emit('busy',false)}
}
async function loadAudits(){
  controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;auditError.value=''
  try{const rows=await getProgressRecordAudits(props.projectId,{signal:controller.signal});if(seq===sequence)audits.value=rows.filter(row=>String(row.recordId)===String(props.record.id)).reverse()}
  catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')auditError.value=e.detail||e.message||'历史记录加载失败'}
  finally{if(seq===sequence)loading.value=false}
}
onBeforeUnmount(()=>{++sequence;controller?.abort()})
onMounted(async()=>{try{editingReady.value=Boolean((await getProgressRecordCapabilities()).editAuditReady)}catch{editingReady.value=false}})
</script>
<style>
.progress-record-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:6px}.progress-record-actions .el-button+.el-button{margin-left:0}.progress-record-audits{max-width:calc(100vw - 32px)!important}.progress-record-audits-body{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.record-audit-entry{margin:12px 0}.record-audit-note{white-space:pre-wrap;overflow-wrap:anywhere}.progress-record-editor{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.progress-record-editor>.el-dialog__header,.progress-record-editor>.el-dialog__footer{flex:none}.progress-record-editor>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.progress-record-editor>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
