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
    @hide="discardDraft"
  >
    <template #reference>
      <slot name="reference" :summary="summary">
        <el-button type="primary" link>字数统计</el-button>
      </slot>
    </template>

    <div class="word-count-matrix">
      <div class="word-count-matrix__header">
        <div>

          <p>{{ aggregated ? '此订单各单位分别由子订单逐级累计，可同时出现字数、份数等多项；请在末级订单填写。' : '我司统计、客户统计每行只能填写一项；清空已填项后可切换口径。空白不保存，零视为已填写。' }}</p>
        </div>
        <el-tag size="small" type="info">{{ aggregated ? '下级自动汇总' : (hybridMode ? '项目保存 / 译员草稿' : (localMode ? '新建草稿' : '独立保存')) }}</el-tag>
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
              </th>
              <td
                v-for="metric in regularMetrics"
                :key="metric.key"
                :data-word-count-cell="`${row.key}-${metric.key}`"
                :class="{ 'is-word-count-target': row.scope === 'entity' && row.dimension === initialDimension && metric.key === initialMetricType }"
              >
                <el-input-number
                  v-model="row.values[metric.key]"
                  :disabled="cellDisabled(row,metric.key)"
                  size="small"
                  :min="0"
                  :step="1"
                  :precision="0"
                  :controls="false"
                  :aria-label="`${row.label}-${metric.label}`"
                />
                <small v-if="aggregated&&row.scope==='entity'&&row.values[metric.key]!=null" class="word-count-source">子订单累计</small>
              </td>
              <td class="word-count-time-cell">
                <select :value="timeMetric(row)" :disabled="cellDisabled(row,timeMetric(row))" :aria-label="`${row.label}-时长单位`" @change="changeTimeUnit(row,$event.target.value)"><option value="minutes">分钟</option><option value="hours">小时</option></select>
                <el-input-number v-model="row.values[timeMetric(row)]" :disabled="cellDisabled(row,timeMetric(row))" :min="0" :precision="4" :controls="false" size="small" :aria-label="`${row.label}-时长`" /><small v-if="aggregated&&row.scope==='entity'&&row.values[timeMetric(row)]!=null" class="word-count-source">子订单累计</small>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td :colspan="WORD_COUNT_METRICS.length + 1" class="word-count-matrix__empty">暂无可编辑的字数维度</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="word-count-matrix__footer">
        <span>{{ hybridMode ? '项目级数据立即保存；新译员数据随外层表单提交' : (localMode ? '应用后仍需保存外层表单' : '保存后立即同步到项目详情与稿件安排') }}</span>
        <div>
          <el-button @click="visible = false">取消</el-button>
          <el-button v-if="!readOnly" type="primary" :loading="saving" :disabled="loading || !draft" @click="saveMatrix">
            {{ hybridMode ? '保存并应用' : (localMode ? '应用到新建表单' : '保存') }}
          </el-button>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getWordCountMatrix, patchWordCountMatrix } from '@/api/wordCountMatrices'
import { focusFormTarget, scrollFormTarget } from '@/utils/formNavigation'
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
  readOnly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'update:translators', 'saved'])
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const draft = ref(null)
const original = ref(null)
const matrixBody = ref(null)
const popoverRef = ref(null)
const popperOptions = {
  modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }]
}
let loadSequence = 0
const localMode = computed(() => props.local || !props.entityId)
const hybridMode = computed(() => localMode.value && Boolean(props.entityId))
const summary = computed(() => formatWordCountMatrix(props.modelValue))
const aggregated = computed(() => draft.value?.source === 'suborder_aggregate')
const regularMetrics=WORD_COUNT_METRICS.filter(item=>!['minutes','hours'].includes(item.key))
const timeUnits=ref({})
const hasDuration=computed(()=>rows.value.some(row=>row.values.minutes!=null||row.values.hours!=null))
function timeMetric(row){return row.values.hours!=null?'hours':row.values.minutes!=null?'minutes':timeUnits.value[row.key]||'minutes'}
function cellDisabled(row,key){return props.readOnly||(aggregated.value&&row.scope==='entity')||(row.scope==='entity'&&['company','customer'].includes(row.dimension)&&row.values[key]==null&&WORD_COUNT_METRICS.some(item=>item.key!==key&&row.values[item.key]!=null))}
function changeTimeUnit(row,unit){const previous=timeMetric(row),value=row.values[previous];row.values[previous]=null;timeUnits.value[row.key]=unit;if(value!=null)row.values[unit]=Number((unit==='hours'?value/60:value*60).toFixed(4))}

