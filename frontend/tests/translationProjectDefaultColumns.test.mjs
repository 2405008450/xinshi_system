import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(
  new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url),
  'utf8',
)

test('笔译项目默认列表不显示项目经理，并迁移上一版默认配置', () => {
  assert.match(
    page,
    /const translationDefaultColumnKeys = previousTranslationDefaultColumnKeys\s+\.filter\(\(key\) => key !== 'projectManagerName'\)\s+\.map\(\(key\) => key === 'projectName' \? 'sourceFileName' : key\)/,
  )
  assert.match(
    page,
    /legacyDefaultKeys: \[legacyTranslationDefaultColumnKeys, legacyTranslationDefaultColumnKeysWithReturnTime, previousTranslationDefaultColumnKeys\]/,
  )
})

test('旧项目名称字段配置映射到文件名列', () => {
  assert.match(page, /keyAliases: \{ projectName: 'sourceFileName' \}/)
})
