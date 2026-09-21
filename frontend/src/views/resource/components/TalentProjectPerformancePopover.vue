<template>
  <el-popover
    trigger="click"
    placement="left"
    :width="760"
    :teleported="true"
    :title="`${personName || '人才'} · ${project.projectName || '未命名项目'}中的表现`"
    popper-class="talent-project-performance-popper"
    @show="loadPerformance"
    @hide="cancelPerformance"
  >
    <template #reference>
      <el-button type="primary" link class="project-name-link">
        {{ project.projectName || '未命名项目' }}
      </el-button>
    </template>

    <div class="project-performance-content" v-loading="loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="订单号">{{ project.orderNo || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目类型">{{ projectTypeLabel(project.projectType) }}</el-descriptions-item>
        <el-descriptions-item label="参与角色">{{ roleText(project) }}</el-descriptions-item>
        <el-descriptions-item label="项目状态">{{ statusLabel(project.status) }}</el-descriptions-item>
        <el-descriptions-item label="最近参与时间" :span="2">{{ formatDateTime(project.participatedAt) }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="project.projectType === 'annotation'">
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <template v-else-if="performance">
          <section>
            <h4>试标 / 试采表现</h4>
            <div v-if="performance.trials?.length" class="performance-record-list">
              <div v-for="trial in performance.trials" :key="trial.id" class="performance-record">
                <div class="performance-record__heading">
                  <strong>第 {{ trial.roundNo }} 轮 · {{ trialActivityLabel(trial.activityType) }}{{ trialDutyLabel(trial.dutyRole) }}</strong>
                  <span v-if="trial.languageLabel" class="performance-record__secondary">{{ trial.languageLabel }}</span>
                  <el-tag size="small" :type="trialStatusType(trial.trialStatus)">{{ trialStatusLabel(trial.trialStatus) }}</el-tag>
                  <el-tag v-if="trial.trialResult" size="small" effect="plain">{{ trialResultLabel(trial.trialResult) }}</el-tag>
                </div>
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="候选阶段">{{ trialStageLabel(trial.candidateStage) }}</el-descriptions-item>
                  <el-descriptions-item label="意愿">{{ performanceLevelLabel(trial.willingnessLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="意愿说明" :span="2">{{ trial.willingnessText || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="开始时间">{{ formatDateTime(trial.startedAt) }}</el-descriptions-item>
                  <el-descriptions-item label="截止时间">{{ formatDateTime(trial.deadlineAt) }}</el-descriptions-item>
                  <el-descriptions-item label="实际提交时间">{{ formatDateTime(trial.submittedAt) }}</el-descriptions-item>
                  <el-descriptions-item label="总体评分">{{ trial.overallScore || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="配合度">{{ performanceLevelLabel(trial.cooperationLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="守时度">{{ performanceLevelLabel(trial.punctualityLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="结果评语" :span="2"><div class="pre-wrap">{{ trial.resultNote || '-' }}</div></el-descriptions-item>
                  <el-descriptions-item label="项目经理评价" :span="2"><div class="pre-wrap">{{ trial.managerComment || '-' }}</div></el-descriptions-item>
                  <el-descriptions-item
                    v-for="field in performance.trialFields || []"
                    :key="field.id"
                    :label="field.fieldLabel"
                    :span="field.dataType === 'textarea' ? 2 : 1"
                  >{{ customValue(trial.customValues?.[field.id]) }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
            <el-empty v-else description="暂无试标/试采记录" :image-size="64" />
          </section>

          <section>
            <h4>正式安排表现</h4>
            <div v-if="performance.assignments?.length" class="performance-record-list">
              <div v-for="assignment in performance.assignments" :key="assignment.id" class="performance-record">
                <div class="performance-record__heading">
                  <strong>{{ assignmentRoleLabel(assignment.assignmentRole) }}</strong>
                  <el-tag size="small" effect="plain">{{ assignmentStatusLabel(assignment.assignmentStatus) }}</el-tag>
                  <span v-if="assignment.languageLabel" class="performance-record__secondary">{{ assignment.languageLabel }}</span>
                </div>
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="质量评分">{{ assignment.qualityScore || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="评价备注"><div class="pre-wrap">{{ assignment.evaluationNote || '-' }}</div></el-descriptions-item>
                  <el-descriptions-item
                    v-for="field in performance.assignmentFields || []"
                    :key="field.id"
                    :label="field.fieldLabel"
                    :span="field.dataType === 'textarea' ? 2 : 1"
                  >{{ customValue(assignment.customValues?.[field.id]) }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
            <el-empty v-else description="暂无正式安排记录" :image-size="64" />
          </section>
        </template>
      </template>
      <el-alert v-else title="当前业务类型暂无独立的项目级评价，以上为该人才的真实参与信息。" type="info" :closable="false" show-icon />

      <div class="performance-actions">
        <AnnotationProjectDetailPopover
          v-if="project.projectType === 'annotation' && project.projectId"
          :project-id="project.projectId"
          :summary="projectSummary"
          :editable="false"
          :teleported="true"
          placement="left"
        >
          <template #reference><el-button @click.stop>查看项目详情</el-button></template>
        </AnnotationProjectDetailPopover>
        <el-button v-else @click="openProjectPage">查看项目详情</el-button>
        <el-button v-if="project.projectType === 'annotation'" type="primary" @click="openTrialWorkspace">打开试标/试采主窗口</el-button>
        <slot name="extra-actions" :project="project" />
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import { getTalentAnnotationProjectPerformance } from '@/api/talents'

const props = defineProps({
  personId: { type: [String, Number], required: true },
  personName: { type: String, default: '' },
  project: { type: Object, required: true },
})

const router = useRouter()
const loading = ref(false)
const performance = ref(null)
const error = ref('')
let requestId = 0
let controller = null

const projectSummary = computed(() => ({
  id: props.project.projectId,
  orderNo: props.project.orderNo,
  projectName: props.project.projectName,
  projectStatus: props.project.status,
}))

const projectTypeLabel = value => ({ translation:'笔译', interpretation:'口译', annotation:'标注', recruitment:'招聘' }[value] || value || '-')
const roleText = row => row.roles?.length ? row.roles.map(assignmentRoleLabel).join('、') : (assignmentRoleLabel(row.role) || '-')
const statusLabel = value => ({
  initial_consultation:'初步咨询', consultation_no_result:'初步咨询后无结果', resource_sourcing:'资源开拓',
  resource_sourcing_cancelled:'取消资源开拓', trial_preparation:'试标准备', trial_in_progress:'试标中',
  trial_submitted:'试标已提交', trial_passed:'试标通过', trial_failed:'试标未通过',
  trial_partially_passed:'部分试标通过', project_in_progress:'项目进行中', sent_to_client:'已发客户',
  client_feedback:'客户反馈', cancelled:'已取消', partially_cancelled:'已部分取消', paused:'暂停',
  actively_abandoned:'主动放弃', ended:'已结束',
}[value] || value || '-')
const assignmentRoleLabel = value => ({ annotator:'标注员', quality_inspector:'质检员' }[value] || value || '')
const assignmentStatusLabel = value => ({ assigned:'已安排', in_progress:'进行中', completed:'已完成', cancelled:'已取消' }[value] || value || '-')
const trialStatusLabel = value => ({ pending:'待开始', in_progress:'进行中', submitted:'已提交', reviewing:'评审中', completed:'已完成', cancelled:'已取消' }[value] || value || '-')
const trialStatusType = value => ({ pending:'info', in_progress:'primary', submitted:'warning', reviewing:'warning', completed:'success', cancelled:'danger' }[value] || 'info')
const trialResultLabel = value => ({ passed:'通过', failed:'未通过', partially_passed:'部分通过', withdrawn:'已退出' }[value] || value || '-')
const trialActivityLabel = value => ({ trial:'试标', collection:'试采' }[value] || value || '')
const trialDutyLabel = value => ({ executor:'员', quality_inspector:'质检员' }[value] || value || '')
const trialStageLabel = value => ({ backup:'备选', contacted:'已联系', pending_confirmation:'待确认', confirmed:'已确认', in_progress:'进行中', submitted:'已提交', reviewed:'已评审', withdrawn:'已退出' }[value] || value || '-')
const performanceLevelLabel = value => ({ high:'高', medium:'中', low:'低' }[value] || value || '-')
const customValue = value => Array.isArray(value) ? (value.join('、') || '-') : value === true ? '是' : value === false ? '否' : value == null || value === '' ? '-' : value
const formatDateTime = value => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12:false })
}

async function loadPerformance() {
  if (props.project.projectType !== 'annotation' || !props.project.projectId) return
  controller?.abort()
  controller = new AbortController()
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await getTalentAnnotationProjectPerformance(
      props.personId, props.project.projectId, { signal:controller.signal },
    )
    if (current === requestId) performance.value = result
  } catch (requestError) {
    if (requestError?.code !== 'ERR_CANCELED' && current === requestId) {
      performance.value = null
      error.value = requestError?.detail || '加载该项目中的人员表现失败'
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

const cancelPerformance = () => {
  controller?.abort()
  requestId += 1
}
onBeforeUnmount(cancelPerformance)

const routeNameMap = {
  translation:'TranslationProjectDetails', interpretation:'InterpretationProjectDetails',
  annotation:'AnnotationProjectDetails', recruitment:'RecruitmentProjectDetails',
}
const openProjectPage = () => router.push({
  name: routeNameMap[props.project.projectType] || 'AnnotationProjectDetails',
  query: { projectId: props.project.projectId },
})
const openTrialWorkspace = () => router.push({
  name:'AnnotationProjectDetails',
  query:{ section:'trials', projectId:props.project.projectId, personId:props.personId },
})
</script>

<style>
.talent-project-performance-popper{max-width:calc(100vw - 32px)!important}
.project-performance-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}
.project-performance-content section{margin-top:16px}
.project-performance-content h4{margin:0 0 8px}
.performance-record-list{display:grid;gap:12px}
.performance-record{padding:10px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-extra-light)}
.performance-record__heading{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.performance-record__secondary{color:var(--el-text-color-secondary);font-size:12px}
.performance-actions{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;margin-top:16px;padding:10px 0 0;border-top:1px solid var(--el-border-color-lighter);background:var(--el-bg-color)}
.project-name-link{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pre-wrap{white-space:pre-wrap;word-break:break-word}
</style>
