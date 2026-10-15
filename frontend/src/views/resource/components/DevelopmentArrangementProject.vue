<template>
  <el-popover trigger="click" placement="left" :width="760" :popper-options="popoverOptions" title="关联项目详情" popper-class="development-detail" @show="load">
    <template #reference><el-button link type="primary" class="arrangement-project-link">{{ showName ? [project.order_no, project.project_name].filter(Boolean).join(' · ') : project.order_no || project.project_name }}</el-button></template>
    <div v-loading="loading" class="development-detail-body">
      <el-alert v-if="error" :title="error" type="warning" :closable="false" />
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="订单号">{{ project.order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目名称">{{ project.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目类型">{{ typeLabel }}</el-descriptions-item>
        <el-descriptions-item label="项目状态">{{ getProjectStatusLabel(project.source_type, detail?.project_status) }}</el-descriptions-item>
        <template v-for="request in detail?.requirements || []" :key="request.request_no">
          <el-descriptions-item label="需求编号">{{ request.request_no }}</el-descriptions-item>
          <el-descriptions-item label="需求状态">{{ demandStatusText(request.demand_status) }}</el-descriptions-item>
          <el-descriptions-item label="语种／方言" :span="2">{{ request.languages.join('、') || '-' }}</el-descriptions-item>
        </template>
      </el-descriptions>
      <RequestArrangementHistory :items="detail?.arrangements || []" />
      <el-button v-if="detail" link type="primary" @click="router.push(arrangementProjectRoute(project))">进入项目</el-button>
    </div>
  </el-popover>
</template>
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementProjectRoute, arrangementProjectTypes, arrangementPopoverOptions as popoverOptions } from '@/utils/resourceArrangements'
import { getProjectStatusLabel } from '@/utils/projectStatus'
import { demandStatusText } from '@/utils/resourceRequestLifecycle'
import RequestArrangementHistory from './RequestArrangementHistory.vue'
const props = defineProps({ project: { type: Object, required: true }, showName: Boolean })
const router = useRouter(), loading = ref(false), error = ref(''), detail = ref(null)
const typeLabel = computed(() => arrangementProjectTypes.find(t => t.value === props.project.source_type)?.label || '-')
let controller, sequence = 0
async function load() {
  controller?.abort(); controller = new AbortController(); const seq = ++sequence
  loading.value = true; error.value = ''; detail.value = null
  try { const data = await api.arrangementProject({ source_type: props.project.source_type, project_id: props.project.project_id }, controller.signal); if (seq === sequence) detail.value = data }
  catch (e) { if (seq === sequence && !controller.signal.aborted) error.value = e.message }
  finally { if (seq === sequence) loading.value = false }
}
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
