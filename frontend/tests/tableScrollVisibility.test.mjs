import test from 'node:test'
import assert from 'node:assert/strict'
import { tableScrollGeometry, horizontalThumb } from '../src/utils/tableScrollVisibility.js'

const base = { root: { top: -100, bottom: 1000 }, header: { top: -100, height: 40 }, source: { left: 200, right: 1000, top: -60, bottom: 1000 }, clip: { left: 200, right: 1000, top: 80, bottom: 700 } }
test('长列表表头固定在滚动视口顶部，水平条紧贴可见区域底部', () => {
  const value = tableScrollGeometry(base)
  assert.equal(value.shift, 180)
  assert.equal(value.top + 14, 700)
  assert.equal(value.width, 800)
  assert.equal(value.visible, true)
})
test('缩放和已应用位移不会逐帧累积或抖动', () => {
  const first = tableScrollGeometry({ ...base, scale: .8 })
  const second = tableScrollGeometry({ ...base, scale: .8, offset: first.shift, header: { top: 80, height: 40 } })
  assert.equal(first.shift, 225)
  assert.equal(second.shift, first.shift)
})
test('表格末尾限制表头位移；不可见表格不显示悬浮滚动条', () => {
  const value = tableScrollGeometry({ ...base, root: { top: -100, bottom: 100 }, clip: { ...base.clip, top: 80 } })
  assert.equal(value.shift, 160)
  assert.equal(value.visible, false)
})
test('弹窗内部横向条按内容区裁剪，不进入固定底栏或遮挡下个表格', () => {
  const value = tableScrollGeometry({ ...base, root: { top: 120, bottom: 600 }, header: { top: 120, height: 40 }, source: { left: 150, right: 1200, top: 160, bottom: 600 }, clip: { left: 200, right: 1000, top: 100, bottom: 550 } })
  assert.equal(value.shift, 0)
  assert.equal(value.top, 536)
  assert.equal(value.left, 200)
  assert.equal(value.width, 800)
})
test('水平滚动滑块正确映射首尾、变宽和窄视口', () => {
  assert.deepEqual(horizontalThumb(800, 1600, 400, 800), {maximum:800,width:400,left:200})
  assert.equal(horizontalThumb(800, 1600, 900, 800).left, 400)
  assert.deepEqual(horizontalThumb(800, 800, 0, 800), {maximum:0,width:800,left:0})
  assert.equal(horizontalThumb(100, 10000, 0, 20).width, 20)
})
