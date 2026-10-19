import assert from 'node:assert/strict'
import test from 'node:test'
import { resourceRequestsLocation, resolveDevelopmentSection } from '../src/utils/resourceDevelopmentNavigation.js'

test('旧需求入口保留来源、筛选和锚点，并固定进入需求页签', () => {
  const query = { sourceType: 'annotation', sourceProjectId: 'project-1', requestCategory: 'annotation_trial', keyword: '客户', section: 'logs' }
  assert.deepEqual(resourceRequestsLocation({ query, hash: '#request' }), {
    path: '/resource-management/resource-development',
    query: { ...query, section: 'requests' }, hash: '#request',
  })
  assert.equal(query.section, 'logs')
})

test('默认日志与页签权限独立，不能通过 URL 打开无权限板块', () => {
  for (const canRequests of [false, true]) {
    for (const canResource of [false, true]) {
      for (const canIssues of [false, true]) {
        const access = { canRequests, canResource, canIssues }
        const fallback = canResource ? 'logs' : canRequests ? 'requests' : canIssues ? 'issues' : ''
        for (const section of [undefined, '', 'unknown', ['requests']]) {
          assert.equal(resolveDevelopmentSection(section, access), fallback)
        }
        for (const [section, allowed] of [['requests', canRequests], ['logs', canResource], ['arrangements', canResource], ['issues', canIssues]]) {
          assert.equal(resolveDevelopmentSection(section, access), allowed ? section : fallback)
        }
      }
    }
  }
})
