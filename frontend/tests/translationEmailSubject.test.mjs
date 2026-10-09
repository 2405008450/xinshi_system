import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { buildTranslationEmailSubject, extractTranslationSubjectPrefix } from '../src/utils/translationEmailSubject.js'

const cases = JSON.parse(fs.readFileSync(new URL('../../tests/fixtures/translation_email_subject_cases.json', import.meta.url), 'utf8'))
const camel = (source) => Object.fromEntries(Object.entries(source).map(([key, value]) => [key.replace(/_([a-z])/g, (_, c) => c.toUpperCase()), value]))

for (const item of cases) {
  test(`笔译主题共享案例：${item.source.order_no}`, () => {
    const result = buildTranslationEmailSubject(camel(item.source))
    assert.equal(result.subject, item.subject)
    assert.equal(result.parts.join('，'), item.subject)
    assert.equal(result.subject.split(item.source.client_short_name).length, 2)
  })
}

test('新主题和名称已经改为文件名的历史主题都能恢复前缀', () => {
  const source = camel(cases[0].source)
  source.subjectPrefix = ''
  assert.equal(extractTranslationSubjectPrefix(cases[0].subject, source), '***急***')
  assert.equal(extractTranslationSubjectPrefix('***急***，TP-261009-001，测试客户，旧业务摘要', source), '***急***')
  assert.equal(extractTranslationSubjectPrefix('人工标题，无格式', source), '')
  assert.equal(extractTranslationSubjectPrefix('TP-261009-001，测试客户，旧业务摘要', source), '')
})

test('项目名称及客户单号变化不进入主题', () => {
  const source = camel(cases[0].source)
  assert.equal(buildTranslationEmailSubject({ ...source, sourceFileName: '新的文件.xlsx', projectName: '新的文件.xlsx', customerOrderNo: 'PO-99' }).subject, cases[0].subject)
})
