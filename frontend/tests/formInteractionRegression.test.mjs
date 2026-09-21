import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { revealFormTarget } from '../src/utils/formNavigation.js'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const moduleFiles = [
  'src/views/client/Consultations.vue',
  'src/views/project/translation/ProjectDetails.vue',
  'src/views/project/interpretation/InterpretationProjectDetails.vue',
  'src/views/project/AnnotationProjects.vue',
  'src/views/project/RecruitmentProjects.vue',
  'src/views/manuscript/ManuscriptArrangements.vue',
  'src/views/client/Clients.vue',
  'src/views/resource/ResourceRequests.vue',
  'src/views/resource/TalentPool.vue',
]

test('九个常用板块的新增编辑表单统一接入 AppForm 和自动字段搜索', () => {
  for (const file of moduleFiles) {
    const source = read(file)
    assert.match(source, /<AppForm\b/, `${file} 缺少 AppForm`)
    assert.match(source, /<DialogFieldSearchHeader\b/, `${file} 缺少字段搜索头部`)
    assert.match(source, /useDialogFieldSearch/, `${file} 缺少自动字段索引`)
  }
})

test('字段搜索由当前 DOM 自动建索引，新字段无需维护手写清单', () => {
  const composable = read('src/composables/useDialogFieldSearch.js')
  const translation = read('src/views/project/translation/ProjectDetails.vue')

  assert.match(composable, /querySelectorAll\(\s*['"]\.el-form-item, \[data-dialog-field-search-label\]/)
  assert.match(composable, /dataset\.dialogFieldSearchAliases/)
  assert.doesNotMatch(translation, /projectFieldSearchItems/)
  assert.match(translation, /data-dialog-field-search-label="item\.label"/)
})

test('稿件安排的业务校验失败会定位对应字段而非只显示消息', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')
  assert.match(source, /locateDialogFieldByLabel: locateDispatchFieldByLabel/)
  assert.match(source, /await locateDispatchFieldByLabel\(validationError\.label, validationError\.occurrence\)/)
  for (const label of ['选择译员', '需翻译部分', '字数与结算', '译员交稿_预定时间', '译员结账方式']) {
    assert.match(source, new RegExp(`label: '${label}'`))
  }
})

test('公共定位能力会先展开隐藏标签页和折叠面板', async () => {
  const calls = []
  const dialog = { parentElement: null, matches: () => false, classList: { contains: value => value === 'el-dialog' } }
  const pane = {
    id: 'pane-progress',
    parentElement: dialog,
    style: { display: 'none' },
    matches: selector => selector === '.el-tab-pane',
    getAttribute: name => name === 'aria-hidden' ? 'true' : null,
    classList: { contains: () => false },
  }
  const collapse = {
    parentElement: pane,
    matches: selector => selector === '.el-collapse-item',
    classList: { contains: () => false },
    querySelector: () => ({ click: () => calls.push('collapse') }),
  }
  const target = { parentElement: collapse }
  const previousDocument = globalThis.document
  const previousRaf = globalThis.requestAnimationFrame
  globalThis.document = {
    querySelector: () => ({
      getAttribute: () => 'false',
      click: () => calls.push('tab'),
    }),
  }
  globalThis.requestAnimationFrame = callback => callback()
  try {
    assert.equal(await revealFormTarget(target), true)
    assert.deepEqual(calls, ['tab', 'collapse'])
  } finally {
    globalThis.document = previousDocument
    globalThis.requestAnimationFrame = previousRaf
  }
})
