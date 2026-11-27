<template>
<section class="payment-registration-fields" data-dialog-field-search-group>
        <PaymentConfirmationFields :history-url="historyUrl" :section-prefix="sectionPrefix" :pricing-mode="form.pricingMode" :billing-tax-mode="effectiveBillingTaxMode(form)" :draft-totals="effectiveDraftTotals" :summary-label="summaryLabel" :model-value="confirmation" :project-id="projectId" :details-in-payments="depositSelected" :payments="payments" :prefix="prefix" @update:model-value="updateConfirmation" @reference-change="updateReference">
          <template #actions><slot name="actions" /></template>
          <template v-if="matchOrders.length" #match-full>
            <el-button @click="openMatch()">{{matchLabel}}</el-button>
            <span v-if="confirmation.matchedOrderIds?.length">已选 {{confirmation.matchedOrderIds.length}} 笔</span>
          </template>
          <template #confirm-full>
            <el-button v-if="canConfirm" :disabled="confirmDisabled || confirmation.fullPaymentAmount==null" @click="emit('confirm-payment',null)">{{confirmation.fullPaymentConfirmedAt?'重新确认全款':'确认全款'}}</el-button>
          </template>
        </PaymentConfirmationFields>
        <TranslationSettlementNumbers v-if="projectId && !depositSelected" :project-id="projectId" :show-empty="isFull" />
        <el-form-item v-if="showDepositCurrency&&currencyOptions&&depositSelected" label="付款币种"><el-select v-model="confirmation.fullPaymentCurrency"><el-option v-for="currency in currencyOptions" :key="currency" :value="currency" /></el-select></el-form-item>
        <el-form-item v-if="currencyOptions&&hasFinal&&new Set(payments.map(item=>item.currency)).size>1" label="付款差异说明" :prop="`${prefix}.mismatchReason`"><el-input v-model="confirmation.mismatchReason" type="textarea" :rows="2" maxlength="2000" placeholder="多币种尾款与项目计费合计不一致时填写原因" /></el-form-item>
        <p v-if="isFull" class="payment-help">已确认全款，无需填写分期明细；切换时确认清除的明细会记入历史。</p>
        <template v-if="depositSelected">
        <el-descriptions :column="3" border class="payment-summary"><el-descriptions-item label="预定合计">{{total('planned_amount')}}</el-descriptions-item><el-descriptions-item label="实际付款合计">{{total('actual_amount')}}</el-descriptions-item><el-descriptions-item label="付款状态">{{paymentStatus}}</el-descriptions-item></el-descriptions>
        <details :key="projectId" class="payment-details">
          <summary>
            <span class="payment-details-collapse">折叠全部付款明细</span>
            <span class="payment-details-expand">展开全部付款明细</span>
            <span>（{{payments.length}} 笔）</span>
          </summary>
        <TranslationSettlementNumbers v-if="projectId" :project-id="projectId" show-empty />
        <div v-for="(item,index) in payments" :key="item.id||index" class="project-payment-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`${sectionPrefix}付款明细 ${index+1}`">
          <div class="payment-row-heading">
            <strong>{{sectionPrefix}}付款明细 {{index+1}}</strong>
            <div>
              <el-button v-if="canConfirm" link type="primary" :disabled="confirmDisabled || !item.id || item.actual_amount==null" @click="emit('confirm-payment',item.id)">{{item.confirmed_at?'重新确认':'确认付款'}}</el-button>
              <el-button link type="danger" @click="removePayment(index)">移除</el-button>
            </div>
          </div>
          <el-form-item v-if="currencyOptions" label="付款币种"><el-select v-model="item.currency" @change="syncFromDetails"><el-option v-for="currency in currencyOptions" :key="currency" :value="currency" /></el-select></el-form-item>
          <el-row :gutter="12">
            <el-col :xs="12" :md="6"><el-form-item label="阶段"><ReadonlyField v-if="index===0&&depositSelected" model-value="定金" source="auto" /><el-select v-else v-model="item.stage_type" @change="syncFromDetails"><el-option label="中期款" value="mid" /><el-option label="尾款" value="final" :disabled="hasFinal && item.stage_type!=='final'" /></el-select></el-form-item></el-col>
            <el-col :xs="12" :md="6"><el-form-item label="期次"><ReadonlyField :model-value="String(index+1)" source="auto" /></el-form-item></el-col>
            <el-col :xs="12" :md="6"><el-form-item label="预定金额"><el-input-number v-model="item.planned_amount" :min="0" :precision="2" :controls="false" /></el-form-item></el-col>
            <el-col :xs="12" :md="6">
              <el-form-item label="实际金额" :prop="`paymentDraft.${index}.actual_amount`"
                :rules="hasFinal?[{required:true,type:'number',message:'登记尾款后请填写每次实际金额',trigger:'change'}]:[]">
                <el-input-number v-model="item.actual_amount" @change="syncFromDetails" :min="0" :precision="2" :controls="false" />
                <div v-if="matchOrders.length" class="payment-detail-match">
                  <el-button link type="primary" @click="openMatch(item)">{{matchLabel}}</el-button>
                  <span v-if="item.matched_order_ids?.length">已选 {{item.matched_order_ids.length}} 笔 · {{matchTotalsLabel(item.matched_order_ids)}}</span>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12"><el-col :xs="24" :md="12"><el-form-item label="付款时间"><el-date-picker v-model="item.payment_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" clearable /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="付款方式"><PaymentAccountSelect v-model="item.payment_method" @update:model-value="syncFromDetails" /></el-form-item></el-col></el-row>
          <el-form-item label="支付截图及备注"><ScreenshotInput v-model="item.proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="可粘贴、拖入或上传本次付款截图，填写付款备注" upload-help="每条明细的截图及备注独立保存，修改或移除后可在付款修改记录中查看。" /></el-form-item>
          <el-row :gutter="12">
            <el-col :xs="24" :md="12"><el-form-item label="确认人"><ReadonlyField :model-value="item.confirmed_by_name || ''" source="auto" placeholder="待行政部确认" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="确认时间"><ReadonlyField :model-value="item.confirmed_at ? formatBusinessDateTime(item.confirmed_at) : ''" source="auto" placeholder="待行政部确认" /></el-form-item></el-col>
          </el-row>
        </div>
        <el-button :disabled="payments.length>=100" @click="addPayment">新增付款明细</el-button>
        </details>
        </template>

        <slot name="footer" />
        <PaymentOrderMatchDialog v-if="matching" :title="matchLabel" :orders="matchOrders"
          :order-ids="matching.ids" :currency="matching.currency" @close="matching=null" @apply="applyMatch" />
