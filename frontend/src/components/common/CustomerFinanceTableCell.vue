<template>
  <div class="finance-sheet-cell" :class="{'is-saving':state.saving,'has-error':cellError}" :title="state.error||''">
    <CustomerAggregatePrices v-if="row.priceAggregate&&field==='unitPrice'" :prices="row.prices" compact :can-edit="!readonly" @edit-order="emit('edit-order',$event)" />
    <ReadonlyField v-else-if="row.priceAggregate&&field==='pricingMode'" model-value="子订单累计" source="auto" />
    <select v-else-if="field==='pricingMode'" v-model="draft.pricingMode" aria-label="计价模式" @change="commit('pricingMode')"><option value="metric">按数量</option><option value="fixed">固定收费</option></select>
    <ReadonlyField v-else-if="field==='billingMonth'" :model-value="draft.billingMonth||'—'" source="auto" title="按订单号所属月份自动生成；跨月调配请在对账单管理中处理" />
    <template v-else-if="field==='unitPrice'">
      <select v-if="draft.pricingMode==='fixed'" v-model="draft.currency" aria-label="固定收费货币" @change="commit('currency')"><option v-for="currency in currencies" :key="currency">{{currency}}</option></select>
      <template v-else>
        <div v-for="(price,index) in draft.prices" :key="index" class="sheet-price">
          <div class="sheet-price-heading"><small>{{price.languagePair||'请选择方向'}}</small><button type="button" :aria-label="`减少单价 ${index+1}`" title="移除此单价" @click="removePrice(index)">－</button></div>
          <label>未税<input :value="price.taxPrices?.unitPriceExclTax??''" type="number" min="0" step="0.0001" :aria-label="`不含税单价 ${index+1}`" @input="setPrice(price,'unitPriceExclTax',$event.target.value)" @blur="commitNumber($event,'prices')" @keydown.enter.prevent="$event.target.blur()" /></label>
          <label>含税<input :value="price.taxPrices?.unitPriceInclTax??''" type="number" min="0" step="0.0001" :aria-label="`含税单价 ${index+1}`" @input="setPrice(price,'unitPriceInclTax',$event.target.value)" @blur="commitNumber($event,'prices')" @keydown.enter.prevent="$event.target.blur()" /></label>
          <el-popover v-model:visible="price._config" :title="`单价 ${index+1} 设置`" trigger="click" placement="left-start" :width="420" popper-class="finance-price-settings-popper">
            <template #reference><button type="button" class="sheet-config-toggle" :aria-label="`单价设置 ${index+1}`">{{`${price.currency}/${Number(price.unitSize||1)} · 设置`}}</button></template>
            <div class="sheet-price-config">
              <label class="sheet-settings-field"><span>语种方向</span><LanguagePairSelect v-model="price.languagePair" single :show-hint="false" :dropdown-width="360" placeholder="搜索并选择语种方向" @update:model-value="priceChanged(price)" /></label>
              <label class="sheet-settings-field"><span>货币</span><el-select v-model="price.currency" aria-label="单价货币" @change="priceChanged(price)"><el-option v-for="currency in currencies" :key="currency" :value="currency" /></el-select></label>
              <label class="sheet-settings-field"><span>统计口径</span><CustomerQuantityBasisSelect v-model="price.metric" :matrix="row.wordCountMatrix" @update:model-value="priceChanged(price)" /></label>
              <small class="sheet-settings-help">选择后自动保存，与编辑收费窗口同步。</small>
            </div>
          </el-popover>
        </div>
        <button type="button" class="sheet-config-toggle" @click="addPrice">＋单价</button>
        <FinanceTablePriceActions :row="row" :prepare="prepare" @saved="emit('saved',$event)" />
      </template>
    </template>
    <template v-else-if="['totalPrice','totalInclTax','adjustedTotal'].includes(field)">
      <small>{{draft.pricingMode==='fixed'?'固定收费':'计算额'}}</small>
      <ReadonlyField :model-value="calculationText" source="auto" />
      <small>{{draft.pricingMode==='fixed'?'登记金额':'调整后金额'}}</small>
      <ReadonlyField v-if="row.priceAggregate||readonly" :model-value="effectiveText" source="auto" />
      <span v-else-if="multipleCurrencies" class="sheet-calculated">{{effectiveText}}</span>
      <input v-else :value="draft[amountKey]??''" type="number" min="0" step="0.01" :aria-label="amountLabel+'调整后金额'" :placeholder="draft.pricingMode==='fixed'?'填写固定收费':'采用计算额'" @input="draft[amountKey]=$event.target.value===''?null:Number($event.target.value)" @blur="commitNumber($event,amountKey)" @keydown.enter.prevent="$event.target.blur()" />
      <small v-if="!row.priceAggregate&&!readonly">{{draft.currency||row.currency||'CNY'}}</small>
      <small v-if="!row.priceAggregate&&draft.pricingMode!=='fixed'&&amountValue==null&&!projectQuantityChoices(row.wordCountMatrix).length" class="sheet-quantity-warning">客户统计和我司统计均未填写，请先登记数量和单位。</small>
    </template>
    <div v-else-if="field==='explanation'" class="sheet-notes"><label>内部说明<ReadonlyField v-if="readonly" :model-value="draft.explanation||'—'" source="auto" /><textarea v-else v-model="draft.explanation" rows="2" maxlength="5000" aria-label="内部说明" placeholder="填写内部说明" @blur="commit('explanation')" /></label><label>客户说明<ReadonlyField v-if="readonly" :model-value="draft.customerExplanation||'—'" source="auto" /><textarea v-else v-model="draft.customerExplanation" rows="2" maxlength="5000" aria-label="客户说明" placeholder="填写客户说明" @blur="commit('customerExplanation')" /></label></div>
    <small v-if="cellError" class="sheet-save-error">未保存</small>
  </div>
