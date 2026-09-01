<template>
  <div v-if="layout === 'cards'" v-loading="loading" class="candidate-card-list">
    <el-empty v-if="!rows.length && !loading" description="暂无简历人选，可点击右上角新增" :image-size="72" />
    <article v-for="row in rows" :key="row.id" class="candidate-card">
      <header class="candidate-card__header">
        <div class="candidate-card__identity">
          <strong>{{ row.candidateName || '未命名候选人' }}</strong>
          <span>最近沟通：{{ formatDate(latestCommunication(row)?.communicationDate) }}</span>
          <span>来源：{{ row.resumeSourceLabel || '-' }}</span>
        </div>
        <div class="candidate-card__actions">
          <el-popover trigger="click" placement="bottom-start" :width="150">
            <template #reference><el-button link type="primary">简历操作</el-button></template>
            <div class="resume-action-list">
              <el-button link type="primary" @click="openResume(row.resumePath)">直接打开简历</el-button>
              <PathActionButtons @open="openResumeFolder(row.resumePath)" @copy="copyResumePath(row.resumePath)" />
            </div>
          </el-popover>
          <TableActionButton v-if="canWrite" action="edit" @click="$emit('edit', row)" />
          <TableActionButton v-if="canWrite" action="delete" @click="$emit('delete', row)" />
          <el-button link type="primary" @click="toggleCandidateCard(row.id)">{{ isCandidateCardExpanded(row.id) ? '收起' : '展开填写' }}</el-button>
        </div>
      </header>

      <div v-if="isCandidateCardExpanded(row.id)" class="candidate-card__body">
        <section class="candidate-detail-section">
          <div class="candidate-detail-section__heading"><strong>基础信息</strong></div>
          <div class="candidate-basic-grid">
            <div class="candidate-field"><span>当前阶段</span><b>{{ stageLabel(row.stage) }}</b></div>
            <div class="candidate-field"><span>联系方式</span><b>{{ row.contactInfo || '-' }}</b></div>
            <div class="candidate-field"><span>跟进人</span><b>{{ row.ownerName || '-' }}</b></div>
            <div class="candidate-field"><span>推荐时间</span><b>{{ formatDateTime(row.recommendedAt) }}</b></div>
            <div class="candidate-field"><span>原面试时间</span><b>{{ formatDateTime(row.interviewAt) }}</b></div>
            <div class="candidate-field"><span>Offer 时间</span><b>{{ formatDateTime(row.offerAt) }}</b></div>
            <div class="candidate-field"><span>计划入职</span><b>{{ formatDate(row.plannedOnboardDate) }}</b></div>
            <div class="candidate-field"><span>实际入职</span><b>{{ formatDate(row.actualOnboardDate) }}</b></div>
            <div class="candidate-field"><span>下次跟进</span><b>{{ formatDateTime(row.nextFollowUpAt) }}</b></div>
            <div class="candidate-field candidate-source-field">
              <span>简历来源</span>
              <el-select
                v-if="canWrite"
                v-model="sourceDrafts[row.id]"
                filterable allow-create default-first-option clearable
                :loading="sourceSavingIds.has(row.id)"
                placeholder="选择或输入来源"
                @change="saveSource(row, $event)"
              >
                <el-option v-for="source in resumeSources" :key="source.id" :label="source.label" :value="source.id" />
              </el-select>
              <b v-else>{{ row.resumeSourceLabel || '-' }}</b>
            </div>
          </div>
        </section>

        <section class="candidate-detail-section">
          <div class="candidate-detail-section__heading">
            <strong>沟通记录（{{ row.communications?.length || 0 }}）</strong>
            <el-button v-if="canWrite" link type="primary" @click="toggleNewCommunication(row)">
              {{ isNewCommunicationOpen(row.id) ? '取消新增' : '新增沟通记录' }}
            </el-button>
          </div>
          <div v-if="isNewCommunicationOpen(row.id)" class="vertical-editor communication-create-editor">
            <el-date-picker v-model="newCommunicationDraft(row).communicationDate" value-format="YYYY-MM-DD" placeholder="沟通日期" style="width:100%" />
            <el-input v-model="newCommunicationDraft(row).details" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" placeholder="请输入沟通情况" />
            <div class="vertical-editor__footer"><el-button type="primary" :loading="newCommunicationDraft(row).saving" @click="addCommunication(row)">添加沟通记录</el-button></div>
          </div>
          <el-empty v-if="!row.communications?.length" description="暂无沟通记录" :image-size="56" />
          <el-collapse v-else class="communication-collapse">
            <el-collapse-item v-for="record in row.communications" :key="record.id" :name="record.id">
              <template #title><span>第{{ ordinalLabel(record.sequenceNo) }}次沟通 · {{ formatDate(record.communicationDate) }} · {{ summarize(record.details) }}</span></template>
              <div v-if="canWrite" class="vertical-editor">
                <el-date-picker v-model="communicationDraft(record).communicationDate" value-format="YYYY-MM-DD" style="width:100%" />
                <el-input v-model="communicationDraft(record).details" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" />
                <div class="vertical-editor__footer"><el-button type="primary" :loading="communicationDraft(record).saving" @click="saveCommunication(record)">保存本次沟通</el-button></div>
              </div>
              <div v-else class="detail-text">{{ record.details || '-' }}</div>
            </el-collapse-item>
          </el-collapse>
        </section>

        <section v-for="interview in row.interviews || []" :key="interview.id || interview.roundNo" class="candidate-detail-section interview-editor-section">
          <div class="candidate-detail-section__heading"><strong>{{ interviewLabel(interview.roundNo) }}日期与详情</strong><span>日期和详情可分别填写</span></div>
          <template v-if="canWrite">
            <div class="vertical-editor">
              <el-date-picker v-model="interviewDraft(row, interview).date" value-format="YYYY-MM-DD" clearable :placeholder="`${interviewLabel(interview.roundNo)}日期`" style="width:100%" />
              <el-input v-model="interviewDraft(row, interview).details" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" :placeholder="`请输入${interviewLabel(interview.roundNo)}详情`" />
              <div class="vertical-editor__footer"><el-button type="primary" :loading="interviewDraft(row, interview).saving" @click="saveInterview(row, interview)">保存{{ interviewLabel(interview.roundNo) }}信息</el-button></div>
            </div>
          </template>
          <el-descriptions v-else :column="1" border size="small">
            <el-descriptions-item label="日期">{{ formatDate(interview.interviewDate) }}</el-descriptions-item>
            <el-descriptions-item label="详情"><div class="detail-text">{{ interview.details || '-' }}</div></el-descriptions-item>
          </el-descriptions>
        </section>
      </div>
    </article>
  </div>

  <el-table v-else ref="tableRef" :data="rows" v-loading="loading" border row-key="id" class="candidate-tracking-table">
    <el-table-column label="最近沟通日期" width="126" fixed="left">
      <template #default="{ row }">{{ formatDate(latestCommunication(row)?.communicationDate) }}</template>
    </el-table-column>
    <el-table-column label="简历人选姓名" min-width="180" fixed="left">
      <template #default="{ row }">
        <div class="candidate-name-cell">
          <span>{{ row.candidateName || '-' }}</span>
          <el-popover trigger="click" placement="bottom-start" :width="150">
            <template #reference><el-button link type="primary" class="resume-actions">简历操作</el-button></template>
            <div class="resume-action-list">
              <el-button link type="primary" @click="openResume(row.resumePath)">直接打开简历</el-button>
              <PathActionButtons @open="openResumeFolder(row.resumePath)" @copy="copyResumePath(row.resumePath)" />
            </div>
          </el-popover>
        </div>
      </template>
    </el-table-column>

    <el-table-column
      v-for="communicationIndex in visibleCommunicationIndexes"
      :key="`communication-${communicationIndex}`"
      :min-width="communicationIndex === 1 ? 250 : 210"
      :class-name="`communication-column-${communicationIndex}`"
      :label-class-name="`communication-column-${communicationIndex}`"
    >
      <template #header>
        <div class="communication-header">
          <span>沟通情况（{{ ordinalLabel(communicationIndex) }}）</span>
          <el-button v-if="communicationIndex === 1" link type="primary" @click="communicationsExpanded = !communicationsExpanded">
            {{ communicationsExpanded ? '收起' : '展开' }}
          </el-button>
        </div>
      </template>
      <template #default="{ row }">
        <div class="communication-cell">
          <el-popover
            v-if="communicationAt(row, communicationIndex)"
            trigger="click"
            placement="left"
            :width="400"
            @show="prepareCommunication(communicationAt(row, communicationIndex))"
          >
            <template #reference>
              <el-button link type="primary" class="communication-preview">
                <span>{{ formatDate(communicationAt(row, communicationIndex).communicationDate) }}</span>
                <span>{{ communicationAt(row, communicationIndex).details }}</span>
              </el-button>
            </template>
            <div class="popover-editor">
              <h4>沟通情况（{{ ordinalLabel(communicationIndex) }}）</h4>
              <template v-if="canWrite">
                <el-date-picker v-model="communicationDraft(communicationAt(row, communicationIndex)).communicationDate" value-format="YYYY-MM-DD" style="width:100%" />
                <el-input v-model="communicationDraft(communicationAt(row, communicationIndex)).details" type="textarea" :rows="5" />
                <div class="popover-footer"><el-button type="primary" :loading="communicationDraft(communicationAt(row, communicationIndex)).saving" @click="saveCommunication(communicationAt(row, communicationIndex))">保存</el-button></div>
              </template>
              <el-descriptions v-else :column="1" border size="small">
                <el-descriptions-item label="沟通日期">{{ formatDate(communicationAt(row, communicationIndex).communicationDate) }}</el-descriptions-item>
                <el-descriptions-item label="沟通详情"><div class="detail-text">{{ communicationAt(row, communicationIndex).details || '-' }}</div></el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
          <span v-else class="empty-value">-</span>
          <el-popover v-if="canWrite && communicationIndex === 1" trigger="click" placement="left" :width="400" @show="prepareNewCommunication(row)">
            <template #reference><el-button link type="primary" class="add-communication">增加沟通情况</el-button></template>
            <div class="popover-editor">
              <h4>增加沟通情况（{{ ordinalLabel((row.communications?.length || 0) + 1) }}）</h4>
              <el-date-picker v-model="newCommunicationDraft(row).communicationDate" value-format="YYYY-MM-DD" style="width:100%" />
              <el-input v-model="newCommunicationDraft(row).details" type="textarea" :rows="5" placeholder="请输入沟通情况" />
              <div class="popover-footer"><el-button type="primary" :loading="newCommunicationDraft(row).saving" @click="addCommunication(row)">添加</el-button></div>
            </div>
          </el-popover>
        </div>
      </template>
    </el-table-column>

    <el-table-column v-for="round in visibleInterviewRounds" :key="`interview-${round}`" :label="`${interviewLabel(round)}日期与详情`" min-width="170">
      <template #default="{ row }">
        <el-popover v-if="interviewAtRound(row, round)" trigger="click" placement="left" :width="420" @show="prepareInterview(row, interviewAtRound(row, round))">
          <template #reference>
            <div class="interview-cell">
              <span>{{ formatDate(interviewAtRound(row, round).interviewDate) }}</span>
              <el-button link type="primary">查看详情</el-button>
            </div>
          </template>
          <div class="popover-editor">
            <h4>{{ interviewLabel(round) }}详情</h4>
            <template v-if="canWrite">
              <el-date-picker v-model="interviewDraft(row, interviewAtRound(row, round)).date" value-format="YYYY-MM-DD" clearable style="width:100%" />
              <el-input v-model="interviewDraft(row, interviewAtRound(row, round)).details" type="textarea" :rows="6" :placeholder="`请输入${interviewLabel(round)}详情`" />
              <div class="popover-footer"><el-button type="primary" :loading="interviewDraft(row, interviewAtRound(row, round)).saving" @click="saveInterview(row, interviewAtRound(row, round))">保存</el-button></div>
            </template>
            <el-descriptions v-else :column="1" border size="small">
              <el-descriptions-item label="日期">{{ formatDate(interviewAtRound(row, round).interviewDate) }}</el-descriptions-item>
              <el-descriptions-item label="详情"><div class="detail-text">{{ interviewAtRound(row, round).details || '-' }}</div></el-descriptions-item>
            </el-descriptions>
          </div>
        </el-popover>
        <span v-else class="empty-value">-</span>
      </template>
    </el-table-column>

    <el-table-column label="入职日期" width="126"><template #default="{ row }">{{ formatDate(row.actualOnboardDate) }}</template></el-table-column>
    <el-table-column label="简历来源" min-width="170">
      <template #default="{ row }">
        <el-select
          v-if="canWrite"
          v-model="sourceDrafts[row.id]"
          filterable
          allow-create
          default-first-option
          clearable
          :loading="sourceSavingIds.has(row.id)"
          placeholder="选择或输入来源"
          @change="saveSource(row, $event)"
        >
          <el-option v-for="source in resumeSources" :key="source.id" :label="source.label" :value="source.id" />
        </el-select>
        <span v-else>{{ row.resumeSourceLabel || '-' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="88" fixed="right" align="center">
      <template #default="{ row }">
        <TableActionButton v-if="canWrite" action="edit" @click="$emit('edit', row)" />
        <TableActionButton v-if="canWrite" action="delete" @click="$emit('delete', row)" />
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import TableActionButton from '@/components/common/TableActionButton.vue'
import { launchOpenPath } from '@/utils/openPath'
import {
  createRecruitmentCandidateCommunication,
  createRecruitmentResumeSource,
  patchRecruitmentCandidate,
  updateRecruitmentCandidateCommunication,
} from '@/api/recruitmentProjects'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  loading: Boolean,
  canWrite: Boolean,
  resumeSources: { type: Array, default: () => [] },
  layout: { type: String, default: 'table' },
})
const emit = defineEmits(['edit', 'delete', 'refresh', 'row-updated', 'source-created'])

