<template>
  <section
    ref="overviewPanelRef"
    class="talent-overview-panel"
    :class="{ 'is-fallback-fullscreen': fallbackFullscreen }"
  >
    <el-card class="talent-overview-card compact-list-card">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span class="page-title">人才概览</span>
            <span class="page-subtitle">
              语种与方言资源快照，共 {{ filteredRows.length }} 项<span v-if="hasActiveFilters">（全部 {{ displayedRows.length }} 项）</span>
            </span>
            <span v-if="updatedAt" class="update-meta">
              最近由 {{ updatedByName || '未知用户' }} 编辑于 {{ formatDateTimeMinute(updatedAt) }}
            </span>
          </div>
          <div class="header-actions">
            <el-button :icon="FullScreen" @click="toggleFullscreen">
              {{ fullscreenActive ? '退出全屏' : '全屏显示' }}
            </el-button>
            <template v-if="editing">
              <el-button :icon="Plus" @click="addRow">新增行</el-button>
              <el-button :icon="Plus" @click="openAddColumn">新增列</el-button>
              <el-button :disabled="saving" @click="cancelEditing">取消</el-button>
              <el-button type="primary" :loading="saving" :disabled="!isDirty" @click="saveOverview">
                保存
              </el-button>
            </template>
            <el-button v-else-if="canWrite" type="primary" :icon="Edit" @click="startEditing">
              编辑
            </el-button>
          </div>
        </div>
      </template>

      <TalentResourceNav />

      <div class="overview-note">
        合计为原表各单元格相加，不代表去重后的人才人数；空白表示原表未填写，明确的零保留显示为 0。
        <template v-if="editing"> 当前为编辑模式，修改将在点击“保存”后统一生效。</template>
      </div>

      <el-table
        ref="overviewTableRef"
        :data="filteredRows"
        v-loading="loading || saving"
        row-key="overviewKey"
        border
        stripe
        show-summary
        :summary-method="summaryMethod"
        :height="tableHeight"
        class="overview-table"
      >
        <el-table-column prop="language" label="语种/方言" width="190" fixed="left" show-overflow-tooltip>
          <template #header>
            <ConfiguredColumnHeaderFilter
              v-model="filterValues.language"
              :definition="languageFilterDefinition"
            />
          </template>
          <template #default="{ row }">
            <el-input
              v-if="isActive(`row:${row.overviewKey}:language`)"
              :ref="captureActiveEditor"
              v-model="row.language"
              size="small"
              maxlength="100"
              @blur="finishActiveEditor"
              @keydown.enter.prevent="finishActiveEditor"
              @keydown.esc.prevent="cancelActiveEditor"
            />
            <button
              v-else-if="editing"
              type="button"
              class="editable-cell editable-cell--text"
              @click="activateEditor(`row:${row.overviewKey}:language`, row.language, value => { row.language = value })"
            >
              {{ row.language || '点击填写' }}
            </button>
            <span v-else>{{ row.language }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="updatedAt" label="更新日期" width="132" fixed="left" align="center">
          <template #header>
            <ConfiguredColumnHeaderFilter
              v-model="filterValues.updatedAt"
              :definition="updatedAtFilterDefinition"
            />
          </template>
          <template #default="{ row }">
            <el-date-picker
              v-if="isActive(`row:${row.overviewKey}:updatedAt`)"
              :ref="captureActiveEditor"
              v-model="row.updatedAt"
              type="date"
              value-format="YYYY-MM-DD"
              size="small"
              clearable
              @change="finishActiveEditor"
              @keydown.esc.prevent="cancelActiveEditor"
            />
            <button
              v-else-if="editing"
              type="button"
              class="editable-cell editable-cell--center"
              @click="activateEditor(`row:${row.overviewKey}:updatedAt`, row.updatedAt, value => { row.updatedAt = value })"
            >
              {{ row.updatedAt || '点击填写' }}
            </button>
            <span v-else>{{ row.updatedAt || '' }}</span>
          </template>
        </el-table-column>

        <el-table-column
          v-for="group in columnGroups"
          :key="group.key"
          :label="group.label"
          header-align="center"
        >
          <el-table-column
            v-for="column in group.columns"
            :key="column.key"
            :prop="`counts.${column.key}`"
            :width="column.width"
            align="right"
            header-align="center"
          >
            <template #header>
              <ConfiguredColumnHeaderFilter
                :definition="countFilterDefinitions[column.key]"
                :model-value="filterValues.counts[column.key] || []"
                @update:model-value="filterValues.counts[column.key] = $event"
              >
                <template #label>
                  <el-input
                    v-if="isActive(`column:${column.key}`)"
                    :ref="captureActiveEditor"
                    v-model="column.label"
                    size="small"
                    maxlength="100"
                    @blur="finishActiveEditor"
                    @keydown.enter.prevent="finishActiveEditor"
                    @keydown.esc.prevent="cancelActiveEditor"
                  />
                  <button
                    v-else-if="editing"
                    type="button"
                    class="editable-header"
                    @click="activateEditor(`column:${column.key}`, column.label, value => { column.label = value })"
                  >
                    {{ column.label || '点击填写' }}
                  </button>
                  <span v-else>{{ column.label }}</span>
                </template>
              </ConfiguredColumnHeaderFilter>
            </template>
            <template #default="{ row }">
              <el-input-number
                v-if="isActive(`row:${row.overviewKey}:count:${column.key}`)"
                :ref="captureActiveEditor"
                v-model="row.counts[column.key]"
                :controls="false"
                :min="0"
                :max="2147483647"
                :precision="0"
                size="small"
                @blur="finishActiveEditor"
                @keydown.enter.prevent="finishActiveEditor"
                @keydown.esc.prevent="cancelActiveEditor"
              />
              <button
                v-else-if="editing"
                type="button"
                class="editable-cell editable-cell--number"
                @click="activateEditor(`row:${row.overviewKey}:count:${column.key}`, row.counts[column.key], value => { row.counts[column.key] = value })"
              >
                {{ formatTalentCount(row.counts[column.key]) || '空' }}
              </button>
              <span v-else>{{ formatTalentCount(row.counts[column.key]) }}</span>
            </template>
          </el-table-column>
        </el-table-column>

        <el-table-column v-if="editing" width="98" fixed="right" align="center">
          <template #header>
            <el-button type="primary" link :icon="Plus" @click="openAddColumn">新增列</el-button>
          </template>
          <template #default><span class="structure-placeholder">—</span></template>
        </el-table-column>

        <el-table-column prop="rowTotal" label="合计" width="112" fixed="right" align="right" header-align="center">
          <template #header>
            <ConfiguredColumnHeaderFilter
              v-model="filterValues.rowTotal"
              :definition="rowTotalFilterDefinition"
              placement="bottom-end"
            />
          </template>
          <template #default="{ row }">{{ formatTalentCount(calculateTalentRowTotal(row, displayedColumns)) }}</template>
        </el-table-column>

        <template v-if="editing" #append>
          <button type="button" class="add-row-button" @click="addRow">
            <el-icon><Plus /></el-icon>
            新增行
          </button>
        </template>
      </el-table>
    </el-card>

    <DraggableFormDialog
      v-model="addColumnVisible"
      title="新增人才来源列"
      width="min(520px, calc(100vw - 32px))"
      :close-on-click-modal="false"
      @closed="resetAddColumnForm"
    >
      <AppForm ref="addColumnFormRef" :model="addColumnForm" :rules="addColumnRules" label-width="96px">
        <el-form-item label="列名称" prop="label">
          <el-input v-model="addColumnForm.label" maxlength="100" placeholder="请输入来源列名称" />
        </el-form-item>
        <el-form-item label="所属分组" prop="group">
          <el-radio-group v-model="addColumnForm.group">
            <el-radio value="sheet">人才资料表</el-radio>
            <el-radio value="wecom">企业微信</el-radio>
          </el-radio-group>
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="addColumnVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddColumn">确定</el-button>
      </template>
    </DraggableFormDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, FullScreen, Plus } from '@element-plus/icons-vue'
