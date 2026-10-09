import Image from '@tiptap/extension-image'
import { Fragment, Slice } from '@tiptap/pm/model'
import { linkifyTextNode } from './richTextLinks.js'

export const MAX_PASTE_IMAGE_BYTES = 20 * 1024 * 1024
export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp']
export const isContentImagePath = src => typeof src === 'string'
  && /^\/api\/company-management\/sections\/[0-9a-f-]{36}\/images\/[0-9a-f-]{36}$/.test(src)

// 鉴权加载只改变显示 DOM，正文 JSON 始终保留稳定的站内地址。
export function createAuthenticatedImage(readImage) {
  return Image.extend({
    draggable: false,
    addInputRules: () => [],
    parseHTML() {
      return [{ tag: 'img[src]', getAttrs: element => isContentImagePath(element.getAttribute('src')) ? null : false }]
    },
    addNodeView() {
      return ({ node }) => {
        const dom = document.createElement('figure')
        dom.className = 'rich-text-image'
        dom.contentEditable = 'false'
        const image = document.createElement('img')
        const status = document.createElement('button')
        status.type = 'button'
        status.className = 'rich-text-image__status'
        dom.append(image, status)
        let controller
        let objectUrl
        let sequence = 0
        let disposed = false
        let currentNode = node
        const release = () => {
          controller?.abort()
          if (objectUrl) URL.revokeObjectURL(objectUrl)
          objectUrl = null
        }
        const load = async () => {
          release()
          const current = ++sequence
          controller = new AbortController()
          image.removeAttribute('src')
          image.alt = currentNode.attrs.alt || '正文图片'
          image.title = currentNode.attrs.title || ''
          status.hidden = false
          status.disabled = true
          status.textContent = '图片加载中…'
          try {
            if (!isContentImagePath(currentNode.attrs.src)) throw new Error('图片地址无效')
            const blob = await readImage(currentNode.attrs.src, controller.signal)
            if (disposed || current !== sequence) return
            objectUrl = URL.createObjectURL(blob)
            image.src = objectUrl
            status.hidden = true
          } catch {
            if (disposed || current !== sequence) return
            status.disabled = false
            status.textContent = '图片加载失败，点击重试'
          }
        }
        image.onerror = () => {
          status.hidden = false
          status.disabled = false
          status.textContent = '图片加载失败，点击重试'
        }
        status.onclick = load
        load()
        return {
          dom,
          stopEvent: event => event.target === status,
          ignoreMutation: () => true,
          update(nextNode) {
            if (nextNode.type !== currentNode.type) return false
            const changed = nextNode.attrs.src !== currentNode.attrs.src
            currentNode = nextNode
            image.alt = nextNode.attrs.alt || '正文图片'
            image.title = nextNode.attrs.title || ''
            if (changed) load()
            return true
          },
          destroy() { disposed = true; sequence++; release() }
        }
      }
    }
  }).configure({ allowBase64: false, resize: false })
}