const clone = (value) => JSON.parse(JSON.stringify(value))

function normalizeResponse(data = {}) {
  return {
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

async function loadMatrix() {
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
      if (sequence !== loadSequence || !visible.value) return
      draft.value = normalizeResponse(response)
    }
    original.value = clone(draft.value)
  } catch (error) {
    if (sequence !== loadSequence) return
    ElMessage.error(error.detail || '加载字数统计失败')
    visible.value = false
  } finally {
    if (sequence === loadSequence) loading.value = false
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

function discardDraft() {
  timeUnits.value={}
  loadSequence += 1
  draft.value = null
  original.value = null
  loading.value = false
}

function buildChanges() {
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
  buildRows(original.value).forEach((row) => beforeRows.set(row.key, row))
  const changes = []
  buildRows(draft.value).forEach((row) => {
    if (aggregated.value && row.scope === 'entity') return
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

async function saveMatrix() {
  if (!draft.value) return
  if(!aggregated.value)for(const dimension of ['company','customer'])if(WORD_COUNT_METRICS.filter(item=>draft.value[dimension][item.key]!=null).length>1)return ElMessage.warning(`${dimension==='company'?'我司统计':'客户统计'}只能填写一个统计字段，请先清空其他字段`)
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
      ElMessage.success(hybridMode.value ? '项目字数已保存，译员字数已应用到草稿' : '字数统计已应用到新建表单')
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
.word-count-matrix { display: flex; flex-direction: column; max-height: min(620px, calc(100vh - 96px)); }
.word-count-matrix__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 0 2px 8px; }
.word-count-matrix__header strong { font-size: 16px; color: var(--el-text-color-primary); }
.word-count-matrix__header p { margin: 3px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.word-count-matrix__body { flex: 1; min-height: 120px; overflow: auto; border: 1px solid var(--el-border-color); }
table { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
th, td { padding: 0; border-right: 1px solid var(--el-border-color); border-bottom: 1px solid var(--el-border-color); background: var(--el-bg-color); }
thead th { position: sticky; top: 0; z-index: 2; padding: 6px 4px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); font-size: 12px; line-height: 1.3; overflow-wrap: anywhere; }
tr:last-child th, tr:last-child td { border-bottom: 0; }
th:last-child, td:last-child { border-right: 0; }
.word-count-matrix__row-title { width: 156px; padding: 6px 8px; text-align: left; background: var(--el-fill-color-lighter); line-height: 1.35; }
.word-count-matrix__row-title span { display: block; }
.word-count-matrix__row-title small { display: block; margin-top: 3px; color: var(--el-text-color-secondary); font-weight: 400; }
.word-count-source{display:block;text-align:center;font-size:10px;color:var(--el-color-primary);padding-bottom:4px}.word-count-time-cell select{width:100%;height:26px;border:0;border-bottom:1px solid var(--el-border-color);background:#fff;color:var(--el-text-color-regular)}.word-count-time-cell select:disabled{background:#f1f5f9}.word-count-matrix>.el-alert{margin-bottom:8px}
td :deep(.el-input-number) { width: 100%; }
td :deep(.el-input__wrapper) { min-height: 28px; padding: 0 5px; border-radius: 0; box-shadow: none; }
.is-word-count-target :deep(.el-input__wrapper) { box-shadow: inset 0 0 0 2px var(--el-color-primary); }
.word-count-matrix__empty { padding: 28px; text-align: center; color: var(--el-text-color-secondary); }
.word-count-matrix__footer { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); }
.word-count-matrix__footer > span { color: var(--el-text-color-secondary); font-size: 12px; }
</style>

<style>
.word-count-matrix-popper { max-width: calc(100vw - 32px) !important; padding: 10px !important; }

@media (max-width: 760px) {
  .word-count-matrix-popper .word-count-matrix__body table { min-width: 720px; }
}
</style>
