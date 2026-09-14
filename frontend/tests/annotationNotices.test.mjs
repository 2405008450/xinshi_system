import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const noticePage = readFileSync(new URL('../src/views/project/AnnotationNotices.vue', import.meta.url), 'utf8')
const noticeManager = readFileSync(new URL('../src/components/annotation/AnnotationNoticeManager.vue', import.meta.url), 'utf8')
const noticeApi = readFileSync(new URL('../src/api/annotationNotices.js', import.meta.url), 'utf8')
const richTextComposer = readFileSync(new URL('../src/components/RichTextComposer.vue', import.meta.url), 'utf8')
const richTextMarks = readFileSync(new URL('../src/utils/richTextMarks.js', import.meta.url), 'utf8')

test('标注须知使用后端树形栏目并按需加载正文', () => {
  assert.match(noticePage, /getAnnotationNoticeTree/)
  assert.match(noticePage, /getAnnotationNoticeDetail/)
  assert.match(noticePage, /root\.children/)
  assert.match(noticePage, /detailCache/)
})

test('栏目管理支持两级新增、拖拽、编辑和删除', () => {
  assert.match(noticeManager, /新增一级栏目/)
  assert.match(noticeManager, /新增二级栏目/)
  assert.match(noticeManager, /draggable/)
  assert.match(noticeManager, /:allow-drop="allowDrop"/)
  assert.match(noticeManager, /reorderAnnotationNotices/)
  assert.match(noticeManager, /deleteAnnotationNotice/)
  assert.match(noticeManager, /<AppForm/)
})

test('标注须知界面统一展示无字母编号的栏目名称', () => {
  assert.match(noticePage, /\{\{ root\.title \}\}/)
  assert.match(noticePage, /\{\{ child\.title \}\}/)
  assert.match(noticePage, /activeNotice\.title/)
  assert.match(noticePage, /row\.displayTitle/)
  assert.match(noticeManager, /\{\{ data\.title \}\}/)
  assert.doesNotMatch(noticePage, /root\.displayTitle|child\.displayTitle|activeNotice\?\.displayTitle/)
  assert.doesNotMatch(noticeManager, /data\.displayTitle|selected\.value\.displayTitle/)
})

test('全文搜索遵循防抖、取消和旧响应保护范式', () => {
  assert.match(noticePage, /搜索栏目名称或内容/)
  assert.match(noticePage, /setTimeout\(\(\) => runSearch\(true, true\), 400\)/)
  assert.match(noticePage, /new AbortController\(\)/)
  assert.match(noticePage, /current !== searchRequestId/)
  assert.match(noticePage, /searchPagination = reactive\(\{ page: 1, limit: 20, total: 0 \}\)/)
  assert.match(noticePage, /<mark v-if="segment\.matched">/)
})

test('前端 API 包含树、结构管理、正文和搜索接口', () => {
  for (const path of [
    '/annotation-notices/tree', '/annotation-notices/search',
    '/annotation-notices/sections', '/content'
  ]) assert.ok(noticeApi.includes(path))
  assert.match(noticeApi, /reorderAnnotationNotices/)
  assert.match(noticeApi, /expected_structure_updated_at/)
})

test('富文本编辑器为列表恢复缩进，编号不会被左边界裁切', () => {
  assert.match(richTextComposer, /\.rich-editor__prose ul/)
  assert.match(richTextComposer, /\.rich-editor__prose ol/)
  assert.match(richTextComposer, /padding-left:\s*28px/)
})

test('Word 高亮不会被误识别为字体颜色，并提供清除格式提示', () => {
  assert.doesNotMatch(richTextMarks, /span\[style\*=["']color/)
  assert.match(richTextMarks, /element\.style\.color \? null : false/)
  assert.match(richTextComposer, /字体颜色或高亮异常时，请全选内容并清除格式后重新设置/)
  assert.match(noticePage, /粘贴内容可能包含不兼容的 Word 格式/)
  assert.match(noticePage, /点击“清除格式”后重新设置字体颜色或高亮/)
})
