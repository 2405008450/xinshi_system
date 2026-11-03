<template>
  <div class="customer-language-prices">
    <el-button v-if="!readonly" :disabled="disabled" type="primary" plain @click="emit('update:modelValue',[...modelValue,newCustomerRate()])">新增单价（含语种方向）</el-button>
    <el-empty v-if="!modelValue.length" description="暂无语种单价" :image-size="40" />
    <div v-for="(row,index) in modelValue" :key="row._key||row.id||index" class="language-price-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`单价 ${index+1}`">
      <div class="language-price-heading"><strong>单价 {{index+1}}</strong><el-button v-if="!readonly" link type="danger" :disabled="disabled" @click="emit('update:modelValue',modelValue.filter((_,i)=>i!==index))">移除单价</el-button></div>
      <el-form-item label="语种方向" :prop="`${fieldPrefix}.${index}.languagePair`" :rules="readonly?[]:[{required:true,message:'请选择语种方向',trigger:'change'}]"><ReadonlyField v-if="readonly" :model-value="row.languagePair||'-'" source="auto" /><LanguagePairSelect v-else :model-value="row.languagePair" single :allow-create="false" :show-hint="false" placeholder="每条单价选择一个语种方向" @update:model-value="setDirection(row,$event)" /></el-form-item>
      <el-form-item label="单价、货币、计价单位" :prop="`${fieldPrefix}.${index}.amount`" :rules="readonly?[]:[{required:true,message:'请填写单价',trigger:'change'}]"><CustomerPriceFields v-model:amount="row.amount" v-model:currency="row.currency" v-model:metric-type="row.metric" v-model:unit-size="row.unitSize" @update:amount="clearReference(row)" @update:currency="clearReference(row)" @update:metric-type="clearReference(row)" @update:unit-size="clearReference(row)" selectable-metric :readonly="readonly" :disabled="disabled" /></el-form-item>
      <el-form-item v-if="matrix&&String(row.metric).startsWith('customer_auto')&&customerQuantityChoices(matrix).length>1" label="客户统计口径（多栏时必须选择）" :prop="`${fieldPrefix}.${index}.metric`" :rules="readonly?[]:[{validator:(_rule,_value,callback)=>callback(resolveRateQuantity(matrix,row.metric).quantity==null?new Error('请选择客户统计口径'):undefined),trigger:'change'}]"><el-select :model-value="String(row.metric).split(':')[1]" :disabled="readonly||disabled" placeholder="客户统计有多栏，请选择" @update:model-value="value=>{row.metric='customer_auto:'+value;clearReference(row)}"><el-option v-for="option in customerQuantityChoices(matrix)" :key="option.key" :value="option.key" :label="`${option.label}：${option.value}`" /></el-select></el-form-item>
      <div v-if="matrix" class="price-preview">登记数量：{{quantity(row)??resolveRateQuantity(matrix,row.metric).error}} · 本项总价：{{preview(row)}}</div>
      <small v-if="row.referenceId">采用客户参考价（保存项目后生效）；之后可独立修改。</small>
    </div>
  </div>
</template>
<script setup>
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ReadonlyField from './ReadonlyField.vue'
import CustomerPriceFields from '@/views/project/translation/components/CustomerPriceFields.vue'
import {newCustomerRate,defaultRateMetric} from '@/utils/customerTranslationRates'
import {normalizeWordCountMatrix} from '@/utils/wordCountMatrix'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
import {resolveRateQuantity,customerQuantityChoices} from '@/utils/translationQuantityBasis'
const props=defineProps({modelValue:{type:Array,default:()=>[]},fieldPrefix:{type:String,default:'prices'},matrix:Object,disabled:Boolean,readonly:Boolean})
const emit=defineEmits(['update:modelValue'])
function setDirection(row,value){row.languagePair=value;row.metric=defaultRateMetric(value);row.unitSize=1;row.referenceId=null;row.referenceRevision=null}
function clearReference(row){row.referenceId=null;row.referenceRevision=null}
const quantity=row=>resolveRateQuantity(props.matrix,row.metric).quantity
const preview=row=>{const value=calculateCustomerPrice(row.amount,quantity(row),row.unitSize);return value==null?'待填写数量或单价':`${row.currency} ${value}`}
</script>
<style scoped>
.language-price-row{padding:12px;margin-top:12px;border:1px solid #dbe3ec;border-radius:6px}.language-price-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.price-preview,.language-price-row small{font-size:12px;color:#64748b}.customer-language-prices{min-width:0}.customer-language-prices :deep(.customer-price-fields){width:100%;min-width:0}
</style>