import AppForm from '@/components/common/AppForm.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getTalentOverview, saveTalentOverview } from '@/api/talents'
import TalentResourceNav from '@/views/resource/components/TalentResourceNav.vue'
import { hasPermission } from '@/utils/permission'
import { formatDateTimeMinute } from '@/utils/dateTime'
import {
  appendTalentOverviewColumn,
  appendTalentOverviewRow,
  calculateTalentColumnTotals,
  calculateTalentGrandTotal,
  calculateTalentRowTotal,
  cloneTalentOverview,
  filterTalentOverviewRows,
  formatTalentCount,
  normalizeTalentOverviewFilterValue,
  TALENT_OVERVIEW_BLANK_FILTER_VALUE,
} from '@/utils/talentOverview'

const overviewPanelRef = ref(null)
const overviewTableRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const tableRows = ref([])
const overviewColumns = ref([])
const draftRows = ref([])
const draftColumns = ref([])
const revision = ref(1)
const updatedAt = ref(null)
const updatedByName = ref('')
const draftBaseline = ref('')
const activeEditorKey = ref('')
const activeEditorOriginal = ref(null)
const activeEditorSetter = ref(null)
const activeEditorRef = ref(null)
const nativeFullscreen = ref(false)
const fallbackFullscreen = ref(false)
const addColumnVisible = ref(false)
const addColumnFormRef = ref(null)
const addColumnForm = reactive({ label: '', group: 'sheet' })
const filterValues = reactive({ language: [], updatedAt: [], rowTotal: [], counts: {} })

