import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const storage = new Map([['user_id','one']])
globalThis.localStorage = { getItem: key => storage.get(key) || null }
const source = await readFile(new URL('../src/utils/listResultCache.js', import.meta.url), 'utf8')
const {listResultTicket, clearListResults} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
test('cache isolation, invalidation races, copies and capacity', () => {
  const ticket = listResultTicket('list', {page:1, term:'?'})
  ticket.write({items:[{id:1}], total:1})
  ticket.read().items[0].id=2
  assert.equal(ticket.read().items[0].id,1)
  assert.equal(listResultTicket('list',{page:2,term:'?'}).read(),null)
  storage.set('user_id','two')
  assert.equal(ticket.read(),null)
  assert.equal(listResultTicket('list',{page:1,term:'?'}).read(),null)
  storage.set('user_id','one')
  clearListResults(); ticket.write({items:[],total:0})
  assert.equal(listResultTicket('list',{page:1,term:'?'}).read(),null)
  const first=listResultTicket('list',{page:0});first.write({items:[]})
  for(let i=1;i<=20;i++)listResultTicket('list',{page:i}).write({items:[]})
  assert.equal(first.read(),null)
})
test('expired results are not restored', () => {
  const original = Date.now
  let now = 1000
  Date.now = () => now
  try {
    const ticket = listResultTicket('expiry')
    ticket.write({items:[]})
    now += 600001
    assert.equal(ticket.read(), null)
  } finally { Date.now = original }
})
test('option invalidation prevents pending request from repopulating cache', async () => {
  const code = await readFile(new URL('../src/utils/optionCache.js', import.meta.url), 'utf8')
  const {getCachedOptions, invalidateOptionCache} = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
  let finish
  const pending = getCachedOptions('race', () => new Promise(resolve => { finish = resolve }))
  await Promise.resolve()
  invalidateOptionCache('race')
  finish(['old'])
  await pending
  assert.deepEqual(await getCachedOptions('race', () => ['new']), ['new'])
})
