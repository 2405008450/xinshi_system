import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const translationPage = readFileSync(new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url), 'utf8')
const interpretationPage = readFileSync(new URL('../src/views/project/interpretation/InterpretationProjectDetails.vue', import.meta.url), 'utf8')
const recruitmentPage = readFileSync(new URL('../src/views/project/RecruitmentProjects.vue', import.meta.url), 'utf8')
const consultationPage = readFileSync(new URL('../src/views/client/Consultations.vue', import.meta.url), 'utf8')
const commonStyles = readFileSync(new URL('../src/styles/common.css', import.meta.url), 'utf8')

test('标注项目名称使用单行省略，避免长名称撑高列表行', () => {
  assert.match(annotationPage, /class="project-name-ellipsis business-clickable-cell" :title="textValue\(row\.projectName\)"/)
})

test('四类项目列表统一使用紧凑项目名称样式', () => {
  assert.match(translationPage, /class="project-name-ellipsis" :title="row\.projectName \|\| '-'"/)
  assert.match(interpretationPage, /class="project-name-ellipsis" :title="textValue\(row\.projectName\)"/)
  assert.match(recruitmentPage, /class="project-name-ellipsis business-clickable-cell" :title="row\.projectName \|\| '待生成'"/)
  assert.match(commonStyles, /\.project-detail-list-table \.project-name-ellipsis\s*\{[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s)
})

test('新咨询列表接入紧凑行高并禁止关键链接换行撑高', () => {
  assert.match(consultationPage, /class="consultation-list-table project-detail-list-table"/)
  assert.match(consultationPage, /\.client-short-name-link,[\s\S]*\.consultation-code-link\s*\{[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/)
})
