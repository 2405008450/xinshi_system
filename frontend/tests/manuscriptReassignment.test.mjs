import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('稿件安排支持逐个译员改派并在发送前预览', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')
  const api = read('src/api/manuscriptArrangements.js')

  assert.match(api, /arrangements\/\$\{arrangementId\}\/reassign/)
  assert.match(source, /title="改派译员"/)
  assert.match(source, /确认改派并预览邮件/)
  assert.match(source, /不会自动向原译员发送取消通知/)
  assert.match(source, /\['ready', 'failed', 'sent'\]\.includes\(item\.status\)/)
  assert.match(source, /await openMailPreviewDialog\(dispatch, replacement\)/)
  assert.match(source, /reassigned_to_translator_name/)
  assert.match(source, /label: '已改派'/)
})

test('已发送历史存在时不允许整批撤回', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')

  assert.match(source, /function dispatchHasSentHistory\(dispatch\)/)
  assert.match(source, /Boolean\(item\.sent_at\)/)
  assert.match(source, /selectedProjectDispatch\?\.status === 'ready' && !dispatchHasSentHistory/)
})
