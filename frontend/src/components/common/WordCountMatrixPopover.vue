<template>
  <el-popover :title="title"
    ref="popoverRef"
    v-model:visible="visible"
    trigger="click"
    placement="bottom-end"
    width="min(960px, calc(100vw - 32px))"
    popper-class="word-count-matrix-popper"
    :teleported="true"
    :popper-options="popperOptions"
    @show="loadMatrix"
    @hide="suspendDraft"
  >
    <template #reference>
      <slot name="reference" :summary="summary">
        <el-button type="primary" link>字数统计</el-button>
      </slot>
    </template>

    <div class="word-count-matrix" data-auto-draft="off">
      <el-alert v-if="Object.keys(draft?.simpleRequirementWordCountMatrix||{}).length" type="info" :closable="false" :title="'本单统计已加入简单需求字数：'+formatWordCountMatrix(draft.simpleRequirementWordCountMatrix)" />
      <div class="word-count-matrix__header">
        <div>

          <strong>{{ readOnly ? '当前统计仅供查看' : '填写当前订单的统计数量' }}</strong>
          <p>母订单与各级子订单独立填报，不再自动汇总或相互覆盖。{{ readOnly ? '当前入口为只读视图。' : '我司统计、客户统计每行仅填写一种口径；可点击“清空本行”重新选择。空白表示未填写，0 表示数量为零。' }}</p>
        </div>
        <el-tag size="small" :type="hasChanges ? 'warning' : 'info'">{{ hasChanges ? '未保存修改' : (readOnly ? '只读' : (localMode ? '随项目保存' : '本单独立统计')) }}</el-tag>
      </div>

      <el-alert v-if="hasDuration" title="本项目可能属于标注项目，请与标注项目部沟通。" type="warning" :closable="false" show-icon />
      <div ref="matrixBody" v-loading="loading" class="word-count-matrix__body">
        <table>
          <thead>
            <tr>
              <th class="word-count-matrix__row-title">统计维度</th>
              <th v-for="metric in regularMetrics" :key="metric.key">{{ metric.label }}</th>
              <th>分钟／小时</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.key">
              <th class="word-count-matrix__row-title">
                <span>{{ row.label }}</span>
                <small v-if="row.hint">{{ row.hint }}</small>
                <small v-if="rowReadonly(row)">只读</small>
                <template v-else>
                  <small>{{ rowMetricHint(row) }}</small>
                  <el-button v-if="rowHasValues(row)" link type="primary" size="small" @click="clearRow(row)">清空本行</el-button>
                </template>
              </th>
              <td
                v-for="metric in regularMetrics"
                :key="metric.key"
                :data-word-count-cell="`${row.key}-${metric.key}`"
                :class="{ 'is-word-count-target': row.scope === 'entity' && row.dimension === initialDimension && metric.key === initialMetricType }"
              >
                <ReadonlyField
                  v-if="cellDisabled(row, metric.key)"
                  :model-value="row.values[metric.key] ?? ''"
                  :source="rowReadonly(row) ? 'auto' : 'locked'"
                  :placeholder="rowReadonly(row) ? '—' : '已锁定'"
                  :tooltip="cellHint(row)"
                  :aria-label="`${row.label}-${metric.label}`"
                  size="small"
                />
                <el-input-number
                  v-else
                  :key="`${row.key}-${metric.key}-${cellDisabled(row,metric.key)}`"
                  v-model="row.values[metric.key]"
                  :disabled="cellDisabled(row,metric.key)"
                  size="small"
                  :min="0"
                  :step="1"
                  :precision="0"
                  :controls="false"
                  :aria-label="`${row.label}-${metric.label}`"
                  placeholder="填写数量"
                />
              </td>
              <td class="word-count-time-cell">
                <template v-if="cellDisabled(row,timeMetric(row))">
                  <small class="word-count-time-unit">{{ timeMetric(row) === 'hours' ? '小时' : '分钟' }}</small>
                  <ReadonlyField :model-value="row.values[timeMetric(row)] ?? ''" :source="rowReadonly(row) ? 'auto' : 'locked'" :placeholder="rowReadonly(row) ? '—' : '已锁定'" :tooltip="cellHint(row)" size="small" :aria-label="`${row.label}-时长`" />
                </template>
                <template v-else>
                  <select :value="timeMetric(row)" :aria-label="`${row.label}-时长单位`" @change="changeTimeUnit(row,$event.target.value)"><option value="minutes">分钟</option><option value="hours">小时</option></select>
                  <el-input-number v-model="row.values[timeMetric(row)]" :min="0" :precision="4" :controls="false" placeholder="填写时长" size="small" :aria-label="`${row.label}-时长`" />
                </template>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td :colspan="WORD_COUNT_METRICS.length + 1" class="word-count-matrix__empty">暂无可编辑的字数维度</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="word-count-matrix__footer">
        <span>{{ !hasEditableRows ? '只读视图，无需保存。' : (hybridMode ? '项目统计立即保存；新译员统计随稿件安排保存' : (localMode ? '统计随项目保存；关闭后保留本账号未保存的修改' : '仅保存当前订单；未保存的修改仅当前账号可见')) }}</span>
        <div>
          <el-button @click="visible = false">关闭</el-button>
          <el-button v-if="hasEditableRows" type="primary" :loading="saving" :disabled="loading || !draft" @click="saveMatrix">
            保存
          </el-button>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ReadonlyField from './ReadonlyField.vue'
