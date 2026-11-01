import test from 'node:test'
import assert from 'node:assert/strict'
import {chooseDraft} from '../src/utils/draftRecovery.js'
test('自动恢复最新草稿，已正式保存的清除版本不恢复旧内容',()=>{
 const remote={revision:2,payload:{content:'云端'},updated_at:'2026-10-31T08:00:00+08:00'}
 assert.equal(chooseDraft(null,remote).content,'云端')
 assert.equal(chooseDraft({content:'旧本机',_savedAt:Date.parse('2026-10-30T08:00:00+08:00')},remote).content,'云端')
 assert.equal(chooseDraft({content:'新本机',_savedAt:Date.parse('2026-10-31T09:00:00+08:00')},remote).content,'新本机')
 assert.equal(chooseDraft({content:'已提交的旧草稿',_savedAt:1},{...remote,payload:null}),null)
 assert.equal(chooseDraft({content:'旧版无时间备份'},{...remote,payload:null}).content,'旧版无时间备份')
})
