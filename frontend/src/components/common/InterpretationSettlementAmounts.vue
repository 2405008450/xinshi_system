<template>
  <section class="finance-region" data-dialog-field-search-group data-dialog-field-search-group-title="结算金额">
    <h3>结算金额</h3>
    <p>计算顺序：折扣前总价 → 折扣 → 调整后价格。填写调整后价格时优先采用该金额；未填写不按零处理，币种分别计算。</p>
    <div v-for="currency in currencies" :key="currency" class="settlement-currency">
      <strong>{{currency}}</strong>
      <div class="settlement-amount-grid">
        <div v-for="basis in bases" :key="basis.key" class="settlement-amount-column">
          <h4>{{basis.label}}</h4>
          <el-form-item :label="basis.label+'折扣前总价'"><ReadonlyField :model-value="baseTotal(currency,basis.value)" source="auto" /></el-form-item>
          <div class="settlement-adjustment-inputs">
            <el-form-item :label="basis.label+'折扣'"><OrderDiscountField :model-value="adjustment(currency)[basis.key+'_discount']" :label="currency+' '+basis.label+'折扣'" @update:model-value="set(currency,basis.key+'_discount',$event)" /><small>例如 90 表示按 90% 结算</small></el-form-item>
            <el-form-item :label="basis.label+'调整后价格'"><el-input-number :model-value="adjustment(currency)[basis.key+'_amount']" :aria-label="currency+' '+basis.label+'调整后价格'" :min="0" :precision="2" :controls="false" placeholder="选填，优先于折扣" @update:model-value="set(currency,basis.key+'_amount',$event)" /></el-form-item>
          </div>
          <el-form-item :label="basis.label+'结算总价'"><ReadonlyField :model-value="finalTotal(currency,basis.value)" source="auto" /></el-form-item>
        </div>
      </div>
    </div>
    <el-form-item label="当前计费合计"><ReadonlyField :model-value="formatFinanceAmounts(interpretationFinanceTotals(model))" source="auto" /></el-form-item>
  </section>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import OrderDiscountField from './OrderDiscountField.vue'
import {interpretationFinanceTotals,formatFinanceAmounts} from '@/utils/interpretationCustomerFinance'
const model=defineModel({type:Object,required:true})
const bases=computed(()=>[{key:'excl',value:'excl_tax',label:'不含税'},{key:'incl',value:'incl_tax',label:'含税'},...(model.value.settlement.tax_basis==='legacy'?[{key:'legacy',value:'legacy',label:'税口径未确认'}]:[])])
const currencies=computed(()=>{const keys=new Set((model.value.settlement_adjustments||[]).map(row=>row.currency));for(const basis of bases.value)Object.keys(interpretationFinanceTotals(model.value,basis.value,false,false)).forEach(key=>keys.add(key));return keys.size?[...keys].sort():['CNY']})
const adjustment=currency=>(model.value.settlement_adjustments||[]).find(row=>row.currency===currency)||{}
const baseTotal=(currency,basis)=>{const value=interpretationFinanceTotals(model.value,basis,false,false)[currency];return value==null?'待计算':`${currency} ${value}`}
const finalTotal=(currency,basis)=>{const value=interpretationFinanceTotals(model.value,basis)[currency];return value==null?'待计算':`${currency} ${value}`}
function set(currency,key,value){const rows=model.value.settlement_adjustments||=[];let row=rows.find(item=>item.currency===currency);if(!row){row={currency};rows.push(row)}if(value==null||value==='')delete row[key];else row[key]=value;if(Object.keys(row).length===1)rows.splice(rows.indexOf(row),1)}
</script>
<style scoped>
.finance-region{margin:12px 0;padding:12px;border:1px solid var(--el-border-color);border-radius:8px;min-width:0}h3{margin:0 0 8px;font-size:14px}h4{margin:0 0 8px}p,small{font-size:12px;color:var(--el-text-color-secondary)}p{margin:4px 0 10px}.settlement-currency{margin-bottom:12px}.settlement-amount-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(270px,100%),1fr));gap:12px;margin-top:8px}.settlement-amount-column{min-width:0;padding:10px;border:1px solid var(--el-border-color-lighter);border-radius:6px}.settlement-adjustment-inputs{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}.settlement-amount-column :deep(.el-input-number){width:100%}.settlement-amount-column :deep(.el-form-item){margin-bottom:10px}small{display:block;line-height:1.4}
</style>