import { getWordCountMatrix, patchWordCountMatrix } from '@/api/wordCountMatrices'
import { focusFormTarget, scrollFormTarget } from '@/utils/formNavigation'
import { useFormDraft } from '@/composables/useFormDraft'
import {
  WORD_COUNT_METRICS,
  createEmptyWordCountMatrix,
  formatWordCountMatrix,
  normalizeWordCountMatrix,
  normalizeWordCountValues
} from '@/utils/wordCountMatrix'

const props = defineProps({
  entityType: { type: String, default: 'project' },
  entityId: { type: [String, Number], default: '' },
  dispatchId: { type: [String, Number], default: '' },
  local: { type: Boolean, default: false },
  translators: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => createEmptyWordCountMatrix() },
  title: { type: String, default: '字数统计' },
  initialDimension: { type: String, default: '' },
  initialMetricType: { type: String, default: '' },
  readOnly: { type: Boolean, default: false },
  pendingDraft: { type: Object, default: undefined },
  draftScope: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'update:translators', 'saved', 'update:pendingDraft'])
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const draftState = reactive({ matrix: null, baseline: null })
const draft = toRef(draftState, 'matrix')
const original = ref(null)
const matrixBody = ref(null)
const popoverRef = ref(null)
const popperOptions = {
  modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }]
}
let loadSequence = 0
let matrixOwner = ''
const editing = ref(false)
const controlledDraft = computed(() => props.pendingDraft !== undefined)
const scopeKey = () => JSON.stringify([props.draftScope || location.pathname, props.entityType, props.entityId || 'create', props.dispatchId || '', props.local ? 'local' : 'record'])
const validPending = value => value?.version === 'word-count-matrix-v2' && value.ownerId === localStorage.getItem('user_id') && value.scope === scopeKey() && value.matrix && value.baseline
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({
  namespace:'word-count-matrix',form:draftState,requireUserId:true,retentionMs:null,draftVersion:'word-count-matrix-v2',
  createDefault:()=>({matrix:null,baseline:null}),
  applyDraft:snapshot=>{
    if(!snapshot.matrix||!snapshot.baseline||!original.value)return
    draft.value=rebaseDraft(snapshot.baseline,snapshot.matrix,original.value)
    draftState.baseline=clone(original.value)
  },
})
const localMode = computed(() => props.local || !props.entityId)
const hybridMode = computed(() => localMode.value && Boolean(props.entityId))
const summary = computed(() => formatWordCountMatrix(props.modelValue))
const hasChanges = computed(() => Boolean(draft.value && original.value && buildChanges().length))
const regularMetrics=WORD_COUNT_METRICS.filter(item=>!['minutes','hours'].includes(item.key))
const timeUnits=ref({})
const hasDuration=computed(()=>rows.value.some(row=>row.values.minutes!=null||row.values.hours!=null))
function timeMetric(row){return row.values.hours!=null?'hours':row.values.minutes!=null?'minutes':timeUnits.value[row.key]||'minutes'}
function cellDisabled(row,key){return props.readOnly||(row.scope==='entity'&&['company','customer'].includes(row.dimension)&&row.values[key]==null&&WORD_COUNT_METRICS.some(item=>item.key!==key&&row.values[item.key]!=null))}
const rowReadonly = () => props.readOnly
const rowHasValues = row => WORD_COUNT_METRICS.some(({ key }) => row.values[key] != null)
const rowMetricHint = row => row.scope === 'entity' && ['company', 'customer'].includes(row.dimension) ? '单一口径' : '可填写多项'
const cellHint = row => rowReadonly(row) ? '当前入口仅可查看' : '本行已填写其他统计口径，请先点击“清空本行”'
function clearRow(row) {
  if (rowReadonly(row)) return
  WORD_COUNT_METRICS.forEach(({ key }) => { row.values[key] = null })
}
function changeTimeUnit(row,unit){const previous=timeMetric(row),value=row.values[previous];row.values[previous]=null;timeUnits.value[row.key]=unit;if(value!=null)row.values[unit]=Number((unit==='hours'?value/60:value*60).toFixed(4))}

