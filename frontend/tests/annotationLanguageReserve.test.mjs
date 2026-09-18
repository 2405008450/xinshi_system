import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const popover = readFileSync(new URL('../src/components/annotation/LanguageTalentReservePopover.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/annotationProjects.js', import.meta.url), 'utf8')

test('标注语言方向按结构化语言项展示人才储备入口并批量查询', () => {
  assert.match(page, /row\.languageItems/)
  assert.match(page, /LanguageTalentReservePopover/)
  assert.match(page, /pageLanguageIds/)
  assert.match(page, /lookupAnnotationLanguageReserves/)
  assert.match(api, /language-reserves\/lookup/)
})

test('人才储备小窗分别展示双语两端并区分未匹配和错误', () => {
  assert.match(popover, /sourceLanguageId/)
  assert.match(popover, /targetLanguageId/)
  assert.match(popover, /项目原始语种/)
  assert.match(popover, /源语种/)
  assert.match(popover, /目标语种/)
  assert.match(popover, /placement="bottom-start"/)
  assert.match(popover, /人才概览暂无可确定的对应语种/)
  assert.match(popover, /人才储备加载失败/)
  assert.match(popover, /不代表去重后的人才人数/)
  assert.equal((popover.match(/v-for="endpoint in endpoints"/g) || []).length, 1)
})

test('小屏幕取消表格左右固定列遮挡，语言储备入口保持可点击', () => {
  assert.match(page, /@media\(max-width:768px\)/)
  assert.match(page, /el-table-fixed-column--left/)
  assert.match(page, /el-table-fixed-column--right/)
  assert.match(page, /position:static!important/)
})