const communicationsExpanded = ref(false)
const tableRef = ref()
const expandedCandidateIds = ref(new Set())
const newCommunicationOpenIds = ref(new Set())
const updateIdSet = (target, id, enabled) => {
  const next = new Set(target.value)
  if (enabled) next.add(id); else next.delete(id)
  target.value = next
}
const isCandidateCardExpanded = (id) => expandedCandidateIds.value.has(id)
const toggleCandidateCard = (id) => updateIdSet(expandedCandidateIds, id, !isCandidateCardExpanded(id))
const isNewCommunicationOpen = (id) => newCommunicationOpenIds.value.has(id)
const toggleNewCommunication = (row) => {
  const open = !isNewCommunicationOpen(row.id)
  updateIdSet(newCommunicationOpenIds, row.id, open)
  if (open) prepareNewCommunication(row)
}
const maximumCommunicationCount = computed(() => Math.max(3, ...props.rows.map((row) => row.communications?.length || 0)))
const visibleCommunicationIndexes = computed(() => communicationsExpanded.value
  ? Array.from({ length: maximumCommunicationCount.value }, (_, index) => index + 1)
  : [1])
const communicationAt = (row, sequence) => (row.communications || []).find((item) => item.sequenceNo === sequence)
const latestCommunication = (row) => (row.communications || []).reduce((latest, item) => (
  !latest || item.communicationDate > latest.communicationDate ? item : latest
), null)
const ordinalLabel = (value) => ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][value] || String(value)
const interviewLabel = (value) => value <= 10 ? `${ordinalLabel(value)}面` : `第${value}轮面试`
const CANDIDATE_STAGE_LABELS={screening:'待筛选',recommended:'已推荐',interviewing:'面试中',offer:'Offer 阶段',pending_onboard:'待入职',onboarded:'已入职',rejected:'已淘汰'}
const stageLabel=(value)=>CANDIDATE_STAGE_LABELS[value]||value||'-'
const interviewAtRound = (row, round) => (row.interviews || []).find((item) => item.roundNo === round)
const visibleInterviewRounds = computed(() => {
  const maximum = Math.max(1, ...props.rows.map((row) => row.interviews?.length || 0))
  return Array.from({ length: maximum }, (_, index) => index + 1)
})
const summarize = (value, length = 36) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  return text.length > length ? `${text.slice(0, length)}…` : (text || '-')
}