</section>
</template>

<script setup>
import {computed,ref,watch} from 'vue'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {effectiveBillingTaxMode} from '@/utils/billingTaxMode'
import PaymentConfirmationFields from './PaymentConfirmationFields.vue'
import ReadonlyField from './ReadonlyField.vue'
import PaymentAccountSelect from './PaymentAccountSelect.vue'
import ScreenshotInput from './ScreenshotInput.vue'
import PaymentOrderMatchDialog from './PaymentOrderMatchDialog.vue'
import TranslationSettlementNumbers from './TranslationSettlementNumbers.vue'
import {collectMatchTotals,formatMatchTotals} from '@/utils/paymentOrderMatching'
import {paymentConfirmationForm,fixFirstDepositStage,clearPaymentSelection} from '@/utils/paymentConfirmation'
const form=defineModel({type:Object,required:true})
const props=defineProps({sectionPrefix:{type:String,default:''},projectId:String,draftTotals:{type:Array,default:null},summaryLabel:String,prefix:{type:String,default:'paymentConfirmation'},canConfirm:Boolean,confirmDisabled:Boolean,matchOrders:{type:Array,default:()=>[]},matchLabel:String,historyUrl:{type:String,default:''},currencyOptions:{type:Array,default:null},showDepositCurrency:{type:Boolean,default:true}})
const emit=defineEmits(['confirm-payment'])
const confirmation=computed({get:()=>form.value.paymentConfirmation,set:value=>{form.value.paymentConfirmation=value}})
const payments=computed({get:()=>form.value.paymentDraft||[],set:value=>{form.value.paymentDraft=value}})
const depositSelected=computed(()=>confirmation.value?.isPaid&&confirmation.value.paymentOption==='deposit')
const isFull=computed(()=>confirmation.value?.isPaid&&confirmation.value.paymentOption==='full')
const matching=ref(null)
const matchTotals=ids=>collectMatchTotals(props.matchOrders,new Set(ids))
const matchTotalsLabel=ids=>formatMatchTotals(matchTotals(ids))
const effectiveDraftTotals=computed(()=>{
  const ids=confirmation.value?.matchedOrderIds
  if(!isFull.value||!ids?.length||!props.matchOrders.length)return props.draftTotals
  return Object.entries(matchTotals(ids)).map(([currency,amount])=>({
    key:`orders:${currency}`,label:'所选订单计费合计',currency,amount,
  }))
})
function openMatch(row=null){
  matching.value={row,ids:row?.matched_order_ids||(!row?confirmation.value.matchedOrderIds:[])||[],
    currency:row?undefined:confirmation.value.fullPaymentCurrency}
}
function applyMatch(ids){
  const row=matching.value.row
  if(row)row.matched_order_ids=ids
  else confirmation.value={...confirmation.value,matchedOrderIds:ids,fullPaymentConfirmedAt:null,fullPaymentConfirmedByName:null}
  matching.value=null
}
const hasFinal=computed(()=>depositSelected.value&&payments.value.some(item=>item.stage_type==='final'))
const cents=value=>BigInt(Number(value||0).toFixed(2).replace('.',''))
const totalCents=key=>payments.value.reduce((sum,item)=>sum+cents(item[key]),0n)
const total=key=>{if(props.currencyOptions){const sums=new Map();for(const row of payments.value){const currency=row.currency||confirmation.value.fullPaymentCurrency;sums.set(currency,(sums.get(currency)||0n)+cents(row[key]))}return [...sums].map(([currency,value])=>`${currency} ${value/100n}.${String(value%100n).padStart(2,'0')}`).join(' / ')||'0.00'}const value=totalCents(key);return `${value/100n}.${String(value%100n).padStart(2,'0')}`}
const paymentStatus=computed(()=>hasFinal.value?'尾款核对（累计实付）':totalCents('actual_amount')>0n?'已付定金／部分付款':'已确认定金（待补充明细）')
function addPayment(){if(!depositSelected.value||payments.value.length>=100)return;const stage=payments.value.length?'mid':'deposit';payments.value=[...payments.value,{...(props.currencyOptions?{currency:confirmation.value.fullPaymentCurrency||'CNY'}:{}),stage_type:stage,stage_no:payments.value.length+1,planned_amount:undefined,actual_amount:undefined,payment_time:null,payment_method:confirmation.value.paymentAccount||'',proofs:payments.value.length?'':confirmation.value.proofs||''}]}
function ensureFirstDeposit(){if(!depositSelected.value)return;if(!payments.value.length)addPayment();fixFirstDepositStage(confirmation.value,payments.value);if(!payments.value[0].payment_method)payments.value[0].payment_method=confirmation.value.paymentAccount||''}
function updateReference(key){
  // 核对口径异步载入只更新参考值，不能触发付款明细重算或标记人工修改。
  confirmation.value.fullPaymentTotalKey=key
}
function updateConfirmation(value){
  if(value.replaceDetails&&(!confirmation.value.replaceDetails||value.paymentOption!==confirmation.value.paymentOption))payments.value=[]
  confirmation.value=paymentConfirmationForm(value)
  if(!confirmation.value.isPaid){payments.value=[];confirmation.value=clearPaymentSelection(confirmation.value);return}
  ensureFirstDeposit()
  if(hasFinal.value)syncFromDetails()
  for(const item of payments.value)if(!item.payment_method)item.payment_method=confirmation.value.paymentAccount||''
}
function syncFromDetails(){
  if(isFull.value)return
  const actual=payments.value.filter(item=>Number(item.actual_amount||0)>0)
  const methods=[...new Set(actual.map(item=>item.payment_method).filter(Boolean))]
  confirmation.value={...confirmation.value,paymentAccount:methods.length===1?methods[0]:methods.length>1?'':confirmation.value.paymentAccount,fullPaymentSource:hasFinal.value&&new Set(payments.value.map(item=>item.currency||'CNY')).size===1?'details':null,fullPaymentCurrency:props.currencyOptions&&hasFinal.value?payments.value[0]?.currency||confirmation.value.fullPaymentCurrency:confirmation.value.fullPaymentCurrency,fullPaymentAmount:hasFinal.value&&new Set(payments.value.map(item=>item.currency||'CNY')).size===1&&payments.value.every(item=>item.actual_amount!=null)?Number(totalCents('actual_amount'))/100:null,fullMatchStatus:'pending'}
}
function removePayment(index){payments.value=payments.value.filter((_item,i)=>i!==index).map((item,i)=>({...item,stage_no:i+1}));ensureFirstDeposit();syncFromDetails()}
watch(()=>form.value.paymentConfirmation,ensureFirstDeposit,{immediate:true})
</script>
<style scoped>
.payment-details > summary{width:fit-content;max-width:100%;padding:6px 0;color:var(--el-color-primary);cursor:pointer;font-weight:600}
.payment-details[open] .payment-details-expand,.payment-details:not([open]) .payment-details-collapse{display:none}
.project-payment-row{padding:14px;border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.payment-row-heading{display:flex;justify-content:space-between;margin-bottom:10px}.project-payment-row .el-input-number{width:100%}.payment-detail-match{display:flex;align-items:center;gap:4px 8px;flex-wrap:wrap;margin-top:4px;line-height:1.5;width:100%}.payment-detail-match .el-button{margin:0}.payment-summary{margin:16px 0}.payment-help{font-size:12px;color:var(--el-text-color-secondary)}
</style>
