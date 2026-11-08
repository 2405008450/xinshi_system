<template>
  <div class="customer-language-prices">
    <div class="language-prices-toolbar"><div><strong>语种单价</strong><p v-if="matrix">已填写 {{projectQuantityChoices(matrix).length}} 项可计价统计；数量可后补，预统计不参与计费。</p></div><el-button v-if="!readonly" :disabled="disabled" type="primary" plain @click="emit('update:modelValue',[...modelValue,newCustomerRate()])">新增单价</el-button></div>
    <slot v-if="!modelValue.length" name="before-prices" />
    <div v-if="!modelValue.length" class="language-prices-empty">暂无语种单价{{readonly?'':'，点击“新增单价”填写'}}</div>
    <div v-for="(row,index) in modelValue" :key="row._key||row.id||index" class="language-price-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`单价 ${index+1}`">
      <div class="language-price-heading"><strong>单价 {{index+1}}</strong><el-button v-if="!readonly" link type="danger" :disabled="disabled" @click="emit('update:modelValue',modelValue.filter((_,i)=>i!==index))">移除单价</el-button></div>
      <slot name="before-prices" :row="row" :index="index" />
      <div class="price-fields-grid price-fields-grid--config">
        <el-form-item label="语种方向" :prop="`${fieldPrefix}.${index}.languagePair`" :rules="readonly?[]:[{required:true,message:'请选择语种方向',trigger:'change'}]"><ReadonlyField v-if="readonly" :model-value="row.languagePair||'-'" source="auto" /><LanguagePairSelect v-else :model-value="row.languagePair" single :allow-create="false" :show-hint="false" placeholder="每条单价选择一个语种方向" @update:model-value="setDirection(row,$event)" /></el-form-item>
        <el-form-item label="货币" :prop="`${fieldPrefix}.${index}.currency`" :rules="readonly?[]:[{required:true,message:'请选择货币',trigger:'change'}]">
          <ReadonlyField v-if="readonly" :model-value="row.currency" source="auto" />
          <el-select v-else v-model="row.currency" :disabled="disabled" filterable aria-label="货币" @change="clearReference(row)"><el-option v-for="option in currencies" :key="option.value" :value="option.value" :label="option.label" /></el-select>
        </el-form-item>
        <el-form-item label="统计口径" :prop="`${fieldPrefix}.${index}.metric`" :rules="readonly?[]:[{validator:(_rule,value,callback)=>callback(validQuantityBasis(value)&&(!referenceMode||value!=='customer_auto')?undefined:new Error(referenceMode?'请明确报价计量单位':'请选择统计口径，数量可后补')),trigger:'change'}]">
          <ReadonlyField v-if="readonly" :model-value="basisLabel(row.metric)" source="auto" />
          <CustomerQuantityBasisSelect v-else v-model="row.metric" :matrix="matrix" :reference-mode="referenceMode" :disabled="disabled" @update:model-value="clearReference(row)" />
        </el-form-item>
        <el-form-item v-if="referenceMode" label="单价对应数量" :prop="`${fieldPrefix}.${index}.unitSize`" :rules="readonly?[]:[{required:true,message:'请填写单价对应数量',trigger:'change'}]"><ReadonlyField v-if="readonly" :model-value="row.unitSize||1" source="auto" /><el-input-number v-else v-model="row.unitSize" :min="0.0001" :precision="4" :controls="false" :disabled="disabled" aria-label="单价对应数量" @change="clearReference(row)" /></el-form-item>
      </div>
      <div class="language-price-bottom" :class="{'language-price-bottom--compact':compactActions&&index===modelValue.length-1&&$slots['price-actions']}">
      <div class="price-fields-grid">
        <el-form-item label="不含税单价" :class="{'price-amount-filled':row.taxPrices?.unitPriceExclTax!=null&&row.taxPrices?.unitPriceExclTax!==''}" :prop="`${fieldPrefix}.${index}.taxPrices.unitPriceExclTax`" :rules="amountRules(row)">
          <ReadonlyField v-if="readonly" :model-value="row.taxPrices?.unitPriceExclTax??'-'" source="auto" />
          <el-input-number v-else :model-value="row.taxPrices?.unitPriceExclTax" :min="0" :precision="4" :controls="false" :disabled="disabled" aria-label="不含税单价" @update:model-value="value=>setTax(row,'unitPriceExclTax',value)" />
        </el-form-item>
        <el-form-item label="含税单价" :class="{'price-amount-filled':row.taxPrices?.unitPriceInclTax!=null&&row.taxPrices?.unitPriceInclTax!==''}" :prop="`${fieldPrefix}.${index}.taxPrices.unitPriceInclTax`" :rules="amountRules(row)">
          <ReadonlyField v-if="readonly" :model-value="row.taxPrices?.unitPriceInclTax??'-'" source="auto" />
          <el-input-number v-else :model-value="row.taxPrices?.unitPriceInclTax" :min="0" :precision="4" :controls="false" :disabled="disabled" aria-label="含税单价" @update:model-value="value=>setTax(row,'unitPriceInclTax',value)" />
        </el-form-item>
      </div>
      <slot v-if="index===modelValue.length-1" name="price-actions" :row="row" :index="index" />
      </div>
      <p v-if="!row.taxPrices && row.amount!=null">原参考价（税口径未确认）：{{row.amount}}</p>
      <div v-if="matrix&&!hideCalculationSummary" class="price-preview">登记数量：{{quantity(row)??resolveRateQuantity(matrix,row.metric).error}} {{quantity(row)!=null?metricName(resolveRateQuantity(matrix,row.metric).metric):''}} · 不含税总价：{{preview(row,'unitPriceExclTax')}} · 含税总价：{{preview(row,'unitPriceInclTax')}}</div>
      <small v-if="row.referenceId&&!hideCalculationSummary">采用客户参考价（保存项目后生效）；之后可独立修改。</small>
    </div>
  </div>
