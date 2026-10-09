import test from 'node:test'
import assert from 'node:assert/strict'
import { getSchema } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { EditorState, TextSelection } from '@tiptap/pm/state'
import { createAuthenticatedImage, imagePasteSlice, isContentImagePath, pasteImageFile, imageFileKey } from '../src/utils/richTextImages.js'
import { noticeLinkOptions } from '../src/utils/richTextLinks.js'

const src = '/api/company-management/sections/11111111-1111-1111-1111-111111111111/images/22222222-2222-2222-2222-222222222222'

test('图文粘贴保留顺序、清除文字来源格式并识别网址', () => {
  const schema = getSchema([StarterKit.configure({ link: noticeLinkOptions }), createAuthenticatedImage(() => {})])
  const slice = imagePasteSlice(schema, [
    { text: '前文 https://example.com\n' }, { image: { alt: '截图' }, saved: { src } }, { text: '后文' }
  ])
  const nodes = slice.content.toJSON()
  assert.equal(nodes[0].content[1].marks[0].type, 'link')
  assert.equal(nodes.find(node => node.type === 'image').attrs.src, src)
  assert.equal(nodes.at(-1).content[0].text, '后文')
  assert.ok(!JSON.stringify(nodes).includes('blob:'))
})

test('图片在文字光标中间插入，前后文字不丢失', () => {
  const schema = getSchema([StarterKit, createAuthenticatedImage(() => {})])
  let state = EditorState.create({ schema, doc: schema.nodeFromJSON({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '前后' }] }] }) })
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, 2)))
  state = state.apply(state.tr.replaceSelection(imagePasteSlice(schema, [{ image: { alt: '截图' }, saved: { src } }])))
  assert.deepEqual(state.doc.toJSON().content.map(node => node.type), ['paragraph', 'image', 'paragraph'])
  assert.equal(state.doc.textContent, '前后')
})

test('失败图片不吞掉前后文字，外部地址不作为保存地址', () => {
  const schema = getSchema([StarterKit, createAuthenticatedImage(() => {})])
  const slice = imagePasteSlice(schema, [{ text: '前文' }, { image: { src: 'file:///test.png' } }, { text: '后文' }])
  assert.equal(slice.content.firstChild.textContent, '前文后文')
  for (const value of ['blob:test', 'data:image/png;base64,test', 'https://example.com/a.png', src + '?a=1']) assert.equal(isContentImagePath(value), false)
  assert.equal(isContentImagePath(src), true)
})

test('文件大小和格式校验，图片内容指纹用于重复来源去重', async () => {
  const file = new File(['same-content'], '截图.png', { type: 'image/png' })
  const second = await pasteImageFile({ file }, new AbortController().signal)
  assert.equal(await imageFileKey(file), await imageFileKey(second))
  await assert.rejects(pasteImageFile({ file: new File(['a'], 'a.svg', { type: 'image/svg+xml' }) }), /仅支持/)
  await assert.rejects(pasteImageFile({ file: new File([], 'a.png', { type: 'image/png' }) }), /不能为空/)
  await assert.rejects(pasteImageFile({ src: 'file:///test.png' }), /重新截图/)
})