const groupLabels = { sheet: '人才资料表', wecom: '企业微信' }
const canWrite = computed(() => hasPermission(['talents:write', 'translators:write']))
const displayedRows = computed(() => editing.value ? draftRows.value : tableRows.value)
const displayedColumns = computed(() => editing.value ? draftColumns.value : overviewColumns.value)
const filteredRows = computed(() => filterTalentOverviewRows(
  displayedRows.value,
  displayedColumns.value,
  filterValues,
))
const columnGroups = computed(() => Object.entries(groupLabels).map(([key, label]) => ({
  key,
  label,
  columns: displayedColumns.value.filter(column => column.group === key),
})))
const draftSignature = computed(() => JSON.stringify({ columns: draftColumns.value, rows: draftRows.value }))
const isDirty = computed(() => editing.value && draftSignature.value !== draftBaseline.value)
const fullscreenActive = computed(() => nativeFullscreen.value || fallbackFullscreen.value)
const tableHeight = computed(() => fullscreenActive.value ? 'calc(100vh - 244px)' : 'calc(100vh - 246px)')
const liveColumnTotals = computed(() => calculateTalentColumnTotals(filteredRows.value, displayedColumns.value))
const liveGrandTotal = computed(() => calculateTalentGrandTotal(filteredRows.value, displayedColumns.value))
const hasActiveFilters = computed(() => (
  filterValues.language.length > 0
  || filterValues.updatedAt.length > 0
  || filterValues.rowTotal.length > 0
  || Object.values(filterValues.counts).some(values => values?.length)
))

function buildFilterOptions(values, formatter = value => String(value)) {
  const uniqueValues = new Map()
  values.forEach(value => {
    const normalized = normalizeTalentOverviewFilterValue(value)
    uniqueValues.set(`${typeof normalized}:${String(normalized)}`, normalized)
  })
  return [...uniqueValues.values()]
    .sort((left, right) => {
      if (left === TALENT_OVERVIEW_BLANK_FILTER_VALUE) return 1
      if (right === TALENT_OVERVIEW_BLANK_FILTER_VALUE) return -1
      if (typeof left === 'number' && typeof right === 'number') return left - right
      return String(left).localeCompare(String(right), 'zh-CN', { numeric: true })
    })
    .map(value => ({
      value,
      label: value === TALENT_OVERVIEW_BLANK_FILTER_VALUE ? '空白' : formatter(value),
    }))
}

