<template>
  <section class="word-count-inline" data-dialog-field-search-label="字数统计">
    <strong>字数统计</strong><p>我司统计、客户统计每行填写一项；清空后可更换口径。预统计不用于计算费用。</p>
    <div class="word-count-inline-scroll"><table><thead><tr><th>统计维度</th><th v-for="metric in WORD_COUNT_METRICS" :key="metric.key">{{ metric.label }}</th></tr></thead><tbody>
      <tr v-for="dimension in dimensions" :key="dimension.key"><th>{{ dimension.label }}</th><td v-for="metric in WORD_COUNT_METRICS" :key="metric.key"><el-input-number :model-value="matrix[dimension.key][metric.key]" :disabled="locked(dimension.key,metric.key)" :aria-label="dimension.label+' '+metric.label" :min="0" :precision="['minutes','hours'].includes(metric.key)?4:0" :controls="false" style="width:100%" @update:model-value="value=>change(dimension.key,metric.key,value)" /></td></tr>
    </tbody></table></div>
  </section>
</template>
<script setup>
import {computed} from 'vue'
import {WORD_COUNT_METRICS,normalizeWordCountMatrix} from '@/utils/wordCountMatrix'
const props=defineProps({modelValue:Object});const emit=defineEmits(['update:modelValue'])
const matrix=computed(()=>normalizeWordCountMatrix(props.modelValue))
const dimensions=[{key:'company',label:'我司统计'},{key:'customer',label:'客户统计'},{key:'preliminary',label:'预统计'},{key:'translatorEstimate',label:'译员预定'}]
const filled=value=>value!==null&&value!==undefined&&value!==''
const locked=(dim,key)=>['company','customer'].includes(dim)&&Object.entries(matrix.value[dim]).some(([other,value])=>other!==key&&filled(value))
function change(dim,key,value){const next=normalizeWordCountMatrix(props.modelValue);next[dim][key]=Number.isFinite(value)?value:null;emit('update:modelValue',next)}
</script>
<style scoped>
.word-count-inline{margin:16px 0}.word-count-inline p{font-size:12px;color:#64748b}.word-count-inline-scroll{overflow-x:auto}.word-count-inline table{border-collapse:collapse;width:100%;min-width:900px}.word-count-inline th,.word-count-inline td{border:1px solid #dce4ef;padding:6px;min-width:90px}.word-count-inline th{background:#f1f5f9;font-size:12px}.word-count-inline th:first-child{min-width:95px}
</style>
