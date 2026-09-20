import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { countTalentNames, getTalentDisplayName } from '../src/utils/talentNames.js'

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

test('人才综合表现支持结构化录入、详情弹窗和高级评分筛选排序', () => {
  for (const field of [
    'overallScore', 'overallRating', 'cooperationLevel', 'cooperationNote',
    'punctualityLevel', 'punctualityNote', 'audioAnnotationScore',
    'audioAnnotationEvaluation', 'nonAudioAnnotationScore',
    'nonAudioAnnotationEvaluation', 'collectionScore', 'collectionEvaluation',
  ]) {
    assert.match(source, new RegExp(`form\\.${field}|${field}:form\\.${field}`))
  }
  for (const filter of ['overallScore', 'audioAnnotationScore', 'nonAudioAnnotationScore', 'collectionScore']) {
    assert.match(source, new RegExp(`key:'${filter}'.*type:'number-range'`))
  }
  assert.match(source, /section="performance"/)
  assert.match(source, /performanceSortField/)
  assert.match(source, /v-if="!isRecruitmentPool" class="form-section performance-form-section"/)
  assert.match(source, /:show-performance="!isRecruitmentPool"/)
  assert.match(detailSource, /shows\('performance'\)/)
  assert.match(detailSource, /音频标注表现/)
  assert.match(detailSource, /非音频标注表现/)
  assert.match(detailSource, /采集表现/)
})

test('总体评价加入默认列并迁移旧默认组合', () => {
  assert.match(source, /defaultColumnKeys=\[[^\]]*'overallRating'/)
  assert.match(source, /legacyDefaultColumnKeys=\[\s*\[\s*'fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','status','duplicateReviewRequired'/)
  assert.match(source, /overallPerformanceSummary/)
})

test('人才列表姓名按中文名、英文名、昵称、其他名字顺序只显示一个', () => {
  assert.equal(getTalentDisplayName({
    chineseName: ' 张三 ', englishName: 'San Zhang', nickname: '小张', otherNames: ['Zhang San'], fullName: '旧名称',
  }), '张三')
  assert.equal(getTalentDisplayName({ englishName: 'San Zhang', nickname: '小张' }), 'San Zhang')
  assert.equal(getTalentDisplayName({ nickname: '小张', otherNames: ['Zhang San'] }), '小张')
  assert.equal(getTalentDisplayName({ otherNames: ['Zhang San'], fullName: '旧名称' }), 'Zhang San')
  assert.equal(getTalentDisplayName({ fullName: '兼容旧姓名' }), '兼容旧姓名')
})

test('姓名区域支持展开收起并要求四类姓名至少填写一项', () => {
  assert.equal(countTalentNames({ chineseName: '', englishName: '', nickname: '', otherNames: [] }), 0)
  assert.equal(countTalentNames({ englishName: 'San Zhang', otherNames: ['Zhang San'] }), 2)
  assert.match(source, /nameFieldsExpanded/)
  assert.match(source, /prop="nameGroup"/)
  assert.match(source, /至少填写一项/)
})
