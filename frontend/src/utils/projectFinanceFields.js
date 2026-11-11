// 已保存项目的财务数据由统一的“价格与付款”接口保存，项目资料编辑不回写旧副本。
export function projectFinanceFields(payload,existing){
  const result={...payload}
  if(existing)for(const key of ['customerChargeItems','paymentConfirmation','paymentDraft','paymentVersion'])delete result[key]
  // 新订单没有服务端付款版本，保留付款草稿但不提交空版本或复用来源的版本。
  else delete result.paymentVersion
  return result
}
