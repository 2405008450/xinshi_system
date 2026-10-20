// docx 与 Tiptap 文档互转；仅由在线编辑器懒加载，不进入主包。
// 读取由 mammoth 转为语义化 HTML，页眉页脚、批注、修订和复杂样式会丢失。
import mammoth from 'mammoth'
import {
  AlignmentType, BorderStyle, Document, ExternalHyperlink, HeadingLevel, ImageRun, LevelFormat, Packer,
  Paragraph, Table, TableCell, TableRow, TextRun, WidthType,
} from 'docx'

export async function docxToHtml(arrayBuffer) {
  const input = typeof window === 'undefined' ? { buffer: Buffer.from(arrayBuffer) } : { arrayBuffer }
  const result = await mammoth.convertToHtml(input)
  return { html: result.value, warnings: result.messages.filter(item => item.type === 'warning').map(item => item.message) }
}

const HEADINGS = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4, HeadingLevel.HEADING_5, HeadingLevel.HEADING_6]
const MAX_IMAGE_WIDTH = 600
const ORDERED = 'material-ordered'

function base64Bytes(value) {
  if (typeof atob === 'function') return Uint8Array.from(atob(value), char => char.charCodeAt(0))
  return new Uint8Array(Buffer.from(value, 'base64'))
}

// 只读取图片头部尺寸，避免依赖浏览器解码；无法识别时使用固定比例。
export function imageSize(bytes) {
  if (bytes[0] === 0x89 && bytes[1] === 0x50) {
    const view = new DataView(bytes.buffer, bytes.byteOffset)
    return { width: view.getUint32(16), height: view.getUint32(20) }
  }
  if (bytes[0] === 0x47 && bytes[1] === 0x49) return { width: bytes[6] | bytes[7] << 8, height: bytes[8] | bytes[9] << 8 }
  if (bytes[0] === 0xFF && bytes[1] === 0xD8) {
    let offset = 2
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 0xFF) { offset += 1; continue }
      const marker = bytes[offset + 1]
      const length = bytes[offset + 2] << 8 | bytes[offset + 3]
      if (marker >= 0xC0 && marker <= 0xCF && ![0xC4, 0xC8, 0xCC].includes(marker)) {
        return { width: bytes[offset + 7] << 8 | bytes[offset + 8], height: bytes[offset + 5] << 8 | bytes[offset + 6] }
      }
      offset += 2 + length
    }
  }
  return { width: 400, height: 300 }
}

function imageRun(src) {
  const match = /^data:image\/(png|jpe?g|gif|bmp);base64,(.+)$/i.exec(src || '')
  if (!match) return null
  const data = base64Bytes(match[2])
  const type = match[1].toLowerCase() === 'jpeg' ? 'jpg' : match[1].toLowerCase()
  let { width, height } = imageSize(data)
  if (!width || !height) ({ width, height } = { width: 400, height: 300 })
  if (width > MAX_IMAGE_WIDTH) { height = Math.round(height * MAX_IMAGE_WIDTH / width); width = MAX_IMAGE_WIDTH }
  return new ImageRun({ type, data, transformation: { width, height } })
}

function safeLink(href) {
  return /^(https?:|mailto:)/i.test(href || '') ? href : null
}

