export const emptyProjectContactDetails=()=>({clientContactMethod:undefined,clientContactDescription:'',clientContactVersion:undefined,clientContactsVisible:false})
export function projectContactPayload(form){
  if(!form.clientContactVersion)return {}
  return {clientContactDescription:form.clientContactDescription||'',clientContactVersion:form.clientContactVersion,
    ...(form.clientContactsVisible?{clientContactMethod:form.clientContactMethod||''}:{})}
}
