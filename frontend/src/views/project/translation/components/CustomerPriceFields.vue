<template>
  <div class="customer-price-fields">
    <label><small>单价<span v-if="taxLabel">（{{taxLabel}}）</span></small><ReadonlyField v-if="readonly" :model-value="amountText" source="auto" /><el-input-number v-else :model-value="amount" :min="0" :precision="4" :controls="false" :disabled="disabled" :aria-label="`${taxLabel}单价`" @update:model-value="emit('update:amount',$event)" @change="emit('change')" /></label>
    <label><small>货币</small><ReadonlyField v-if="readonly" :model-value="currency==='CNY'?'CNY 人民币':currency || 'CNY 人民币'" source="auto" /><el-select v-else :model-value="currency" filterable :disabled="disabled" aria-label="货币" @update:model-value="emit('update:currency',$event)"><el-option v-for="option in currencies" :key="option.value" :value="option.value" :label="option.label" /></el-select></label>
    <label><small>计价单位</small><ReadonlyField v-if="readonly" :model-value="unitText" source="auto" /><el-select v-else-if="selectableMetric" :model-value="`${metricType}|${unitSize}`" :disabled="disabled" aria-label="计价单位" @update:model-value="selectUnit"><el-option v-for="option in metricOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select><el-select v-else :model-value="unitSize" :disabled="disabled" aria-label="计价单位" @update:model-value="emit('update:unitSize',$event)" @change="emit('change')"><el-option v-for="size in sizes" :key="size" :value="size" :label="`${size}${metricLabel}`" /></el-select></label>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import {settlementCurrencyOptions as currencies} from '@/utils/talentSettlement'
import {WORD_COUNT_METRICS} from '@/utils/wordCountMatrix'
const props=defineProps({amount:{type:[Number,String],default:null},currency:{type:String,default:'CNY'},unitSize:{type:[Number,String],default:1000},metricType:{type:String,default:'words'},taxLabel:{type:String,default:''},readonly:Boolean,disabled:Boolean,selectableMetric:Boolean})
const emit=defineEmits(['update:amount','update:currency','update:unitSize','update:metricType','change'])
const metricLabel=computed(()=>WORD_COUNT_METRICS.find(item=>item.key===props.metricType)?.shortLabel||'字数')
const amountText=computed(()=>props.amount==null?'-':Number(props.amount).toLocaleString('zh-CN',{maximumFractionDigits:4}))
const unitText=computed(()=>props.metricType==='characters_no_spaces'&&Number(props.unitSize)===1?'字数（字符不计空格）':`${props.unitSize||1}${metricLabel.value}`)
const sizes=computed(()=>[...new Set([1,1000,Number(props.unitSize)||1])].sort((a,b)=>a-b))
const metricOptions=computed(()=>{const options=[{value:'foreign_words|1',label:'外文字数'},{value:'characters_no_spaces|1',label:'字符数不计空格'},{value:'words|1',label:'字数'},{value:'cjk_chars_korean_words|1',label:'中朝统计'},{value:'documents|1',label:'份数'},{value:'pages|1',label:'页数'}];const value=`${props.metricType}|${props.unitSize}`;if(!options.some(item=>item.value===value))options.push({value,label:unitText.value});return options})
function selectUnit(value){const [metric,size]=value.split('|');emit('update:metricType',metric);emit('update:unitSize',Number(size));emit('change')}
</script>
<style scoped>
.customer-price-fields{display:grid;grid-template-columns:minmax(85px,1fr) 90px minmax(100px,1fr);gap:8px;min-width:300px}.customer-price-fields>label{display:flex;flex-direction:column;gap:4px;min-width:0}.customer-price-fields small{font-size:11px;color:#64748b}.customer-price-fields .el-input-number,.customer-price-fields .el-select{width:100%}
</style>