export function clipboardImageTokens(clipboard) {
  const files = [...(clipboard?.items || [])]
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile()).filter(Boolean)
  if (!files.length) files.push(...[...(clipboard?.files || [])].filter(file => file.type.startsWith('image/')))
  const html = clipboard?.getData('text/html') || ''
  const plain = clipboard?.getData('text/plain') || ''
  const tokens = []
  if (html) {
    const parsed = new DOMParser().parseFromString(html, 'text/html')
    const blocks = new Set(['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'TR', 'BLOCKQUOTE', 'PRE'])
    const newline = () => {
      if (tokens.length && tokens.at(-1)?.text?.endsWith('\n')) return
      tokens.push({ text: '\n' })
    }
    const visit = element => {
      if (element.nodeType === 3) { tokens.push({ text: element.textContent.replace(/\s+/g, ' ') }); return }
      if (element.nodeType !== 1 || ['SCRIPT', 'STYLE', 'HEAD', 'IFRAME', 'OBJECT', 'SVG', 'NOSCRIPT'].includes(element.tagName)) return
      if (element.tagName === 'IMG') {
        tokens.push({ image: { src: element.getAttribute('src') || '', alt: (element.getAttribute('alt') || '粘贴图片').slice(0, 255) } })
        return
      }
      if (element.tagName === 'BR') { tokens.push({ text: '\n' }); return }
      if (blocks.has(element.tagName) && tokens.length) newline()
      element.childNodes.forEach(visit)
      if (blocks.has(element.tagName)) newline()
    }
    parsed.body.childNodes.forEach(visit)
  }
  const images = tokens.filter(token => token.image)
  if (!images.length && !files.length) return null
  if (!images.length) {
    tokens.splice(0, tokens.length, ...(plain ? [{ text: plain }] : []), ...files.map(file => ({ image: { file, alt: file.name || '粘贴图片' } })))
  } else {
    let fileIndex = 0
    for (const token of images) {
      // 来源图片与文件数量一致时按剪贴板顺序配对；文件/data URL 不再重复追加。
      if (files.length === images.length || !/^(data:image\/|https?:\/\/|\/api\/company-management\/)/i.test(token.image.src)) {
        if (files[fileIndex]) token.image.file = files[fileIndex++]
      }
    }
    // 保留HTML之外的文件项；上传时按内容指纹排除双表示，避免漏掉多图剪贴板。
    for (const file of files.slice(fileIndex)) tokens.push({ image: { file, alt: file.name || '粘贴图片', supplemental: true } })
  }
  while (tokens[0]?.text === '\n') tokens.shift()
  while (tokens.at(-1)?.text === '\n') tokens.pop()
  return tokens
}

export async function pasteImageFile(image, signal, readImage) {
  let blob = image.file
  if (!blob) {
    const src = image.src
    const address = typeof location !== 'undefined' ? new URL(src || '', location.href) : null
    const ownPath = address && address.origin === globalThis.location?.origin && !address.search && !address.hash
      && isContentImagePath(address.pathname) ? address.pathname : null
    if (isContentImagePath(src) || ownPath) blob = await readImage(ownPath || src, signal)
    else {
      const ownBlob = address?.protocol === 'blob:' && address.origin === globalThis.location?.origin
      if (!ownBlob && !/^(data:image\/(png|jpeg|webp);base64,|https?:\/\/)/i.test(src || '')) {
        throw new Error('无法读取来源图片，请重新截图粘贴')
      }
      if (src.length > MAX_PASTE_IMAGE_BYTES * 1.4) throw new Error('单张正文图片不能超过20MB')
      const response = await fetch(src, { signal, credentials: 'omit', mode: 'cors', redirect: 'error' })
      if (!response.ok) throw new Error('无法读取来源图片，请重新截图粘贴')
      if (Number(response.headers.get('content-length')) > MAX_PASTE_IMAGE_BYTES) throw new Error('单张正文图片不能超过20MB')
      const reader = response.body?.getReader()
      if (reader) {
        const chunks = []
        let size = 0
        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            size += value.byteLength
            if (size > MAX_PASTE_IMAGE_BYTES) throw new Error('单张正文图片不能超过20MB')
            chunks.push(value)
          }
        } finally { await reader.cancel() }
        blob = new Blob(chunks, { type: (response.headers.get('content-type') || '').split(';')[0].trim() })
      } else blob = await response.blob()
    }
  }
  if (!IMAGE_TYPES.includes(blob.type)) throw new Error('仅支持 PNG、JPEG、WebP 图片')
  if (!blob.size || blob.size > MAX_PASTE_IMAGE_BYTES) throw new Error('图片不能为空，且单张不能超过20MB')
  const extension = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' }[blob.type]
  return new File([blob], `粘贴图片.${extension}`, { type: blob.type })
}

export async function imageFileKey(file) {
  const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return [...new Uint8Array(hash)].map(value => value.toString(16).padStart(2, '0')).join('')
}

// 将图文重新构造成无来源格式的切片，并让插入发生在同一个撤销步骤中。
export function imagePasteSlice(schema, tokens) {
  const nodes = []
  let text = ''
  const flush = () => {
    if (!text) return
    for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
      nodes.push(schema.nodes.paragraph.create(null, line
        ? (schema.marks.link ? linkifyTextNode({ type: 'text', text: line }).map(node => schema.nodeFromJSON(node)) : schema.text(line))
        : null))
    }
    text = ''
  }
  for (const token of tokens) {
    if (token.text !== undefined) text += token.text
    else if (token.saved) {
      flush()
      nodes.push(schema.nodes.image.create({ src: token.saved.src, alt: token.image.alt, title: null }))
    }
  }
  flush()
  return Slice.maxOpen(Fragment.fromArray(nodes))
}