const clone = (value) => JSON.parse(JSON.stringify(value))

function normalizeResponse(data = {}) {
  return {
    simpleRequirementWordCountMatrix:data.simple_requirement_word_count_matrix||data.simpleRequirementWordCountMatrix||{},
    entity_type: data.entity_type || props.entityType,
    entity_id: data.entity_id || props.entityId,
    source: data.source,
    company: normalizeWordCountValues(data.company),
    customer: normalizeWordCountValues(data.customer),
    preliminary: normalizeWordCountValues(data.preliminary),
    translator_estimate: normalizeWordCountValues(data.translator_estimate || data.translatorEstimate),
    translators: (data.translators || []).map((item) => ({
      ...item,
      planned: normalizeWordCountValues(item.planned),
      actual: normalizeWordCountValues(item.actual)
    }))
  }
}

function normalizeLocalTranslators(items = []) {
  return items.map((item) => ({
    arrangement_id: item.arrangement_id || item.id || item.translator_id,
    translator_id: item.translator_id,
    translator_name: item.translator_name || item.translator_name_snapshot,
    planned: normalizeWordCountValues(item.planned),
    actual: normalizeWordCountValues(item.actual)
  }))
}

const rows = computed(() => {
  if (!draft.value) return []
  const result = [
    { key: 'entity-company', scope: 'entity', dimension: 'company', label: '我司统计', values: draft.value.company },
    { key: 'entity-customer', scope: 'entity', dimension: 'customer', label: '客户统计', values: draft.value.customer },
    { key: 'entity-preliminary', scope: 'entity', dimension: 'preliminary', label: '预统计', hint: '不用以计算费用', values: draft.value.preliminary },
    { key: 'entity-estimate', scope: 'entity', dimension: 'translator_estimate', label: '译员预定（项目预估）', hint: '尚未分配具体译员时使用', values: draft.value.translator_estimate }
  ]
  draft.value.translators.forEach((translator) => {
    const name = translator.translator_name || '当前译员'
    result.push(
      { key: `${translator.arrangement_id}-planned`, scope: 'translator', arrangementId: translator.arrangement_id, dimension: 'planned', label: `${name} · 预定`, values: translator.planned },
      { key: `${translator.arrangement_id}-actual`, scope: 'translator', arrangementId: translator.arrangement_id, dimension: 'actual', label: `${name} · 实际`, values: translator.actual }
    )
  })
  return result
})
const hasEditableRows = computed(() => rows.value.some(row => !rowReadonly(row)))

