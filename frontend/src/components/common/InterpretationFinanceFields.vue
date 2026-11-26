<template>
  <div>
    <template v-if="referenceOnly||!fixed"><p v-if="referenceOnly">同一口译方向可添加多行，分别登记月、周、天、半天、小时的客户参考单价。</p><p v-else>同一口译方向可添加多行，组合月、周、天、半天、小时；金额按单价 × 数量累计，币种分别统计。</p>
    <section v-for="(rate,index) in model.rates" :key="index" class="rate-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`口译单价 ${index+1}`">
      <el-form-item label="口译方向" :prop="`rates.${index}.direction`" :rules="[{validator:(_rule,value,done)=>done(!value||(!referenceOnly&&!directions.some(item=>item.label===value))?new Error('请选择项目中的口译方向'):undefined),trigger:'change'}]">
        <LanguagePairSelect v-if="referenceOnly" :model-value="rate.direction.replace(/\s*↔\s*/g,'→')" single :allow-create="false" :show-hint="false" placeholder="请选择系统语言对" @update:model-value="rate.direction=$event.replace(/→/g,' ↔ ')" />
        <el-select v-else v-model="rate.direction" filterable default-first-option><el-option v-for="item in directionOptions" :key="item" :label="item" :value="item" /></el-select>
      </el-form-item>
      <TaxPriceFields v-model="rate.taxPrices" :prefix="`rates.${index}.taxPrices`" :show-totals="false" @change="value=>{rate.amount=taxUnitAmount(value,rate.amount);clearLineOverride(rate)}" />
      <el-form-item v-if="rate.taxPrices?.unitPriceExclTax==null&&rate.taxPrices?.unitPriceInclTax==null" label="税口径未确认的单价" :prop="`rates.${index}.amount`" :rules="[{required:true,message:'请填写单价',trigger:'change'}]">
        <el-input-number v-model="rate.amount" :min="0" :precision="6" :controls="false" />
      </el-form-item>
      <el-form-item label="货币" :prop="`rates.${index}.currency`" :rules="[{required:true,pattern:/^[A-Z]{3}$/,message:'填写三位大写货币代码',trigger:'change'}]"><el-select v-model="rate.currency" filterable allow-create><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item>
      <el-form-item label="单位"><el-select v-model="rate.unit" @change="unitChanged(rate)"><el-option v-for="unit in interpretationUnits" :key="unit" :value="unit" /></el-select></el-form-item>
      <el-form-item v-if="!referenceOnly" label="工作量" :prop="`rates.${index}.quantity`" :rules="[{required:true,message:'请填写工作量',trigger:'change'}]"><el-input-number v-model="rate.quantity" @update:model-value="clearLineOverride(rate)" placeholder="填写工作量" :min="0" :max="999999" :precision="4" :controls="false" /></el-form-item>
      <el-form-item v-if="['天','半天'].includes(rate.unit)" label="每单位小时数" :prop="`rates.${index}.hours`" :rules="[{required:true,message:'请填写小时数',trigger:'change'}]"><el-input-number v-model="rate.hours" :min="0.0001" :max="744" :precision="4" :controls="false" /><el-checkbox v-if="rate.unit==='天'" v-model="rate.includes_lunch">含中午/午餐时间</el-checkbox></el-form-item>
      <div v-if="!referenceOnly" class="line-totals">
        <el-form-item v-for="basis in taxBases" :key="basis.value" :label="basis.label+'小计'">
          <ReadonlyField :model-value="lineTotal(rate,basis.value)" source="auto" placeholder="填写单价和数量后计算" />
        </el-form-item>
        <el-form-item v-if="hasLineOverride(rate)" label="历史小计调整">
          <el-button link @click="clearLineOverride(rate)">改为按当前单价与工作量计算</el-button>
        </el-form-item>
      </div>
      <el-button type="danger" link @click="model.rates.splice(index,1)">移除此项</el-button>
    </section>
    <el-button :disabled="!referenceOnly&&!directions.length" @click="addRate">添加组合单价</el-button>
    <p v-if="!referenceOnly&&!directions.length">请先在项目表单选择完整的口译方向。</p>
    </template>
    <template v-if="!referenceOnly&&!fixed">
      <el-form-item label="加班费"><el-checkbox v-model="model.has_overtime">有加班费</el-checkbox></el-form-item>
      <div v-if="model.has_overtime" class="money-row"><TaxPriceFields v-model="model.overtime.taxPrices" prefix="overtime.taxPrices" :show-unit-prices="false" @change="value=>model.overtime.amount=value.totalExclTax??value.totalInclTax??model.overtime.amount" /><el-form-item label="原加班费（税口径未确认）" prop="overtime.amount" :rules="[{required:true,message:'请填写总加班费'}]"><el-input-number v-model="model.overtime.amount" :min="0" :precision="2" :controls="false" /></el-form-item><el-form-item label="加班费货币"><el-select v-model="model.overtime.currency"><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item></div>
    </template>
    <template v-if="!referenceOnly&&!hideTotals">
      <section class="settlement-totals" :class="{'settlement-totals--compact':compact}" data-dialog-field-search-group :data-dialog-field-search-group-title="fixed?'固定收费':'总价与说明'">
        <div class="settlement-totals-heading"><h3>{{fixed?'固定收费':'总价与说明'}}</h3><el-button v-if="compact&&!fixed" size="small" :disabled="amountRows.length>=20" @click="addAmount">添加总价调整</el-button></div>
        <template v-if="!fixed">
          <p>各行小计四舍五入到分，再按币种合计并加上加班费。需要改价时，可单独填写调整后总价。</p>
          <div class="line-totals">
            <el-form-item v-for="basis in taxBases" :key="basis.value" :label="basis.label+'总价（自动计算）'">
              <ReadonlyField type="textarea" autosize :model-value="formatFinanceAmounts(interpretationFinanceTotals(model,basis.value,true))" source="auto" />
            </el-form-item>
          </div>
        </template>
        <div v-for="(row,index) in amountRows" :key="index" class="money-row">
          <el-form-item v-for="basis in taxBases" :key="basis.value"
            :label="basis.label+(fixed?'固定收费':'调整后总价')">
            <el-input-number v-model="row.taxPrices[basis.field]" :min="0" :precision="2" :controls="false"
              @update:model-value="row.amount=row.taxPrices.totalExclTax??row.taxPrices.totalInclTax??row.amount" />
          </el-form-item>
          <el-form-item v-if="row.taxPrices?.totalExclTax==null&&row.taxPrices?.totalInclTax==null" :label="fixed?'固定收费（税口径未确认）':'调整后总价（税口径未确认）'" :prop="`${amountKey}.${index}.amount`" :rules="[{required:true,message:'请填写金额'}]">
            <el-input-number v-model="row.amount" :min="0" :precision="2" :controls="false" />
          </el-form-item>
          <el-form-item label="货币" :prop="`${amountKey}.${index}.currency`" :rules="[{required:true,pattern:/^[A-Z]{3}$/,message:'填写三位大写货币代码'}]"><el-select v-model="row.currency" filterable allow-create><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item>
          <el-button link type="danger" @click="amountRows.splice(index,1)">移除</el-button>
        </div>
        <el-form-item v-if="fixed" label="固定收费金额" prop="fixed_totals" :rules="[{type:'array',required:true,min:1,message:'请至少添加一项固定收费'}]">
          <el-button :disabled="amountRows.length>=20" @click="addAmount">添加固定收费</el-button>
        </el-form-item>
        <el-button v-if="!fixed&&!compact" :disabled="amountRows.length>=20" @click="addAmount">添加总价调整</el-button>
        <div v-if="compact" class="settlement-compact-notes"><slot name="notes"><el-form-item label="内部说明"><el-input v-model="model.explanation" type="textarea" :rows="2" maxlength="5000" show-word-limit /></el-form-item></slot></div>
      </section>
    </template>
    <el-form-item v-if="!compact||referenceOnly" :label="referenceOnly?'说明':'内部说明'"><el-input v-model="model.explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import {interpretationCurrencies as currencies,interpretationUnits,interpretationLineTotal,
  interpretationFinanceTotals,formatFinanceAmounts} from '@/utils/interpretationCustomerFinance'
