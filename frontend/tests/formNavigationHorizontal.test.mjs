import assert from 'node:assert/strict'
import test from 'node:test'
import { scrollFormTarget } from '../src/utils/formNavigation.js'

test('表格字段定位同时滚动目标行与目标列，固定头尾不移动', () => {
  const prior = globalThis.window
  const requests = []
  const container = { scrollTop: 30, scrollLeft: 0, scrollWidth: 2000, clientWidth: 500, scrollHeight: 1000, clientHeight: 400, classList: { contains: () => false }, parentElement: null,
    getBoundingClientRect: () => ({ left: 10, top: 20 }), scrollTo: value => requests.push(value) }
  const target = { parentElement: container, getBoundingClientRect: () => ({ left: 900, right: 1100, top: 700, height: 80, width: 200 }) }
  globalThis.window = { getComputedStyle: () => ({ overflowX: 'auto', overflowY: 'auto' }) }
  try {
    assert.equal(scrollFormTarget(target, container), true)
    assert.deepEqual(requests, [{ top: 550, left: 740, behavior: 'smooth' }])
  } finally { globalThis.window = prior }
})

test('只有横向滚动时将字段居中，避免被表格固定操作列遮挡', () => {
  const prior = globalThis.window, calls = []
  const container = {scrollWidth:2000,clientWidth:500,scrollHeight:100,clientHeight:100,classList:{contains:()=>false},parentElement:null}
  const target = {parentElement:container,scrollIntoView:options=>calls.push(options)}
  globalThis.window = {getComputedStyle:()=>({overflowX:'auto',overflowY:'auto'})}
  try { scrollFormTarget(target); assert.equal(calls[0].inline,'center') }
  finally { globalThis.window = prior }
})