async function loadMatrix() {
  editing.value = false
  pauseDraft()
  matrixOwner = localStorage.getItem('user_id') || ''
  const sequence = ++loadSequence
  loading.value = true
  try {
    if (localMode.value) {
      const local = normalizeWordCountMatrix(props.modelValue)
      draft.value = normalizeResponse({
        ...local,
        translator_estimate: local.translatorEstimate,
        translators: normalizeLocalTranslators(props.translators)
      })
    } else {
      const params = props.dispatchId ? { dispatch_id: props.dispatchId } : {}
      const response = await getWordCountMatrix(props.entityType, props.entityId, params)
      if (sequence !== loadSequence || !visible.value || matrixOwner !== (localStorage.getItem('user_id') || '')) return
      draft.value = normalizeResponse(response)
      publishMatrix(draft.value)
    }
    original.value = clone(draft.value)
    draftState.baseline = clone(original.value)
    if (!props.readOnly && matrixOwner) {
      if (controlledDraft.value) {
        if (validPending(props.pendingDraft)) draft.value = rebaseDraft(props.pendingDraft.baseline, props.pendingDraft.matrix, original.value)
      } else await beginDraft(scopeKey())
    }
  } catch (error) {
    if (sequence !== loadSequence) return
    ElMessage.error(error.detail || '加载字数统计失败')
    visible.value = false
  } finally {
    if (sequence === loadSequence) { loading.value = false; editing.value = !props.readOnly && visible.value }
  }
  if (sequence === loadSequence && visible.value) await focusInitialCell()
}

async function focusInitialCell() {
  await nextTick()
  // 异步加载后表格高度会变化，重新定位并把操作栏限制在视口内。
  await popoverRef.value?.popperRef?.popperInstanceRef?.update()
  const body = matrixBody.value
  const target = body?.querySelector('.is-word-count-target')
  if (!visible.value || !target) return
  // 复用公共字段导航；横向定位只滚动统计表，不带动外层长表单。
  if (body.scrollHeight > body.clientHeight) scrollFormTarget(target, body)
  if (body.scrollWidth > body.clientWidth) {
    const bodyRect = body.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    body.scrollTo({ left: Math.max(0, body.scrollLeft + targetRect.left - bodyRect.left - (body.clientWidth - targetRect.width) / 2) })
  }
  if (!props.readOnly) focusFormTarget(target)
}

function suspendDraft() {
  pauseDraft()
  editing.value = false
  timeUnits.value={}
  loadSequence += 1
  draft.value = null
  original.value = null
  loading.value = false
}

function buildChanges(beforeMatrix = original.value, afterMatrix = draft.value) {
  if (!beforeMatrix || !afterMatrix) return []
  const beforeRows = new Map()
  const buildRows = (matrix) => {
    const result = [
      { key: 'entity-company', scope: 'entity', dimension: 'company', values: matrix.company },
      { key: 'entity-customer', scope: 'entity', dimension: 'customer', values: matrix.customer },
      { key: 'entity-preliminary', scope: 'entity', dimension: 'preliminary', values: matrix.preliminary },
      { key: 'entity-estimate', scope: 'entity', dimension: 'translator_estimate', values: matrix.translator_estimate }
    ]
    matrix.translators.forEach((item) => {
      result.push(
        { key: `${item.arrangement_id}-planned`, scope: 'translator', arrangementId: item.arrangement_id, dimension: 'planned', values: item.planned },
        { key: `${item.arrangement_id}-actual`, scope: 'translator', arrangementId: item.arrangement_id, dimension: 'actual', values: item.actual }
      )
    })
    return result
  }
  buildRows(beforeMatrix).forEach((row) => beforeRows.set(row.key, row))
  const changes = []
  buildRows(afterMatrix).forEach((row) => {
    const before = beforeRows.get(row.key)?.values || {}
    WORD_COUNT_METRICS.forEach(({ key }) => {
      const value = row.values[key] === '' || row.values[key] === undefined ? null : row.values[key]
      const previous = before[key] === '' || before[key] === undefined ? null : before[key]
      if (value !== previous) {
        changes.push({
          scope: row.scope,
          dimension: row.dimension,
          metric_type: key,
          value,
          arrangement_id: row.arrangementId || null
        })
      }
    })
  })
  return changes
}

