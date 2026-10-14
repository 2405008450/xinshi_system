import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { computed, reactive, ref, watch, effectScope, nextTick } from 'vue'

const querySource = readFileSync(new URL('../src/composables/useChatMentions.js', import.meta.url), 'utf8')
const navSource = readFileSync(new URL('../src/composables/useProjectMentionNavigation.js', import.meta.url), 'utf8')
const source = [querySource, navSource].map(s => s.replace(/^import .*\r?\n/gm, '').replace(/export function /g, 'function ')).join('\n')
const flush = async () => { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
const project = id => ({ key: `annotation:${id}`, projectType: 'annotation', projectId: id })
const message = (id, seq) => ({ ...project(id), messageId: `${id}-${seq}`, sequenceNo: seq })

function harness(t, request, locate = async () => true) {
  const scope = effectScope(), cleanup = [], calls = [], cancelled = []
  const nav = scope.run(() => runInNewContext(`${source}\nuseProjectMentionNavigation(locate, key => cancelled.push(key))`, {
    computed, nextTick, reactive, ref, watch, AbortController, locate, cancelled,
    chatRequest: async (path, options) => { calls.push(options); return request(options) },
    localStorage: { getItem: () => 'me' },
    onMounted: () => {}, onBeforeUnmount: fn => cleanup.push(fn),
    setTimeout, clearTimeout, clearInterval, setInterval, subscribe: () => () => {},
  }))
  t.after(() => { cleanup.forEach(fn => fn()); scope.stop() })
  return { nav, calls, cancelled }
}
function paging(rows) {
  return async ({ params }) => {
    const all = rows.filter(m => m.projectId === params.project_id).sort((a,b) => b.sequenceNo-a.sequenceNo)
    const rest = all.filter(m => !params.before || m.sequenceNo < params.before)
    const items = rest.slice(0, params.limit), hasMore = rest.length > items.length
    return { items, total: all.length, hasMore, nextBefore: hasMore ? items.at(-1).sequenceNo : null }
  }
}

test('项目内分页和双向跳转不扩大项目范围，重复选择仍定位', async t => {
  const rows = Array.from({length:55},(_,i)=>message('a',i+1)).concat(message('b',99))
  const located = [], {nav,calls} = harness(t, paging(rows), async item => { located.push(item.messageId); return true })
  nav.browse(project('a')); await flush()
  assert.equal(nav.model.total,55); assert.equal(nav.model.items.length,50)
  assert.equal(located.length,0)
  assert.equal(calls.at(-1).params.keyword,'')
  await nav.select(nav.model.items[49]); await nav.move(1)
  assert.equal(nav.model.index,50); assert.equal(nav.model.items.length,55)
  await nav.move(-1); await nav.select(nav.model.items[49])
  assert.equal(located.slice(-2).join(','),'a-6,a-6')
  await nav.select(nav.model.items[54]); await nav.move(1)
  assert.equal(nav.model.index,54)
  nav.close(); assert.equal(nav.model.selectedId,'')
})

test('刷新新增提及保留原消息锚点，撤回不自动跳到别条', async t => {
  const rows = Array.from({length:55},(_,i)=>message('a',i+1))
  const located = [], {nav} = harness(t,paging(rows),async item=>{located.push(item.messageId);return true})
  nav.browse(project('a')); await flush(); await nav.select(nav.model.items[49])
  rows.push(message('a',56)); await nav.model.refresh(); await flush()
  assert.equal(nav.model.selectedId,'a-6'); assert.equal(nav.model.index,50)
  rows.splice(rows.findIndex(m=>m.messageId==='a-6'),1)
  await nav.model.refresh(); await flush()
  assert.equal(nav.model.selectedId,''); assert.match(nav.model.notice,/撤回或不可查看/)
  assert.equal(located.length,1)
})

test('快速切换项目取消旧请求，晚到响应不得覆盖新项目', async t => {
  const pending = [], {nav,calls} = harness(t, ({params}) => new Promise(resolve=>pending.push({params,resolve})))
  nav.browse(project('a')); await flush()
  nav.browse(project('b')); await flush()
  assert.ok(calls[0].signal.aborted)
  pending.filter(x=>x.params.project_id==='b').forEach(x=>x.resolve({items:[message('b',1)],total:1}))
  await flush()
  pending.filter(x=>x.params.project_id==='a').forEach(x=>x.resolve({items:[message('a',1)],total:1}))
  await flush(); assert.equal(nav.model.items[0].projectId,'b')
})

test('定位失败可重选，旧失败不得覆盖最后一次选择，关闭取消定位', async t => {
  const pending = [], {nav,cancelled} = harness(t,paging([message('a',1),message('a',2)]), item=>new Promise(resolve=>pending.push({item,resolve})))
  nav.browse(project('a')); await flush()
  const first=nav.select(nav.model.items[0]), second=nav.select(nav.model.items[1])
  pending[1].resolve(true); await second; pending[0].resolve(false); await first
  assert.equal(nav.model.selectedId,'a-1'); assert.equal(nav.model.notice,'')
  const failed=nav.select(nav.model.items[0]); pending[2].resolve(false); await failed
  assert.match(nav.model.notice,/无法定位/)
  nav.close(); assert.equal(cancelled.at(-1),'annotation:a')
})

test('分页请求失败保留阅读位置并允许重试', async t => {
  const rows=Array.from({length:51},(_,i)=>message('a',i+1)), base=paging(rows)
  let fail=true
  const {nav}=harness(t,options=>{if(options.params.before && fail) throw new Error('网络错误'); return base(options)})
  nav.browse(project('a')); await flush(); await nav.select(nav.model.items[49]); await nav.move(1)
  assert.equal(nav.model.index,49); assert.equal(nav.model.error,'网络错误')
  fail=false; await nav.move(1); assert.equal(nav.model.index,50); assert.equal(nav.model.error,'')
})

test('首次上箭头按需加载并定位最新消息，取消后不跳转', async t => {
  const located=[], {nav,calls}=harness(t,paging([message('a',1),message('a',2)]),async item=>{located.push(item.messageId);return true})
  assert.equal(calls.length,0)
  await nav.latest(project('a')); assert.equal(located.join(','),'a-2')
  await nav.move(1); assert.equal(nav.model.selectedId,'a-1')
  await nav.move(-1); assert.equal(nav.model.selectedId,'a-2')
  nav.close()
  const attempt=nav.latest(project('a')); nav.close(); await attempt
  assert.equal(located.length,3)
})

test('从独立预览选择第二页消息时，导航首次加载覆盖选中锚点', async t => {
  const rows=Array.from({length:55},(_,i)=>message('a',i+1))
  const {nav}=harness(t,paging(rows))
  nav.browse(project('a')); await nav.select(message('a',1)); await flush()
  assert.equal(nav.model.selectedId,'a-1'); assert.equal(nav.model.index,54)
  assert.equal(nav.model.notice,'')
})
