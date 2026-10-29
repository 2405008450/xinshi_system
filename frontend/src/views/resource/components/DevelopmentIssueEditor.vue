<template>
  <DraggableFormDialog :z-index="100002" v-model="visible" :title="dialogTitle" width="min(960px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="dialogTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="记录已被其他人修改，当前草稿已保留。请复制需要保留的内容，或重新加载后编辑。" type="warning" :closable="false"><el-button text @click="reloadDraft">重新加载</el-button></el-alert>
      <el-alert v-if="!access.summary_ready" title="总结字段尚未初始化，当前可预览表单，初始化后可保存。" type="info" :closable="false" />
      <el-descriptions :column="1" border size="small" class="issue-save-person" data-dialog-field-search-label="保存人">
        <el-descriptions-item label="保存人">{{ savePersonName }}</el-descriptions-item>
      </el-descriptions>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="!!form.id && form.can_edit===false">
        <div class="issue-grid">
          <el-form-item label="内容" prop="content" class="wide"><el-input v-model="form.content" type="textarea" :autosize="{minRows:5,maxRows:12}" maxlength="20000" show-word-limit /></el-form-item>
          <el-form-item label="类别" prop="category"><el-select popper-class="chat-topic-select-popper" v-if="!form.id && !sourceMessageId" v-model="form.category"><el-option v-for="option in issueCategories" :key="option.value" :value="option.value" :label="option.label" /></el-select><template v-else><ReadonlyField :model-value="issueCategoryLabel(form.category)" source="auto" /><span class="issue-hint">按聊天收录入口自动填写</span></template></el-form-item>
          <el-form-item label="具体分类" prop="specific_classification"><el-input v-model="form.specific_classification" maxlength="200" clearable placeholder="填写具体分类" /></el-form-item>
          <el-form-item label="需同步部门/人" class="wide"><SummaryAudienceSelect v-model="audience" :users="users" :departments="departments" /><span class="issue-hint">保存后向所选人员及所选部门的当前人员发送业务通知，重复人员只通知一次。</span></el-form-item>
          <el-form-item label="查看权限" class="wide"><SummaryAudienceSelect v-model="viewAudience" allow-everyone :users="users" :departments="departments" /><span class="issue-hint">默认全体可见，可多选部门或人员；清空后仅保存人与统筹管理人员可见。通知对象须在查看范围内。此设置不改变原会话权限。</span></el-form-item>
          <template v-if="form.category==='execution'">
            <el-form-item label="预定完成时间"><el-date-picker v-model="form.planned_completion_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm:ss" placeholder="选择完成时间（UTC+8）" /></el-form-item>
            <el-form-item label="跟进人"><el-select v-model="form.follower_user_ids" multiple clearable filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="3" popper-class="chat-topic-select-popper" @change="selectFollowers"><el-option label="全体人员" value="__all__" /><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
            <el-form-item label="实际进度" class="wide"><el-input v-model="form.actual_progress" type="textarea" :autosize="{minRows:4,maxRows:10}" maxlength="10000" show-word-limit placeholder="填写当前进展、完成情况或待解决事项" /></el-form-item>
          </template>
          <el-form-item label="提出人"><ReadonlyField :model-value="form.proposer_name" source="auto" /><span class="issue-hint">{{ form.source_type === 'manual' ? '当前用户自动带出' : '从消息发送人自动带出' }}</span></el-form-item>
          <el-form-item label="来源" class="wide"><ReadonlyField :model-value="form.source_title" source="auto" /><span class="issue-hint">来源对话自动记录；总结内容按查看权限展示。</span></el-form-item>
          <el-form-item v-if="form.source_type !== 'manual'" label="原始消息" class="wide"><ReadonlyField :model-value="form.source_content" source="auto" type="textarea" :autosize="{minRows:3,maxRows:8}" /></el-form-item>
          <el-form-item label="备注" prop="remarks" class="wide"><el-input v-model="form.remarks" type="textarea" :autosize="{minRows:3,maxRows:8}" maxlength="10000" show-word-limit /></el-form-item>
        </div>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(() => visible = false)">{{ form.id && form.can_edit===false?'关闭':'取消' }}</el-button><el-button v-if="!form.id || form.can_edit" type="primary" :loading="saving" :disabled="loading || conflict || !access.summary_ready" @click="save()">{{ hasNotifyAudience ? '保存并通知' : '保存' }}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import { issueCategoryLabel, issueCategories } from '@/utils/resourceIssues'