function rebaseDraft(before, edited, current) {
  const result = clone(current)
  for (const change of buildChanges(normalizeResponse(before), normalizeResponse(edited))) {
    if (change.scope === 'entity') {
      result[change.dimension][change.metric_type] = change.value
    } else {
      const translator = result.translators.find(item => item.arrangement_id === change.arrangement_id)
      if (translator) translator[change.dimension][change.metric_type] = change.value
    }
  }
  return result
}

function publishMatrix(matrix) {
  emit('update:modelValue', {
    company: clone(matrix.company), customer: clone(matrix.customer), preliminary: clone(matrix.preliminary),
    translatorEstimate: clone(matrix.translator_estimate)
  })
}
function clearPending() {
  editing.value = false
  clearDraft()
  if (controlledDraft.value) emit('update:pendingDraft', null)
}
function validateMatrix(matrix) {
  for (const dimension of ['company','customer']) {
    if (WORD_COUNT_METRICS.filter(item=>matrix?.[dimension]?.[item.key]!=null).length>1) {
      ElMessage.warning(`${dimension==='company'?'我司统计':'客户统计'}只能填写一个统计字段，请先清空其他字段`)
      return false
    }
  }
  return true
}
// 外层保存新项目时，同步提交尚未点击统计弹窗“保存”的本账号输入。
function prepareSubmit() {
  if (!controlledDraft.value || !validPending(props.pendingDraft)) return true
  const matrix = normalizeResponse(props.pendingDraft.matrix)
  if (!validateMatrix(matrix)) return false
  publishMatrix(matrix)
  return true
}
watch([draftState, editing], () => {
  if (!controlledDraft.value || !editing.value || loading.value || !draft.value || !matrixOwner || matrixOwner !== localStorage.getItem('user_id')) return
  const pending = hasChanges.value ? { version:'word-count-matrix-v2', ownerId:matrixOwner, scope:scopeKey(), matrix:clone(draft.value), baseline:clone(original.value) } : null
  if (JSON.stringify(pending) !== JSON.stringify(props.pendingDraft)) emit('update:pendingDraft', pending)
}, {deep:true,flush:'sync'})
watch(()=>props.pendingDraft, pending=>{
  if(editing.value && !hasChanges.value && validPending(pending)) draft.value=rebaseDraft(pending.baseline,pending.matrix,original.value)
}, {deep:true})
watch(()=>[props.entityType,props.entityId,props.dispatchId],()=>{if(visible.value){suspendDraft();visible.value=false}})
const closeForAccountChange=()=>{suspendDraft();visible.value=false}
const accountStorageChanged=event=>{if(event.key==='user_id' && matrixOwner !== (localStorage.getItem('user_id')||''))closeForAccountChange()}
window.addEventListener('auth-session-clearing',closeForAccountChange)
window.addEventListener('storage',accountStorageChanged)
onBeforeUnmount(()=>{loadSequence++;pauseDraft();window.removeEventListener('auth-session-clearing',closeForAccountChange);window.removeEventListener('storage',accountStorageChanged)})
defineExpose({prepareSubmit})

