<template>
  <div class="arrangement-project-card">
    <ResourceRequestDetailPopover v-model="opened" :request="requestLink" title="项目安排详情" back-label="返回项目安排" @show="load" @hide="cancel">
      <template #reference="{ toggle }">
        <el-button link type="primary" class="arrangement-project-link" @click.stop="toggle">{{ showName ? project.project_name || '未命名项目' : project.order_no || project.project_name }}</el-button>
        <el-button v-if="showName" link type="primary" class="arrangement-project-more" :aria-label="`${project.project_name} 更多`" @click.stop="toggle">更多</el-button>
      </template>
      <template #default="{ openProject }">
        <div v-loading="loading" class="arrangement-project-detail-body">
          <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="订单号">{{ project.order_no || '-' }}</el-descriptions-item>
            <el-descriptions-item label="项目名称"><el-button link type="primary" class="arrangement-open-project-detail" @click="openProject($event.currentTarget)">{{ project.project_name || '未命名项目' }}</el-button></el-descriptions-item>
            <el-descriptions-item label="项目类型">{{ typeLabel }}</el-descriptions-item>
            <el-descriptions-item label="项目状态">{{ getProjectStatusLabel(project.source_type, detail?.project_status) }}</el-descriptions-item>
            <el-descriptions-item v-if="day" label="安排日期">{{ day.work_date }}</el-descriptions-item>
            <el-descriptions-item v-if="cell" label="负责人">{{ cell.owner_name || '未分配' }}</el-descriptions-item>
            <el-descriptions-item v-if="cell" label="本次安排范围" :span="2"><div v-for="scope in scopes" :key="scope">{{ scope }}</div><span v-if="!scopes.length">语种、城市未配置</span></el-descriptions-item>
            <template v-for="target in targets" :key="`${target.kind}:${target.request_id}:${target.language_id}`">
              <el-descriptions-item label="需求编号">{{ target.request_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="安排备注">{{ target.arrangement_note || '-' }}</el-descriptions-item>
            </template>
            <el-descriptions-item v-if="cell" label="账号备注" :span="2">{{ cell.remarks || '-' }}</el-descriptions-item>
            <el-descriptions-item v-for="requirement in !cell ? detail?.requirements || [] : []" :key="requirement.request_no" :label="`${requirement.request_no} · 语种`" :span="2">{{ requirement.languages?.join('、') || '-' }}</el-descriptions-item>
          </el-descriptions>
          <RequestArrangementHistory :items="detail?.arrangements || []" />
          <DevelopmentArrangementHistory v-if="opened && day && cell?.id" :day="day" :cell="cell" />
        </div>
      </template>
    </ResourceRequestDetailPopover>
    <div v-if="showName && cell" class="arrangement-project-scopes"><el-tag v-for="scope in scopes" :key="scope" size="small" type="info">{{ scope }}</el-tag><span v-if="!scopes.length" class="muted">语种、城市未配置</span></div>
    <small v-for="target in targets.filter(item => item.active === false)" :key="`${target.kind}:${target.request_id}:${target.language_id}`" class="arrangement-warning">{{ target.inactive_reason }}</small>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementProjectKey, arrangementProjectScopes, arrangementProjectTypes } from '@/utils/resourceArrangements'
import { getProjectStatusLabel } from '@/utils/projectStatus'
import RequestArrangementHistory from './RequestArrangementHistory.vue'
import ResourceRequestDetailPopover from './ResourceRequestDetailPopover.vue'
import DevelopmentArrangementHistory from './DevelopmentArrangementHistory.vue'
const props = defineProps({ project: { type: Object, required: true }, showName: Boolean, day: Object, cell: Object })
const opened = ref(false), loading = ref(false), error = ref(''), detail = ref(null)
const requestLink = computed(() => ({ sourceType: props.project.source_type, [`${props.project.source_type}ProjectId`]: props.project.project_id }))
const typeLabel = computed(() => arrangementProjectTypes.find(t => t.value === props.project.source_type)?.label || '-')
const targets = computed(() => (props.cell?.targets || []).filter(t => t.project && arrangementProjectKey(t.project) === arrangementProjectKey(props.project)))
const scopes = computed(() => arrangementProjectScopes(targets.value))
let controller, sequence = 0
function cancel() { sequence++; controller?.abort(); detail.value = null }
async function load() {
  cancel(); controller = new AbortController(); const seq = sequence
  loading.value = true; error.value = ''
  try { const data = await api.arrangementProject({ source_type: props.project.source_type, project_id: props.project.project_id }, controller.signal); if (seq === sequence) detail.value = data }
  catch (e) { if (seq === sequence && e.code !== 'ERR_CANCELED') error.value = e.message }
  finally { if (seq === sequence) loading.value = false }
}
onBeforeUnmount(cancel)
</script>
<style>
.arrangement-project-card { min-width: 0; width: 100%; margin: 4px 0 8px; }
.arrangement-project-card .resource-detail-reference { display: flex; width: 100%; align-items: flex-start; }
.arrangement-project-card .arrangement-project-link { white-space: normal; height: auto; text-align: left; min-width: 0; overflow-wrap: anywhere; flex: 1; justify-content: flex-start; }
.arrangement-project-card .arrangement-project-more { flex-shrink: 0; margin-left: 4px; }
.arrangement-project-scopes { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.arrangement-project-scopes .el-tag { height: auto; white-space: normal; }
.arrangement-project-detail-body { max-height: min(560px, calc(100vh - 140px)); overflow-y: auto; overflow-wrap: anywhere; }
.arrangement-open-project-detail { height: auto; white-space: normal; text-align: left; }
</style>
