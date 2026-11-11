// 已保存项目的财务数据由统一的“价格与付款”接口保存，项目资料编辑不回写旧副本。
export function projectFinanceFields(payload,existing){
  const result={...payload}
  if(existing)for(const key of ['customerChargeItems','paymentConfirmation','paymentDraft','paymentVersion'])delete result[key]
  return result
}
