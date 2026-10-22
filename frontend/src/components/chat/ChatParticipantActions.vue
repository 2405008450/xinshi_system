<template>
  <el-button size="small" type="danger" plain @click="open">删除参与人</el-button>
  <el-button size="small" :loading="leaving" @click="leave">退出群组</el-button>
  <DraggableFormDialog v-model="visible" :z-index="dialogZ" title="删除参与人" width="min(560px, calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close class="chat-remove-participants" @open="selected = []; keyword = ''">
    <p>移出后，对方将无法查看此会话或继续发言；历史消息保留。</p>
    <AppForm :model="form" @submit.prevent="remove">
      <el-form-item label="搜索参与人"><el-input v-model="keyword" clearable placeholder="姓名" /></el-form-item>
      <el-form-item label="选择参与人"><el-checkbox-group v-model="selected" class="chat-remove-participants__users"><el-checkbox v-for="person in filteredMembers" :key="person.id" :value="person.id" :disabled="String(person.id) === currentUserId">{{ person.name }}{{ String(person.id) === currentUserId ? '（自己，请使用退出群组）' : '' }}</el-checkbox></el-checkbox-group></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><el-button @click="visible = false">取消</el-button><el-button type="danger" :disabled="!selected.length || leaving" :loading="removing" @click="remove">移出所选</el-button><el-button :loading="leaving" :disabled="removing" @click="leave">退出群组</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { chatRequest } from '@/api/projectChat'
import { matchesSearch } from '@/utils/searchMatching'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const props = defineProps({ projectType: String, projectId: String, members: { type: Array, default: () => [] } })
const emit = defineEmits(['changed'])
const currentUserId = localStorage.getItem('user_id') || ''
const visible = ref(false), selected = ref([]), keyword = ref(''), error = ref(''), removing = ref(false), leaving = ref(false)
const form = reactive({})
const dialogZ = ref(2120)
function open(event) { dialogZ.value = chatOverlayZIndex(event.currentTarget); error.value = ''; visible.value = true }
const filteredMembers = computed(() => props.members.filter(person => matchesSearch(person.name, keyword.value)))
async function remove() {
  if (!selected.value.length || removing.value) return
  removing.value = true; error.value = ''
  try {
    await chatRequest(`conversations/${props.projectType}/${props.projectId}/participants/remove`, { method: 'post', data: { userIds: selected.value } })
    visible.value = false; selected.value = []; emit('changed'); ElMessage.success('已移出所选参与人')
  } catch (e) { error.value = e.detail || e.message || '移出失败' }
  finally { removing.value = false }
}
async function leave(event) {
  if (leaving.value || removing.value) return
  try { await ElMessageBox.confirm('退出后将无法查看和发送消息，需要群内成员重新邀请才能加入。确定退出？', '退出群组', { confirmButtonText: '退出群组', cancelButtonText: '取消', type: 'warning', zIndex: chatOverlayZIndex(event?.currentTarget) }) } catch { return }
  leaving.value = true; error.value = ''
  try {
    await chatRequest(`conversations/${props.projectType}/${props.projectId}/participants/leave`, { method: 'post' })
    visible.value = false
    window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: { projectType: props.projectType, projectId: props.projectId } }))
    ElMessage.success('已退出群组')
  } catch (e) { error.value = e.detail || e.message || '退出失败'; ElMessage.error(error.value) }
  finally { leaving.value = false }
}
</script>
<style>
.chat-remove-participants{display:flex;flex-direction:column;max-height:84vh;overflow:hidden}.chat-remove-participants>.el-dialog__header,.chat-remove-participants>.el-dialog__footer{flex:none}.chat-remove-participants>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.chat-remove-participants>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}.chat-remove-participants__users{display:flex;flex-direction:column;gap:8px;width:100%}.chat-remove-participants__users .el-checkbox{white-space:normal;height:auto;min-height:28px}.chat-remove-participants p{font-size:12px;color:#64748b}
</style>