</template>
<script setup>
import {taxPriceForm,taxUnitAmount} from '@/utils/taxPrices'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ReadonlyField from './ReadonlyField.vue'
import CustomerQuantityBasisSelect from './CustomerQuantityBasisSelect.vue'
import {settlementCurrencyOptions as currencies} from '@/utils/talentSettlement'
import {newCustomerRate} from '@/utils/customerTranslationRates'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
import {resolveRateQuantity,metricName,projectQuantityChoices,validQuantityBasis,basisLabel} from '@/utils/translationQuantityBasis'
const props=defineProps({modelValue:{type:Array,default:()=>[]},fieldPrefix:{type:String,default:'prices'},matrix:Object,disabled:Boolean,readonly:Boolean,referenceMode:Boolean,hideCalculationSummary:Boolean,compactActions:Boolean})
const emit=defineEmits(['update:modelValue'])
function setDirection(row,value){row.languagePair=value;clearReference(row)}
function amountRules(row){return props.readonly?[]:[{validator:(_rule,_value,callback)=>callback(row.taxPrices?.unitPriceExclTax!=null||row.taxPrices?.unitPriceInclTax!=null||(!row.taxPrices&&row.amount!=null)?undefined:new Error('请至少填写不含税或含税单价')),trigger:'change'}]}
function setTax(row,key,value){row.taxPrices={...taxPriceForm(row.taxPrices),[key]:value};row.amount=taxUnitAmount(row.taxPrices,undefined);clearReference(row)}
function clearReference(row){row.referenceId=null;row.referenceRevision=null}
const quantity=row=>resolveRateQuantity(props.matrix,row.metric).quantity
const preview=(row,key)=>{const value=calculateCustomerPrice(row.taxPrices?.[key],quantity(row),row.unitSize);return value==null?'待填写数量或单价':`${row.currency} ${value}`}
</script>
<style scoped>
.language-price-bottom--compact{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;align-items:start}.language-price-bottom--compact>*{min-width:0}.language-price-bottom--compact :deep(.finance-sync-actions){margin:0;padding:0;border:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.language-price-bottom--compact :deep(.finance-sync-actions .el-button){max-width:100%;padding-left:10px;padding-right:10px}.language-price-bottom--compact :deep(.finance-sync-actions .el-button>span){min-width:0;overflow:hidden;text-overflow:ellipsis}@media(max-width:1000px){.language-price-bottom--compact{grid-template-columns:minmax(0,1fr)}}
.price-amount-filled :deep(.el-input__inner){color:#111;font-weight:700;-webkit-text-fill-color:#111}
.price-amount-filled :deep(.el-form-item__label){align-self:flex-start;width:fit-content;background:#111;color:#fff;font-weight:400;border:1px solid #111;border-radius:4px;padding:2px 8px;box-sizing:border-box}
.language-price-row{padding:12px;margin-top:12px;border:1px solid #dbe3ec;border-radius:6px}.language-price-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.price-preview,.language-price-row small{font-size:12px;color:#64748b}.customer-language-prices{min-width:0}.price-fields-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.price-fields-grid--config{grid-template-columns:minmax(0,1fr) minmax(0,.7fr) minmax(0,1.4fr)}.price-fields-grid>*{min-width:0}.price-fields-grid .el-input-number,.price-fields-grid .el-select{width:100%}.price-fields-grid small{display:block;line-height:1.6}@media(max-width:680px){.price-fields-grid,.price-fields-grid--config{grid-template-columns:minmax(0,1fr)}}
.language-prices-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.language-prices-toolbar strong{font-size:14px}.language-prices-toolbar p{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6;margin:4px 0 0}.language-prices-empty{border:1px dashed var(--el-border-color);border-radius:6px;padding:16px;text-align:center;font-size:13px;color:var(--el-text-color-secondary)}.price-preview{padding:8px 10px;background:var(--el-fill-color-light);border-radius:4px;line-height:1.6}@media(max-width:680px){.language-prices-toolbar{align-items:flex-start}}
</style>
