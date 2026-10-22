<template>
  <el-button v-if="canAdjust" size="small" class="chat-annotation-managers-button" @mousedown.stop @dblclick.stop @click.stop="open">添加项目经理</el-button>
  <DraggableFormDialog v-model="visible" :z-index="dialogZ" title="添加项目经理" width="min(620px, calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close class="chat-annotation-managers" @open="load">
    <p>保存后同步到标注项目管理的“项目经理”，保留原有项目经理。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon><el-button v-if="!loaded" link @click="load">重新加载</el-button></el-alert>
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" v-loading="loading" @submit.prevent="save">
      <el-form-item label="当前项目"><ReadonlyField :model-value="project?.orderNo || ''" source="auto" /></el-form-item>
      <el-form-item label="已有项目经理"><span>{{ currentNames || '未分配' }}</span></el-form-item>
      <el-form-item label="添加人员（全体人员，可多选）" prop="additionalIds"><el-select v-model="form.additionalIds" multiple filterable clearable :teleported="false" placeholder="选择要添加的项目经理" style="width:100%" :disabled="!loaded || saving"><el-option v-for="person in users" :key="person.id" :label="person.full_name || person.username" :value="person.id" :disabled="currentIds.includes(person.id)" /></el-select></el-form-item>
      <el-form-item v-if="requiresReason" label="调整原因" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="请填写添加项目经理的原因" /></el-form-item>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :disabled="loading || !loaded || !form.additionalIds.length" :loading="saving" @click="save">添加并同步</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getAnnotationManagerOptions, getAnnotationProject, updateAnnotationProjectManagers } from '@/api/annotationProjects'
import { managerIds } from '@/utils/annotationManagerChange'
import { notifyAnnotationManagersUpdated } from '@/utils/annotationManagerSync'
import { hasPermission } from '@/utils/permission'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const props = defineProps({ projectId: { type: String, required: true } })
const canAdjust = computed(() => hasPermission('projects:read') || hasPermission('projects:write'))
const visible = ref(false), dialogZ = ref(2120), loading = ref(false), loaded = ref(false), saving = ref(false), error = ref('')
const project = ref(null), users = ref([]), formRef = ref(), form = reactive({ additionalIds: [], reason: '' })
const currentIds = computed(() => managerIds(project.value, 'project_manager'))
const requiresReason = computed(() => currentIds.value.length > 0 || !!project.value?.managerAssignmentHistory?.project_manager)
const currentNames = computed(() => currentIds.value.map(id => users.value.find(person => person.id === id)?.full_name || users.value.find(person => person.id === id)?.username || project.value?.roleAssignments?.find(row => (row.assigneeId || row.assignee_id) === id)?.assigneeName || id).join('、'))
const rules = {
  additionalIds: [{ type: 'array', min: 1, required: true, message: '请选择要添加的项目经理', trigger: 'change' }],
  reason: [{ required: true, validator: (_rule, value, callback) => requiresReason.value && !String(value || '').trim() ? callback(new Error('请填写调整原因')) : callback(), trigger: 'blur' }],
}
let controller, generation = 0
function open(event) { dialogZ.value = chatOverlayZIndex(event.currentTarget); visible.value = true }
async function load() {
  controller?.abort(); controller = new AbortController(); const version = ++generation
  loading.value = true; loaded.value = false; error.value = ''; project.value = null; form.additionalIds = []; form.reason = ''
  try {
    const [detail, options] = await Promise.all([getAnnotationProject(props.projectId, { signal: controller.signal }), getAnnotationManagerOptions({ signal: controller.signal })])
    if (version !== generation) return
    project.value = detail; users.value = options; loaded.value = true
  } catch (e) { if (version === generation && e.code !== 'ERR_CANCELED') error.value = e.detail || e.message || '加载项目经理失败' }
  finally { if (version === generation) loading.value = false }
}
async function save() {
  if (!loaded.value || saving.value || !canAdjust.value) return
  if (!await formRef.value?.validate().catch(() => false)) return
  const version = generation, id = props.projectId
  saving.value = true; error.value = ''
  try {
    await updateAnnotationProjectManagers(id, { projectManagerIds: [...new Set([...currentIds.value, ...form.additionalIds])], expectedUpdatedAt: project.value.updatedAt, reason: form.reason.trim() || null })
    notifyAnnotationManagersUpdated(id)
    if (version === generation) { visible.value = false; ElMessage.success('项目经理已添加并同步到标注项目管理') }
  } catch (e) {
    if (version !== generation) return
    error.value = e.detail || e.message || '添加失败'
    if ((e.response?.status || e.status) === 409) { loaded.value = false; error.value = '项目已被其他人更新，请重新加载后再添加' }
  } finally { if (version === generation) saving.value = false }
}
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style>
.chat-annotation-managers-button{flex:none;margin:0!important;font-size:11px;padding:6px 8px}.chat-annotation-managers{display:flex;flex-direction:column;max-height:84vh;overflow:hidden}.chat-annotation-managers>.el-dialog__header,.chat-annotation-managers>.el-dialog__footer{flex:none}.chat-annotation-managers>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.chat-annotation-managers>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}.chat-annotation-managers p{font-size:12px;color:#64748b}
</style>
