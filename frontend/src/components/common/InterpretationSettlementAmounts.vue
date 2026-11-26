<template>
  <section class="finance-region total-notes-region" data-dialog-field-search-group data-dialog-field-search-group-title="总价与说明">
    <div class="total-notes-heading"><h3>{{fixed?'固定收费与说明':'总价与说明'}}</h3><div class="billing-mode"><span>计费口径</span><el-radio-group v-model="model.settlement.tax_basis" size="small"><el-radio-button value="excl_tax">不含税</el-radio-button><el-radio-button value="incl_tax">含税</el-radio-button><el-radio-button v-if="model.settlement.tax_basis==='legacy'" value="legacy">税口径未确认</el-radio-button></el-radio-group><small>用于本订单计费及新生成的对账单</small></div></div>
    <div class="total-notes-body">
      <div class="tax-totals">
        <div v-for="currency in currencies" :key="currency" class="currency-totals">
          <div v-for="basis in bases" :key="basis.key" class="tax-total">
            <h4 :class="{'total-filled':hasAmount(currency,basis)}">{{basis.label}}{{fixed?'固定收费':'总价'}} <small>{{currency}}</small></h4>
            <div class="amount-inputs">
              <el-form-item v-if="!fixed" label="自动计算" :data-dialog-field-search-aliases="basis.label+'总价'"><ReadonlyField :model-value="baseTotal(currency,basis.value)" source="auto" /></el-form-item>
              <el-form-item v-if="!fixed" label="折扣" :data-dialog-field-search-label="basis.label+'折扣'"><OrderDiscountField :model-value="adjustment(currency)[basis.key+'_discount']" :label="currency+' '+basis.label+'折扣'" @update:model-value="set(currency,basis.key+'_discount',$event)" /></el-form-item>
              <el-form-item :label="fixed?'固定收费':'调整后金额'" :data-dialog-field-search-label="basis.label+(fixed?'固定收费':'调整后金额')" :data-dialog-field-search-aliases="basis.label+'调整后价格'"><el-input-number :model-value="manualAmount(currency,basis)" :aria-label="currency+' '+basis.label+(fixed?'固定收费':'调整后金额')" :min="0" :precision="2" :controls="false" placeholder="选填" @update:model-value="setAmount(currency,basis,$event)" /></el-form-item>
            </div>
          </div>
        </div>
        <el-form-item v-if="fixed" label="固定收费金额" prop="fixed_totals" :rules="[{type:'array',required:true,min:1,message:'请填写至少一项固定收费'}]"><el-button link @click="addCurrency">添加币种</el-button></el-form-item>
      </div>
      <div class="notes-grid"><el-form-item label="内部说明"><el-input v-model="model.explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item><el-form-item label="客户说明"><el-input v-model="model.settlement.customer_explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item></div>
    </div>
  </section>
</template>
<script setup>
import {computed} from 'vue'
import {ElMessageBox} from 'element-plus'
import ReadonlyField from './ReadonlyField.vue'
import OrderDiscountField from './OrderDiscountField.vue'
import {interpretationFinanceTotals} from '@/utils/interpretationCustomerFinance'
import {taxPriceForm} from '@/utils/taxPrices'
const model=defineModel({type:Object,required:true})
const fixed=computed(()=>model.value.settlement.pricing_mode==='fixed')
const bases=computed(()=>[{key:'excl',value:'excl_tax',field:'totalExclTax',label:'不含税'},{key:'incl',value:'incl_tax',field:'totalInclTax',label:'含税'},...(model.value.settlement.tax_basis==='legacy'?[{key:'legacy',value:'legacy',label:'税口径未确认'}]:[])])
const currencies=computed(()=>{const keys=new Set([...(model.value.settlement_adjustments||[]),...(model.value.fixed_totals||[]),...(model.value.adjusted_totals||[])].map(row=>row.currency));for(const basis of bases.value)Object.keys(interpretationFinanceTotals(model.value,basis.value,false,false)).forEach(key=>keys.add(key));return keys.size?[...keys].sort():['CNY']})
const adjustment=currency=>(model.value.settlement_adjustments||[]).find(row=>row.currency===currency)||{}
const baseTotal=(currency,basis)=>interpretationFinanceTotals(model.value,basis,false,false)[currency]??'—（待补充）'
const fixedRow=currency=>model.value.fixed_totals.find(row=>row.currency===currency)
const manualAmount=(currency,basis)=>fixed.value?(basis.value==='legacy'?fixedRow(currency)?.amount:fixedRow(currency)?.taxPrices?.[basis.field]):adjustment(currency)[basis.key+'_amount']
const hasAmount=(currency,basis)=>manualAmount(currency,basis)!=null||interpretationFinanceTotals(model.value,basis.value,false,false)[currency]!=null
function set(currency,key,value){const rows=model.value.settlement_adjustments||=[];let row=rows.find(item=>item.currency===currency);if(!row){row={currency};rows.push(row)}if(value==null||value==='')delete row[key];else row[key]=value;if(Object.keys(row).length===1)rows.splice(rows.indexOf(row),1)}
function setAmount(currency,basis,value){
 if(!fixed.value){set(currency,basis.key+'_amount',value);return}
 let row=fixedRow(currency);if(!row){if(value==null)return;row={currency,amount:value,taxPrices:taxPriceForm()};model.value.fixed_totals.push(row)}
 if(basis.value==='legacy')row.amount=value;else{row.taxPrices[basis.field]=value;row.amount=row.taxPrices.totalExclTax??row.taxPrices.totalInclTax??undefined}
 if(row.amount==null&&row.taxPrices.totalExclTax==null&&row.taxPrices.totalInclTax==null)model.value.fixed_totals.splice(model.value.fixed_totals.indexOf(row),1)
}
async function addCurrency(){try{const {value}=await ElMessageBox.prompt('填写三位大写货币代码','添加固定收费币种',{inputPattern:/^[A-Z]{3}$/,inputErrorMessage:'填写三位大写货币代码',inputValue:'CNY'});if(!fixedRow(value))model.value.fixed_totals.push({currency:value,amount:undefined,taxPrices:taxPriceForm()})}catch{}}
</script>
<style scoped>
.finance-region{margin:18px 0;padding:18px;border:1px solid var(--el-border-color);border-radius:8px;min-width:0}.total-notes-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:18px}h3{margin:0;font-size:14px}.billing-mode{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.billing-mode small{color:var(--el-text-color-secondary)}.total-notes-body{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:20px}.currency-totals,.notes-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.currency-totals+.currency-totals{margin-top:12px}.tax-total,.tax-totals,.notes-grid>.el-form-item{min-width:0}.tax-total h4{display:inline-block;margin:0 0 14px;padding:5px 8px 5px 0;font-size:14px;font-weight:500}.tax-total h4 small{margin-left:6px}.tax-total h4.total-filled{background:#111;color:white;padding-left:8px;border-radius:4px;font-weight:600}.amount-inputs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.amount-inputs>.el-form-item:only-child{grid-column:1/-1}.amount-inputs :deep(.el-input-number){width:100%}.amount-inputs :deep(.el-form-item__label){font-size:12px;color:var(--el-text-color-secondary)}.notes-grid>.el-form-item{margin:0}@media(max-width:1100px){.total-notes-body{grid-template-columns:minmax(0,1fr)}}@media(max-width:650px){.currency-totals,.notes-grid{grid-template-columns:minmax(0,1fr)}.billing-mode{align-items:flex-start}.amount-inputs{gap:6px}}
</style>
