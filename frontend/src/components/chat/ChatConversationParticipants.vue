<template>
  <ChatParticipantsPopover v-model="form.userIds" :members="members" :invitable-users="eligibleUsers" :current-user-id="currentUserId" :z-index="participantsZ" :loading="loading" :inviting="inviting" :error="error" @show="load" @invite="invite" @member-click="startDirect">
    <template #reference><el-button link :icon="User" aria-label="参与人" title="参与人" @click="participantsZ = chatOverlayZIndex($event.currentTarget)"><span v-if="menuLayout">参与人</span></el-button></template>
    <template #management><ChatParticipantActions :project-type="projectType" :project-id="projectId" :members="members" @changed="load" /></template>
  </ChatParticipantsPopover>
</template>
<script setup>
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { User } from '@element-plus/icons-vue'
import ChatParticipantsPopover from './ChatParticipantsPopover.vue'
import ChatParticipantActions from './ChatParticipantActions.vue'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { chatRequest } from '@/api/projectChat'
const props = defineProps({ projectType: String, projectId: String,menuLayout:Boolean })
const members = ref([]), eligibleUsers = ref([]), form = reactive({ userIds: [] })
const { refresh: refreshSessions } = useAnnotationFollowed()
const currentUserId = localStorage.getItem('user_id') || ''
const participantsZ = ref(2110)
const loading = ref(false), inviting = ref(false), error = ref('')
let controller, generation = 0
function accept(data) { members.value = data.members; eligibleUsers.value = data.eligibleUsers }
async function load() {
  controller?.abort(); controller = new AbortController(); const version = ++generation
  loading.value = true; error.value = ''
  try { const data = await chatRequest(`conversations/${props.projectType}/${props.projectId}/participants`, { signal: controller.signal }); if (version === generation) accept(data) }
  catch (e) { if (version === generation && e.code !== 'ERR_CANCELED') error.value = e.detail || e.message }
  finally { if (version === generation) loading.value = false }
}
async function startDirect(member) {
  try {
    const data = await chatRequest('direct/conversations', { method: 'post', data: { userId: member.id } })
    useProjectChatDock().openChat({ projectId: data.id, projectType: 'direct', title: data.title, subtitle: data.subtitle })
    await refreshSessions()
  } catch (e) { ElMessage.error(e.detail || e.message || '打开私聊失败') }
}
async function invite() {
  if (!form.userIds.length || loading.value || inviting.value) return
  const version = generation
  inviting.value = true; error.value = ''
  try { const data = await chatRequest(`conversations/${props.projectType}/${props.projectId}/invitations`, { method: 'post', data: { userIds: form.userIds } }); if (version === generation) { accept(data); form.userIds = [] } }
  catch (e) { if (version === generation) error.value = e.detail || e.message }
  finally { inviting.value = false }
}
watch(() => [props.projectId, props.projectType], () => { ++generation; controller?.abort(); members.value = []; eligibleUsers.value = []; form.userIds = []; error.value = ''; loading.value = false })
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
