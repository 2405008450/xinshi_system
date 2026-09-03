import test from 'node:test'
import assert from 'node:assert/strict'

import { resolvePreferredProjectPath } from '../src/utils/projectPath.js'

test('原文路径优先于所有备用路径并去除首尾空白', () => {
  const result = resolvePreferredProjectPath(
    {
      storage_path: '  \\\\server\\source  ',
      dispatch_path: '\\\\server\\dispatch',
      translation_path: '\\\\server\\translation',
    },
    {
      referenceFilePathOne: '\\\\server\\reference',
      networkFilePath: '\\\\server\\legacy',
    },
  )

  assert.deepEqual(result, { source: '原文路径', path: '\\\\server\\source' })
})

test('空白原文路径按界面顺序回退到第一个已填写路径', () => {
  const result = resolvePreferredProjectPath(
    {
      storage_path: '   ',
      dispatch_path: ' \\\\server\\dispatch ',
      translation_path: '\\\\server\\translation',
      feedback_delivery_path: '\\\\server\\feedback-delivery',
    },
    { referenceFilePathOne: '\\\\server\\reference' },
  )

  assert.deepEqual(result, { source: '派稿文路径', path: '\\\\server\\dispatch' })
})

test('派稿文为空时参考文件路径一优先于后续流程路径', () => {
  const result = resolvePreferredProjectPath(
    { translation_path: '\\\\server\\translation' },
    { reference_file_path_one: ' \\\\server\\reference ' },
  )

  assert.deepEqual(result, { source: '参考文件路径一', path: '\\\\server\\reference' })
})

test('兼容项目列表中的旧版网络文件路径', () => {
  const result = resolvePreferredProjectPath({}, { networkFilePath: ' \\\\server\\legacy ' })

  assert.deepEqual(result, { source: '网络文件路径', path: '\\\\server\\legacy' })
})

test('所有路径为空时返回 null', () => {
  const result = resolvePreferredProjectPath(
    { storage_path: '', dispatch_path: null, translation_path: '  ' },
    { referenceFilePathOne: undefined, networkFilePath: '' },
  )

  assert.equal(result, null)
})
