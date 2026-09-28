import assert from 'node:assert/strict'
import test from 'node:test'
import { mailPolicyRules } from '../src/utils/mailPolicyForm.js'

test('项目邮件允许仅抄送，但主送和抄送不能同时清空', () => {
  const check = (policy, to) => {
    let error
    mailPolicyRules(policy).to_group_ids[0].validator(null, to, value => { error = value })
    return error
  }
  assert.ok(check({ cc_group_ids: [] }, []))
  assert.equal(check({ cc_group_ids: ['group'] }, []), undefined)
  assert.equal(check({ cc_group_ids: [] }, ['group']), undefined)
  assert.equal(mailPolicyRules({ cc_group_ids: ['group'] }).to_group_ids[0].required, false)
})
