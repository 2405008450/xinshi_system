import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/views/resource/TalentPool.vue', import.meta.url), 'utf8')
const detailSource = readFileSync(new URL('../src/views/resource/components/TalentDetailContent.vue', import.meta.url), 'utf8')

test('人才列表提供四类摘要入口和独立详情列', () => {
  for (const key of ['basicSummary', 'regionSummary', 'educationSummary', 'languageSummary']) {
    assert.match(source, new RegExp(`key:'${key}'`))
  }
  assert.match(source, /label="详情"/)
  assert.match(source, /TalentDetailContent/)
})

test('人才编辑表单包含结构化姓名、职业、学历、语言、证书和媒体字段', () => {
  for (const field of [
    'chineseName', 'englishName', 'nickname', 'wechat', 'whatsapp', 'employmentStatus',
    'birthYearMonth', 'educationExperiences', 'languageSkills', 'certificates',
    'annotationExperience', 'interpretationExperience', 'translationExperience',
  ]) {
    assert.match(source, new RegExp(`form\\.${field}`))
  }
  assert.match(source, /queueAttachment\('photo'/)
  assert.match(source, /queueAttachment\('audio'/)
})

test('人才详情按分类展示且不依赖悬浮才能访问', () => {
  for (const section of ['identity', 'basic', 'region', 'education', 'language', 'experience', 'projects']) {
    assert.match(detailSource, new RegExp(`shows\\('${section}'\\)`))
  }
  assert.match(source, /trigger="click"/)
})

test('人才长表单每次打开时恢复到顶部', () => {
  assert.match(source, /@open="onEditorOpened"/)
  assert.match(source, /scrollBody\.scrollTop=0/)
})
