import test from 'node:test'
import assert from 'node:assert/strict'
import { auditWindowPopovers } from '../tools/audit-window-popovers.mjs'

test('全系统窗口浮层有标题栏，业务弹窗统一走公共拖动/关闭组件',()=>{
  const result=auditWindowPopovers()
  assert.ok(result.popovers>=120)
  assert.ok(result.windowPopovers>=60)
  assert.ok(result.dialogs>50)
  assert.deepEqual(result.issues,[])
})
