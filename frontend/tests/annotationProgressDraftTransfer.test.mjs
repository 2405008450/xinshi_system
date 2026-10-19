import assert from 'node:assert/strict'
import test from 'node:test'
import { combineAnnotationProgressDrafts } from '../src/utils/annotationProgressDraftTransfer.js'

test('切换归属完整保留当前原文、换行和节点时间', () => {
  const draft = { changeNote: '  已完成试标\n等待客户回复  ', effectiveOn: '2026-10-19 10:26:09', source: null }
  assert.deepEqual(combineAnnotationProgressDrafts({}, draft), draft)
})

test('目标已有草稿只追加，保留双方原文并使用当前节点时间', () => {
  const target = { changeNote: '已有草稿\n', effectiveOn: '2026-10-18 08:00:00', source: { messageCount: 1, senderSummary: '黄萌' } }
  const incoming = { changeNote: '  当前文字', effectiveOn: '2026-10-19 10:26:09', source: { messageCount: 2, senderSummary: '黄萌、Jimmy' } }
  const result = combineAnnotationProgressDrafts(target, incoming)
  assert.equal(result.changeNote, '已有草稿\n\n\n  当前文字')
  assert.equal(result.effectiveOn, incoming.effectiveOn)
  assert.deepEqual(result.source, { messageCount: 3, senderSummary: '黄萌、Jimmy' })
  assert.equal(target.changeNote, '已有草稿\n')
  assert.equal(target.effectiveOn, '2026-10-18 08:00:00')
})

test('合并超长与正在编辑的客户记录均阻止转移，原草稿不变', () => {
  const target = { changeNote: '甲'.repeat(9999), effectiveOn: '2026-10-18 08:00:00' }
  const incoming = { changeNote: '乙', effectiveOn: '2026-10-19 10:26:09' }
  assert.throws(() => combineAnnotationProgressDrafts(target, incoming), /超过 10000 字/)
  assert.equal(target.changeNote.length, 9999)
  assert.equal(incoming.changeNote, '乙')
  assert.throws(() => combineAnnotationProgressDrafts({ editingId: 'existing-record' }, incoming), /保存或取消/)
  assert.throws(() => combineAnnotationProgressDrafts({}, { ...incoming, editingId: 'existing-record' }), /保存或取消/)
})
