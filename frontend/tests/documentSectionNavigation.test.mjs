import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/utils/documentSectionNavigation.js', import.meta.url), 'utf8')
const { sectionPath, sectionQuery, flattenSections, sectionHeight, sectionPlacements } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const tree = [{ id: 'a', title: '一级', children: [{ id: 'b', title: '二级' }] }, { id: 'c', title: '其他' }]

test('三级栏目路径、导航及排序均保留全部层级',()=>{
  const nested=[{id:'a',title:'一级',children:[{id:'b',title:'二级',children:[{id:'d',title:'三级'}]}]}]
  assert.deepEqual(sectionPath(nested,'d').map(row=>row.title),['一级','二级','三级'])
  assert.deepEqual(flattenSections(nested).map(row=>row.id),['a','b','d'])
  assert.equal(sectionHeight(nested[0]),3)
  assert.deepEqual(sectionPlacements(nested).map(({id,parentId,sortOrder})=>({id,parentId,sortOrder})),[{id:'a',parentId:null,sortOrder:1},{id:'b',parentId:'a',sortOrder:1},{id:'d',parentId:'b',sortOrder:1}])
})

test('首页、一级、二级及失效路径', () => {
  assert.deepEqual(sectionPath(tree, null), [])
  assert.deepEqual(sectionPath(tree, 'a').map(x => x.title), ['一级'])
  assert.deepEqual(sectionPath(tree, 'b').map(x => x.title), ['一级', '二级'])
  assert.deepEqual(sectionPath(tree, 'missing'), [])
  assert.deepEqual(sectionPath(tree, ['b']), [])
})

test('移动与改名后面包屑从当前栏目树派生', () => {
  const next = [{ ...tree[0], children: [] }, { ...tree[1], children: [{ id: 'b', title: '新名称' }] }]
  assert.deepEqual(sectionPath(next, 'b').map(x => x.title), ['其他', '新名称'])
})

test('进入栏目及返回首页保留其他查询参数、不修改原对象', () => {
  const query = { section: 'notices', projectId: '123' }
  const child = sectionQuery(query, 'b', 'noticeSectionId')
  assert.deepEqual(child, { ...query, noticeSectionId: 'b' })
  assert.deepEqual(query, { section: 'notices', projectId: '123' })
  assert.deepEqual(sectionQuery(child, null, 'noticeSectionId'), query)
})

test('公司管理使用自己的栏目参数，不注入标注页签', () => {
  const query = { source: 'bookmark' }
  const child = sectionQuery(query, 'b', 'companySectionId')
  assert.deepEqual(child, { source: 'bookmark', companySectionId: 'b' })
  assert.deepEqual(sectionQuery(child, null, 'companySectionId'), query)
  assert.deepEqual(sectionQuery({}, 'b'), { documentSectionId: 'b' })
})
