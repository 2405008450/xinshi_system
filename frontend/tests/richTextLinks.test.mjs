import test from 'node:test'
import assert from 'node:assert/strict'
import { getSchema } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { EditorState } from '@tiptap/pm/state'
import { Slice } from '@tiptap/pm/model'
import { handleWebLinkClick, isWebUrl, linkifyDocument, noticeLinkOptions } from '../src/utils/richTextLinks.js'
import { pasteWithoutFormatting } from '../src/utils/plainTextPaste.js'

test('批量纯文本粘贴立即识别多个网址，不要求末尾空格并清除原有样式', () => {
  const schema = getSchema([StarterKit.configure({ link: noticeLinkOptions })])
  const view = { state: EditorState.create({ schema }) }
  view.dispatch = tr => { view.state = view.state.apply(tr) }
  const text = '参考 https://example.com/a?q=1&b=2#part\nwww.example.org\n结束 https://example.net'
  pasteWithoutFormatting(view, { clipboardData: { getData: () => text } }, Slice.empty)
  const links = []
  view.state.doc.descendants(node => {
    if (node.isText) {
      assert.ok(node.marks.every(mark => mark.type.name === 'link'))
      for (const mark of node.marks) links.push(mark.attrs)
    }
  })
  assert.deepEqual(links.map(link => link.href), ['https://example.com/a?q=1&b=2#part', 'https://www.example.org', 'https://example.net'])
  assert.ok(links.every(link => link.target === '_blank' && link.rel.includes('noopener')))
  assert.equal(view.state.doc.textBetween(0, view.state.doc.content.size, '\n'), text)
})

test('旧正文网址可识别，保留已有文字样式且不重复增加链接标记', () => {
  const doc = { type: 'doc', content: [{ type: 'paragraph', content: [
    { type: 'text', text: 'https://example.com', marks: [{ type: 'bold' }] }
  ] }] }
  const converted = linkifyDocument(doc)
  assert.equal(converted.content[0].content[0].marks[1].attrs.href, 'https://example.com')
  assert.equal(converted.content[0].content[0].marks[0].type, 'bold')
  assert.deepEqual(linkifyDocument(converted), converted)
  assert.equal(doc.content[0].content[0].marks.length, 1)
})

test('只允许有效网页地址', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,test', 'file:///C:/test', '//example.com', 'https://', 'https://exam\nple.com']) {
    assert.equal(isWebUrl(url), false, url)
  }
  assert.equal(isWebUrl('https://example.com/path?q=1#part'), true)
})

test('编辑区点击链接打开新标签页，不将当前页面引用交给外站', () => {
  const calls = []
  const previous = globalThis.window
  globalThis.window = { open: (...args) => calls.push(args) }
  try {
    const anchor = { href: 'https://example.com/' }
    const view = { dom: { contains: value => value === anchor } }
    let prevented = false
    const event = { button: 0, target: { closest: () => anchor }, preventDefault: () => { prevented = true } }
    assert.equal(handleWebLinkClick(view, 0, event), true)
    assert.equal(prevented, true)
    assert.deepEqual(calls, [['https://example.com/', '_blank', 'noopener,noreferrer']])
    anchor.href = 'javascript:alert(1)'
    assert.equal(handleWebLinkClick(view, 0, event), false)
    assert.equal(calls.length, 1)
  } finally {
    if (previous === undefined) delete globalThis.window
    else globalThis.window = previous
  }
})
