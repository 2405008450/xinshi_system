import test from 'node:test'
import assert from 'node:assert/strict'
import { buildFolderTree, folderNameError, folderParentId, folderPath, folderBreadcrumbs, materialFileType, newFolderId } from '../src/utils/annotationMaterialFolders.js'

const folders = [
  { id: 'a', parent_id: null, name: '规范' },
  { id: 'b', parent_id: 'a', name: '中文', pending: true },
  { id: 'c', parent_id: null, name: '交付' },
]

test('目录树包含根目录、空目录及待保存的二级目录', () => {
  const tree = buildFolderTree(folders)
  assert.equal(tree[0].id, null)
  assert.equal(tree[0].children.length, 2)
  assert.equal(tree[0].children[0].children[0].pending, true)
  assert.deepEqual(tree[0].children[1].children, [])
})

test('一级和二级选择均能确定新建二级目录的父目录及完整路径', () => {
  assert.equal(folderParentId(folders, null), null)
  assert.equal(folderParentId(folders, 'a'), 'a')
  assert.equal(folderParentId(folders, 'b'), 'a')
  assert.equal(folderPath(folders, 'b'), '项目资料 / 规范 / 中文')
  assert.equal(folderPath(folders, null), '项目资料（根目录）')
})

test('名称校验拒绝路径与控制字符，按同父目录判断重名', () => {
  for (const name of ['', '  ', '.', '..', 'a/b', 'a\\b', 'a\u0000b', 'a\u007fb', 'x'.repeat(101)]) assert.ok(folderNameError(name, folders))
  assert.ok(folderNameError(' 规范 ', folders))
  assert.ok(folderNameError('中文', folders, 'a'))
  assert.equal(folderNameError('中文', folders, 'c'), '')
  assert.equal(folderNameError('规范', folders, 'c'), '')
})

test('HTTP环境没有randomUUID时仍生成标准UUID', () => {
  const first = newFolderId(), second = newFolderId()
  assert.match(first, /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/)
  assert.notEqual(first, second)
})

test('资源管理器路径保留每一级目录ID，根路径可返回', () => {
  assert.deepEqual(folderBreadcrumbs(folders, 'b'), [{ id: null, name: '项目资料' }, { id: 'a', name: '规范' }, { id: 'b', name: '中文' }])
  assert.deepEqual(folderBreadcrumbs(folders, null), [{ id: null, name: '项目资料' }])
  assert.deepEqual(folderBreadcrumbs(folders, 'missing'), [{ id: null, name: '项目资料' }])
})

test('文件类型识别兼容大小写、多点名称和无扩展名', () => {
  assert.deepEqual(materialFileType('项目需求.PNG'), { family: 'image', label: 'PNG 图像' })
  assert.equal(materialFileType('sample.audio.wav').family, 'audio')
  assert.equal(materialFileType('sample.MP4').family, 'video')
  assert.equal(materialFileType('交付说明').label, '文件')
})