async function saveMatrix() {
  if(matrixOwner !== (localStorage.getItem('user_id')||'')){visible.value=false;return}
  if (!draft.value) return
  if (!validateMatrix(draft.value)) return
  if (localMode.value) {
    if (saving.value) return
    saving.value = true
    try {
      let saved = clone(draft.value)
      if (hybridMode.value) {
        const entityChanges = buildChanges().filter((change) => change.scope === 'entity')
        if (entityChanges.length) {
          saved = normalizeResponse(
            await patchWordCountMatrix(props.entityType, props.entityId, { changes: entityChanges })
          )
          saved.translators = clone(draft.value.translators)
        }
      }
      emit('update:modelValue', {
        company: clone(saved.company),
        customer: clone(saved.customer),
        preliminary: clone(saved.preliminary),
        translatorEstimate: clone(saved.translator_estimate)
      })
      emit('update:translators', props.translators.map((item) => {
        const key = item.arrangement_id || item.id || item.translator_id
        const edited = draft.value.translators.find((row) => row.arrangement_id === key)
        return edited ? { ...item, planned: clone(edited.planned), actual: clone(edited.actual) } : item
      }))
      emit('saved', saved)
      clearPending()
      ElMessage.success(hybridMode.value ? '项目字数已保存，译员字数已带回稿件安排' : '字数统计已保存到当前项目表单')
      visible.value = false
    } catch (error) {
      ElMessage.error(error.detail || '保存字数统计失败')
    } finally {
      saving.value = false
    }
    return
  }
  const changes = buildChanges()
  if (!changes.length) {
    clearPending()
    visible.value = false
    return
  }
  if (saving.value) return
  saving.value = true
  try {
    const params = props.dispatchId ? { dispatch_id: props.dispatchId } : {}
    const saved = normalizeResponse(await patchWordCountMatrix(props.entityType, props.entityId, { changes }, params))
    emit('update:modelValue', {
      company: saved.company,
      customer: saved.customer,
      preliminary: saved.preliminary,
      translatorEstimate: saved.translator_estimate
    })
    emit('saved', saved)
    clearPending()
    ElMessage.success('字数统计已保存')
    visible.value = false
  } catch (error) {
    ElMessage.error(error.detail || '保存字数统计失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.word-count-matrix { display: flex; flex-direction: column; gap: 14px; max-height: min(680px, calc(100vh - 120px)); }
.word-count-matrix__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; background: var(--el-fill-color-lighter); }
.word-count-matrix__header strong { font-size: 14px; color: var(--el-text-color-primary); }
.word-count-matrix__header p { max-width: 680px; margin: 6px 0 0; color: var(--el-text-color-regular); font-size: 12px; line-height: 1.7; }
.word-count-matrix__header .el-tag { flex-shrink: 0; }
.word-count-matrix__body { flex: 1; min-height: 120px; overflow: auto; border: 1px solid var(--el-border-color); border-radius: 8px; }
table { width: 100%; min-width: 880px; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
th, td { padding: 10px 6px; border-right: 1px solid var(--el-border-color-lighter); border-bottom: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); vertical-align: middle; }
thead th { position: sticky; top: 0; z-index: 2; padding: 12px 6px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
tr:last-child th, tr:last-child td { border-bottom: 0; }
th:last-child, td:last-child { border-right: 0; }
.word-count-matrix__row-title { width: 166px; padding: 12px; text-align: left; background: var(--el-fill-color-lighter); line-height: 1.5; }
.word-count-matrix__row-title span { display: block; color: var(--el-text-color-primary); font-size: 13px; }
.word-count-matrix__row-title small { display: block; margin-top: 4px; color: var(--el-text-color-secondary); font-size: 11px; font-weight: 400; }
.word-count-time-cell select { width: 100%; height: 28px; margin-bottom: 6px; border: 1px solid var(--el-border-color); border-radius: 6px; background: #fff; color: var(--el-text-color-regular); }
.word-count-time-unit { display: block; margin-bottom: 6px; text-align: center; color: var(--el-text-color-secondary); }
td :deep(.el-input-number) { width: 100%; }
td :deep(.el-input__wrapper) { min-height: 32px; padding: 0 6px; border-radius: 6px; }
.is-word-count-target :deep(.el-input__wrapper) { box-shadow: inset 0 0 0 2px var(--el-color-primary); }
.word-count-matrix__empty { padding: 28px; text-align: center; color: var(--el-text-color-secondary); }
.word-count-matrix__footer { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
.word-count-matrix__footer > span { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.word-count-matrix__footer > div { display: flex; flex-shrink: 0; }
@media (max-width: 600px) {
  .word-count-matrix__header { flex-direction: column; gap: 8px; padding: 10px; }
}
</style>

<style>
.word-count-matrix-popper { max-width: calc(100vw - 32px) !important; padding: 16px !important; }
.word-count-matrix-popper .app-window-popover__body { display: flex; overflow: hidden; padding-top: 12px; }
.word-count-matrix-popper .word-count-matrix { flex: 1; min-width: 0; min-height: 0; max-height: min(680px, calc(100vh - 120px)) !important; }
</style>