function textRuns(nodes = [], extra = {}) {
  const runs = []
  for (const node of nodes) {
    if (node.type === 'hardBreak') { runs.push(new TextRun({ text: '', break: 1 })); continue }
    if (node.type === 'image') { const run = imageRun(node.attrs?.src); if (run) runs.push(run); continue }
    if (node.type !== 'text') continue
    const options = { text: node.text, ...extra }
    let link = null
    for (const mark of node.marks || []) {
      if (mark.type === 'bold') options.bold = true
      else if (mark.type === 'italic') options.italics = true
      else if (mark.type === 'underline') options.underline = {}
      else if (mark.type === 'strike') options.strike = true
      else if (mark.type === 'code') options.font = 'Consolas'
      else if (mark.type === 'highlight') options.highlight = 'yellow'
      else if (mark.type === 'textColor' && /^#[0-9a-f]{6}$/i.test(mark.attrs?.color || '')) options.color = mark.attrs.color.slice(1)
      else if (mark.type === 'link') link = safeLink(mark.attrs?.href)
    }
    if (link) runs.push(new ExternalHyperlink({ link, children: [new TextRun({ ...options, style: 'Hyperlink' })] }))
    else runs.push(new TextRun(options))
  }
  return runs
}

function convertBlocks(nodes = [], context) {
  const output = []
  for (const node of nodes) output.push(...convertBlock(node, context))
  return output
}

function convertBlock(node, context) {
  const { quote = false, list = null } = context
  const base = {
    ...(quote ? { indent: { left: 720 }, border: { left: { style: BorderStyle.SINGLE, size: 12, color: 'CBD5E1', space: 8 } } } : {}),
    ...(list ? (list.ordered ? { numbering: { reference: ORDERED, level: list.level, instance: list.instance } } : { bullet: { level: list.level } }) : {}),
  }
  switch (node.type) {
    case 'paragraph':
      return [new Paragraph({ ...base, children: textRuns(node.content) })]
    case 'heading':
      return [new Paragraph({ ...base, heading: HEADINGS[Math.min(Math.max(node.attrs?.level || 1, 1), 6) - 1], children: textRuns(node.content) })]
    case 'blockquote':
      return convertBlocks(node.content, { ...context, quote: true })
    case 'codeBlock': {
      const lines = (node.content || []).map(item => item.text || '').join('').split('\n')
      return lines.map(line => new Paragraph({ ...base, children: [new TextRun({ text: line, font: 'Consolas' })] }))
    }
    case 'horizontalRule':
      return [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'CBD5E1', space: 1 } }, children: [] })]
    case 'image': {
      const run = imageRun(node.attrs?.src)
      return run ? [new Paragraph({ ...base, alignment: AlignmentType.CENTER, children: [run] })] : []
    }
    case 'bulletList':
    case 'orderedList': {
      const ordered = node.type === 'orderedList'
      const level = list ? Math.min(list.level + 1, 8) : 0
      // 每个有序列表独立编号，避免后一个列表接着前一个列表计数。
      const instance = ordered ? ++context.state.instance : 0
      return (node.content || []).flatMap(item => (item.content || []).flatMap((child, index) => {
        const nested = ['bulletList', 'orderedList'].includes(child.type)
        // 列表项第二段起不再带编号，仅保持缩进。
        if (!nested && index > 0) return convertBlocks([child], { ...context, list: null })
        return convertBlocks([child], { ...context, list: nested ? { ...(list || {}), level, ordered, instance } : { level, ordered, instance } })
      }))
    }
    case 'table':
      return [convertTable(node, context)]
    default:
      return node.content ? convertBlocks(node.content, context) : []
  }
}

function convertTable(node, context) {
  const rows = (node.content || []).map(row => new TableRow({
    children: (row.content || []).map(cell => {
      const children = convertBlocks(cell.content, { ...context, quote: false, list: null })
      return new TableCell({
        children: children.length ? children : [new Paragraph('')],
        columnSpan: cell.attrs?.colspan > 1 ? cell.attrs.colspan : undefined,
        rowSpan: cell.attrs?.rowspan > 1 ? cell.attrs.rowspan : undefined,
        shading: cell.type === 'tableHeader' ? { fill: 'F1F5F9' } : undefined,
      })
    }),
  }))
  return new Table({ rows, width: { size: 100, type: WidthType.PERCENTAGE } })
}

export function tiptapJsonToDocument(json) {
  const children = convertBlocks(json?.content || [], { state: { instance: 0 } })
  return new Document({
    numbering: {
      config: [{
        reference: ORDERED,
        levels: Array.from({ length: 9 }, (_, level) => ({
          level, format: [LevelFormat.DECIMAL, LevelFormat.LOWER_LETTER, LevelFormat.LOWER_ROMAN][level % 3],
          text: `%${level + 1}.`, alignment: AlignmentType.START,
          style: { paragraph: { indent: { left: 720 * (level + 1), hanging: 360 } } },
        })),
      }],
    },
    sections: [{ children: children.length ? children : [new Paragraph('')] }],
  })
}

export async function tiptapJsonToDocx(json) {
  return new Uint8Array(await Packer.toArrayBuffer(tiptapJsonToDocument(json)))
}
