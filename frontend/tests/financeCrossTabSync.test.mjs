import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
const source=readFileSync(new URL('../src/utils/paymentConfirmation.js',import.meta.url),'utf8').replace(/^export /gm,'')

test('同项目财务保存通知跨标签页发送一次，不回传形成循环',()=>{
  const channels=[],received=[[],[]]
  class Channel{
    constructor(name){this.name=name;channels.push(this)}
    postMessage(data){for(const peer of channels)if(peer!==this&&peer.name===this.name)peer.onmessage?.({data:structuredClone(data)})}
  }
  const contexts=received.map(items=>{
    const window={BroadcastChannel:Channel,dispatchEvent:event=>items.push(event.detail)}
    const ctx={window,CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail}}}
    vm.createContext(ctx);vm.runInContext(source,ctx);ctx.connectPaymentSync();return ctx
  })
  contexts[0].notifyPaymentChanged('same-project',{revision:6,isPaid:false},'finance-A')
  assert.equal(received[0].length,1);assert.equal(received[1].length,1)
  assert.equal(received[1][0].projectId,'same-project');assert.equal(received[1][0].confirmation.isPaid,false)
  assert.equal(received[1][0].source,'finance-A')
  contexts[1].connectPaymentSync();assert.equal(channels.length,2)
})
