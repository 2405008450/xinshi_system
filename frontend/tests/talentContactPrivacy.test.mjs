import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const component = readFileSync(
  new URL('../src/components/common/SensitiveContactValue.vue', import.meta.url),
  'utf8',
)
const pool = readFileSync(
  new URL('../src/views/resource/TalentPool.vue', import.meta.url),
  'utf8',
)
const detail = readFileSync(
  new URL('../src/views/resource/components/TalentDetailContent.vue', import.meta.url),
  'utf8',
)

test('受限联系方式固定显示遮罩并阻止常规复制', () => {
  assert.match(component, /'\*\*\*\*\*\*'/)
  assert.match(component, /@copy\.prevent\.stop/)
  assert.match(component, /@cut\.prevent\.stop/)
  assert.match(component, /@dragstart\.prevent\.stop/)
  assert.match(component, /@contextmenu\.prevent\.stop/)
  assert.match(component, /user-select:\s*none/)
})

test('普通用户不显示联系方式表单和筛选，也不提交联系方式', () => {
  assert.match(pool, /v-if="canViewContacts" class="form-section"><h3>联系方式/)
  assert.match(pool, /filter\(item=>canViewContacts\.value\|\|!contactColumnKeys\.has\(item\.key\)\)/)
  assert.match(pool, /if\(!canViewContacts\.value\)contactPayloadKeys\.forEach/)
  assert.match(pool, /SensitiveContactValue/)
})

test('人才详情的全部联系方式均经过敏感值组件展示', () => {
  const protectedFields = [
    'primaryPhone', 'secondaryPhone', 'primaryEmail', 'secondaryEmail',
    'wechat', 'whatsapp', 'skype', 'line', 'otherContact', 'contactInfo',
  ]
  protectedFields.forEach(field => assert.match(detail, new RegExp(`detail\\.${field}`)))
  assert.equal((detail.match(/<SensitiveContactValue/g) || []).length, 9)
})
