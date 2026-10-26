import test from 'node:test'
import assert from 'node:assert/strict'
import {referenceTreeRows,referenceGraphRoot} from '../src/utils/chatReferenceTree.js'

test('按父子分支排列全部引用，保留原编号和原始数据',()=>{
  const rows=[{id:'a',referenceNumber:1,ancestorIds:[]},{id:'b',referenceNumber:2,ancestorIds:[]},{id:'c',referenceNumber:3,ancestorIds:['a']},{id:'d',referenceNumber:4,ancestorIds:['a','c']}]
  assert.deepEqual(referenceTreeRows(rows).map(row=>row.id),['a','c','d','b'])
  assert.equal(rows[0].children,undefined)
})
test('被撤回的中间消息不丢失后续引用，挂在可见的最近祖先下',()=>{
  const rows=[{id:'a',referenceNumber:1,ancestorIds:[]},{id:'b',referenceNumber:2,ancestorIds:[]},{id:'d',referenceNumber:3,ancestorIds:['a','withdrawn']}]
  assert.deepEqual(referenceTreeRows(rows).map(row=>row.id),['a','d','b'])
})

test('完整引用树从 A 开始，在 B 后同时显示 C-D 和 B1 两个分支',()=>{
  const root=referenceGraphRoot({id:'A'},[
    {id:'B',referenceNumber:1,ancestorIds:[]},
    {id:'C',referenceNumber:2,ancestorIds:['B']},
    {id:'D',referenceNumber:3,ancestorIds:['B','C']},
    {id:'B1',referenceNumber:4,ancestorIds:['B']},
  ])
  assert.equal(root.id,'A')
  assert.equal(root.isOriginal,true)
  assert.deepEqual(root.children.map(node=>node.id),['B'])
  assert.deepEqual(root.children[0].children.map(node=>node.id),['C','B1'])
  assert.equal(root.children[0].children[0].children[0].id,'D')
})
