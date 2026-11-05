import test from 'node:test'
import assert from 'node:assert/strict'
import {createProjectStatusFeed} from '../src/utils/projectStatusFeed.js'
function setup(fetchStatuses){let visible=true,intervals=new Map(),queued=new Map(),id=0,watches=[];const feed=createProjectStatusFeed({fetchStatuses,setWatch:value=>watches.push(value),visible:()=>visible,setInterval:fn=>{intervals.set(++id,fn);return id},clearInterval:key=>intervals.delete(key),setTimeout:fn=>{queued.set(++id,fn);return id},clearTimeout:key=>queued.delete(key)});return {feed,intervals,queued,watches,hide:()=>{visible=false;feed.update()},show:()=>{visible=true;feed.update()}}}
test('多表格共用一次检查，未变化不触发整表刷新',async()=>{
 let requests=0,refreshes=0;const item={projectType:'translation',id:'one',status:'confirmed'},ctx=setup(async()=>{requests++;return {items:[{...item}]}})
 ctx.feed.register({active:()=>true,items:()=>[item],changed:()=>refreshes++});ctx.feed.register({active:()=>true,items:()=>[item],changed:()=>refreshes++})
 assert.equal(ctx.intervals.size,1);await ctx.feed.check();assert.equal(requests,1);assert.equal(refreshes,0)
 ctx.feed.push({items:[{...item,status:'sent_to_client'}]});assert.equal(refreshes,2)
})
test('隐藏暂停检查与订阅，恢复立即安排核对，卸载停止',async()=>{
 let requests=0;const ctx=setup(async()=>{requests++;return {items:[]}}),off=ctx.feed.register({active:()=>true,items:()=>[{projectType:'annotation',id:'one'}],changed(){}})
 ctx.hide();assert.equal(ctx.intervals.size,0);assert.deepEqual(ctx.watches.at(-1),[]);await ctx.feed.check();assert.equal(requests,0)
 ctx.show();assert.equal(ctx.intervals.size,1);assert.equal(ctx.queued.size,1);off();assert.equal(ctx.intervals.size,0);assert.equal(ctx.queued.size,0)
})
test('状态推送到达后，较早的检查响应不能覆盖新状态',async()=>{
 let resolve;const item={projectType:'translation',id:'one',status:'confirmed'},ctx=setup(()=>new Promise(done=>{resolve=done}))
 ctx.feed.register({active:()=>true,items:()=>[item],changed:changes=>{item.status=changes[0].status}})
 const pending=ctx.feed.check();ctx.feed.push({items:[{...item,status:'sent_to_client'}]});resolve({items:[{...item,status:'confirmed'}]});await pending
 assert.equal(item.status,'sent_to_client')
})