import SummaryAudienceSelect from '@/components/chat/SummaryAudienceSelect.vue'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { refreshDepartments } from '@/composables/useDepartmentCatalog'
import { newChatRequestId } from '@/utils/chatTopics'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { refreshIssueAccess, useResourceIssues } from '@/composables/useResourceIssues'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import './issueDialogs.css'
const emit = defineEmits(['saved'])
const visible = ref(false), loading = ref(false), saving = ref(false), conflict = ref(false), formRef = ref(), bodyRef = ref(), users=ref([]),departments=ref([])
const form = reactive({}), rules = {content:[{required:true, whitespace:true, message:'请填写内容', trigger:'blur'}], category:[{required:true,message:'请选择类别',trigger:'change'}]}
const dialogTitle = computed(() => form.id ? form.can_edit===false?'总结详情':'编辑总结' : form.source_type === 'manual' ? '新增总结' : '分类保存和通知')
const audience=computed({get:()=>({userIds:form.notify_user_ids||[],departmentIds:form.notify_department_ids||[]}),set:value=>{form.notify_user_ids=value.userIds;form.notify_department_ids=value.departmentIds}})
const hasNotifyAudience=computed(()=>!!(form.notify_user_ids?.length||form.notify_department_ids?.length))
const viewAudience=computed({get:()=>({everyone:form.view_all,userIds:form.view_user_ids||[],departmentIds:form.view_department_ids||[]}),set:value=>{form.view_all=value.everyone;form.view_user_ids=value.userIds;form.view_department_ids=value.departmentIds}})
function selectFollowers(values){if(values.includes('__all__'))form.follower_user_ids=users.value.map(row=>row.id)}
function applyForm(data){const meta=data.summary||data.summary_data||{};Object.assign(form,data,{specific_classification:meta.specific_classification??data.topic_path??'',planned_completion_at:meta.planned_completion_at?businessDateTimeInputValue(meta.planned_completion_at):'',follower_user_ids:meta.follower_user_ids||[],actual_progress:meta.actual_progress||'',notify_user_ids:meta.notify_user_ids||[],notify_department_ids:meta.notify_department_ids||[],view_all:meta.view_all??(data.id?null:true),view_user_ids:meta.view_user_ids||[],view_department_ids:meta.view_department_ids||[]})}
const {fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch} = useDialogFieldSearch(bodyRef)
const { access } = useResourceIssues()
const currentSaverName = ref('')
const savePersonName = computed(() => form.id ? form.collected_by_name || '-' : currentSaverName.value || '-')
let baseline = '', sourceMessageId = '', sourceCategory = '', clientRequestId = ''
let sourceDiscussionRoomId = null
let openVersion = 0
const draft = () => JSON.stringify({content:form.content, remarks:form.remarks, category:form.category,specific_classification:form.specific_classification,planned_completion_at:form.planned_completion_at,follower_user_ids:form.follower_user_ids,actual_progress:form.actual_progress,notify_user_ids:form.notify_user_ids,notify_department_ids:form.notify_department_ids,view_all:form.view_all,view_user_ids:form.view_user_ids,view_department_ids:form.view_department_ids})
async function open(row, messageId, category, discussionRoomId = null) {
  const version = ++openVersion
  currentSaverName.value = access.user_name || ''
  visible.value = true; loading.value = true; conflict.value = false; clearFieldSearch(); sourceMessageId = messageId; sourceCategory = category; sourceDiscussionRoomId = discussionRoomId
  Object.keys(form).forEach(key => delete form[key])
  try {
    clientRequestId = newChatRequestId()
    const [data,options,departmentOptions]=await Promise.all([row?.id ? issueApi.detail(row.id) : messageId ? issueApi.source(messageId,sourceDiscussionRoomId).then(source=>({...source,category,remarks:''})) : Promise.resolve({category:category||'problem',content:'',remarks:'',source_type:'manual',source_title:'手工新增',proposer_name:access.user_name||'当前用户'}),issueApi.options(),refreshDepartments()])
    if (version !== openVersion) return
    users.value=options.users;departments.value=options.departments||departmentOptions.items||[]
    currentSaverName.value=options.user_name||access.user_name||''
    applyForm({...data,content:data.content??data.source_content}); baseline = draft()
    await nextTick(); formRef.value?.clearValidate()
  } catch (e) { if (version === openVersion) { visible.value = false; ElMessage.error(e.message) } } finally { if (version === openVersion) loading.value = false }
}
async function beforeClose(done) {
  if (saving.value || loading.value) return
  if (draft() !== baseline) { try { await ElMessageBox.confirm('当前修改尚未保存，是否放弃？','关闭开拓问题',{type:'warning',customClass:'chat-issue-message-box',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'}) } catch { return } }
  done()
}
async function save(close = true) {
  if (saving.value || loading.value || conflict.value || !access.summary_ready || !await formRef.value.validate().catch(() => false)) return false
  saving.value = true
  try {
    const execution=form.category==='execution'
    const summary={view_all:form.view_all,view_user_ids:form.view_user_ids||[],view_department_ids:form.view_department_ids||[],specific_classification:form.specific_classification||'',notify_user_ids:form.notify_user_ids||[],notify_department_ids:form.notify_department_ids||[],follower_user_ids:execution?form.follower_user_ids||[]:[],planned_completion_at:execution&&form.planned_completion_at?form.planned_completion_at.replace(' ','T')+'+08:00':null,actual_progress:execution?form.actual_progress||'':''}
    const values = {content:form.content, remarks:form.remarks, summary}
    const data = form.id ? await issueApi.update(form.id, {...values, revision:form.revision}) : await issueApi.create({...values, source_message_id:sourceDiscussionRoomId ? null : sourceMessageId || null, ...(sourceDiscussionRoomId ? {source_discussion_room_id:sourceDiscussionRoomId,source_discussion_message_id:sourceMessageId} : {}), category:form.category, ...(!sourceMessageId ? {client_request_id:clientRequestId} : {})})
    applyForm(data); baseline = draft(); emit('saved', data); refreshIssueAccess(true).catch(() => {})
    ElMessage.success(data.already_collected ? '该消息已保存过，已打开已有总结' : hasNotifyAudience.value ? '总结已保存并通知' : '总结已保存')
    if (close) visible.value = false
    return true
  } catch (e) { conflict.value = e.status === 409 || e.response?.status === 409; ElMessage.error(e.message); return false } finally { saving.value = false }
}
async function reloadDraft() {
  try { await ElMessageBox.confirm('重新加载会替换当前草稿，是否继续？','重新加载',{type:'warning',customClass:'chat-issue-message-box'}) } catch { return }
  await open(form.id ? {id:form.id} : null, sourceMessageId, sourceCategory, sourceDiscussionRoomId)
}
defineExpose({open})
</script>
<style scoped>.issue-save-person{margin-bottom:16px}</style>
