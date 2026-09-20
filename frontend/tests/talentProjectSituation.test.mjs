import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const pool = readFileSync(new URL('../src/views/resource/TalentPool.vue', import.meta.url), 'utf8')
const situation = readFileSync(new URL('../src/views/resource/components/TalentProjectSituationPopover.vue', import.meta.url), 'utf8')
const performance = readFileSync(new URL('../src/views/resource/components/TalentProjectPerformancePopover.vue', import.meta.url), 'utf8')
const trials = readFileSync(new URL('../src/views/project/AnnotationTrials.vue', import.meta.url), 'utf8')
const talentApi = readFileSync(new URL('../src/api/talents.js', import.meta.url), 'utf8')

test('人才总库默认展示项目情况并迁移旧默认列组合', () => {
  assert.match(pool, /key:'projectSituation',label:'项目情况'/)
  assert.match(pool, /defaultColumnKeys=\[[^\]]*'projectSituation'/)
  assert.match(pool, /TalentProjectSituationPopover/)
  assert.match(pool, /'overallRating','status','duplicateReviewRequired'/)
})

test('项目情况按项目名称加数量摘要并提供筛选分页', () => {
  assert.match(situation, /summary\.primary\.projectName/)
  assert.match(situation, /\+\{\{ remainingCount \}\}/)
  assert.match(situation, /placeholder="搜索订单号、项目名称或参与角色"/)
  assert.match(situation, /v-model="filters\.projectType"/)
  assert.match(situation, /v-model="filters\.projectStatus"/)
  assert.match(situation, /<el-pagination/)
  assert.match(situation, /setTimeout\(search, 400\)/)
  assert.doesNotMatch(situation, /project-situation-reference" @click\.stop/)
})

test('项目名称打开人员表现并复用项目详情入口', () => {
  assert.match(situation, /TalentProjectPerformancePopover/)
  assert.match(performance, /试标 \/ 试采表现/)
  assert.match(performance, /正式安排表现/)
  assert.match(performance, /AnnotationProjectDetailPopover/)
  assert.match(performance, /:teleported="true"/)
  assert.doesNotMatch(performance, /project-name-link" @click\.stop/)
  assert.match(performance, /new AbortController\(\)/)
  assert.match(performance, /section:'trials', projectId:props\.project\.projectId, personId:props\.personId/)
  assert.match(talentApi, /getTalentAnnotationProjectPerformance/)
})

test('试标主窗口支持项目和人员精确筛选', () => {
  assert.match(trials, /v-model="personId"/)
  assert.match(trials, /personId:personId\.value\|\|undefined/)
  assert.match(trials, /route\.query\.projectId/)
  assert.match(trials, /route\.query\.personId/)
})
