import test from 'node:test'
import assert from 'node:assert/strict'
import {fillMissingClientIdentity} from '../src/utils/clientIdentity.js'

const client={id:'parent',client_name:'客户完整名称有限公司',client_short_name:'客户简称',client_code:'C001',sub_clients:[{id:'child',client_name:'子客户完整名称',client_short_name:'子客户简称',sub_client_code:'SC001'}]}

test('笔译、口译标注及咨询等字段命名均补齐客户全称、简称和编号',async()=>{
 for(const model of [{clientId:'parent',clientName:'',clientShortName:'',clientCode:''},{clientId:'parent',clientFullName:'',clientShortName:'',clientCode:''},{client_id:'parent',client_name:'',client_short_name:'',client_code:''}]){
  await fillMissingClientIdentity(model,{loadClient:async()=>client})
  assert.equal(model.clientName||model.clientFullName||model.client_name,client.client_name)
  assert.equal(model.clientShortName||model.client_short_name,client.client_short_name)
  assert.equal(model.clientCode||model.client_code,client.client_code)
 }
})

test('独立母子客户字段带出母客户，组合选择框带出准确子客户',async()=>{
 const parent={clientId:'parent',subClientId:'child',subClientName:'子客户',clientName:'',clientShortName:'',clientCode:''}
 const child={clientId:'parent',subClientId:'child',clientFullName:'',clientShortName:'',clientCode:''}
 await Promise.all([parent,child].map(model=>fillMissingClientIdentity(model,{loadClient:async()=>client})))
 assert.equal(parent.clientName,client.client_name)
 assert.equal(child.clientFullName,client.sub_clients[0].client_name)
 assert.equal(child.clientCode,'SC001')
})

test('切换客户、关闭表单或手工输入后，迟到响应不能覆盖当前内容',async()=>{
 for(const change of ['switch','close','type']){
  let release,live=true
  const model={id:'p1',clientId:'parent',clientName:'',clientShortName:''}
  const work=fillMissingClientIdentity(model,{loadClient:()=>new Promise(resolve=>{release=resolve}),isCurrent:()=>live})
  await Promise.resolve()
  if(change==='switch')model.clientId='another'
  if(change==='close')live=false
  if(change==='type')model.clientName='手工填写的完整名称'
  release(client);await work
  assert.equal(model.clientName,change==='type'?'手工填写的完整名称':'')
 }
})

test('并发表单共用请求，未选择客户不请求，已有完整内容不覆盖',async()=>{
 let calls=0,release
 const loadClient=()=>{calls++;return new Promise(resolve=>{release=resolve})}
 const first={clientId:'parent',clientName:'',clientShortName:''},second={clientId:'parent',clientName:'',clientShortName:''}
 const jobs=[first,second].map(model=>fillMissingClientIdentity(model,{loadClient,owner:'same-user'}))
 await Promise.resolve();assert.equal(calls,1);release(client);await Promise.all(jobs)
 await fillMissingClientIdentity({clientId:'',clientName:'新客户',clientShortName:''},{loadClient})
 await fillMissingClientIdentity({clientId:'parent',clientName:'原全称',clientShortName:'原简称'},{loadClient})
 assert.equal(calls,1)
})