const languageFilterDefinition = computed(() => ({
  key: 'language',
  label: '语种/方言',
  type: 'select',
  headerWidth: 300,
  options: buildFilterOptions(displayedRows.value.map(row => row.language)),
}))
const updatedAtFilterDefinition = computed(() => ({
  key: 'updatedAt',
  label: '更新日期',
  type: 'select',
  headerWidth: 280,
  options: buildFilterOptions(displayedRows.value.map(row => row.updatedAt)),
}))
const countFilterDefinitions = computed(() => Object.fromEntries(displayedColumns.value.map(column => [
  column.key,
  {
    key: column.key,
    label: column.label,
    type: 'select',
    headerWidth: 260,
    options: buildFilterOptions(
      displayedRows.value.map(row => row.counts?.[column.key]),
      formatTalentCount,
    ),
  },
])))
const rowTotalFilterDefinition = computed(() => ({
  key: 'rowTotal',
  label: '合计',
  type: 'select',
  headerWidth: 260,
  options: buildFilterOptions(
    displayedRows.value.map(row => calculateTalentRowTotal(row, displayedColumns.value)),
    formatTalentCount,
  ),
}))

const addColumnRules = {
  label: [
    { required: true, message: '请输入列名称', trigger: 'blur' },
    { max: 100, message: '列名称不能超过 100 个字符', trigger: 'blur' },
  ],
  group: [{ required: true, message: '请选择所属分组', trigger: 'change' }],
}

function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, character => {
    const random = Math.random() * 16 | 0
    return (character === 'x' ? random : (random & 0x3 | 0x8)).toString(16)
  })
}

function todayValue() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date()).filter(item => item.type !== 'literal').map(item => [item.type, item.value]))
  return `${parts.year}-${parts.month}-${parts.day}`
}

function applyOverview(result) {
  overviewColumns.value = result.columns || []
  tableRows.value = result.rows || []
  revision.value = result.revision || 1
  updatedAt.value = result.updatedAt || null
  updatedByName.value = result.updatedByName || ''
}

async function fetchOverview() {
  loading.value = true
  try {
    applyOverview(await getTalentOverview())
  } catch (error) {
    ElMessage.error(error?.detail || '人才概览加载失败')
  } finally {
    loading.value = false
  }
}

function startEditing() {
  const cloned = cloneTalentOverview(overviewColumns.value, tableRows.value)
  draftColumns.value = cloned.columns
  draftRows.value = cloned.rows
  draftBaseline.value = JSON.stringify(cloned)
  editing.value = true
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前人才概览存在未保存修改，确定放弃吗？', '未保存修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑',
    })
    return true
  } catch {
    return false
  }
}

async function cancelEditing() {
  if (!await confirmDiscard()) return
  finishActiveEditor()
  editing.value = false
  draftColumns.value = []
  draftRows.value = []
}

function validateDraft() {
  const columns = draftColumns.value.map(column => column.label.trim())
  const languages = draftRows.value.map(row => row.language.trim())
  if (columns.some(label => !label)) return '来源列名称不能为空'
  if (languages.some(label => !label)) return '语种/方言不能为空'
  if (new Set(columns.map(label => label.toLocaleLowerCase())).size !== columns.length) return '来源列名称不能重复'
  if (new Set(languages.map(label => label.toLocaleLowerCase())).size !== languages.length) return '语种/方言名称不能重复'
  draftColumns.value.forEach((column, index) => { column.label = columns[index] })
  draftRows.value.forEach((row, index) => { row.language = languages[index] })
  return ''
}

