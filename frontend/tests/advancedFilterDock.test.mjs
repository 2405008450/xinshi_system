import test from 'node:test'
import assert from 'node:assert/strict'
import {filterDockStorageKey,readDockKeys} from '../src/utils/advancedFilterDock.js'

test('常用筛选按用户、页面与窗口分别记忆',()=>{
  const key=filterDockStorageKey('/translation-details','project','alice')
  assert.notEqual(key,filterDockStorageKey('/translation-details','project','bob'))
  assert.notEqual(key,filterDockStorageKey('/clients','project','alice'))
  assert.notEqual(key,filterDockStorageKey('/translation-details','history','alice'))
})
test('损坏或历史配置安全回退，去除非字符串与重复项',()=>{
  for(const value of ['invalid','null','{}'])assert.deepEqual(readDockKeys({getItem:()=>value},'key'),[])
  assert.deepEqual(readDockKeys({getItem:()=> '["客户简称","客户简称",null,2,"译员分配情况"]'},'key'),['客户简称','译员分配情况'])
})
