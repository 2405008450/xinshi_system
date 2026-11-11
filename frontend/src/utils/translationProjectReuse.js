// 复用业务字段；新项目的身份、编号、草稿及发送/审计记录始终独立。
export function reusableTranslationValues(source, emptyForm, pathGroup){
  const excluded=new Set(['id','orderNo','initialSubOrderNamesText','createWithSubOrders','pendingSubOrderDetails','pendingSubOrderDefaults','childFieldDifferences','filePathDraft','wordCountPendingDraft','wordCountMatrixSource','wordCountSubOrderCount','clientManagerChangeReason','paymentConfirmation','paymentDraft','paymentVersion','quotationDraft','emailSubjectPreview','pmConfirmedBy','majorProjectManagerConfirmation','assignedTranslators'])
  const clone=value=>JSON.parse(JSON.stringify(value))
  const values=Object.fromEntries(Object.keys(emptyForm).filter(key=>!excluded.has(key)&&source[key]!==undefined).map(key=>[key,clone(source[key])]))
  values.clientId=source.clientId||source.client_id||source.client?.id||''
  values.clientName=source.clientName||source.clientFullName||source.client_name||source.client?.client_name||source.client?.clientName||''
  values.clientShortName=source.clientShortName||source.client_short_name||source.client?.client_short_name||source.client?.clientShortName||''
  values.clientCode=source.clientCode||source.client_code||source.client?.client_code||source.client?.clientCode||''
  values.sourceFileName=source.sourceFileName||source.projectName||''
  values.networkFilePath=source.networkFilePath||''
  values.originalStoragePath=source.originalStoragePath||source.networkFilePath||''
  values.wordCountMatrixSource='project';values.wordCountSubOrderCount=0
  values.customerChargeItems=(values.customerChargeItems||[]).map(({id,projectId,subOrderId,...item})=>item)
  if(source.roleAssignments){
    const keys={project_manager:'projectManagerId',project_specialist:'projectSpecialistId',project_assistant:'projectAssistantId',layout_specialist:'layoutSpecialistId'}
    for(const role of source.roleAssignments){const key=keys[role.roleCode];if(key)values[key]=role.assigneeUserId||role.assigneeId||''}
  }
  if(pathGroup){
    const keys=['storage_path','dispatch_path','translation_path','translator_return_path','client_delivery_path','project_feedback_path','feedback_delivery_path','translation_domain_level1','translation_domain_level2','file_type','file_type_secondary','file_format','file_attribute_level1','file_attribute_level2','file_attribute_level3','file_difficulty']
    values.filePathDraft=Object.fromEntries(keys.map(key=>[key,pathGroup[key]||'']))
    values.originalStoragePath=pathGroup.storage_path||source.originalStoragePath||source.networkFilePath||''
  }
  return values
}
