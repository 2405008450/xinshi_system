<template>
  <DraggableFormDialog :z-index="100002" v-model="visible" :title="dialogTitle" width="min(960px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="dialogTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="记录已被其他人修改，当前草稿已保留。请复制需要保留的内容，或重新加载后编辑。" type="warning" :closable="false"><el-button text @click="reloadDraft">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="issue-grid">
          <el-form-item label="内容" prop="content" class="wide"><el-input v-model="form.content" type="textarea" :autosize="{minRows:5,maxRows:12}" maxlength="20000" show-word-limit /></el-form-item>
          <el-form-item label="类别" prop="category"><el-select popper-class="chat-topic-select-popper" v-if="!form.id && !sourceMessageId" v-model="form.category"><el-option v-for="option in issueCategories" :key="option.value" :value="option.value" :label="option.label" /></el-select><template v-else><ReadonlyField :model-value="issueCategoryLabel(form.category)" source="auto" /><span class="issue-hint">按聊天收录入口自动填写</span></template></el-form-item>
          <el-form-item label="讨论主题"><ChatTopicSelect v-model="form.topic_id" /></el-form-item>
          <el-form-item label="提出人"><ReadonlyField :model-value="form.proposer_name" source="auto" /><span class="issue-hint">{{ form.source_type === 'manual' ? '当前用户自动带出' : '从消息发送人自动带出' }}</span></el-form-item>
          <el-form-item label="来源" class="wide"><ReadonlyField :model-value="form.source_title" source="auto" /><span class="issue-hint">来源对话自动记录；收录内容对关联人员及开拓统筹人员可见。</span></el-form-item>
          <el-form-item v-if="form.source_type !== 'manual'" label="原始消息" class="wide"><ReadonlyField :model-value="form.source_content" source="auto" type="textarea" :autosize="{minRows:3,maxRows:8}" /></el-form-item>
          <el-form-item label="后续安排" class="wide"><el-button :disabled="loading || saving" @click="openTasks">{{ form.id ? `管理后续安排（${form.tasks?.length || 0}）` : '保存后添加后续安排' }}</el-button></el-form-item>
          <el-form-item label="备注" prop="remarks" class="wide"><el-input v-model="form.remarks" type="textarea" :autosize="{minRows:3,maxRows:8}" maxlength="10000" show-word-limit /></el-form-item>
        </div>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(() => visible = false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || conflict" @click="save()">保存</el-button></template>
  </DraggableFormDialog>
  <DevelopmentIssueTasks ref="tasksRef" @saved="tasksSaved" />
</template>
<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import { issueCategoryLabel, issueCategories } from '@/utils/resourceIssues'
import ChatTopicSelect from '@/components/chat/ChatTopicSelect.vue'
import { newChatRequestId } from '@/utils/chatTopics'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { refreshIssueAccess, useResourceIssues } from '@/composables/useResourceIssues'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DevelopmentIssueTasks from './DevelopmentIssueTasks.vue'
import './issueDialogs.css'
const emit = defineEmits(['saved'])
const visible = ref(false), loading = ref(false), saving = ref(false), conflict = ref(false), formRef = ref(), bodyRef = ref(), tasksRef = ref()
const form = reactive({}), rules = {content:[{required:true, whitespace:true, message:'请填写内容', trigger:'blur'}], category:[{required:true,message:'请选择类别',trigger:'change'}]}
const dialogTitle = computed(() => form.id ? '编辑开拓问题' : form.source_type === 'manual' ? '新增开拓事项' : '收录到开拓问题')
const {fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch} = useDialogFieldSearch(bodyRef)
const { access } = useResourceIssues()
let baseline = '', sourceMessageId = '', sourceCategory = '', clientRequestId = ''
let openVersion = 0
const draft = () => JSON.stringify({content:form.content, remarks:form.remarks, topic_id:form.topic_id, category:form.category})
async function open(row, messageId, category) {
  const version = ++openVersion
  visible.value = true; loading.value = true; conflict.value = false; clearFieldSearch(); sourceMessageId = messageId; sourceCategory = category
  Object.keys(form).forEach(key => delete form[key])
  try {
    clientRequestId = newChatRequestId()
    const data = row?.id ? await issueApi.detail(row.id) : messageId ? {...await issueApi.source(messageId), category, remarks:''} : {category: category || 'problem', content:'', remarks:'', topic_id:null, source_type:'manual', source_title:'手工新增', proposer_name:access.user_name || '当前用户'}
    if (version !== openVersion) return
    Object.assign(form, data, {content: data.content ?? data.source_content}); baseline = draft()
    await nextTick(); formRef.value?.clearValidate()
  } catch (e) { if (version === openVersion) { visible.value = false; ElMessage.error(e.message) } } finally { if (version === openVersion) loading.value = false }
}
async function beforeClose(done) {
  if (saving.value || loading.value) return
  if (draft() !== baseline) { try { await ElMessageBox.confirm('当前修改尚未保存，是否放弃？','关闭开拓问题',{type:'warning',customClass:'chat-issue-message-box',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'}) } catch { return } }
  done()
}
async function save(close = true) {
  if (saving.value || loading.value || conflict.value || !await formRef.value.validate().catch(() => false)) return false
  saving.value = true
  try {
    const values = {content:form.content, remarks:form.remarks, topic_id:form.topic_id || null}
    const data = form.id ? await issueApi.update(form.id, {...values, revision:form.revision}) : await issueApi.create({...values, source_message_id:sourceMessageId || null, category:form.category, ...(!sourceMessageId ? {client_request_id:clientRequestId} : {})})
    Object.assign(form, data); baseline = draft(); emit('saved', data); refreshIssueAccess(true).catch(() => {})
    ElMessage.success(data.already_collected ? '该消息已收录，已打开已有记录' : '开拓问题已保存')
    if (close) visible.value = false
    return true
  } catch (e) { conflict.value = e.status === 409 || e.response?.status === 409; ElMessage.error(e.message); return false } finally { saving.value = false }
}
async function openTasks() {
  if (!form.id || draft() !== baseline) { if (!await save(false)) return }
  // 重复收录可能返回只有查看权限的记录，任务管理仍按服务器能力执行。
  await tasksRef.value.open(form)
}
function tasksSaved(row) { Object.assign(form, {revision:row.revision, tasks:row.tasks}); emit('saved', row) }
async function reloadDraft() {
  try { await ElMessageBox.confirm('重新加载会替换当前草稿，是否继续？','重新加载',{type:'warning',customClass:'chat-issue-message-box'}) } catch { return }
  await open(form.id ? {id:form.id} : null, sourceMessageId, sourceCategory)
}
defineExpose({open})
</script>
