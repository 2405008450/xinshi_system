export const partialCancellationOptions=['行程/计划改变','支付定金后（部分）取消','其他原因（自行填写）']
export function parsePartialCancellation(text=''){
 const match=text.match(/^部分取消原因：([^\n]+)/)
 const reasons=match?match[1].split('；').filter(item=>partialCancellationOptions.includes(item)):[]
 const other=text.match(/(?:^|\n)其他原因：([\s\S]*?)(?:\n截图和说明：\n|$)/)?.[1]||''
 const note=text.includes('\n截图和说明：\n')?text.split('\n截图和说明：\n').slice(1).join('\n截图和说明：\n'):match?'':text
 return {reasons,other,note}
}
export function formatPartialCancellation(value){return ['部分取消原因：'+value.reasons.join('；'),value.reasons.includes(partialCancellationOptions[2])?'其他原因：'+value.other.trim():'',value.note.trim()?'截图和说明：\n'+value.note.trim():''].filter(Boolean).join('\n')}
export function validPartialCancellation(text){const value=parsePartialCancellation(text);return String(text||'').split('\n')[0].replace(/^部分取消原因：/,'').split('；').every(item=>partialCancellationOptions.includes(item))&&value.reasons.length>0&&(!value.reasons.includes(partialCancellationOptions[2])||!!value.other.trim())}

export const cancellationTree={"客户已找到": {"已找到其他供应商": null, "已自行找到译员": null, "同事找到译员": null, "其他合作伙伴已协助解决": null, "时间赶不及/时间已过": null, "其他原因（自行填写）": null}, "客户已取消": {"公司内部消化": null, "客户自身改变计划": null, "客户的客户改变计划": null, "客户的客户已有译员": null, "客户的客户未回复": null, "信实费用高": null, "客户预算低": null, "客户（领导）审批未通过": null, "有懂该语言的朋友同行": null, "不可抗力": null, "未回复原因": null, "客户无法出国": null, "译员原因": {"译员无法联系上": null, "译员主观原因": {"价格问题": null, "态度问题": null, "其他原因（自行填写）": null}, "译员客观原因": {"交通问题": null, "身体原因": null, "家庭原因": null, "其他原因（自行填写）": null}, "客户对译员不满意": null, "其他原因（自行填写）": null}}, "客户不回复": null, "客户未回复原因": null, "无法找到译员": null, "无法提供合适译员": null, "其他原因（自行填写）": null}
export function cancellationOptions(tree=cancellationTree){return Object.entries(tree).map(([value,children])=>({value,label:value,...(children?{children:cancellationOptions(children)}:{})}))}
