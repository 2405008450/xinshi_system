<template>
  <div class="project-identity-header" @dragstart.stop @mousedown.stop>
    <div class="project-identity-heading">
      <el-popover v-if="projectId && type" trigger="click" placement="bottom-end" :width="760" :title="projectTypeNames[type] + '详情'" popper-class="project-identity-detail" @show="load">
        <template #reference><button type="button" class="project-order-link" :aria-label="'查看项目详情 ' + displayOrder" data-field-copy="true">{{ displayOrder }}</button></template>
        <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
        <template v-else>
          <AnnotationProjectDetailContent v-if="type === 'annotation'" :row="detail" :project-id="projectId" :loading="loading" />
          <InterpretationProjectDetailContent v-else-if="type === 'interpretation'" v-loading="loading" :row="detail" />
          <BusinessDetailContent v-else :row="detail" :loading="loading" :items="detailItems" :status-label="statusLabel" :status-type="statusType" />
        </template>
      </el-popover>
      <strong class="project-identity-name">{{ projectName || detail.projectName || fallbackTitle }}</strong>
      <el-button v-if="projectId && type" type="primary" plain size="small" :disabled="reportDisabled" @click="openReport">填写工作报告</el-button>
    </div>
    <div v-if="projectId && type" class="project-identity-meta" :aria-busy="loading">
      <span>项目状态：<el-tag size="small" :type="statusType(detail.projectStatus)">{{ loading && !detail.projectStatus ? '加载中' : statusLabel(detail.projectStatus) }}</el-tag></span>
      <span>客户经理：{{ detail.clientManagerName || detail.currentClientManager || detail.clientManager || '未设置' }}</span>
      <span>项目经理：{{ projectManagerNames(detail) }}</span>
      <el-button v-if="error" link type="danger" @click="load">加载失败，重试</el-button>
    </div>
  </div>
</template>
<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BusinessDetailContent from './BusinessDetailContent.vue'
import { translationProjectDetailItems } from '@/utils/translationProjectDetail'
import { recruitmentProjectDetailItems } from '@/utils/recruitmentProjectDetail'
import { getProjectStatusLabel, getProjectStatusType } from '@/utils/projectStatus'
import { loadProjectIdentity, projectManagerNames, projectTypeNames, resolveProjectType } from '@/utils/projectIdentity'
const AnnotationProjectDetailContent = defineAsyncComponent(() => import('@/components/annotation/AnnotationProjectDetailContent.vue'))
const InterpretationProjectDetailContent = defineAsyncComponent(() => import('@/components/project/InterpretationProjectDetailContent.vue'))
const props = defineProps({ projectId: String, projectType: String, orderNo: String, projectName: String, fallbackTitle: String, reportDisabled: Boolean })
const router = useRouter()
const detail = ref({}), loading = ref(false), error = ref('')
const type = computed(() => resolveProjectType(props.projectType, props.orderNo))
const displayOrder = computed(() => props.orderNo || detail.value.orderNo || '查看项目详情')
const detailItems = computed(() => type.value === 'translation' ? translationProjectDetailItems : recruitmentProjectDetailItems)
const statusLabel = value => getProjectStatusLabel(type.value, value)
const statusType = value => getProjectStatusType(type.value, value)
let controller, sequence = 0
async function load() {
  if (!props.projectId || !type.value) return
  controller?.abort()
  controller = new AbortController()
  const current = ++sequence
  loading.value = true
  error.value = ''
  try {
    const value = await loadProjectIdentity(type.value, props.projectId, { signal: controller.signal })
    if (current === sequence) detail.value = value
  } catch (e) {
    if (current === sequence && e.code !== 'ERR_CANCELED') error.value = e.detail || '读取项目详情失败'
  } finally { if (current === sequence) loading.value = false }
}
async function openReport() {
  const failure = await router.push({ name: 'WorkDashboard', query: { section: 'daily-report', reportProjectId: props.projectId, reportProjectType: type.value } })
  if (failure && router.currentRoute.value.query.reportProjectId !== props.projectId) return
  window.dispatchEvent(new CustomEvent('open-my-work-report'))
  window.dispatchEvent(new CustomEvent('project-work-report-opened'))
}
watch(() => [props.projectId, type.value], () => { detail.value = {}; load() }, { immediate: true })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<style scoped>
.project-identity-header{min-width:0;user-select:text;cursor:text}.project-identity-heading{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.project-order-link{border:0;background:none;padding:0;color:var(--el-color-primary);font:inherit;font-weight:700;cursor:pointer;text-decoration:underline;text-underline-offset:3px}.project-order-link:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:3px}.project-identity-name{overflow-wrap:anywhere}.project-identity-heading>.el-button{margin-left:auto}.project-identity-meta{display:flex;gap:8px 20px;flex-wrap:wrap;align-items:center;margin-top:8px;font-size:13px;color:var(--el-text-color-regular)}
</style>
<style>
.project-identity-detail{width:min(760px,calc(100vw - 32px))!important;max-height:min(560px,calc(100vh - 120px));overflow-y:auto;overflow-wrap:anywhere}
</style>
