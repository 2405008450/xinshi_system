import test from 'node:test'
import assert from 'node:assert/strict'
import { decodeText, documentFileName, documentNameError, encodeText, onlineEditBlocker, onlineEditKind } from '../src/utils/materialDocument.js'
import { docxToHtml, imageSize, tiptapJsonToDocx } from '../src/utils/materialDocx.js'

test('只识别 docx、md、txt，超过大小限制时提示本地编辑', () => {
  assert.equal(onlineEditKind('规范.DOCX'), 'docx')
  assert.equal(onlineEditKind('说明.md'), 'markdown')
  assert.equal(onlineEditKind('a.txt'), 'text')
  assert.equal(onlineEditKind('旧版.doc'), null)
  assert.equal(onlineEditBlocker({ original_name: 'a.md', file_size: 100 }), '')
  assert.match(onlineEditBlocker({ original_name: 'a.txt', file_size: 6 * 1024 * 1024 }), /5MB/)
  assert.match(onlineEditBlocker({ original_name: 'a.pdf', file_size: 1 }), /仅支持/)
})

test('新建文档名自动补扩展名，校验路径字符和同目录重名', () => {
  assert.equal(documentFileName(' 交付说明 ', 'markdown'), '交付说明.md')
  assert.equal(documentFileName('交付说明.docx', 'docx'), '交付说明.docx')
  assert.equal(documentFileName('笔记.md', 'text'), '笔记.md.txt')
  assert.match(documentNameError('a/b', 'text'), /路径分隔符/)
  assert.match(documentNameError('  ', 'text'), /不能为空/)
  assert.match(documentNameError('说明', 'docx', ['说明.DOCX']), /同名/)
  assert.equal(documentNameError('说明', 'docx', ['说明.md']), '')
})

test('文本解码识别 UTF-8 BOM、GBK 回退和 CRLF，保存时还原换行符', () => {
  const crlf = decodeText(new Uint8Array([0xEF, 0xBB, 0xBF, ...new TextEncoder().encode('第一行\r\n第二行')]))
  assert.deepEqual(crlf, { text: '第一行\n第二行', encoding: 'utf-8', bom: true, eol: '\r\n' })
  assert.deepEqual([...encodeText('甲\n乙', { eol: '\r\n', bom: true }).slice(0, 3)], [0xEF, 0xBB, 0xBF])
  assert.equal(new TextDecoder().decode(encodeText('甲\n乙', { eol: '\r\n' })), '甲\r\n乙')
  // “中文”的 GBK 编码。
  const gbk = decodeText(new Uint8Array([0xD6, 0xD0, 0xCE, 0xC4]))
  assert.equal(gbk.text, '中文'); assert.equal(gbk.encoding, 'gb18030')
})

test('读取 PNG 图片尺寸', () => {
  const png = Uint8Array.from(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64'))
  assert.deepEqual(imageSize(png), { width: 1, height: 1 })
})

test('Tiptap 文档导出 docx 后可被重新解析，保留标题、列表、表格、链接和图片', async () => {
  const doc = { type: 'doc', content: [
    { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '项目详情' }] },
    { type: 'paragraph', content: [
      { type: 'text', text: '加粗', marks: [{ type: 'bold' }] }, { type: 'hardBreak' },
      { type: 'text', text: '官网', marks: [{ type: 'link', attrs: { href: 'https://example.com' } }] },
      { type: 'text', text: '脚本', marks: [{ type: 'link', attrs: { href: 'javascript:alert(1)' } }] },
    ] },
    { type: 'orderedList', content: [{ type: 'listItem', content: [
      { type: 'paragraph', content: [{ type: 'text', text: '第一步' }] },
      { type: 'bulletList', content: [{ type: 'listItem', content: [{ type: 'paragraph', content: [{ type: 'text', text: '子项' }] }] }] },
    ] }] },
    { type: 'table', content: [{ type: 'tableRow', content: [
      { type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: '语种' }] }] },
      { type: 'tableCell', content: [{ type: 'paragraph' }] },
    ] }] },
    { type: 'image', attrs: { src: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==' } },
  ] }
  const bytes = await tiptapJsonToDocx(doc)
  const { html } = await docxToHtml(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
  assert.match(html, /<h2>项目详情<\/h2>/)
  assert.match(html, /<strong>加粗<\/strong><br \/>/)
  assert.match(html, /<a href="https:\/\/example.com">官网<\/a>/)
  assert.doesNotMatch(html, /javascript:/)
  assert.match(html, /<ol><li>第一步<ul><li>子项<\/li><\/ul><\/li><\/ol>/)
  assert.match(html, /<table><tr><td><p>语种<\/p><\/td><td><\/td><\/tr><\/table>/)
  assert.match(html, /<img src="data:image\/png;base64,/)
})

test('空文档也能生成有效 docx', async () => {
  const bytes = await tiptapJsonToDocx({ type: 'doc', content: [] })
  const { html } = await docxToHtml(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
  assert.equal(html, '')
})
