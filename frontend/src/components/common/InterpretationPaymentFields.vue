<template>
  <section class="finance-region" data-dialog-field-search-group data-dialog-field-search-group-title="付款情况">
    <h3>付款情况</h3>
    <el-form-item label="付款状态"><el-select :model-value="model.settlement.payment_status" :disabled="switching" @update:model-value="changeStatus"><el-option label="未付款" value="unrecorded" /><el-option label="已付定金" value="deposit" /><el-option label="已付进度款" value="partial" /><el-option label="已付全款（含尾款）" value="full" /></el-select></el-form-item>
    <template v-if="model.settlement.payment_status!=='unrecorded'||model.settlement.payments.length">
      <section v-for="(receipt,index) in model.settlement.payments" :key="index" class="finance-receipt" data-dialog-field-search-group :data-dialog-field-search-group-title="'付款明细 '+(index+1)">
        <el-form-item label="付款类型"><el-select :model-value="receipt.stage_type||legacyStage(index)" @update:model-value="receipt.stage_type=$event"><el-option label="定金" value="deposit" /><el-option label="进度款" value="mid" /><el-option label="尾款" value="tail" /><el-option label="一次性全款" value="full" /></el-select></el-form-item>
        <el-form-item label="实际付款金额" :prop="'settlement.payments.'+index+'.amount'" :rules="[{required:true,message:'请填写实际付款金额'}]"><el-input-number v-model="receipt.amount" :min="0" :precision="2" :controls="false" /></el-form-item>
        <el-form-item label="付款货币"><el-select v-model="receipt.currency" filterable allow-create><el-option v-for="currency in interpretationCurrencies" :key="currency" :value="currency" /></el-select></el-form-item>
        <el-form-item label="付款日期"><el-date-picker v-model="receipt.received_on" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="付款备注"><el-input v-model="receipt.note" maxlength="2000" /></el-form-item>
        <el-button link type="danger" @click="model.settlement.payments.splice(index,1)">移除本次付款</el-button>
      </section>
      <el-button :disabled="model.settlement.payments.length>=100" @click="addPayment">{{model.settlement.payment_status==='full'&&model.settlement.payments.length?'新增尾款明细':'新增付款明细'}}</el-button>
    </template>
    <div class="payment-summary">
      <el-form-item label="应付项目计费金额"><ReadonlyField :model-value="formatFinanceAmounts(due)" source="auto" /></el-form-item>
      <el-form-item label="实际付款（各期累计）"><ReadonlyField :model-value="formatFinanceAmounts(received)" source="auto" /></el-form-item>
      <el-form-item label="付款差额（累计实付－应付）"><ReadonlyField :model-value="formatFinanceAmounts(difference)" source="auto" /></el-form-item>
    </div>
    <el-alert v-if="model.settlement.payment_status==='full'&&Object.values(difference).some(value=>Number(value)!==0)" type="warning" :closable="false" title="已选已付全款，但累计实付与应付金额不一致，请核对金额并填写付款说明。" />
    <small>负数为尚欠，正数为超付；按币种核对，不自动换算。</small>
    <el-form-item label="付款说明"><el-input v-model="model.settlement.payment_note" type="textarea" :rows="2" maxlength="5000" /></el-form-item>
  </section>
</template>
<script setup>
import {computed,ref} from 'vue'
import {ElMessageBox} from 'element-plus'
import ReadonlyField from './ReadonlyField.vue'
import {quotationLineCents,quotationMoney} from '@/utils/quotation'
import {interpretationCurrencies,interpretationFinanceTotals,formatFinanceAmounts} from '@/utils/interpretationCustomerFinance'
const model=defineModel({type:Object,required:true}),switching=ref(false)
const props=defineProps({amounts:Object})
const due=computed(()=>props.amounts??interpretationFinanceTotals(model.value))
const received=computed(()=>{const sums={};for(const row of model.value.settlement.payments){if(row.amount==null||!Number.isFinite(Number(row.amount)))continue;const cents=quotationLineCents({quantity:1,unit_price:row.amount},2);sums[row.currency]=(sums[row.currency]||0n)+cents}return Object.fromEntries(Object.entries(sums).map(([key,value])=>[key,quotationMoney(value)]))})
const difference=computed(()=>Object.fromEntries([...new Set([...Object.keys(due.value),...Object.keys(received.value)])].map(currency=>[currency,quotationMoney(quotationLineCents({quantity:1,unit_price:received.value[currency]||0},2)-quotationLineCents({quantity:1,unit_price:due.value[currency]||0},2))])))
function legacyStage(index){const status=model.value.settlement.payment_status;return status==='deposit'&&index===0?'deposit':status==='full'&&model.value.settlement.payments.length===1?'full':status==='full'&&index===model.value.settlement.payments.length-1?'tail':'mid'}
function addPayment(){const status=model.value.settlement.payment_status;model.value.settlement.payments.push({currency:Object.keys(due.value)[0]||'CNY',received_on:null,note:'',stage_type:status==='deposit'&&!model.value.settlement.payments.length?'deposit':status==='full'?model.value.settlement.payments.length?'tail':'full':'mid'})}
async function changeStatus(value){if(switching.value||value===model.value.settlement.payment_status)return;switching.value=true;try{if(value==='unrecorded'&&model.value.settlement.payments.length){try{await ElMessageBox.confirm('改为未付款将清空当前付款明细，保存后生效并保留修改记录。是否继续？','清空付款明细',{type:'warning',confirmButtonText:'继续并清空',cancelButtonText:'取消',closeOnClickModal:false})}catch{return}model.value.settlement.payments=[]}model.value.settlement.payment_status=value;if(value!=='unrecorded'&&!model.value.settlement.payments.length)addPayment()}finally{switching.value=false}}
</script>
<style scoped>
.finance-region{margin:12px 0;padding:12px;border:1px solid var(--el-border-color);border-radius:8px}h3{margin:0 0 10px;font-size:14px}.finance-receipt,.payment-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr));gap:10px}.finance-receipt{border:1px solid var(--el-border-color-lighter);padding:10px;border-radius:6px;margin-bottom:10px}.finance-receipt :deep(.el-input-number),.finance-receipt :deep(.el-date-editor){max-width:100%;width:100%}small{display:block;color:var(--el-text-color-secondary);font-size:12px;margin:5px 0 10px}.payment-summary{margin-top:12px}
</style>
