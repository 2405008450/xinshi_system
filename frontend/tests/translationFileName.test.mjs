import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { translationFileNameError, translationFileExtension, translationFileExtensionCategories } from '../src/utils/translationFileName.js'
test('只有母订单可免扩展名，仍拒绝多个文件名',()=>{
  assert.equal(translationFileNameError('母订单',{allowMissingExtension:true}),'')
  assert.ok(translationFileNameError('独立文件'))
  assert.ok(translationFileNameError('甲.pdf；乙.docx',{allowMissingExtension:true}))
})
const cases=JSON.parse(readFileSync(new URL('../../tests/fixtures/translation_file_name_cases.json',import.meta.url),'utf8'))
test('前后端共用文件名样例：完整后缀、版本号、单文件及多文件',()=>{
  for(const name of cases.valid) assert.equal(translationFileNameError(name),'',name)
  for(const name of cases.invalid) assert.ok(translationFileNameError(name),name)
})
test('清单全部格式均能验证，复合后缀及分卷得到保留',()=>{
  for(const ext of new Set(Object.values(translationFileExtensionCategories).flat())) assert.equal(translationFileNameError('文件.'+ext),'',ext)
  assert.equal(translationFileExtension('备份.TAR.GZ'),'.tar.gz')
  assert.equal(translationFileExtension('分卷.001'),'.001')
  assert.equal(translationFileExtension('报告.v2'),'')
})
