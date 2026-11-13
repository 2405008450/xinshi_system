import test from 'node:test'
import assert from 'node:assert/strict'
import {buildLanguagePairOptions} from '../src/utils/languagePairOptions.js'

const languages = [
  {id:'zh', code:'zh-CN', label:'中文（简体）', shortcuts:['中','简中'], aliases:['中文','汉语']},
  {id:'en', code:'en-US', label:'英语（美国）', shortcuts:['英','美英'], aliases:['英文','English']},
  {id:'fr', code:'fr-FR', label:'法语', shortcuts:['法'], aliases:['French']},
]
const common = [['zh-CN','en-US'],['en-US','zh-CN']]
test('简称、方向、分词及规范全称均可检索，常用方向优先', () => {
  for (const query of ['中英','中译英','中文 英语','中文（简体）→英语（美国）','zh-CN en-US']) {
    assert.equal(buildLanguagePairOptions(languages, common, query)[0].value, '中文（简体）→英语（美国）')
  }
  assert.equal(buildLanguagePairOptions(languages, common, '英中')[0].value, '英语（美国）→中文（简体）')
  assert.equal(buildLanguagePairOptions(languages, common).length, 6)
  assert.deepEqual(buildLanguagePairOptions(languages, common, '不存在'), [])
  assert.equal(buildLanguagePairOptions(languages, common, '校对', {allowProofreading:true})[0].value, '校对')
})
test('500语种仅生成有限候选，后部语种仍能通过检索找到', () => {
  const rows = Array.from({length:500}, (_, i) => ({id:String(i), label:`语种${i}`, shortcuts:[`语种${i}`]}))
  assert.equal(buildLanguagePairOptions(rows, []).length, 200)
  assert.ok(buildLanguagePairOptions(rows, [], '语种499→语种498').some(item => item.value === '语种499→语种498'))
})
