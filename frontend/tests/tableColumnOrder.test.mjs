import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, ref, nextTick } from 'vue'
import { normalizeColumnOrder, moveColumn, sortColumns } from '../src/utils/tableColumnOrder.js'
import { useTableColumnOrder } from '../src/composables/useTableColumnOrder.js'
import { createTableColumnDefaults } from '../src/utils/tableColumnDefaults.js'

const fields = ['a','b','c','d'].map(key => ({key}))
test('拖动支持前移和后移，不丢失隐藏字段，不修改原数组', () => {
  const keys = ['a','b','c','d']
  assert.deepEqual(moveColumn(keys,'a','d'), ['b','c','d','a'])
  assert.deepEqual(moveColumn(keys,'d','a'), ['d','a','b','c'])
  assert.deepEqual(moveColumn(keys,'missing','a'), keys)
  assert.deepEqual(keys,['a','b','c','d'])
  assert.deepEqual(sortColumns([fields[0],fields[3]],moveColumn(keys,'d','a')).map(x=>x.key),['d','a'])
})
test('历史顺序过滤删除项、去重并在末尾加入新字段', () => {
  assert.deepEqual(normalizeColumnOrder(['c','removed','c','a'],fields),['c','a','b','d'])
  assert.deepEqual(normalizeColumnOrder(null,fields),['a','b','c','d'])
})
test('各入口实时共享顺序，按账号、模块、主子表隔离，并可恢复系统顺序', async t => {
  const values=new Map([['user_id','order-alice']])
  const previous=globalThis.localStorage
  globalThis.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}
  const scope=effectScope()
  t.after(()=>{scope.stop();globalThis.localStorage=previous})
  const open=(module='test-order',section='main',columns)=>scope.run(()=>useTableColumnOrder(module,section,columns))
  const definitions=ref(fields)
  const settings=open('test-order','main',definitions),table=open()
  settings.setOrder(['d','a','b','c'])
  assert.deepEqual(table.order.value,['d','a','b','c'])
  assert.equal(table.custom.value,true)
  assert.equal(open('test-order','secondary').custom.value,false)
  assert.equal(open('another-module').custom.value,false)
  values.set('user_id','order-bob')
  assert.equal(open().custom.value,false)
  values.set('user_id','order-alice')
  const savedKey=[...values.keys()].find(key=>key.startsWith('table-column-order:'))
  assert.deepEqual(JSON.parse(values.get(savedKey)),['d','a','b','c'])
  definitions.value=[...fields,{key:'new'}]
  await nextTick()
  assert.deepEqual(table.order.value,['d','a','b','c','new'])
  settings.resetOrder()
  assert.equal(table.custom.value,false)
  assert.equal(values.has(savedKey),false)
  assert.deepEqual(table.order.value,['a','b','c','d','new'])
})
test('我的默认同时保存勾选与完整顺序，兼容旧版快照', () => {
  const values=new Map(),storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}
  const options={moduleKey:'x',userKey:'a',storage}
  const defaults=createTableColumnDefaults(options)
  defaults.save(['a','d'],fields,['d','b','a','c'])
  const reloaded=createTableColumnDefaults(options)
  assert.deepEqual(reloaded.restore(fields),['a','d'])
  assert.deepEqual(reloaded.restoreOrder(),['d','b','a','c'])
  defaults.save([],fields)
  assert.deepEqual(defaults.restore(fields),[])
  assert.equal(defaults.restoreOrder(),null)
})

import { h, Fragment, Comment } from 'vue'
import { orderTableColumnNodes } from '../src/utils/orderTableColumnNodes.js'
test('静态列与动态列混排保留结构列、单元格插槽及分组列', () => {
  const Column={name:'TestColumn'}, slot=()=>['original-cell']
  const selection=h(Column,{type:'selection',fixed:'left'})
  const index=h(Column,{type:'index'})
  const actions=h(Column,{label:'操作',fixed:'right'})
  const a=h(Column,{prop:'a',fixed:'left'},{default:slot})
  const b=h(Column,{label:'展示名称',columnKey:'b'})
  const group=h(Column,{label:'来源分组','column-key':'c'},{default:()=>[h(Column,{prop:'counts.c'})]})
  const comment=h(Comment)
  const input=[selection,index,a,h(Fragment,null,[comment,b,group]),actions]
  const output=orderTableColumnNodes(input,fields,['c','b','a','d'])
  assert.deepEqual(output.filter(node=>node.key?.startsWith('ordered:')).map(node=>node.key),['ordered:c','ordered:b','ordered:a'])
  assert.equal(output[0],selection)
  assert.equal(output[1],index)
  assert.equal(output.at(-1),actions)
  assert.equal(output[3],comment)
  assert.equal(output[5].children.default,slot)
  assert.equal(output[5].props.fixed,false)
  assert.equal(a.props.fixed,'left')
  assert.equal(output[2].children.default,group.children.default)
})
