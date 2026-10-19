import assert from 'node:assert/strict'
import test from 'node:test'
import { associatedProject, associatedProjectError, createAssociatedProjectLoader } from '../src/utils/associatedProjectDetail.js'
import { recruitmentProjectDetailItems, formatDate } from '../src/utils/recruitmentProjectDetail.js'
import { translationProjectDetailItems, formatTranslatorReturnTimes } from '../src/utils/translationProjectDetail.js'
import { timeRangesText } from '../src/utils/interpretationProjectDetail.js'

test('四类需求只使用各自关联 ID；其他类型和没有 ID 的快照不生成入口', () => {
  for (const sourceType of ['annotation', 'translation', 'interpretation', 'recruitment']) {
    assert.deepEqual(associatedProject({ sourceType, [`${sourceType}ProjectId`]: 'project-id' }), { sourceType, projectId: 'project-id' })
    assert.equal(associatedProject({ sourceType, sourceProjectNameSnapshot: '同名项目', annotationProjectId: sourceType === 'annotation' ? null : 'wrong-id' }), null)
  }
  assert.equal(associatedProject({ sourceType: 'other', otherProjectId: 'id' }), null)
  assert.equal(associatedProject(null), null)
})

test('关闭、快速切换和失败重试不会回写旧项目或旧错误', async () => {
  const pending = [], states = []
  const loader = createAssociatedProjectLoader((target, signal) => new Promise((resolve, reject) => pending.push({ target, signal, resolve, reject })), value => states.push(value))
  const old = loader.load('old'), latest = loader.load('latest')
  assert.equal(pending[0].signal.aborted, true)
  pending[1].resolve({ detail: { id: 'latest' } }); await latest
  pending[0].resolve({ detail: { id: 'old' } }); await old
  assert.equal(states.at(-1).detail.id, 'latest')
  const closing = loader.load('closing'); loader.cancel()
  const count = states.length
  pending[2].reject(new Error('迟到的错误')); await closing
  assert.equal(states.length, count)
  const fail = loader.load('failure'); pending[3].reject({ status: 404 }); await fail
  assert.match(states.at(-1).error, /不存在或已被删除/)
  const retry = loader.load('retry'); pending[4].resolve({ detail: { id: 'retry' } }); await retry
  assert.equal(states.at(-1).error, '')
  assert.equal(states.at(-1).detail.id, 'retry')
  assert.match(associatedProjectError({ response: { status: 403 } }), /没有权限/)
})

test('共享字段保留原项目业务显示，并明确按 UTC+8 展示时间', () => {
  assert.equal(translationProjectDetailItems.find(item => item.label === '项目名称').key, 'sourceFileName')
  assert.equal(recruitmentProjectDetailItems.find(item => item.key === 'headcount').formatter(null, { headcountMin: 2, headcountMax: 5 }), '2–5人')
  assert.match(formatTranslatorReturnTimes([{ translatorName: '译员', translatorReturnTime: '2026-10-19T00:30:00Z' }]), /08:30/)
  assert.match(timeRangesText([{ scheduledStart: '2026-10-19T00:30:00Z', scheduledEnd: '2026-10-19T01:30:00Z' }]), /08:30.*09:30/)
  assert.equal(formatDate('2026-10-19'), '2026/10/19')
})
