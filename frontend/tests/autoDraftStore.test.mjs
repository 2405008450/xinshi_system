import test from 'node:test'
import assert from 'node:assert/strict'
import {createAutoDraftStore,sanitizeDraft,AUTO_DRAFT_TTL,draftBusinessNow,draftStringify} from '../src/utils/autoDraftStore.js'
function memory(){const data=new Map();return {getItem:key=>data.get(key)||null,setItem:(key,value)=>data.set(key,value)}}
test('对象键顺序变化不产生重复的云端草稿内容',()=>{assert.equal(draftStringify({a:1,b:{x:2,y:3}}),draftStringify({b:{y:3,x:2},a:1}));assert.notEqual(draftStringify([1,2]),draftStringify([2,1]))})
test('草稿按账号隔离、相同内容不重复写入、超过7天不恢复',()=>{
 const storage=memory();let time=1000000000
 const first=createAutoDraftStore({storage,owner:'one',clock:()=>time,retentionMs:AUTO_DRAFT_TTL}),second=createAutoDraftStore({storage,owner:'two',clock:()=>time,retentionMs:AUTO_DRAFT_TTL})
 assert.equal(first.save({id:'record',data:{name:'草稿'}}),true)
 assert.equal(first.save({id:'record',data:{name:'草稿'}}),false)
 assert.equal(first.get('record').data.name,'草稿');assert.equal(second.list().length,0)
 time+=AUTO_DRAFT_TTL+1;assert.equal(first.list().length,0)
})

test('编辑窗口默认持续保留当前账号未保存内容，不因七天过期丢失',()=>{
 const storage=memory();let time=1000000000
 const store=createAutoDraftStore({storage,owner:'one',clock:()=>time})
 store.save({id:'record',data:{name:'未保存内容'}})
 time+=AUTO_DRAFT_TTL*10
 assert.equal(store.get('record').data.name,'未保存内容')
 assert.equal(createAutoDraftStore({storage,owner:'two',clock:()=>time}).get('record'),undefined)
})
test('密码、令牌、私钥、文件本体不进入草稿；存储失败必须报错',()=>{
 const value=sanitizeDraft({name:'正常',password:'禁止',api_token:'禁止',nested:{privateKey:'禁止',notes:'保留'},file:new Blob(['file'])})
 assert.deepEqual(value,{name:'正常',nested:{notes:'保留'}})
 const storage={getItem:()=>null,setItem:()=>{throw new Error('quota')}}
 assert.throws(()=>createAutoDraftStore({storage,owner:'one'}).save({id:'one',data:'text'}),/quota/)
 assert.equal(draftBusinessNow(Date.parse('2026-10-28T00:00:00Z')),'2026-10-28T08:00:00.000+08:00')
})
test('容量受控且不会改动其他模块存储；单条过大拒绝保存',()=>{
 const storage=memory(),store=createAutoDraftStore({storage,owner:'one',budget:1500,recordBudget:500})
 storage.setItem('other-module','保留')
 for(let i=0;i<10;i++)store.save({id:String(i),data:'文本'.repeat(20)})
 assert.ok(store.list().length<10);assert.equal(storage.getItem('other-module'),'保留')
 assert.throws(()=>store.save({id:'big',data:'x'.repeat(1000)}),/256KB/)
})
