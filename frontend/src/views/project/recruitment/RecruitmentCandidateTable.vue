<template>
  <el-table ref="tableRef" :data="rows" v-loading="loading" border row-key="id" class="candidate-tracking-table">
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
              <el-button link type="primary" @click="openResumeFolder(row.resumePath)">打开路径</el-button>
              <el-button link type="primary" @click="copyResumePath(row.resumePath)">复制路径</el-button>
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

    <el-table-column v-for="round in [1, 2]" :key="`interview-${round}`" :label="`${round === 1 ? '一' : '二'}面日期与详情`" min-width="170">
      <template #default="{ row }">
        <el-popover trigger="click" placement="left" :width="420" @show="prepareInterview(row, round)">
          <template #reference>
            <div class="interview-cell">
              <span>{{ formatDate(interviewValue(row, round, 'date')) }}</span>
              <el-button link type="primary">查看详情</el-button>
            </div>
          </template>
          <div class="popover-editor">
            <h4>{{ round === 1 ? '一' : '二' }}面详情</h4>
            <template v-if="canWrite">
              <el-date-picker v-model="interviewDraft(row, round).date" value-format="YYYY-MM-DD" clearable style="width:100%" />
              <el-input v-model="interviewDraft(row, round).details" type="textarea" :rows="6" :placeholder="`请输入${round === 1 ? '一' : '二'}面详情`" />
              <div class="popover-footer"><el-button type="primary" :loading="interviewDraft(row, round).saving" @click="saveInterview(row, round)">保存</el-button></div>
            </template>
            <el-descriptions v-else :column="1" border size="small">
              <el-descriptions-item label="日期">{{ formatDate(interviewValue(row, round, 'date')) }}</el-descriptions-item>
              <el-descriptions-item label="详情"><div class="detail-text">{{ interviewValue(row, round, 'details') || '-' }}</div></el-descriptions-item>
            </el-descriptions>
          </div>
        </el-popover>
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
import TableActionButton from '@/components/common/TableActionButton.vue'
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
})
const emit = defineEmits(['edit', 'delete', 'refresh', 'row-updated', 'source-created'])

const communicationsExpanded = ref(false)
const tableRef = ref()
const maximumCommunicationCount = computed(() => Math.max(3, ...props.rows.map((row) => row.communications?.length || 0)))
const visibleCommunicationIndexes = computed(() => communicationsExpanded.value
  ? Array.from({ length: maximumCommunicationCount.value }, (_, index) => index + 1)
  : [1])
const communicationAt = (row, sequence) => (row.communications || []).find((item) => item.sequenceNo === sequence)
const latestCommunication = (row) => (row.communications || []).reduce((latest, item) => (
  !latest || item.communicationDate > latest.communicationDate ? item : latest
), null)
const ordinalLabel = (value) => ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][value] || String(value)

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
    tableRef.value?.$el?.querySelector(`.communication-column-${created.sequenceNo}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    ElMessage.success('沟通情况已添加')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '沟通情况添加失败')
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
    ElMessage.error(error?.response?.data?.detail || '沟通情况更新失败')
  } finally { draft.saving = false }
}

const interviewDrafts = reactive({})
const interviewKey = (row, round) => `${row.id}:${round}`
const interviewValue = (row, round, field) => row[`${round === 1 ? 'first' : 'second'}Interview${field === 'date' ? 'Date' : 'Details'}`]
const interviewDraft = (row, round) => interviewDrafts[interviewKey(row, round)] || (interviewDrafts[interviewKey(row, round)] = { date: '', details: '', saving: false })
const prepareInterview = (row, round) => Object.assign(interviewDraft(row, round), { date: interviewValue(row, round, 'date') || '', details: interviewValue(row, round, 'details') || '' })
const saveInterview = async (row, round) => {
  const draft = interviewDraft(row, round)
  const prefix = round === 1 ? 'firstInterview' : 'secondInterview'
  draft.saving = true
  try {
    const updated = await patchRecruitmentCandidate(row.id, { [`${prefix}Date`]: draft.date || null, [`${prefix}Details`]: draft.details.trim() || null })
    emit('row-updated', updated)
    ElMessage.success(`${round === 1 ? '一' : '二'}面详情已保存`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '面试详情保存失败')
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
    ElMessage.error(error?.response?.data?.detail || '简历来源保存失败')
  } finally { setSourceSaving(row.id, false) }
}

const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN').format(new Date(`${value}T00:00:00`)) : '-'
const toOpenPathHref = (path) => `openpath://${encodeURIComponent(String(path).replace(/^\\\\/, '')).replace(/%5C/gi, '\\').replace(/%2F/gi, '/')}`
const requirePath = (path) => {
  const value = String(path || '').trim()
  if (!value) ElMessage.warning('该人选暂无简历路径')
  return value
}
const openResume = (path) => { const value = requirePath(path); if (value) window.location.href = toOpenPathHref(value) }
const resumeDirectory = (path) => {
  const value = path.replace(/[\\/]+$/, '')
  const name = value.split(/[\\/]/).pop() || ''
  return /\.[^\\/.]+$/.test(name) ? value.slice(0, Math.max(value.lastIndexOf('\\'), value.lastIndexOf('/'))) : value
}
const openResumeFolder = (path) => { const value = requirePath(path); if (value) window.location.href = toOpenPathHref(resumeDirectory(value)) }
const copyResumePath = async (path) => {
  const value = requirePath(path)
  if (!value) return
  try { await navigator.clipboard.writeText(value); ElMessage.success('简历路径已复制') } catch { ElMessage.error('复制失败，请手工复制') }
}
</script>

<style scoped>
.candidate-tracking-table{width:100%}.candidate-name-cell,.communication-header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.candidate-name-cell{position:relative;min-height:38px}.resume-actions{align-self:flex-start;font-size:12px}.resume-action-list{display:flex;flex-direction:column;align-items:flex-start}.resume-action-list .el-button{margin-left:0}.communication-cell{display:flex;flex-direction:column;align-items:flex-start;gap:4px}.communication-preview{display:flex;height:auto;max-width:100%;flex-direction:column;align-items:flex-start;white-space:normal;text-align:left}.communication-preview span:last-child{display:-webkit-box;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2;word-break:break-word}.add-communication{font-size:12px}.empty-value{color:var(--el-text-color-placeholder)}.interview-cell{display:flex;min-height:48px;flex-direction:column;align-items:flex-end;justify-content:space-between}.interview-cell>span{align-self:flex-start}.popover-editor{display:flex;flex-direction:column;gap:12px}.popover-editor h4{margin:0}.popover-footer{display:flex;justify-content:flex-end}.detail-text{max-height:360px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
</style>
