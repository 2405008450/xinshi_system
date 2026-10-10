<template>
  <div v-if="projectId && projectType !== 'direct'" class="chat-project-actions" @mousedown.stop @dblclick.stop>
    <AnnotationProjectDetailPopover v-if="projectType === 'annotation'" :project-id="projectId" :editable="false" trigger="click" placement="bottom-end" popper-class="chat-project-popover">
      <template #reference><el-button link size="small">项目详情</el-button></template>
    </AnnotationProjectDetailPopover>
    <BusinessDetailPopover v-else :row="project" title="笔译项目详情" placement="bottom-end" popper-class="business-detail-popover chat-project-popover" :items="translationFields" :loading="loading" @show="loadProject">
      <template #reference><el-button link size="small">项目详情</el-button></template>
    </BusinessDetailPopover>
    <el-popover v-if="projectType === 'annotation'" trigger="click" placement="bottom-end" :width="760" title="项目资料" popper-class="chat-project-popover" @show="materials = true" @hide="materials = false">
      <template #reference><el-button link size="small">项目资料</el-button></template>
      <div class="chat-project-materials"><AnnotationMaterialManager v-if="materials" :project-id="projectId" readonly /></div>
    </el-popover>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import AnnotationMaterialManager from '@/components/annotation/AnnotationMaterialManager.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import { getProject } from '@/api/projects'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props = defineProps({ projectId: String, projectType: String })
const project = ref({}), materials = ref(false), loading = ref(false)
let version = 0
const translationFields = [
  { key: 'orderNo', label: '订单号' }, { key: 'projectStatus', label: '项目状态' },
  { key: 'projectName', label: '项目名称', span: 2 }, { key: 'clientShortName', label: '客户简称' },
  { key: 'projectManagerName', label: '项目经理' }, { key: 'clientFullName', label: '客户全称', span: 2 },
  { key: 'deliveryDate', label: '交付时间', formatter: formatBusinessDateTime },
  { key: 'createdAt', label: '创建时间', formatter: formatBusinessDateTime }, { key: 'remarks', label: '备注', span: 2 },
]
watch(() => props.projectId, () => { ++version; project.value = {}; materials.value = false; loading.value = false })
async function loadProject() {
  if (project.value.id || loading.value) return
  const requestId = ++version; loading.value = true
  try { const data = await getProject(props.projectId); if (requestId === version) project.value = data }
  catch (e) { ElMessage.error(e.detail || e.message || '项目详情加载失败') }
  finally { if (requestId === version) loading.value = false }
}
</script>
<style scoped>
.chat-project-actions{display:flex;gap:8px;align-items:center;flex-shrink:0}.chat-project-materials{max-height:min(560px,calc(100vh - 120px));overflow:auto}
.chat-project-actions :deep(.el-button){height:18px;margin-left:0;line-height:18px}
</style>
<style>
.chat-project-popover,.chat-session-popover,.annotation-members-popover{z-index:100000!important;max-width:calc(100vw - 32px)!important}
</style>
