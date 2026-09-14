import { Mark, mergeAttributes } from '@tiptap/core'

export const TextColor = Mark.create({
  name: 'textColor',

  addAttributes() {
    return {
      color: {
        default: null,
        parseHTML: element => element.style.color || null,
        renderHTML: attributes => attributes.color
          ? { style: `color:${attributes.color};` }
          : {}
      }
    }
  },

  parseHTML() {
    return [{
      tag: 'span',
      // 不能使用 style*="color"，否则 Word 粘贴的 background-color
      // 也会被误识别成字体颜色，并生成 color: null 的无效标记。
      getAttrs: element => element.style.color ? null : false
    }]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes), 0]
  }
})

export const YellowHighlight = Mark.create({
  name: 'highlight',

  addAttributes() {
    return {
      color: {
        default: '#fff59d',
        parseHTML: () => '#fff59d',
        renderHTML: () => ({ style: 'background-color:#fff59d;' })
      }
    }
  },

  parseHTML() {
    return [
      { tag: 'mark' },
      { tag: 'span[style*="background-color"]' }
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['mark', mergeAttributes(HTMLAttributes), 0]
  }
})
