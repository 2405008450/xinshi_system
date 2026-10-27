import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/annotationOps.js', import.meta.url), 'utf8')
const auditPage = readFileSync(new URL('../src/views/system/ProjectOperationAudits.vue', import.meta.url), 'utf8')
const recordActions = readFileSync(new URL('../src/components/annotation/AnnotationProgressRecordActions.vue', import.meta.url), 'utf8')

test('所有项目进度和变更说明共用编辑删除入口，删除后保留本条历史入口', () => {
  assert.match(page, /<AnnotationProgressRecordActions[^>]+:record="child"/)
  assert.doesNotMatch(page, /v-if="canWrite && child\.kind === 'progress'"/)
  assert.match(recordActions, /查看编辑 \/ 删除记录/)
  assert.match(recordActions, /recordPart:statusNote.value\?'status_note':'progress'/)
  assert.ok(page.includes("'删除客户进度' : '删除具体进度'"))
})

test('删除具体进度必须填写原因并提交并发版本', () => {
  assert.match(page, /prop="reason"/)
  assert.match(page, /请填写删除原因/)
  assert.match(page, /expectedUpdatedAt:target\.updatedAt\|\|null/)
  assert.match(api, /deleteStatusHistoryProgress = \(id, data\) => api\.delete/)
  assert.match(api, /data: convert\(data, snake\)/)
})

test('项目操作审计可筛选并查看具体进度删除原因', () => {
  assert.match(auditPage, /label="删除具体进度" value="progress_delete"/)
  assert.match(auditPage, /row\.operation_type === 'progress_delete'/)
  assert.match(auditPage, /row\.change_reason \|\| '-'/)
  assert.match(auditPage, /progress_record_delete: '项目进度记录'/)
})
