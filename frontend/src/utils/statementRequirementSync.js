function versionTime(value){
  if(!value)return null
  const text=String(value).trim().replace(' ','T')
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(text)?text:`${text}+08:00`)
}

// 子窗口只提交这一字段；只有原版本一致时，才推进主表单的版本。
export function applyStatementRequirementResult(target,data){
  target.statementRequired=data.statementRequired
  target.statementRequiredExplicit=true
  if(versionTime(target.updatedAt)===versionTime(data.previousUpdatedAt))target.updatedAt=data.updatedAt
}
