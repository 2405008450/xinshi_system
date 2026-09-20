import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { nextTick } from 'vue'
import { useTableColumns } from '../src/composables/useTableColumns.js'
import { countTalentNames, getTalentDisplayName } from '../src/utils/talentNames.js'

const source = readFileSync(new URL('../src/views/resource/TalentPool.vue', import.meta.url), 'utf8')
const detailSource = readFileSync(new URL('../src/views/resource/components/TalentDetailContent.vue', import.meta.url), 'utf8')
const fieldSearchSource = readFileSync(new URL('../src/composables/useDialogFieldSearch.js', import.meta.url), 'utf8')

test('人才列表移除基本信息聚合列并提供三类摘要入口和独立详情列', () => {
  assert.doesNotMatch(source, /\{key:'basicSummary',label:'基本信息'/)
  assert.doesNotMatch(source, /summarySectionMap=\{basicSummary:/)
  for (const key of ['regionSummary', 'educationSummary', 'languageSummary']) {
    assert.match(source, new RegExp(`key:'${key}'`))
  }
  assert.match(source, /label="详情"/)
  assert.match(source, /TalentDetailContent/)
})

test('人才编辑表单包含结构化姓名、职业、学历、语言、证书和媒体字段', () => {
  for (const field of [
    'chineseName', 'englishName', 'nickname', 'wechat', 'whatsapp', 'employmentStatus',
    'birthYearMonth', 'educationExperiences', 'languageSkills', 'certificates',
    'annotationExperience', 'interpretationExperience', 'translationExperience', 'otherExperience',
  ]) {
    assert.match(source, new RegExp(`form\\.${field}`))
  }
  assert.match(source, /queueAttachment\('photo'/)
  assert.match(source, /queueAttachment\('audio'/)
  assert.match(detailSource, /label="其他经验"/)
})

test('人才总库支持维护、展示和筛选低中高标注意愿', () => {
  assert.match(source, /v-model="form\.annotationWillingness"/)
  assert.match(source, /\{key:'annotationWillingness',label:'标注意愿'/)
  assert.match(source, /key:'annotationWillingness'.*type:'select'.*willingnessOptions/)
  assert.match(source, /annotationWillingness:form\.annotationWillingness\|\|null/)
  assert.match(detailSource, /label="标注意愿"/)
  for (const value of ['low', 'medium', 'high']) {
    assert.match(source, new RegExp(`value:'${value}'`))
  }
})

test('人才总库全部可配置列均复用公共漏斗筛选', () => {
  const tableBlock = source.match(/const tableColumns=\[([\s\S]*?)\n\]/)?.[1] || ''
  const filterBlock = source.match(/const talentFilterFields=\[([\s\S]*?)\n\]\.filter/)?.[1] || ''
  const tableKeys = [...tableBlock.matchAll(/\{key:'([^']+)'/g)].map(match => match[1])
  const filterKeys = new Set([...filterBlock.matchAll(/\{key:'([^']+)'/g)].map(match => match[1]))

  assert.ok(tableKeys.length >= 28)
  assert.deepEqual(tableKeys.filter(key => !filterKeys.has(key)), [])
  assert.match(source, /const headerFilterDefinition=\(key\)=>talentFilterFields\.find/)
  assert.doesNotMatch(source, /defaultColumnKeys\.includes\(key\)\?talentFilterFields\.find/)
  for (const key of ['regionSummary', 'educationSummary', 'languageSummary', 'overallRating', 'projectSituation']) {
    assert.match(filterBlock, new RegExp(`key:'${key}'.*type:'text'`))
  }
  for (const key of ['capabilityTypes', 'status', 'cooperationType', 'annotationWillingness', 'employmentStatus']) {
    assert.match(filterBlock, new RegExp(`key:'${key}'.*type:'select'`))
  }
  for (const key of ['yearsExperience', 'age']) {
    assert.match(filterBlock, new RegExp(`key:'${key}'.*type:'number-range'`))
  }
  for (const key of ['firstContactDate', 'updatedAt']) {
    assert.match(filterBlock, new RegExp(`key:'${key}'.*type:'date-range'`))
  }
  assert.match(filterBlock, /key:'duplicateReviewRequired'.*type:'boolean'/)
  assert.match(source, /timer=setTimeout\(searchNow,400\)/)
  assert.match(source, /controller\?\.abort\(\).*const current=\+\+sequence/)
  assert.match(source, /function searchNow\(\).*pagination\.page=1;fetchData\(\)/)
  assert.match(source, /resetFilterModel\(search,talentFilterFields\)/)
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

test('新增工作经验和综合表现字段进入表单字段搜索索引', () => {
  assert.match(source, /label="其他经验"/)
  assert.match(source, /data-dialog-field-search-group/)
  assert.match(source, /data-dialog-field-search-group-title>总体评价/)
  assert.match(source, /data-dialog-field-search-group-title>配合度/)
  assert.match(source, /data-dialog-field-search-group-title>守时度/)
  assert.match(source, /data-dialog-field-search-group-title>{{ item\.label }}/)
  assert.match(fieldSearchSource, /\[data-dialog-field-search-group\]/)
  assert.match(fieldSearchSource, /\[data-dialog-field-search-group-title\]/)
})

test('人才基础字段和总体评价加入默认列并迁移旧默认组合', () => {
  assert.match(source, /\{key:'gender',label:'性别'/)
  assert.match(source, /\{key:'nationality',label:'国籍'/)
  assert.match(source, /\{key:'employmentStatus',label:'职业状态'/)
  assert.match(source, /column\.key === 'employmentStatus'.*employmentOptions\.find/)
  assert.match(source, /defaultColumnKeys=\['fullName','gender','nationality','employmentStatus'/)
  assert.match(source, /defaultColumnKeys=\[[^\]]*'overallRating'/)
  assert.match(source, /legacyDefaultColumnKeys=\[\s*\[\s*'fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','overallRating','projectSituation','status','duplicateReviewRequired'/)
  assert.match(source, /\['fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','status','duplicateReviewRequired'\]/)
  assert.match(source, /overallPerformanceSummary/)
})

test('旧默认列自动迁移，自定义列仅清理已移除字段', async () => {
  const values = new Map([['user_id', 'talent-column-test']])
  globalThis.localStorage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  }
  const storageKey = 'table-columns:resource-talents-test:talent-column-test'
  const columns = [
    { key: 'fullName' }, { key: 'gender' }, { key: 'nationality' },
    { key: 'employmentStatus' }, { key: 'regionSummary' }, { key: 'age' },
  ]
  const defaults = ['fullName', 'gender', 'nationality', 'employmentStatus', 'regionSummary']
  const oldDefaults = ['fullName', 'basicSummary', 'regionSummary']

  values.set(storageKey, JSON.stringify(oldDefaults))
  const migrated = useTableColumns('resource-talents-test', columns, defaults, {
    legacyDefaultKeys: [oldDefaults],
  })
  assert.deepEqual(migrated.selectedKeys.value, defaults)
  assert.equal(values.get(storageKey), JSON.stringify(defaults))

  values.set(storageKey, JSON.stringify(['fullName', 'basicSummary', 'age']))
  const customized = useTableColumns('resource-talents-test', columns, defaults, {
    legacyDefaultKeys: [oldDefaults],
  })
  await nextTick()
  assert.deepEqual(customized.selectedKeys.value, ['fullName', 'age'])
  assert.equal(values.get(storageKey), JSON.stringify(['fullName', 'age']))
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
