import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source=readFileSync(new URL('../src/composables/useChatMessageInteractions.js',import.meta.url),'utf8').replace(/^import .*\r?\n/gm,'').replace('export function','function')
function harness({available=true}={}){
  const calls=[],timers=new Map(),mounted=[],disposed=[],active={value:true}
  let observer,sequence=0,focused=true
  const document={visibilityState:'visible',hasFocus:()=>focused,addEventListener(){},removeEventListener(){}}
  const window={addEventListener(){},removeEventListener(){}}
  const api=runInNewContext(source+`;useChatMessageInteractions(options)`,{
    options:{projectId:{value:'project'},projectType:{value:'annotation'},messages:{value:[{id:'visible'},{id:'hidden'}]},active},
    computed:fn=>({get value(){return fn()}}),reactive:value=>value,ref:value=>({value}),watch(){},onMounted:fn=>mounted.push(fn),onBeforeUnmount:fn=>disposed.push(fn),
    document,window,AbortController,subscribe:()=>()=>{},
    setTimeout:fn=>{const id=++sequence;timers.set(id,fn);return id},clearTimeout:id=>timers.delete(id),setInterval:()=>1,clearInterval(){},
    IntersectionObserver:class{constructor(callback,options){observer={callback,options}}observe(){}unobserve(){}disconnect(){}},
    chatRequest:async(path,options)=>{calls.push({path,options});return path.endsWith('message-stats')?{viewsAvailable:available,items:[]}:{}},
  })
  mounted.forEach(fn=>fn())
  const run=async name=>{for(const [id,fn] of timers){if(fn.name===name){timers.delete(id);await fn();return}}}
  const expose=(id,ratio)=>observer.callback([{target:{dataset:{interactionMessageId:id}},isIntersecting:ratio>0,intersectionRatio:ratio}])
  return{api,calls,observer,active,document,run,expose,setFocus:value=>{focused=value},dispose:()=>disposed.forEach(fn=>fn())}
}

test('逐条回执只记录实际可见、前台聚焦的消息，屏幕外和平铺滚动区域不能误报',async()=>{
  const h=harness()
  assert.equal(h.observer.options.root,null)
  h.expose('visible',.8);h.expose('hidden',.3)
  await h.run('refresh')
  h.setFocus(false);await h.run('flush')
  assert.equal(h.calls.filter(call=>call.path.endsWith('message-views')).length,0)
  h.setFocus(true);h.expose('visible',.8);await h.run('flush')
  const reads=h.calls.filter(call=>call.path.endsWith('message-views'))
  assert.equal(reads.length,1)
  assert.deepEqual(Array.from(reads[0].options.data.messageIds),['visible'])
  h.expose('visible',.8);await h.run('flush')
  assert.equal(h.calls.filter(call=>call.path.endsWith('message-views')).length,1)
  h.dispose()
})

test('未启用回执表或窗口不活跃时不会写入阅读回执',async()=>{
  for(const available of [false,true]){
    const h=harness({available})
    h.expose('visible',1);await h.run('refresh')
    if(available)h.active.value=false
    await h.run('flush')
    assert.equal(h.calls.filter(call=>call.path.endsWith('message-views')).length,0)
    h.dispose()
  }
})
