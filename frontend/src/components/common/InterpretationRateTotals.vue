<template>
 <div class="interpretation-rate-totals">
  <div v-for="basis in bases" :key="basis.key" class="rate-total-basis">
   <div v-for="currency in currencies" :key="currency" class="rate-total-line">
    <el-form-item :label="`${basis.label}${title} ${currency}`"><ReadonlyField :model-value="display(basis.key,currency)" source="auto" placeholder="填写单价和数量后计算"/></el-form-item>
    <details class="rate-adjustments"><summary>折扣 / 调整后价格</summary><div class="rate-adjustment-inputs">
     <el-form-item label="折扣（%）"><el-input-number :model-value="value(currency,basis.prefix+'_discount')" :min="1" :max="99" :precision="0" :controls="false" placeholder="90 即九折" @update:model-value="update(currency,basis.prefix+'_discount',$event)"/></el-form-item>
     <el-form-item label="调整后价格"><el-input-number :model-value="value(currency,basis.prefix+'_amount')" :min="0" :precision="2" :controls="false" :placeholder="discounted(basis,currency)" @update:model-value="update(currency,basis.prefix+'_amount',$event)"/></el-form-item>
    </div></details>
   </div>
  </div>
 </div>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import {quotationMoney} from '@/utils/quotation'
const props=defineProps({rows:{type:Array,default:()=>[]},title:String,adjustments:{type:Array,default:()=>[]},totals:{type:Function,required:true}})
const emit=defineEmits(['update:adjustments'])
const bases=[{key:'excl_tax',prefix:'excl',label:'不含税'},{key:'incl_tax',prefix:'incl',label:'含税'}]
const currencies=computed(()=>[...new Set(props.rows.map(row=>row.currency||'CNY'))])
const value=(currency,key)=>{const amount=props.adjustments.find(row=>row.currency===currency)?.[key];return amount==null?undefined:Number(amount)}
function update(currency,key,next){const rows=props.adjustments.map(row=>({...row}));let row=rows.find(row=>row.currency===currency);if(!row){row={currency};rows.push(row)}if(next==null)delete row[key];else row[key]=next;emit('update:adjustments',rows.filter(row=>Object.keys(row).length>1))}
function display(basis,currency){const cents=props.totals(basis)[currency];return cents==null?'':quotationMoney(cents)}
function discounted(basis,currency){const cents=props.totals(basis.key)[currency],discount=value(currency,basis.prefix+'_discount');return cents==null?'选填':quotationMoney(discount==null?cents:(cents*BigInt(discount)+50n)/100n)}
</script>
<style scoped>.interpretation-rate-totals{margin:14px 0}.rate-total-line{display:grid;grid-template-columns:minmax(150px,1fr) minmax(160px,2fr);gap:12px;align-items:start}.rate-adjustments{padding-top:8px}.rate-adjustments summary{cursor:pointer;color:var(--el-color-primary);padding:0 0 12px}.rate-adjustment-inputs{display:grid;grid-template-columns:1fr 1fr;gap:12px}.rate-adjustments[open]{padding-top:0}.rate-total-line :deep(.el-input-number){width:100%}@media(max-width:640px){.rate-total-line,.rate-adjustment-inputs{grid-template-columns:1fr}}
</style>
