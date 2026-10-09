import test from 'node:test'
import assert from 'node:assert/strict'
import { pasteReferralImages, referralClipboardImages, referralImageError, queueReferralImages, removeReferralDraft, releaseReferralDrafts, REFERRAL_IMAGE_MAX_BYTES } from '../src/utils/referralImages.js'

const image = (name = '截图.png', type = 'image/png', size = 3) => new File([new Uint8Array(size)], name, { type })
const clipboard = (files, text = '') => ({ items: files.map(file => ({ kind: 'file', type: file.type, getAsFile: () => file })), files, getData: () => text })
function queueOptions() {
  const active = new Set(), revoked = []
  let index = 0
  return { active, revoked, createId: () => String(++index), urls: {
    createObjectURL: () => { const url = `blob:qa-${index}`; active.add(url); return url },
    revokeObjectURL: url => { active.delete(url); revoked.push(url) },
  } }
}

test('剪贴板优先使用 items，files 回退保留多图且不读取 HTML 外链', () => {
  const first = image(), second = image('第二张.webp', 'image/webp')
  assert.deepEqual(referralClipboardImages(clipboard([first, second])), [first, second])
  assert.deepEqual(referralClipboardImages({ items: [], files: [first, new File(['x'], '说明.txt', { type: 'text/plain' })] }), [first])
  assert.deepEqual(referralClipboardImages({ getData: () => '<img src="file:///截图.png">' }), [])
  assert.deepEqual(referralClipboardImages(null), [])
})

test('纯图片接管粘贴，说明框混合图文保留原生文本粘贴，图片区只接收图片', () => {
  const file = image(), received = []
  let prevented = 0
  const event = { clipboardData: clipboard([file]), preventDefault: () => prevented++ }
  assert.equal(pasteReferralImages(event, files => received.push(files), { preserveText: true }), true)
  assert.equal(prevented, 1)
  event.clipboardData = clipboard([file], '中文说明')
  pasteReferralImages(event, files => received.push(files), { preserveText: true })
  assert.equal(prevented, 1)
  pasteReferralImages(event, files => received.push(files))
  assert.equal(prevented, 2)
  assert.deepEqual(received, [[file], [file], [file]])
})

test('禁用状态不接收图片，普通文字粘贴不受影响', () => {
  let calls = 0, prevented = 0
  const event = { clipboardData: clipboard([image()]), preventDefault: () => prevented++ }
  pasteReferralImages(event, () => calls++, { disabled: true })
  assert.equal(calls, 0)
  assert.equal(prevented, 1)
  event.clipboardData = clipboard([], '微信号')
  assert.equal(pasteReferralImages(event, () => calls++), false)
  assert.equal(prevented, 1)
})

test('统一校验格式、空图及5MB边界，合法项继续入队', () => {
  assert.equal(referralImageError({ type: 'image/jpeg', size: REFERRAL_IMAGE_MAX_BYTES }), '')
  assert.match(referralImageError({ type: 'image/png', size: REFERRAL_IMAGE_MAX_BYTES + 1 }), /5MB/)
  assert.match(referralImageError(image('空图.png', 'image/png', 0)), /不能为空/)
  const options = queueOptions()
  const result = queueReferralImages([], [image('不支持.svg', 'image/svg+xml'), image(), image('空图.png', 'image/png', 0)], 'pull', options)
  assert.equal(result.errors.length, 2)
  assert.equal(result.items.length, 1)
  assert.equal(result.items[0].category, 'pull')
  assert.equal(options.active.size, 1)
})

test('三类凭证各自支持多图、分类稳定，不变更其他类别或原有失败项', () => {
  const options = queueOptions()
  let items = []
  for (const category of ['pull', 'moments', 'groups']) items = queueReferralImages(items, [image(), image()], category, options).items
  items[0].error = '上次失败'
  items = queueReferralImages(items, [image()], 'groups', options).items
  assert.deepEqual(items.map(item => item.category), ['pull', 'pull', 'moments', 'moments', 'groups', 'groups', 'groups'])
  assert.equal(items[0].error, '上次失败')
  assert.equal(new Set(items.map(item => item.id)).size, 7)
  assert.throws(() => queueReferralImages(items, [image()], 'unknown', options), /未知图片类别/)
})

test('收款码保留最后一张合法图，释放旧预览，无效替换保留旧码', () => {
  const options = queueOptions()
  let items = queueReferralImages([], [image()], 'pull', options).items
  items = queueReferralImages(items, [image('旧码.png')], 'qr', options).items
  const oldUrl = items[1].previewUrl
  items = queueReferralImages(items, [image('新码1.png'), image('新码2.png')], 'qr', options).items
  assert.deepEqual(items.map(item => item.file.name), ['截图.png', '新码2.png'])
  assert.deepEqual(options.revoked, [oldUrl])
  assert.equal(options.active.size, 2)
  const invalid = queueReferralImages(items, [image('无效.gif', 'image/gif')], 'qr', options)
  assert.equal(invalid.items, items)
  assert.equal(options.active.size, 2)
})

test('移除或上传成功释放指定预览，关闭与卸载释放剩余资源', () => {
  const options = queueOptions()
  let items = queueReferralImages([], [image(), image()], 'pull', options).items
  const second = items[1]
  items = removeReferralDraft(items, items[0].id, options.urls)
  assert.deepEqual(items, [second])
  assert.equal(options.active.size, 1)
  releaseReferralDrafts(items, options.urls)
  assert.equal(options.active.size, 0)
  assert.equal(options.revoked.length, 2)
})
