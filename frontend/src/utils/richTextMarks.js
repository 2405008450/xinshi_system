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
    return [{ tag: 'span[style*="color"]' }]
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
