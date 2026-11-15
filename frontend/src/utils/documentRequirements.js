import {effectiveBillingTaxMode} from './billingTaxMode.js'

export const documentNotesForm=value=>({quotation:value?.quotation||'',statement:value?.statement||'',invoice:value?.invoice||''})
export const invoiceStatusOptions=[{value:'unissued',label:'未开票'},{value:'partial',label:'部分开票'},{value:'issued',label:'已开票'}]
export const invoiceStatusLabels=Object.fromEntries(invoiceStatusOptions.map(item=>[item.value,item.label]))

export function invoiceRequirement(order){
  if(order.paymentMethod && order.paymentMethod!=='special'){
    const mode=effectiveBillingTaxMode(order)
    return mode==='incl_tax'?true:mode==='excl_tax'?false:null
  }
  if(typeof order.invoiceRequirementOverride==='boolean')return order.invoiceRequirementOverride
  if(order.priceAggregate||order.pricingMode==='aggregate'){
    const children=(order.children||[]).map(invoiceRequirement)
    return children.includes(true)?true:children.includes(null)||!children.length?null:false
  }
  const mode=effectiveBillingTaxMode(order)
  return mode==='incl_tax'?true:mode==='excl_tax'?false:null
}

export function documentConsistencyRows(root, draft){
  function withDraft(order, fixedAncestor=false){
    const current = order.id===draft.id ? draft : order
    const fixedParent = fixedAncestor || (current.pricingMode==='fixed' ? current.orderNo || true : false)
    return {...current,
      fixedPricingFrom:fixedAncestor,
      quotationRequired:draft.quotationRequired,
      statementRequired:draft.statementRequired,
      invoiceRequirementOverride:draft.invoiceRequirementOverride,
      children:(order.children||[]).map(child=>withDraft(child, fixedParent))}
  }
  const current = withDraft(root)
  const rows = []
  function invoiceNeeded(order){
    if(draft.paymentMethod && draft.paymentMethod!=='special'){
      const basis=taxBasis(order)
      return basis==='incl_tax'?true:basis==='excl_tax'?false:null
    }
    if(typeof order.invoiceRequirementOverride==='boolean')return order.invoiceRequirementOverride
    if(order.priceAggregate || order.pricingMode==='aggregate'){
      const children=order.children.map(invoiceNeeded)
      return children.includes(true)?true:children.includes(null)||!children.length?null:false
    }
    const basis=taxBasis(order)
    return basis==='incl_tax'?true:basis==='excl_tax'?false:null
  }
  function taxBasis(order){
    if(draft.paymentMethod && draft.paymentMethod!=='special'){
      const mode=draft.unifiedBillingTaxMode ?? draft.billingTaxMode
      if(mode)return mode
    }
    if(order.priceAggregate || order.pricingMode==='aggregate'){
      const modes = new Set(order.children.map(child => child.fixedPricingFrom ? null : taxBasis(child)))
      return modes.size > 1 ? 'mixed' : modes.values().next().value ?? null
    }
    return order.id===draft.id ? effectiveBillingTaxMode(order) : order.effectiveBillingTaxMode ?? effectiveBillingTaxMode(order)
  }
  function visit(order, inheritedInvoice, inheritedTax){
    const invoice = order.fixedPricingFrom ? inheritedInvoice : invoiceNeeded(order)
    const tax = order.fixedPricingFrom ? inheritedTax : taxBasis(order)
    rows.push({id:order.id, orderNo:order.orderNo, quotation:!!order.quotationRequired,
      statement:draft.paymentMethod&&draft.paymentMethod!=='special'?tax==='incl_tax':order.statementRequired!==false,
      invoice, tax, fixedPricingFrom:order.fixedPricingFrom,
      totalsExclTax:order.totalsExclTax, totalsInclTax:order.totalsInclTax})
    for(const child of order.children)visit(child, invoice, tax)
  }
  visit(current)
  return rows
}

export function documentConsistencySnapshot(rows){
  const snapshot = rows.map(row => [row.id,row.quotation,row.statement,row.invoice,row.tax])
  return snapshot.slice(1).some(row=>row.slice(1).some((value,index)=>value!==snapshot[0][index+1])) ? snapshot : []
}
export const documentRequirementLabel = value => value == null ? '待判断' : value ? '需' : '无需'
