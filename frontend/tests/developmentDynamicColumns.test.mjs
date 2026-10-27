import assert from 'node:assert/strict'
import test from 'node:test'
import {buildDevelopmentColumns,developmentColumnValue,cleanColumns,defaultDevelopmentColumns} from '../src/utils/resourceDevelopment.js'
import {newEntryRow,entryPayload} from '../src/utils/developmentBatchEntry.js'
const options={user_id:'u',options:[{id:'field1',kind:'custom_field',name:'擅长领域'}],custom_account_fields:[{key:'custom_account:telegram',name:'Telegram'}]}
test('字段设置覆盖WhatsApp、自定义账号的独立列和新增文本字段',()=>{
 const columns=buildDevelopmentColumns(options)
 assert.equal(columns.find(item=>item.key==='whatsapp').label,'资源 WhatsApp 号')
 assert.equal(columns.find(item=>item.key==='custom_account:telegram').label,'资源Telegram号')
 assert.equal(columns.find(item=>item.key==='custom_field:field1').label,'擅长领域')
 assert.deepEqual(cleanColumns(['custom_field:field1','custom_account:telegram','removed'],defaultDevelopmentColumns,columns),['custom_account:telegram','custom_field:field1'])
 assert.deepEqual(cleanColumns([],defaultDevelopmentColumns,columns),[])
})
test('动态列读取对应记录值，复制和保存保留自定义内容且数组互不影响',()=>{
 const row=newEntryRow(options,{custom_fields:{field1:'医疗'},custom_accounts:[{name:'Telegram',value:'tg-1'}]})
 assert.equal(developmentColumnValue(row,'custom_field:field1'),'医疗')
 assert.equal(developmentColumnValue(row,'custom_account:telegram'),'tg-1')
 assert.equal(entryPayload(row).custom_fields.field1,'医疗')
 const copied=newEntryRow(options,row);copied.custom_fields.field1='金融';assert.equal(row.custom_fields.field1,'医疗')
})
