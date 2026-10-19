<template>
  <div class="request-arrangement-details">
    <el-popover v-if="request.project" v-model:visible="projectOpen" trigger="click" placement="left" :width="760" :popper-options="popoverOptions" popper-class="associated-project-popover" @show="loadProject" @hide="loader.cancel()">
      <template #reference><el-button link type="primary">项目详情</el-button></template>
      <AssociatedProjectDetailPanel :source-type="request.project.source_type" :project-id="request.project.project_id" :state="state" title="项目详情" @retry="loadProject" @close="projectOpen = false" @enter="enterProject" />
    </el-popover>
    <span v-else class="muted">未关联项目</span>
    <el-popover v-model:visible="requestOpen" trigger="click" placement="left" :width="760" :popper-options="popoverOptions" title="资源需求详情" popper-class="associated-project-popover" @show="loadRequest">
      <template #reference><el-button link type="primary">需求详情</el-button></template>
      <div v-loading="requestLoading" class="request-arrangement-detail-body">
        <el-button link type="primary" @click="requestOpen = false">关闭</el-button>
        <el-alert v-if="requestError" :title="requestError" type="warning" :closable="false"><el-button link @click="loadRequest">重新加载</el-button></el-alert>
        <ResourceRequestDetailContent v-if="detail" :request="detail" :owner-label="ownerLabel" />
      </div>
    </el-popover>
  </div>
</template>
<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getResourceRequest } from '@/api/resourceRequests'
import { fetchAssociatedProject } from '@/api/associatedProjectDetail'
import { createAssociatedProjectLoader } from '@/utils/associatedProjectDetail'
import { arrangementProjectRoute, arrangementPopoverOptions as popoverOptions } from '@/utils/resourceArrangements'
import ResourceRequestDetailContent from './ResourceRequestDetailContent.vue'
const AssociatedProjectDetailPanel = defineAsyncComponent(() => import('@/components/project/AssociatedProjectDetailPanel.vue'))
const props = defineProps({ request: { type: Object, required: true }, users: { type: Array, default: () => [] } })
const router = useRouter(), projectOpen = ref(false), requestOpen = ref(false), detail = ref(null), requestLoading = ref(false), requestError = ref('')
const ownerLabel = computed(() => { const user = props.users.find(u => u.id === detail.value?.ownerId); return user?.name || user?.full_name || user?.username || '-' })
const state = reactive({ loading: false, detail: null, error: '', extras: {} })
const loader = createAssociatedProjectLoader(fetchAssociatedProject, value => Object.assign(state, value))
function loadProject() { requestOpen.value = false; const project = props.request.project; if (project) loader.load({ sourceType: project.source_type, projectId: project.project_id }) }
function enterProject() { projectOpen.value = false; router.push(arrangementProjectRoute(props.request.project)) }
let sequence = 0
async function loadRequest() {
  projectOpen.value = false
  const seq = ++sequence; requestLoading.value = true; requestError.value = ''; detail.value = null
  try { const value = await getResourceRequest(props.request.id); if (seq === sequence) detail.value = value }
  catch (error) { if (seq === sequence) requestError.value = error.message || '加载需求详情失败' }
  finally { if (seq === sequence) requestLoading.value = false }
}
onBeforeUnmount(() => { sequence++; loader.cancel() })
</script>
<style>
.request-arrangement-details { display: flex; gap: 16px; margin-bottom: 16px; }
.request-arrangement-detail-body { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; overflow-wrap: anywhere; white-space: pre-wrap; }
</style>