</template>

<script setup>
import {computed} from 'vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import CustomerQuantityBasisSelect from './CustomerQuantityBasisSelect.vue'
import ReadonlyField from './ReadonlyField.vue'
import FinanceTablePriceActions from './FinanceTablePriceActions.vue'
import CustomerAggregatePrices from './CustomerAggregatePrices.vue'
import {sameFinanceField} from '@/utils/financeTableDraft'
import {newCustomerRate} from '@/utils/customerTranslationRates'
import {taxUnitAmount} from '@/utils/taxPrices'
import {calculateTaxOrderPriceTree,projectQuantityChoices} from '@/utils/translationQuantityBasis'
const props=defineProps({field:String,row:{type:Object,required:true},state:{type:Object,required:true},prepare:Function,readonly:Boolean})
const emit=defineEmits(['commit','saved','edit-order'])
const draft=computed(()=>props.state.draft)
const currencies=['CNY','USD','HKD','EUR','GBP','JPY']
const amountKey=computed(()=>props.field==='totalInclTax'?'adjustedTotalInclTax':'adjustedTotal')
const logicalField=computed(()=>({unitPrice:'prices',totalPrice:'adjustedTotal',totalInclTax:'adjustedTotalInclTax',adjustedTotal:'adjustedTotal'}[props.field]||props.field))
const cellError=computed(()=>props.state.error&&(!sameFinanceField(logicalField.value,draft.value[logicalField.value],props.state.base[logicalField.value])||props.field==='explanation'&&!sameFinanceField('customerExplanation',draft.value.customerExplanation,props.state.base.customerExplanation)))
const amountLabel=computed(()=>({totalPrice:'不含税总价',totalInclTax:'含税总价',adjustedTotal:'调整后总价'}[props.field]))
const calculated=computed(()=>calculateTaxOrderPriceTree({...props.row,...draft.value},props.row.prices||[]))
const amounts=computed(()=>calculated.value[props.field==='totalInclTax'?'incl':'excl'].totals)
const multipleCurrencies=computed(()=>draft.value.pricingMode!=='fixed'&&new Set(draft.value.prices.map(price=>price.currency)).size>1)
const amountSummary=computed(()=>Object.entries(amounts.value).map(([currency,amount])=>`${currency} ${amount}`).join('\n')||'待补录')
const amountValue=computed(()=>draft.value[amountKey.value]??(draft.value.pricingMode==='fixed'?null:amounts.value[draft.value.prices[0]?.currency||draft.value.currency]))
const formatAmounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('\n')||'待填写'
const calculationText=computed(()=>props.row.priceAggregate?formatAmounts(props.row[props.field==='totalInclTax'?'calculatedTotalsInclTax':'calculatedTotalsExclTax']):draft.value.pricingMode==='fixed'?'按登记金额':formatAmounts(amounts.value))
const effectiveText=computed(()=>props.row.priceAggregate||props.readonly?formatAmounts(props.row[props.field==='totalInclTax'?'totalsInclTax':'totalsExclTax']):draft.value[amountKey.value]==null?formatAmounts(amounts.value):`${draft.value.currency||props.row.currency||'CNY'} ${Number(draft.value[amountKey.value]).toFixed(2)}`)
function commit(field){emit('commit',field)}

