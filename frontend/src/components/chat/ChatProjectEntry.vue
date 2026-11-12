<template>
  <el-config-provider :z-index="10000">
    <el-dropdown v-if="projectType === 'annotation' && projectId && hasPermission('projects:read')" ref="projectMenu" trigger="click" @command="open">
      <el-button class="chat-project-entry" size="small" aria-label="项目入口" title="项目入口" @mousedown.stop @dblclick.stop><el-icon><Menu /></el-icon></el-button>
      <template #dropdown><el-dropdown-menu>
        <el-dropdown-item v-if="hasPermission('projects:write')" command="edit">项目编辑</el-dropdown-item>
        <el-dropdown-item command="progress">项目进度</el-dropdown-item>
        <el-dropdown-item v-if="hasPermission('projects:write')" command="request">资源需求</el-dropdown-item>
        <el-dropdown-item command="technical">技术需求</el-dropdown-item>
        <el-dropdown-item command="trials">试标试采管理</el-dropdown-item>
        <el-dropdown-item command="ai" title="左键运行，右键查看分析结果"
          @contextmenu.prevent.stop="openAiHistory" @keydown.shift.f10.prevent.stop="openAiHistory">AI 分析</el-dropdown-item>
      </el-dropdown-menu></template>
    </el-dropdown>
    <ResourceRequestEditor v-if="source" editor-only :source-request="source" @editor-closed="source=null" />
    <AnnotationProgressHost v-if="progressProjectId" :key="progressProjectId" embedded progress-only :progress-project-id="progressProjectId" @progress-closed="progressProjectId=''" />
    <AnnotationTrialsHost v-if="trialsProjectId" :key="trialsProjectId" workspace-only :workspace-project-id="trialsProjectId" @workspace-closed="trialsProjectId=''" />
    <AnnotationProgressHost v-if="editRequest" :key="`editor:${projectId}`" embedded editor-only :editor-project-id="projectId" :create-request="editRequest" />
    <AnnotationChatAiDialog v-if="aiMode && projectId" :key="`ai:${projectId}`" :project-id="projectId" :initial-mode="aiMode" @close="aiMode=''" />
  </el-config-provider>
</template>
<script setup>
import { defineAsyncComponent, ref, watch } from 'vue'
import { Menu } from '@element-plus/icons-vue'
import { hasPermission } from '@/utils/permission'
import { chatRequest } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { ElMessage } from 'element-plus'
const ResourceRequestEditor = defineAsyncComponent(() => import('@/views/resource/ResourceRequests.vue'))
const AnnotationProgressHost = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const AnnotationTrialsHost = defineAsyncComponent(() => import('@/views/project/AnnotationTrials.vue'))
const AnnotationChatAiDialog = defineAsyncComponent(() => import('./AnnotationChatAiDialog.vue'))
const props = defineProps({ projectId: String, projectType: String })
const emit = defineEmits(['navigate'])
const progressProjectId=ref(''),trialsProjectId=ref('')
const source = ref(null)
const editRequest = ref(0)
const aiMode = ref('')
const projectMenu = ref(null)
watch(()=>props.projectId,()=>{editRequest.value=0; aiMode.value=''})
function openAiHistory() {
  projectMenu.value?.handleClose()
  aiMode.value = 'history'
}
async function open(command) {
  if (command === 'ai') aiMode.value = 'run'
  if(command==='technical'){
    try{const room=await chatRequest(`technical/projects/${props.projectId}/room`,{method:'post',data:{userIds:[]}});useProjectChatDock().openChat({projectId:room.roomId,projectType:'discussion',title:room.title,subtitle:room.orderNo})}
    catch(e){ElMessage.error(e.detail||e.message||'打开技术需求失败')}
  }
  if(command==='edit' && hasPermission('projects:write')) editRequest.value++
  if(command==='progress'){
    progressProjectId.value=props.projectId
  }
  if (command === 'request') source.value = { sourceType: 'annotation', sourceProjectId: props.projectId }
  if (command === 'trials') {
    trialsProjectId.value=props.projectId
  }
}
</script>
<style scoped>
.chat-project-entry{display:inline-flex;align-items:center;justify-content:center}
.chat-project-entry :deep(>span){display:flex;align-items:center;justify-content:center}
</style>
