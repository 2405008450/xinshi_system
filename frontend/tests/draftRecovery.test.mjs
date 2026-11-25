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
test('同一云端版本之后的新本机草稿不被服务器快钟和清空记录覆盖',()=>{
 const local={items:[{progress_content:'尚未填完'}],_savedAt:100,_baseRevision:3}
 assert.equal(chooseDraft(local,{revision:3,payload:null,updated_at:'2099-01-01T00:00:00+08:00'}),local)
 assert.equal(chooseDraft(local,{revision:4,payload:null,updated_at:'2099-01-01T00:00:00+08:00'}),null)
})
test('比较草稿编辑时刻而非同步响应时刻，避免较旧云端内容覆盖新编辑',()=>{
 const local={items:[{progress_content:'最新编辑'}],_savedAt:200,_baseRevision:1}
 const remote={revision:2,payload:{items:[{progress_content:'旧内容'}],_savedAt:100},updated_at:'2099-01-01T00:00:00+08:00'}
 assert.equal(chooseDraft(local,remote),local)
})
