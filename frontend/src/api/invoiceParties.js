import api from './index'
export const getInvoiceSubjects=()=>api.get('/invoice-parties/subjects')
export const saveInvoiceSubject=(key,data)=>api.put(`/invoice-parties/subjects/${key}`,data)
export const getClientInvoiceProfile=id=>api.get(`/invoice-parties/clients/${id}`)
export const saveClientInvoiceProfile=(id,data)=>api.put(`/invoice-parties/clients/${id}`,data)
export const getClientInvoiceRecords=(id,params,config={})=>api.get(`/invoice-parties/clients/${id}/records`,{...config,params})
export const invoicePartiesEvent='invoice-parties-changed'
let channel
export function connectInvoiceParties(){if(!channel&&typeof window.BroadcastChannel==='function'){channel=new window.BroadcastChannel('invoice-parties-sync');channel.onmessage=event=>window.dispatchEvent(new CustomEvent(invoicePartiesEvent,{detail:event.data}))}}
export function notifyInvoiceParties(detail){connectInvoiceParties();window.dispatchEvent(new CustomEvent(invoicePartiesEvent,{detail}));channel?.postMessage(detail)}
export const emptyInvoiceParty=()=>({title:'',tax_number:'',address:'',phone:'',bank:'',bank_account:'',email:'',remarks:''})
export const invoicePartyFields=[{key:'title',label:'开票抬头 / 公司名称',max:300},{key:'tax_number',label:'纳税人识别号',max:100},{key:'address',label:'注册地址',max:500},{key:'phone',label:'注册电话',max:100},{key:'bank',label:'开户银行',max:300},{key:'bank_account',label:'银行账号',max:100},{key:'email',label:'收票邮箱',max:300},{key:'remarks',label:'开票备注',max:2000}]