async function saveOverview() {
  finishActiveEditor()
  const validationError = validateDraft()
  if (validationError) return ElMessage.warning(validationError)
  saving.value = true
  try {
    const result = await saveTalentOverview({
      expectedRevision: revision.value,
      columns: draftColumns.value,
      rows: draftRows.value,
    })
    applyOverview(result)
    editing.value = false
    draftColumns.value = []
    draftRows.value = []
    ElMessage.success('人才概览已保存')
  } catch (error) {
    if (error?.response?.status === 409) {
      try {
        await ElMessageBox.confirm(
          '人才概览已被其他人更新。重新加载会放弃当前草稿，是否加载最新数据？',
          '保存冲突',
          { type: 'warning', confirmButtonText: '重新加载', cancelButtonText: '保留草稿' },
        )
        editing.value = false
        await fetchOverview()
      } catch {
        // 用户选择保留当前草稿，便于人工核对后再处理。
      }
    } else {
      ElMessage.error(error?.detail || '人才概览保存失败')
    }
  } finally {
    saving.value = false
  }
}

function isActive(key) {
  return activeEditorKey.value === key
}

function activateEditor(key, value, setter) {
  if (!editing.value) return
  finishActiveEditor()
  activeEditorKey.value = key
  activeEditorOriginal.value = value
  activeEditorSetter.value = setter
  nextTick(() => activeEditorRef.value?.focus?.())
}

function captureActiveEditor(element) {
  if (element) activeEditorRef.value = element
}

function finishActiveEditor() {
  activeEditorKey.value = ''
  activeEditorOriginal.value = null
  activeEditorSetter.value = null
  activeEditorRef.value = null
}

function cancelActiveEditor() {
  activeEditorSetter.value?.(activeEditorOriginal.value)
  finishActiveEditor()
}

function openAddColumn() {
  finishActiveEditor()
  addColumnVisible.value = true
}

function resetAddColumnForm() {
  Object.assign(addColumnForm, { label: '', group: 'sheet' })
  addColumnFormRef.value?.clearValidate?.()
}

async function confirmAddColumn() {
  const valid = await addColumnFormRef.value?.validate().catch(() => false)
  if (!valid) return
  const label = addColumnForm.label.trim()
  if (draftColumns.value.some(column => column.label.trim().toLocaleLowerCase() === label.toLocaleLowerCase())) {
    return ElMessage.warning('来源列名称不能重复')
  }
  const next = appendTalentOverviewColumn(draftColumns.value, draftRows.value, {
    key: `col-${uuid()}`,
    label,
    group: addColumnForm.group,
    width: 120,
  })
  draftColumns.value = next.columns
  draftRows.value = next.rows
  addColumnVisible.value = false
}

function clearOverviewFilters() {
  filterValues.language = []
  filterValues.updatedAt = []
  filterValues.rowTotal = []
  filterValues.counts = {}
}

async function addRow() {
  finishActiveEditor()
  const overviewKey = `row-${uuid()}`
  draftRows.value = appendTalentOverviewRow(draftRows.value, draftColumns.value, {
    overviewKey,
    language: '',
    aliases: [],
    updatedAt: todayValue(),
  })
  if (!filteredRows.value.some(row => row.overviewKey === overviewKey)) clearOverviewFilters()
  await nextTick()
  overviewTableRef.value?.setScrollTop?.(Number.MAX_SAFE_INTEGER)
  activateEditor(
    `row:${overviewKey}:language`,
    '',
    value => {
      const row = draftRows.value.find(item => item.overviewKey === overviewKey)
      if (row) row.language = value
    },
  )
}

function summaryMethod({ columns }) {
  return columns.map(column => {
    if (column.property === 'language') return '合计'
    if (column.property === 'updatedAt') return ''
    if (column.property === 'rowTotal') return formatTalentCount(liveGrandTotal.value)
    const key = column.property?.replace(/^counts\./, '')
    return key && displayedColumns.value.some(item => item.key === key)
      ? formatTalentCount(liveColumnTotals.value[key])
      : ''
  })
}