import {quotationMoney} from '@/utils/quotation'
import TaxPriceFields from './TaxPriceFields.vue'
import {taxPriceForm,taxUnitAmount} from '@/utils/taxPrices'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
const model=defineModel({type:Object,required:true})
const props=defineProps({directions:{type:Array,default:()=>[]},referenceOnly:Boolean,compact:Boolean,hideTotals:Boolean})
const fixed=computed(()=>!props.referenceOnly&&model.value.settlement.pricing_mode==='fixed')
const amountKey=computed(()=>fixed.value?'fixed_totals':'adjusted_totals')
const amountRows=computed(()=>model.value[amountKey.value])
const taxBases=[
  {value:'excl_tax',label:'不含税',field:'totalExclTax'},
  {value:'incl_tax',label:'含税',field:'totalInclTax'},
]
const hasLineOverride=row=>row.taxPrices?.totalExclTax!=null||row.taxPrices?.totalInclTax!=null
function clearLineOverride(row){row.taxPrices={...row.taxPrices,totalExclTax:undefined,totalInclTax:undefined}}
function lineTotal(row,basis){
  const amount=interpretationLineTotal(row,basis)
  return amount==null?'':`${row.currency} ${quotationMoney(amount)}`
}
function addAmount(){amountRows.value.push({amount:undefined,currency:'CNY',taxPrices:taxPriceForm()})}
const directionOptions=computed(()=>[...new Set(props.directions.map(x=>x.label))])
function addRate(){model.value.rates.push({direction:props.directions[0]?.label||'',amount:undefined,currency:'CNY',taxPrices:taxPriceForm(),unit:'天',quantity:1,hours:8,includes_lunch:false})}
function unitChanged(row){row.hours=row.unit==='天'?8:row.unit==='半天'?3:null;if(row.unit!=='天')row.includes_lunch=false}
</script>
<style scoped>
 .line-totals{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;width:100%}.line-totals .el-form-item{width:auto!important}.settlement-totals{margin:16px 0;padding:14px;border:1px solid var(--el-border-color);border-radius:8px}p{font-size:12px;color:#64748b}.rate-row{display:flex;flex-wrap:wrap;gap:10px;border:1px solid #e2e8f0;border-radius:6px;padding:12px;margin:12px 0}.rate-row .el-form-item{width:170px}.rate-row .el-form-item:first-child{width:280px}.el-select,.el-input-number{width:100%}.money-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}.money-row .el-select{width:130px}
</style>

<style scoped>
.settlement-totals-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.settlement-totals--compact{margin:12px 0;padding:12px}
.settlement-totals--compact h3{margin:0;font-size:14px}
.settlement-totals--compact p{margin:4px 0 8px;line-height:1.4}
.settlement-totals--compact :deep(.el-form-item){margin-bottom:10px}
.settlement-totals--compact .line-totals{gap:8px 12px}
.settlement-compact-notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:4px}
.settlement-compact-notes :deep(.el-form-item){min-width:0;margin-bottom:0}
@media(max-width:700px){.settlement-compact-notes{grid-template-columns:minmax(0,1fr)}}
</style>
