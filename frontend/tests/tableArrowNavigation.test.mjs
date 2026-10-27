import test from 'node:test'
import assert from 'node:assert/strict'
import { findTableArrowTarget, handleTableArrowNavigation } from '../src/utils/tableArrowNavigation.js'

const grid = [
  [[], [], ['name-1'], ['phone-1'], [], ['custom-name-1', 'custom-value-1'], ['remarks-1'], []],
  [[], [], ['name-2'], ['phone-2'], [], [], ['remarks-2'], []],
  [[], [], ['name-3'], [], [], ['custom-name-3', 'custom-value-3'], ['remarks-3'], []],
]
test('左右切换可编辑输入格，跳过下拉、只读和没有输入框的格', () => {
  assert.equal(findTableArrowTarget(grid,0,2,0,'ArrowRight'),'phone-1')
  assert.equal(findTableArrowTarget(grid,0,3,0,'ArrowRight'),'custom-name-1')
  assert.equal(findTableArrowTarget(grid,0,5,0,'ArrowRight'),'custom-value-1')
  assert.equal(findTableArrowTarget(grid,0,5,0,'ArrowLeft'),'phone-1')
  assert.equal(findTableArrowTarget(grid,0,6,0,'ArrowLeft'),'custom-value-1')
})
test('上下保持列位置，跳过没有可编辑框的行，不在边界换列或循环', () => {
  assert.equal(findTableArrowTarget(grid,0,2,0,'ArrowDown'),'name-2')
  assert.equal(findTableArrowTarget(grid,2,2,0,'ArrowUp'),'name-2')
  assert.equal(findTableArrowTarget(grid,0,5,1,'ArrowDown'),'custom-value-3')
  assert.equal(findTableArrowTarget(grid,0,2,0,'ArrowUp'),null)
  assert.equal(findTableArrowTarget(grid,2,2,0,'ArrowDown'),null)
  assert.equal(findTableArrowTarget(grid,0,2,0,'ArrowLeft'),null)
})
test('组合输入和带修饰键的方向键保留原行为', () => {
  for(const event of [{isComposing:true},{keyCode:229},{ctrlKey:true},{metaKey:true},{altKey:true},{shiftKey:true},{defaultPrevented:true},{key:'Enter'}]){
    handleTableArrowNavigation({key:'ArrowDown',...event,preventDefault:()=>assert.fail('不能接管该按键')})
  }
})
