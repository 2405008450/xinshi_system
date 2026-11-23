<template>
  <el-config-provider :z-index="10000">
    <el-button v-if="projectType === 'annotation' && projectId" class="chat-work-report-entry"
      :loading="openingReport" @mousedown.stop @dblclick.stop @click="openWorkReport">工作报告</el-button>
    <el-dropdown v-if="projectType === 'annotation' && projectId && hasPermission('projects:read')" ref="projectMenu" trigger="click" @command="open">
      <el-button class="chat-project-entry" size="small" aria-label="项目入口" title="项目入口" @mousedown.stop @dblclick.stop><el-icon><Menu /></el-icon></el-button>
      <template #dropdown><el-dropdown-menu>
        <el-dropdown-item v-if="hasPermission('projects:write')" command="edit">项目编辑</el-dropdown-item>
        <el-dropdown-item command="progress">项目进度</el-dropdown-item>
        <el-dropdown-item v-if="hasPermission('projects:write')" command="request">资源需求</el-dropdown-item>
        <el-dropdown-item command="technical">技术需求</el-dropdown-item>
        <el-dropdown-item command="trials">试标试采管理</el-dropdown-item>
        <el-dropdown-item command="ai" title="查看分析进度和结果"
          @contextmenu.prevent.stop="openAiHistory" @keydown.shift.f10.prevent.stop="openAiHistory">AI 分析</el-dropdown-item>
      </el-dropdown-menu></template>
    </el-dropdown>
    <ResourceRequestEditor v-if="source" editor-only :source-request="source" @editor-closed="source=null" />
    <AnnotationProgressHost v-if="progressProjectId" :key="progressProjectId" embedded progress-only :progress-project-id="progressProjectId" @progress-closed="progressProjectId=''" />
    <AnnotationTrialsHost v-if="trialsProjectId" :key="trialsProjectId" workspace-only :workspace-project-id="trialsProjectId" @workspace-closed="trialsProjectId=''" />
    <AnnotationProgressHost v-if="editRequest" :key="`editor:${projectId}`" embedded editor-only :editor-project-id="projectId" :create-request="editRequest" />
    <AnnotationChatAiDialog v-if="aiVisible && projectId" :key="`ai:${projectId}`" :project-id="projectId" @close="aiVisible=false" />
  </el-config-provider>
</template>
<script setup>
import { defineAsyncComponent, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Menu } from '@element-plus/icons-vue'
import { hasPermission } from '@/utils/permission'
import { chatRequest } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { ElMessage } from 'element-plus'
import { copyTextToClipboard } from '@/utils/clipboard'
import { getAnnotationProject } from '@/api/annotationProjects'
const ResourceRequestEditor = defineAsyncComponent(() => import('@/views/resource/ResourceRequests.vue'))
const AnnotationProgressHost = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const AnnotationTrialsHost = defineAsyncComponent(() => import('@/views/project/AnnotationTrials.vue'))
const AnnotationChatAiDialog = defineAsyncComponent(() => import('./AnnotationChatAiDialog.vue'))
const props = defineProps({ projectId: String, projectType: String, orderNo: String })
const emit = defineEmits(['navigate'])
const router = useRouter()
const openingReport = ref(false)
const progressProjectId=ref(''),trialsProjectId=ref('')
const source = ref(null)
const editRequest = ref(0)
const aiVisible = ref(false)
const projectMenu = ref(null)
watch(()=>props.projectId,()=>{editRequest.value=0; aiVisible.value=false})
function openAiHistory() {
  projectMenu.value?.handleClose()
  aiVisible.value = true
}
async function openWorkReport() {
  if (openingReport.value) return
  openingReport.value = true
  try {
    const projectId = props.projectId
    const details = props.orderNo ? null : await getAnnotationProject(projectId).catch(() => null)
    const orderNo = props.orderNo || details?.orderNo
    const copied = await copyTextToClipboard(orderNo)
    if (!copied) ElMessage.warning('订单号自动复制失败，请手动复制')
    const failure = await router.push({
      name: 'WorkDashboard',
      query: { section: 'daily-report', reportAnnotationProject: projectId, reportChatProject: projectId },
    })
    if (!failure || router.currentRoute.value.query.reportAnnotationProject === props.projectId) emit('navigate')
  } catch (error) {
    ElMessage.error(error.detail || '打开工作报告失败')
  } finally {
    openingReport.value = false
  }
}
async function open(command) {
  if (command === 'ai') aiVisible.value = true
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
