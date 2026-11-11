import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {ref} from 'vue'
const source=readFileSync(new URL('../src/views/project/translation/CustomerFinance.vue',import.meta.url),'utf8')

test('已保存的母订单和子订单均调用同一个价格与付款编辑入口',async()=>{
  for(const child of [false,true]){
    const calls=[],parent={id:'root'},target=child?{id:'child'}:parent
    const ctx={openEditor:async row=>calls.push(row),documentParent:ref(null),projectFormTarget:ref(null)}
    vm.createContext(ctx)
    vm.runInContext(source.slice(source.indexOf('async function openForForm('),source.indexOf('async function saveLocalFinance()')),ctx)
    await ctx.openForForm(target,parent)
    assert.equal(calls.length,1)
    assert.equal(calls[0].id,target.id)
    assert.equal(calls[0].rootId,'root')
    assert.equal(ctx.projectFormTarget.value.id,target.id)
  }
})

test('新增项目保存后补存客户说明和参考价，使用新生成收费项ID',async()=>{
  const target={},pendingFormFinance=new WeakMap(),calls=[]
  pendingFormFinance.set(target,{pricingMode:'metric',prices:[{amount:0.2,referenceId:'reference'}],customerExplanation:'给客户的说明'})
  const ctx={pendingFormFinance,getCustomerFinanceProject:async()=>({version:'v1',item:{id:'new-root',prices:[{id:'new-charge'}],children:[]}}),ratePayload:row=>row,saveCustomerFinanceTable:async(id,data)=>calls.push({id,data})}
  vm.createContext(ctx)
  vm.runInContext(source.slice(source.indexOf('async function persistForForm('),source.indexOf('async function openForForm(')),ctx)
  await ctx.persistForForm(target,{id:'new-root'})
  assert.equal(calls[0].id,'new-root')
  assert.equal(calls[0].data.customer_explanation,'给客户的说明')
  assert.equal(calls[0].data.prices[0].id,'new-charge')
  assert.equal(calls[0].data.prices[0].referenceId,'reference')
  assert.equal(pendingFormFinance.has(target),false)
})
