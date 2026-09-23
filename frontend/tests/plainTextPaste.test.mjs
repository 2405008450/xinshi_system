import test from 'node:test'
import assert from 'node:assert/strict'
import { Schema, Slice } from '@tiptap/pm/model'
import { EditorState, TextSelection } from '@tiptap/pm/state'
import { history, undo, redo } from '@tiptap/pm/history'
import { pasteWithoutFormatting } from '../src/utils/plainTextPaste.js'

const schema = new Schema({
  nodes: {
    doc: { content: 'block+' },
    paragraph: { content: 'inline*', group: 'block' },
    heading: { content: 'inline*', group: 'block' },
    text: { group: 'inline' },
    hardBreak: { inline: true, group: 'inline' }
  },
  marks: {
    bold: {},
    textColor: { attrs: { color: {} } },
    highlight: {}
  }
})
const color = schema.marks.textColor.create({ color: 'rgb(255, 0, 0)' })
const paragraph = text => schema.nodes.paragraph.create(null, text ? schema.text(text) : null)
const clipboard = text => ({ clipboardData: { getData: type => type === 'text/plain' ? text : '' } })
function makeView(doc = schema.nodes.doc.create(null, paragraph())) {
  const view = { state: EditorState.create({ schema, doc, plugins: [history()] }) }
  view.dispatch = tr => { view.state = view.state.apply(tr) }
  return view
}

test('批量粘贴保留中文、空行和特殊字符，清除来源格式且支持撤销重做', () => {
  const view = makeView()
  const rich = schema.nodes.heading.create(null, schema.text('来源格式', [color, schema.marks.bold.create()]))
  const original = view.state.doc.toJSON()
  assert.equal(pasteWithoutFormatting(view, clipboard('中文 <测试>\r\n\r\n第二段\r末段'), Slice.maxOpen(rich.content)), true)
  const pasted = view.state.doc.toJSON()
  assert.deepEqual(pasted.content, ['中文 <测试>', '', '第二段', '末段'].map(text => paragraph(text).toJSON()))
  assert.equal(undo(view.state, view.dispatch), true)
  assert.deepEqual(view.state.doc.toJSON(), original)
  assert.equal(redo(view.state, view.dispatch), true)
  assert.deepEqual(view.state.doc.toJSON(), pasted)
})

test('替换选中文字时不继承周围颜色，已有内容保留样式，粘贴后可重新设置颜色', () => {
  const view = makeView(schema.nodes.doc.create(null,
    schema.nodes.paragraph.create(null, schema.text('前替换后', [color]))))
  view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, 2, 4)))
  pasteWithoutFormatting(view, clipboard('新文字'), Slice.empty)
  const content = view.state.doc.firstChild.content.content
  assert.equal(content[0].marks[0].attrs.color, 'rgb(255, 0, 0)')
  assert.equal(content[1].text, '新文字')
  assert.deepEqual(content[1].marks, [])
  assert.equal(content[2].marks[0].attrs.color, 'rgb(255, 0, 0)')
  view.dispatch(view.state.tr.addMark(2, 5, schema.marks.textColor.create({ color: '#2563eb' })))
  assert.equal(view.state.doc.firstChild.child(1).marks[0].attrs.color, '#2563eb')
})

test('没有纯文本剪贴板时从解析结果提取文字与换行，丢弃标题和高亮', () => {
  const view = makeView()
  const rich = schema.nodes.doc.create(null, [
    schema.nodes.heading.create(null, [schema.text('标题', [color]), schema.nodes.hardBreak.create(), schema.text('换行')]),
    schema.nodes.paragraph.create(null, schema.text('正文', [schema.marks.highlight.create()]))
  ])
  pasteWithoutFormatting(view, clipboard(''), Slice.maxOpen(rich.content))
  assert.deepEqual(view.state.doc.toJSON().content, ['标题', '换行', '正文'].map(text => paragraph(text).toJSON()))
})
