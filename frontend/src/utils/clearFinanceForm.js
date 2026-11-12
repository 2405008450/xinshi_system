import {clearPaymentSelection} from './paymentConfirmation.js'

export function clearFinanceForm(order,createRate){
  return {...order,
    clearedAll:true,
    ...(order.priceAggregate?{}:{pricingMode:order.pricingMode||'metric',currency:'CNY',prices:[],adjustedTotal:undefined,adjustedTotalInclTax:undefined,billingTaxMode:null,effectiveBillingTaxMode:null,totalsExclTax:{},totalsInclTax:{},billingTotals:{}}),
    explanation:'',customerExplanation:'',quotationRequired:false,statementRequired:false,statementRequiredDirty:true,statementSync:null,statementCustomerSync:null,
    documentNotes:{quotation:'',statement:'',invoice:''},documentNotesDirty:true,
    paymentDraft:[],
    paymentConfirmation:{...clearPaymentSelection(order.paymentConfirmation),fullPaymentCurrency:'CNY'}
  }
}
export function isClearedFinanceForm(order){
  const filled=value=>value!=null&&value!==''
  return !!order.clearedAll&&!(order.prices||[]).some(row=>filled(row.taxPrices?.unitPriceExclTax)||filled(row.taxPrices?.unitPriceInclTax)||filled(row.amount))&&!filled(order.adjustedTotal)&&!filled(order.adjustedTotalInclTax)
}
