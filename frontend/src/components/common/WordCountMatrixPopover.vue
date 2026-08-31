<template>
  <el-popover
    v-model:visible="visible"
    trigger="click"
    placement="bottom-end"
    width="min(960px, calc(100vw - 32px))"
    popper-class="word-count-matrix-popper"
    :teleported="true"
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
          <strong>{{ title }}</strong>
          <p>可按来源及计量口径分别填写，空白单元格不会保存。</p>
        </div>
        <el-tag size="small" type="info">{{ hybridMode ? '项目保存 / 译员草稿' : (localMode ? '新建草稿' : '独立保存') }}</el-tag>
      </div>

      <div v-loading="loading" class="word-count-matrix__body">
        <table>
          <thead>
            <tr>
              <th class="word-count-matrix__row-title">统计维度</th>
              <th v-for="metric in WORD_COUNT_METRICS" :key="metric.key">{{ metric.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.key">
              <th class="word-count-matrix__row-title">
                <span>{{ row.label }}</span>
                <small v-if="row.hint">{{ row.hint }}</small>
              </th>
              <td v-for="metric in WORD_COUNT_METRICS" :key="metric.key">
                <el-input-number
                  v-model="row.values[metric.key]"
                  :min="0"
                  :step="1"
                  :precision="0"
                  :controls="false"
                  :aria-label="`${row.label}-${metric.label}`"
                />
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
          <el-button type="primary" :loading="saving" @click="saveMatrix">
            {{ hybridMode ? '保存并应用' : (localMode ? '应用到新建表单' : '保存') }}
          </el-button>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getWordCountMatrix, patchWordCountMatrix } from '@/api/wordCountMatrices'
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
  title: { type: String, default: '字数统计' }
})

const emit = defineEmits(['update:modelValue', 'update:translators', 'saved'])
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const draft = ref(null)
const original = ref(null)
const localMode = computed(() => props.local || !props.entityId)
const hybridMode = computed(() => localMode.value && Boolean(props.entityId))
const summary = computed(() => formatWordCountMatrix(props.modelValue))

const clone = (value) => JSON.parse(JSON.stringify(value))

function normalizeResponse(data = {}) {
  return {
    entity_type: data.entity_type || props.entityType,
    entity_id: data.entity_id || props.entityId,
    company: normalizeWordCountValues(data.company),
    customer: normalizeWordCountValues(data.customer),
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
    { key: 'entity-company', scope: 'entity', dimension: 'company', label: '我司字数', values: draft.value.company },
    { key: 'entity-customer', scope: 'entity', dimension: 'customer', label: '客户字数', values: draft.value.customer },
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
      draft.value = normalizeResponse(await getWordCountMatrix(props.entityType, props.entityId, params))
    }
    original.value = clone(draft.value)
  } catch (error) {
    ElMessage.error(error.detail || '加载字数统计失败')
    visible.value = false
  } finally {
    loading.value = false
  }
}

function discardDraft() {
  draft.value = null
  original.value = null
}

function buildChanges() {
  const beforeRows = new Map()
  const buildRows = (matrix) => {
    const result = [
      { key: 'entity-company', scope: 'entity', dimension: 'company', values: matrix.company },
      { key: 'entity-customer', scope: 'entity', dimension: 'customer', values: matrix.customer },
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
  if (localMode.value) {
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
  saving.value = true
  try {
    const params = props.dispatchId ? { dispatch_id: props.dispatchId } : {}
    const saved = normalizeResponse(await patchWordCountMatrix(props.entityType, props.entityId, { changes }, params))
    emit('update:modelValue', {
      company: saved.company,
      customer: saved.customer,
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
.word-count-matrix { display: flex; flex-direction: column; max-height: min(560px, calc(100vh - 120px)); }
.word-count-matrix__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 2px 2px 12px; }
.word-count-matrix__header strong { font-size: 16px; color: var(--el-text-color-primary); }
.word-count-matrix__header p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.word-count-matrix__body { flex: 1; min-height: 120px; overflow: auto; border: 1px solid var(--el-border-color); }
table { width: 100%; min-width: 1120px; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
th, td { padding: 0; border-right: 1px solid var(--el-border-color); border-bottom: 1px solid var(--el-border-color); background: var(--el-bg-color); }
thead th { position: sticky; top: 0; z-index: 2; padding: 10px 8px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); font-size: 12px; }
tr:last-child th, tr:last-child td { border-bottom: 0; }
th:last-child, td:last-child { border-right: 0; }
.word-count-matrix__row-title { width: 210px; padding: 9px 10px; text-align: left; background: var(--el-fill-color-lighter); }
.word-count-matrix__row-title span { display: block; }
.word-count-matrix__row-title small { display: block; margin-top: 3px; color: var(--el-text-color-secondary); font-weight: 400; }
td :deep(.el-input-number) { width: 100%; }
td :deep(.el-input__wrapper) { border-radius: 0; box-shadow: none; }
.word-count-matrix__empty { padding: 28px; text-align: center; color: var(--el-text-color-secondary); }
.word-count-matrix__footer { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
.word-count-matrix__footer > span { color: var(--el-text-color-secondary); font-size: 12px; }
</style>

<style>
.word-count-matrix-popper { max-width: calc(100vw - 32px) !important; padding: 14px !important; }
</style>
