<template>
  <section class="word-count-inline" data-dialog-field-search-label="字数统计">
    <strong>字数统计</strong>
    <p v-if="aggregated">此订单由下级汇总，请在末级子订单修改统计。</p>
    <p v-else>我司统计、客户统计每行可选字数类、份数、页数或时长。字数类可填多项，清空当前区域后可切换。预统计不用于计算费用。</p>
    <DocumentWordCounter v-if="!disabled && !aggregated" :current-matrix="matrix" @apply="applyFileCount" />
    <div class="word-count-inline-scroll"><table><thead><tr><th>统计维度</th><th v-for="metric in WORD_COUNT_METRICS" :key="metric.key">{{ metric.label }}</th></tr></thead><tbody>
      <tr v-for="dimension in dimensions" :key="dimension.key">
        <th>
          {{ dimension.label }}
          <el-button v-if="!disabled && !aggregated && ['company','customer'].includes(dimension.key) && Object.values(matrix[dimension.key]).some(value => value != null)" link @click="clearRow(dimension.key)">清空本行</el-button>
        </th>
        <td v-for="metric in WORD_COUNT_METRICS" :key="metric.key">
          <el-input-number :key="locked(dimension.key,metric.key)" :model-value="matrix[dimension.key][metric.key]" :disabled="locked(dimension.key,metric.key)" :aria-label="dimension.label+' '+metric.label" :min="0" :precision="['minutes','hours'].includes(metric.key)?4:0" :controls="false" style="width:100%" @update:model-value="value=>change(dimension.key,metric.key,value)" />
        </td>
      </tr>
    </tbody></table></div>
  </section>
</template>
<script setup>
import {computed} from 'vue'
import DocumentWordCounter from './DocumentWordCounter.vue'
import {WORD_COUNT_METRICS,createEmptyWordCountValues,normalizeWordCountMatrix,isWordCountRegionLocked} from '@/utils/wordCountMatrix'
function applyFileCount({dimension,metric,value}){const next=normalizeWordCountMatrix(props.modelValue);Object.keys(next[dimension]).forEach(key=>next[dimension][key]=null);next[dimension][metric]=value;emit('update:modelValue',next)}
const props=defineProps({modelValue:Object,disabled:Boolean,aggregated:Boolean});const emit=defineEmits(['update:modelValue'])
const matrix=computed(()=>normalizeWordCountMatrix(props.modelValue))
const dimensions=[{key:'company',label:'我司统计'},{key:'customer',label:'客户统计'},{key:'preliminary',label:'预统计'},{key:'translatorEstimate',label:'译员预定'}]
function locked(dimension, key) {
  if (props.disabled || props.aggregated) return true
  const values = matrix.value[dimension]
  if ((key === 'minutes' && values.hours != null) || (key === 'hours' && values.minutes != null)) return true
  return ['company', 'customer'].includes(dimension) && isWordCountRegionLocked(values, key)
}
function change(dimension, key, value) {
  if (locked(dimension, key)) return
  const next = normalizeWordCountMatrix(props.modelValue)
  next[dimension][key] = Number.isFinite(value) ? value : null
  emit('update:modelValue', next)
}
function clearRow(dimension) {
  emit('update:modelValue', { ...matrix.value, [dimension]: createEmptyWordCountValues() })
}
</script>
<style scoped>
.word-count-inline{margin:16px 0}.word-count-inline p{font-size:12px;color:#64748b}.word-count-inline-scroll{overflow-x:auto}.word-count-inline table{border-collapse:collapse;width:100%;min-width:900px}.word-count-inline th,.word-count-inline td{border:1px solid #dce4ef;padding:6px;min-width:90px}.word-count-inline th{background:#f1f5f9;font-size:12px}.word-count-inline th:first-child{min-width:95px}
</style>
