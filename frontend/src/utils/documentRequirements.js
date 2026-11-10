import {effectiveBillingTaxMode} from './billingTaxMode.js'

export const documentNotesForm=value=>({quotation:value?.quotation||'',statement:value?.statement||'',invoice:value?.invoice||''})
export const invoiceStatusOptions=[{value:'unissued',label:'未开票'},{value:'partial',label:'部分开票'},{value:'issued',label:'已开票'}]
export const invoiceStatusLabels=Object.fromEntries(invoiceStatusOptions.map(item=>[item.value,item.label]))

export function invoiceRequirement(order){
  if(order.priceAggregate||order.pricingMode==='aggregate'){
    const children=(order.children||[]).map(invoiceRequirement)
    return children.includes(true)?true:children.includes(null)||!children.length?null:false
  }
  const mode=effectiveBillingTaxMode(order)
  return mode==='incl_tax'?true:mode==='excl_tax'?false:null
}