function commitNumber(event,field){if(event.target.validity.valid){props.state.error='';commit(field)}else props.state.error='请输入有效的非负金额'}
function setPrice(price,key,value){price.taxPrices={...price.taxPrices,[key]:value===''?null:Number(value)};price.amount=taxUnitAmount(price.taxPrices,null);price.referenceId=null;price.referenceRevision=null}
function priceChanged(price){price.referenceId=null;price.referenceRevision=null;commit('prices')}
function addPrice(){const directions=String(props.row.languagePair||'').split('；').filter(Boolean);const direction=directions.find(value=>!draft.value.prices.some(price=>price.languagePair===value))||'';draft.value.prices.push({...newCustomerRate(direction),_config:!direction});if(direction)commit('prices')}
function removePrice(index){draft.value.prices.splice(index,1);commit('prices')}
</script>

<style scoped>
.sheet-notes{display:grid;gap:8px}.sheet-notes label{display:grid;gap:3px;font-size:12px}.finance-sheet-cell{min-width:0}.finance-sheet-cell input,.finance-sheet-cell select,.finance-sheet-cell textarea{box-sizing:border-box;width:100%;min-width:0;border:1px solid transparent;border-radius:3px;background:#fff;color:var(--el-text-color-regular);font:inherit;padding:3px;outline:none;line-height:1.45}.finance-sheet-cell select{font-size:12px;padding:3px 0}.finance-sheet-cell input:hover,.finance-sheet-cell select:hover,.finance-sheet-cell textarea:hover{border-color:var(--el-border-color)}.finance-sheet-cell input:focus,.finance-sheet-cell select:focus,.finance-sheet-cell textarea:focus{border-color:var(--el-color-primary)}.finance-sheet-cell input::-webkit-inner-spin-button{appearance:none}.finance-sheet-cell textarea{resize:vertical;min-height:28px}.finance-sheet-cell small{display:block;font-size:11px;color:var(--el-text-color-secondary);overflow-wrap:anywhere}.sheet-price-heading{display:flex;align-items:center;gap:2px}.sheet-price-heading small{flex:1;min-width:0}.sheet-price-heading button{color:var(--el-color-danger);font-weight:700}.finance-sheet-cell :deep(.readonly-field){font-size:12px;min-width:0;padding:3px}.finance-sheet-cell :deep(.el-input__wrapper){padding:0 4px}.finance-sheet-cell :deep(.el-input__inner){font-size:12px}.finance-sheet-cell :deep(.readonly-field__icon){font-size:10px}.sheet-price+ .sheet-price{border-top:1px solid var(--el-border-color-lighter);margin-top:5px;padding-top:5px}.sheet-price label{display:flex;align-items:center;gap:2px;font-size:11px;white-space:nowrap}.sheet-price label input{flex:1;text-align:right}.finance-sheet-cell button{border:0;background:transparent;color:var(--el-color-primary);padding:2px 0;font:inherit;font-size:11px;cursor:pointer}.sheet-price-config{display:grid;gap:14px}.sheet-settings-heading{display:flex;align-items:center;justify-content:space-between}.sheet-settings-field{display:grid;gap:6px;font-size:13px}.sheet-settings-field .el-select{width:100%}.sheet-settings-help{color:var(--el-text-color-secondary);font-size:12px}.sheet-calculated{background:#f1f5f9;white-space:pre-wrap}.finance-sheet-cell .sheet-save-error{color:var(--el-color-danger)}.has-error{outline:1px solid var(--el-color-danger)}
</style>

<style>
.finance-price-settings-popper{max-width:calc(100vw - 32px);box-sizing:border-box}.finance-price-settings-popper .language-pair-select__row>.el-select-v2{flex:1;min-width:0}
</style>
