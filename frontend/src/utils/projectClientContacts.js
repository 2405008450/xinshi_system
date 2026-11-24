export const emptyProjectContactDetails=()=>({clientContactMethod:undefined,clientContactDescription:'',clientContactJobTitle:'',clientContactDepartment:'',clientContactCompany:'',clientContactVersion:undefined,clientContactsVisible:false})
export function projectContactPayload(form){
  if(!form.clientContactVersion)return {}
  return {clientContactDescription:form.clientContactDescription||'',clientContactVersion:form.clientContactVersion,
    clientContactJobTitle:form.clientContactJobTitle||'',clientContactDepartment:form.clientContactDepartment||'',clientContactCompany:form.clientContactCompany||'',
    ...(form.clientContactsVisible?{clientContactMethod:form.clientContactMethod||''}:{})}
}
