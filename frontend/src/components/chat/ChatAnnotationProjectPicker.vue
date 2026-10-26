<template>
  <el-config-provider :z-index="10000">
    <DraggableFormDialog :model-value="modelValue" :title="`标注项目管理 · ${actionLabel}`" width="min(1440px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="chat-annotation-picker" :close-on-click-modal="false" @update:model-value="$emit('update:modelValue', $event)">
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
      <AnnotationProjects v-if="modelValue && canRead" conversation-picker :picker-action-label="actionLabel" :picker-joined-label="joinedLabel" :joined-project-ids="joinedIds" :joining-project-ids="[...joining]" @join-conversation="join" />
      <el-alert v-else-if="!canRead" title="没有标注项目查看权限" type="warning" :closable="false" />
      <template #footer>
        <span class="chat-annotation-picker__feedback" role="status">{{ feedback || (favoriteMode ? '关注后加入收藏夹，并按项目当前状态归类，可连续关注多个项目。' : '将项目加入会话列表，并按项目当前状态归类，可连续加入多个项目。') }}</span>
        <el-button :disabled="joining.size > 0" @click="$emit('update:modelValue', false)">完成</el-button>
      </template>
    </DraggableFormDialog>
  </el-config-provider>
</template>
<script setup>
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { annotationChatRequest } from '@/api/projectChat'
import { getAnnotationProject } from '@/api/annotationProjects'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { hasPermission } from '@/utils/permission'
import { annotationStatusLabels, normalizeAnnotationStatus } from '@/utils/annotationStatus'

const AnnotationProjects = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const props = defineProps({ modelValue: Boolean, favoriteMode: Boolean })
const actionLabel=computed(()=>props.favoriteMode ? '加入关注' : '创建/加入会话')
const joinedLabel=computed(()=>props.favoriteMode ? '已关注' : '已加入会话')
const emit = defineEmits(['update:modelValue', 'joined'])
const { sessions, refresh } = useAnnotationFollowed()
const departmentChatAccess=ref(false)
const canRead = computed(() => hasPermission('projects:read') || departmentChatAccess.value)
const joined = ref(new Set()), joining = ref(new Set()), error = ref(''), feedback = ref('')
const joinedIds = computed(() => [...new Set([
  ...sessions.value.filter(row => row.kind === 'annotation' && row.following).map(row => row.projectId),
  ...joined.value,
])])
watch(() => props.modelValue, async value => {
  if (value) { error.value = ''; feedback.value = ''; joined.value = new Set(); refresh();try{departmentChatAccess.value=!!(await annotationChatRequest('','conversation-capabilities')).canCreate}catch{} }
},{immediate:true})
async function join(row) {
  if(!props.favoriteMode){feedback.value=`“${row.projectName || row.orderNo}”已加入会话列表`;emit('joined',row);return}
  if (!canRead.value || joining.value.has(row.id) || joinedIds.value.includes(row.id)) return
  joining.value = new Set([...joining.value, row.id]); error.value = ''
  try {
    const project = await getAnnotationProject(row.id)
    await annotationChatRequest(row.id, 'start', { method: 'post' })
    await annotationChatRequest(row.id, 'following', { method: 'put', data: { following: true } })
    joined.value = new Set([...joined.value, row.id])
    await refresh()
    const projectStatus = project.projectStatus || row.projectStatus
    emit('joined', { ...row, ...project, projectStatus })
    feedback.value = `已加入“${row.projectName || row.orderNo}” → 标注项目 / ${annotationStatusLabels[normalizeAnnotationStatus(projectStatus)] || '其他状态'}`
  } catch (e) { error.value = e.detail || e.message || `${actionLabel.value}失败，请重试` }
  finally { joining.value = new Set([...joining.value].filter(id => id !== row.id)) }
}
</script>
<style>
.chat-annotation-picker{height:90vh;max-height:90vh}
.chat-annotation-picker>.el-dialog__body{display:flex;flex-direction:column;min-height:0;overflow:hidden}
.chat-annotation-picker>.el-dialog__body>.el-alert{flex:none;margin-bottom:8px}
.chat-annotation-picker>.el-dialog__footer{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--el-border-color-lighter)}
.chat-annotation-picker__feedback{min-width:0;text-align:left;font-size:12px;color:var(--el-text-color-secondary);overflow-wrap:anywhere}
</style>
