import assert from 'node:assert/strict'
import test from 'node:test'
import { mergeTalentEdit, talentEditValues } from '../src/utils/talentEditDraft.js'

test('人才草稿只合并自己的修改，保留最新字段和新增简历语种', () => {
  const base = { remarks: '旧备注', talentGrade: 'pending', resumeProfile: { versions: {} } }
  const latest = { ...base, remarks: '同事更新', reportedAge: 30 }
  const draft = { ...base, talentGrade: 'active', resumeProfile: { versions: { en: { name: 'Test' } } } }
  assert.deepEqual(mergeTalentEdit(latest, draft, base), {
    values: { ...latest, talentGrade: 'active', resumeProfile: draft.resumeProfile },
    changes: [],
  })
})

test('同字段冲突保留输入，关闭再打开也需要处理未确认的冲突', () => {
  const base = { remarks: '旧备注' }
  const latest = { remarks: '同事更新' }
  const draft = { remarks: '我的更新' }
  const result = mergeTalentEdit(latest, draft, base)
  assert.deepEqual(result.values, draft)
  assert.deepEqual(result.changes, [{ path: 'remarks', keys: ['remarks'], current: '我的更新', latest: '同事更新' }])
  assert.deepEqual(mergeTalentEdit(latest, draft, latest, ['remarks']), result)
  assert.deepEqual(mergeTalentEdit(draft, draft, base).changes, [])
})

test('旧草稿缺失的新字段继续使用最新资料，旧字段差异需核对', () => {
  const latest = { remarks: '最新备注', reportedAge: 30, resumeProfile: { catTools: ['Trados'], selfAssessment: '现有自评' } }
  const draft = { remarks: '草稿备注', resumeProfile: { selfAssessment: '草稿自评' } }
  const rebased = mergeTalentEdit(latest, draft)
  assert.deepEqual(rebased.values, { ...latest, ...draft, resumeProfile: { ...latest.resumeProfile, ...draft.resumeProfile } })
  assert.deepEqual(rebased.changes.map(row => row.path), ['remarks', 'resumeProfile.selfAssessment'])
})

test('版本字段、附件和无权限字段不从草稿写入，临时行键不制造冲突', () => {
  const form = { updatedAt: '旧版本', id: '1', remarks: '', primaryPhone: '123', attachments: [], resumeProfile: { revision: 3, catTools: [] } }
  assert.deepEqual(talentEditValues(form, ['id', 'remarks', 'primaryPhone', 'attachments', 'resumeProfile', 'reportedAge'], ['primaryPhone']), { remarks: '', resumeProfile: { catTools: [] } })
  assert.equal(form.resumeProfile.revision, 3)
  const row = { id: '1', name: '证书' }
  assert.deepEqual(mergeTalentEdit({ certificates: [{ ...row, _key: 'latest' }] }, { certificates: [{ ...row, _key: 'draft' }] }).changes, [])
})
