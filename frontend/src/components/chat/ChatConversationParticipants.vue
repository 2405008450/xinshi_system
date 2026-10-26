<template>
  <el-popover :z-index="participantsZ" trigger="click" placement="bottom-end" :width="340" @show="load">
    <template #reference><el-button link :icon="User" aria-label="参与人" title="参与人" @click="participantsZ = chatOverlayZIndex($event.currentTarget)"><span v-if="menuLayout">参与人</span></el-button></template>
    <div v-loading="loading" class="chat-conversation-participants">
      <p>仅会话参与人可以查看和发言。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <div class="chat-conversation-participants__names"><span v-for="member in members" :key="member.id">{{ member.name }}</span></div>
      <AppForm ref="formRef" :model="form" @submit.prevent="invite">
        <el-form-item label="邀请人员" prop="userIds"><el-select v-model="form.userIds" multiple filterable placeholder="可一次选择多人" :teleported="false"><el-option v-for="person in eligibleUsers" :key="person.id" :label="person.name" :value="person.id" /></el-select></el-form-item>
        <el-button type="primary" size="small" :disabled="!form.userIds.length || loading" :loading="inviting" @click="invite">邀请参与</el-button>
        <ChatParticipantActions :project-type="projectType" :project-id="projectId" :members="members" @changed="load" />
      </AppForm>
    </div>
  </el-popover>
</template>
<script setup>
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { User } from '@element-plus/icons-vue'
import AppForm from '@/components/common/AppForm.vue'
import ChatParticipantActions from './ChatParticipantActions.vue'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { chatRequest } from '@/api/projectChat'
const props = defineProps({ projectType: String, projectId: String,menuLayout:Boolean })
const members = ref([]), eligibleUsers = ref([]), form = reactive({ userIds: [] }), formRef = ref()
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
async function invite() {
  if (!form.userIds.length || inviting.value) return
  const version = generation
  inviting.value = true; error.value = ''
  try { const data = await chatRequest(`conversations/${props.projectType}/${props.projectId}/invitations`, { method: 'post', data: { userIds: form.userIds } }); if (version === generation) { accept(data); form.userIds = [] } }
  catch (e) { if (version === generation) error.value = e.detail || e.message }
  finally { inviting.value = false }
}
watch(() => [props.projectId, props.projectType], () => { ++generation; controller?.abort(); members.value = []; eligibleUsers.value = []; form.userIds = []; error.value = ''; loading.value = false })
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style scoped>
.chat-conversation-participants p{font-size:12px;color:#64748b}
.chat-conversation-participants__names{display:flex;gap:8px;flex-wrap:wrap;max-height:160px;overflow:auto;margin:12px 0}
.chat-conversation-participants__names span{padding:3px 6px;background:#f1f5f9;border-radius:4px;font-size:12px}
</style>
