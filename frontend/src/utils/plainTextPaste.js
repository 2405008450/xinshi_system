import { Fragment, Slice } from '@tiptap/pm/model'
import { linkifyTextNode } from './richTextLinks.js'

// 重新构造文本切片，避免继承来源及光标处的样式；网址按编辑器能力重新识别。
export function pasteWithoutFormatting(view, event, slice) {
  const text = event.clipboardData?.getData('text/plain')
    || slice.content.textBetween(0, slice.content.size, '\n', '\n')
  if (!text) return true

  const { schema } = view.state
  const paragraphs = text.replace(/\r\n?/g, '\n').split('\n').map(line =>
    schema.nodes.paragraph.create(null, line
      ? (schema.marks.link ? linkifyTextNode({ type: 'text', text: line }).map(node => schema.nodeFromJSON(node)) : schema.text(line))
      : null)
  )
  const content = Slice.maxOpen(Fragment.fromArray(paragraphs))
  view.dispatch(view.state.tr.replaceSelection(content).scrollIntoView())
  return true
}