async function toggleFullscreen() {
  if (fallbackFullscreen.value) {
    fallbackFullscreen.value = false
    return
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen()
    return
  }
  if (!overviewPanelRef.value?.requestFullscreen) {
    fallbackFullscreen.value = true
    return
  }
  try {
    await overviewPanelRef.value.requestFullscreen()
    if (!document.fullscreenElement) fallbackFullscreen.value = true
  } catch {
    fallbackFullscreen.value = true
  }
}

function handleFullscreenChange() {
  nativeFullscreen.value = document.fullscreenElement === overviewPanelRef.value
}

function handleKeydown(event) {
  if (event.key === 'Escape' && fallbackFullscreen.value) fallbackFullscreen.value = false
}

function handleBeforeUnload(event) {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(async () => await confirmDiscard())

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener('beforeunload', handleBeforeUnload)
  fetchOverview()
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.talent-overview-panel {
  min-height: 0;
  background: var(--el-bg-color-page);
}

.card-header,
.header-actions {
  display: flex;
  align-items: center;
}

.card-header {
  justify-content: space-between;
  gap: 16px;
}

.title-block {
  min-width: 0;
}

.header-actions {
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.header-actions .el-button + .el-button {
  margin-left: 0;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle,
.update-meta {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.update-meta {
  padding-left: 12px;
  border-left: 1px solid var(--el-border-color);
}

.overview-note {
  margin-bottom: 12px;
  padding: 9px 12px;
  border: 1px solid var(--el-color-info-light-7);
  border-radius: var(--el-border-radius-base);
  background: var(--el-color-info-light-9);
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}

.overview-table {
  min-height: 360px;
}

.overview-table :deep(.el-table__header-wrapper th) {
  background: var(--el-fill-color-light);
}

.overview-table :deep(.el-table__header-wrapper .cell) {
  white-space: normal;
  line-height: 1.35;
}

.overview-table :deep(.el-table__footer-wrapper td) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.editable-cell,
.editable-header,
.add-row-button {
  width: 100%;
  border: 1px dashed transparent;
  background: transparent;
  color: inherit;
  cursor: text;
  font: inherit;
}

.editable-cell {
  min-height: 28px;
  padding: 4px 7px;
  border-radius: var(--el-border-radius-small);
}

.editable-cell:hover,
.editable-header:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.editable-cell--text {
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editable-cell--center {
  text-align: center;
}

.editable-cell--number {
  text-align: right;
}

.editable-header {
  min-height: 30px;
  padding: 3px 5px;
  border-radius: var(--el-border-radius-small);
  text-align: center;
}

.overview-table :deep(.el-input-number),
.overview-table :deep(.el-date-editor.el-input) {
  width: 100%;
}

.structure-placeholder {
  color: var(--el-text-color-placeholder);
}

.add-row-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 42px;
  border-color: var(--el-border-color);
  color: var(--el-color-primary);
  cursor: pointer;
}

.add-row-button:hover {
  background: var(--el-color-primary-light-9);
}

.talent-overview-panel:fullscreen,
.talent-overview-panel.is-fallback-fullscreen {
  width: 100vw;
  height: 100vh;
  min-height: 100vh;
  padding: 16px;
  overflow: hidden;
  background: var(--el-bg-color-page);
}

.talent-overview-panel.is-fallback-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 3000;
}

.talent-overview-panel:fullscreen .talent-overview-card,
.talent-overview-panel.is-fallback-fullscreen .talent-overview-card {
  height: 100%;
}

@media (max-width: 768px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .page-subtitle,
  .update-meta {
    display: block;
    margin: 4px 0 0;
    padding-left: 0;
    border-left: 0;
  }

  .overview-note {
    font-size: 12px;
  }

  .talent-overview-panel:fullscreen,
  .talent-overview-panel.is-fallback-fullscreen {
    padding: 8px;
  }
}
</style>