const currentDate = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
const communicationDrafts = reactive({})
const communicationDraft = (record) => communicationDrafts[record.id] || (communicationDrafts[record.id] = { communicationDate: record.communicationDate, details: record.details, saving: false })
const prepareCommunication = (record) => Object.assign(communicationDraft(record), { communicationDate: record.communicationDate, details: record.details })
const newCommunicationDrafts = reactive({})
const newCommunicationDraft = (row) => newCommunicationDrafts[row.id] || (newCommunicationDrafts[row.id] = { communicationDate: currentDate(), details: '', saving: false })
const prepareNewCommunication = (row) => Object.assign(newCommunicationDraft(row), { communicationDate: currentDate(), details: '' })

const addCommunication = async (row) => {
  const draft = newCommunicationDraft(row)
  if (!draft.communicationDate || !draft.details.trim()) return ElMessage.warning('请填写沟通日期和沟通情况')
  draft.saving = true
  try {
    const created = await createRecruitmentCandidateCommunication(row.id, { communicationDate: draft.communicationDate, details: draft.details.trim() })
    communicationsExpanded.value = true
    emit('row-updated', { ...row, communications: [...(row.communications || []), created] })
    await nextTick()
    if (props.layout === 'cards') {
      updateIdSet(newCommunicationOpenIds, row.id, false)
      Object.assign(draft, { communicationDate: currentDate(), details: '' })
    } else {
      tableRef.value?.$el?.querySelector(`.communication-column-${created.sequenceNo}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
    ElMessage.success('沟通情况已添加')
  } catch (error) {
    ElMessage.error(error?.detail || '沟通情况添加失败')
  } finally { draft.saving = false }
}
const saveCommunication = async (record) => {
  const draft = communicationDraft(record)
  if (!draft.communicationDate || !draft.details.trim()) return ElMessage.warning('请填写沟通日期和沟通情况')
  draft.saving = true
  try {
    await updateRecruitmentCandidateCommunication(record.id, { communicationDate: draft.communicationDate, details: draft.details.trim() })
    emit('refresh')
    ElMessage.success('沟通情况已更新')
  } catch (error) {
    ElMessage.error(error?.detail || '沟通情况更新失败')
  } finally { draft.saving = false }
}

const interviewDrafts = reactive({})
const interviewKey = (row, interview) => `${row.id}:${interview.roundNo}`
const interviewDraft = (row, interview) => interviewDrafts[interviewKey(row, interview)] || (interviewDrafts[interviewKey(row, interview)] = { date: interview.interviewDate || '', details: interview.details || '', saving: false })
const prepareInterview = (row, interview) => Object.assign(interviewDraft(row, interview), { date: interview.interviewDate || '', details: interview.details || '' })
const saveInterview = async (row, interview) => {
  const draft = interviewDraft(row, interview)
  draft.saving = true
  try {
    const interviews = (row.interviews || []).map((item) => ({
      roundNo: item.roundNo,
      interviewDate: item.roundNo === interview.roundNo ? (draft.date || null) : item.interviewDate,
      details: item.roundNo === interview.roundNo ? (draft.details.trim() || null) : item.details,
    }))
    const updated = await patchRecruitmentCandidate(row.id, { interviews })
    emit('row-updated', updated)
    ElMessage.success(`${interviewLabel(interview.roundNo)}详情已保存`)
  } catch (error) {
    ElMessage.error(error?.detail || '面试详情保存失败')
  } finally { draft.saving = false }
}

const sourceDrafts = reactive({})
watch(() => props.rows, (rows) => rows.forEach((row) => { sourceDrafts[row.id] = row.resumeSourceId || '' }), { immediate: true, deep: true })
const sourceSavingIds = ref(new Set())
const setSourceSaving = (id, saving) => {
  const next = new Set(sourceSavingIds.value)
  if (saving) next.add(id); else next.delete(id)
  sourceSavingIds.value = next
}
const saveSource = async (row, value) => {
  setSourceSaving(row.id, true)
  try {
    let sourceId = value || null
    if (value && !props.resumeSources.some((source) => source.id === value)) {
      const matching = props.resumeSources.find((source) => source.label.trim().toLowerCase() === String(value).trim().toLowerCase())
      const source = matching || await createRecruitmentResumeSource(String(value).trim())
      sourceId = source.id
      sourceDrafts[row.id] = source.id
      if (!matching) emit('source-created', source)
    }
    const updated = await patchRecruitmentCandidate(row.id, { resumeSourceId: sourceId })
    emit('row-updated', updated)
    ElMessage.success('简历来源已保存')
  } catch (error) {
    sourceDrafts[row.id] = row.resumeSourceId || ''
    ElMessage.error(error?.detail || '简历来源保存失败')
  } finally { setSourceSaving(row.id, false) }
}

const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN').format(new Date(`${value}T00:00:00`)) : '-'
const formatDateTime = (value) => value ? new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '-'
const requirePath = (path) => {
  const value = String(path || '').trim()
  if (!value) ElMessage.warning('该人选暂无简历路径')
  return value
}
const openResume = (path) => { const value = requirePath(path); if (value && !launchOpenPath(value)) ElMessage.error('该路径不在企业允许的网络目录中，已阻止打开') }
const resumeDirectory = (path) => {
  const value = path.replace(/[\\/]+$/, '')
  const name = value.split(/[\\/]/).pop() || ''
  return /\.[^\\/.]+$/.test(name) ? value.slice(0, Math.max(value.lastIndexOf('\\'), value.lastIndexOf('/'))) : value
}
const openResumeFolder = (path) => { const value = requirePath(path); if (value && !launchOpenPath(resumeDirectory(value))) ElMessage.error('该路径不在企业允许的网络目录中，已阻止打开') }
const copyResumePath = async (path) => {
  const value = requirePath(path)
  if (!value) return
  try { await navigator.clipboard.writeText(value); ElMessage.success('简历路径已复制') } catch { ElMessage.error('复制失败，请手工复制') }
}
</script>

<style scoped>
.candidate-tracking-table{width:100%}.candidate-name-cell,.communication-header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.candidate-name-cell{position:relative;min-height:38px}.resume-actions{align-self:flex-start;font-size:12px}.resume-action-list{display:flex;flex-direction:column;align-items:flex-start}.resume-action-list .el-button{margin-left:0}.communication-cell{display:flex;flex-direction:column;align-items:flex-start;gap:4px}.communication-preview{display:flex;height:auto;max-width:100%;flex-direction:column;align-items:flex-start;white-space:normal;text-align:left}.communication-preview span:last-child{display:-webkit-box;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2;word-break:break-word}.add-communication{font-size:12px}.empty-value{color:var(--el-text-color-placeholder)}.interview-cell{display:flex;min-height:48px;flex-direction:column;align-items:flex-end;justify-content:space-between}.interview-cell>span{align-self:flex-start}.popover-editor{display:flex;flex-direction:column;gap:12px}.popover-editor h4{margin:0}.popover-footer{display:flex;justify-content:flex-end}.detail-text{max-height:360px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
.candidate-card-list{display:flex;flex-direction:column;gap:12px;width:100%}.candidate-card{overflow:hidden;border:1px solid var(--el-border-color-lighter);border-radius:9px;background:var(--el-bg-color)}.candidate-card__header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 14px;background:var(--el-fill-color-extra-light)}.candidate-card__identity{display:flex;align-items:center;gap:14px;min-width:0}.candidate-card__identity strong{color:var(--el-text-color-primary);font-size:15px}.candidate-card__identity span{color:var(--el-text-color-secondary);font-size:12px}.candidate-card__actions{display:flex;align-items:center;gap:4px;flex:none}.candidate-card__body{display:flex;flex-direction:column;gap:14px;padding:14px}.candidate-detail-section{padding:14px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-blank)}.candidate-detail-section__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;color:var(--el-text-color-secondary);font-size:12px}.candidate-detail-section__heading strong{color:var(--el-text-color-primary);font-size:14px}.candidate-basic-grid{display:grid;grid-template-columns:minmax(160px,.6fr) minmax(240px,1fr);gap:12px}.candidate-field{display:flex;flex-direction:column;gap:6px}.candidate-field>span{color:var(--el-text-color-secondary);font-size:12px}.candidate-field>b{font-size:14px;font-weight:500}.vertical-editor{display:flex;flex-direction:column;gap:10px}.vertical-editor__footer{display:flex;justify-content:flex-end}.communication-create-editor{margin-bottom:12px;padding:12px;border-radius:8px;background:var(--el-color-primary-light-9)}.communication-collapse{border-top:0}.communication-collapse :deep(.el-collapse-item__header){height:auto;min-height:44px;line-height:1.5}.communication-collapse :deep(.el-collapse-item__content){padding:12px}.interview-editor-section :deep(.el-textarea__inner){line-height:1.65}
@media(max-width:720px){.candidate-card__header,.candidate-card__identity{align-items:flex-start;flex-direction:column}.candidate-card__actions{width:100%;flex-wrap:wrap}.candidate-basic-grid{grid-template-columns:1fr}.candidate-card__body{padding:10px}.candidate-detail-section{padding:12px}}
</style>
