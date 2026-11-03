<template>
  <div class="customer-language-prices">
    <el-button v-if="!readonly" :disabled="disabled" type="primary" plain @click="emit('update:modelValue',[...modelValue,newCustomerRate()])">新增单价（含语种方向）</el-button>
    <p v-if="matrix">项目已填写 {{projectQuantityChoices(matrix).length}} 项可计价统计，请选择其中一项；预统计不用于费用计算。</p>
    <el-empty v-if="!modelValue.length" description="暂无语种单价" :image-size="40" />
    <div v-for="(row,index) in modelValue" :key="row._key||row.id||index" class="language-price-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`单价 ${index+1}`">
      <div class="language-price-heading"><strong>单价 {{index+1}}</strong><el-button v-if="!readonly" link type="danger" :disabled="disabled" @click="emit('update:modelValue',modelValue.filter((_,i)=>i!==index))">移除单价</el-button></div>
      <el-form-item label="语种方向" :prop="`${fieldPrefix}.${index}.languagePair`" :rules="readonly?[]:[{required:true,message:'请选择语种方向',trigger:'change'}]"><ReadonlyField v-if="readonly" :model-value="row.languagePair||'-'" source="auto" /><LanguagePairSelect v-else :model-value="row.languagePair" single :allow-create="false" :show-hint="false" placeholder="每条单价选择一个语种方向" @update:model-value="setDirection(row,$event)" /></el-form-item>
      <p v-if="!row.taxPrices && row.amount!=null">原参考价（税口径未确认）：{{row.amount}}</p>
      <el-form-item label="不含税单价、货币、计价单位" :prop="`${fieldPrefix}.${index}.amount`" :rules="readonly?[]:[{required:true,message:'请填写含税或不含税单价',trigger:'change'},{validator:(_rule,_value,callback)=>callback(matrix&&!projectQuantityChoices(matrix).some(option=>option.value===row.metric)?new Error('请选择项目已填写的一项字数统计'):undefined),trigger:'change'}]"><CustomerPriceFields :amount="row.taxPrices?.unitPriceExclTax" v-model:currency="row.currency" v-model:metric-type="row.metric" v-model:unit-size="row.unitSize" tax-label="不含税" @update:amount="value=>setTax(row,'unitPriceExclTax',value)" @update:currency="clearReference(row)" @update:metric-type="clearReference(row)" @update:unit-size="clearReference(row)" :matrix="matrix" selectable-metric :readonly="readonly" :disabled="disabled" /></el-form-item>
      <el-form-item label="含税单价"><CustomerPriceFields :amount="row.taxPrices?.unitPriceInclTax" :currency="row.currency" :metric-type="row.metric" :unit-size="row.unitSize" tax-label="含税" @update:amount="value=>setTax(row,'unitPriceInclTax',value)" @update:currency="row.currency=$event" @update:metric-type="row.metric=$event" @update:unit-size="row.unitSize=$event" :matrix="matrix" selectable-metric :readonly="readonly" :disabled="disabled" /></el-form-item>
      <div v-if="matrix" class="price-preview">登记数量：{{quantity(row)??resolveRateQuantity(matrix,row.metric).error}} · 不含税总价：{{preview(row,'unitPriceExclTax')}} · 含税总价：{{preview(row,'unitPriceInclTax')}}</div>
      <small v-if="row.referenceId">采用客户参考价（保存项目后生效）；之后可独立修改。</small>
    </div>
  </div>
</template>
<script setup>
import {watch} from 'vue'
import {taxPriceForm,taxUnitAmount} from '@/utils/taxPrices'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ReadonlyField from './ReadonlyField.vue'
import CustomerPriceFields from '@/views/project/translation/components/CustomerPriceFields.vue'
import {newCustomerRate,defaultRateMetric} from '@/utils/customerTranslationRates'
import {normalizeWordCountMatrix} from '@/utils/wordCountMatrix'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
import {resolveRateQuantity,customerQuantityChoices,projectQuantityChoices} from '@/utils/translationQuantityBasis'
const props=defineProps({modelValue:{type:Array,default:()=>[]},fieldPrefix:{type:String,default:'prices'},matrix:Object,disabled:Boolean,readonly:Boolean})
const emit=defineEmits(['update:modelValue'])
watch(()=>[props.matrix,props.modelValue],()=>{
  if(!props.matrix)return
  const choices=projectQuantityChoices(props.matrix)
  for(const row of props.modelValue){
    if(choices.length===1 && (!row.metric||row.metric==='customer_auto'||!row.id))row.metric=choices[0].value
    else if(choices.length>1 && !row.id && row.metric==='customer_auto')row.metric=''
  }
},{deep:true,immediate:true})
function setDirection(row,value){row.languagePair=value;row.metric=defaultRateMetric(value);row.unitSize=1;row.referenceId=null;row.referenceRevision=null}
function setTax(row,key,value){row.taxPrices={...taxPriceForm(row.taxPrices),[key]:value};row.amount=taxUnitAmount(row.taxPrices,undefined);clearReference(row)}
function clearReference(row){row.referenceId=null;row.referenceRevision=null}
const quantity=row=>resolveRateQuantity(props.matrix,row.metric).quantity
const preview=(row,key)=>{const value=calculateCustomerPrice(row.taxPrices?.[key],quantity(row),row.unitSize);return value==null?'待填写数量或单价':`${row.currency} ${value}`}
</script>
<style scoped>
.language-price-row{padding:12px;margin-top:12px;border:1px solid #dbe3ec;border-radius:6px}.language-price-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.price-preview,.language-price-row small{font-size:12px;color:#64748b}.customer-language-prices{min-width:0}.customer-language-prices :deep(.customer-price-fields){width:100%;min-width:0}
</style>
