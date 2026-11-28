import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { helpScreenshotCatalog, helpSectionImages } from '../src/utils/helpScreenshots.js'

test('help screenshots resolve to supported local image assets', () => {
  for (const image of Object.values(helpScreenshotCatalog)) {
    assert.ok(image.caption && image.alt)
    const file = new URL('../public' + image.src, import.meta.url)
    const bytes = readFileSync(file)
    assert.ok(bytes.length > 1000, image.src)
    const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8
    const png = bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))
    assert.ok(jpeg || png, image.src)
  }
})

test('chapter screenshots preserve existing images and deduplicate shared assets', () => {
  const existing = helpScreenshotCatalog.regions
  const images = helpSectionImages('会话', { id: 'chat-start', images: [existing] })
  assert.deepEqual(images, [existing])
  assert.equal(helpSectionImages('未知模块', { id: 'missing' }).length, 0)
  assert.ok(helpSectionImages('招聘', { id: 'project-entry' }).length)
  assert.ok(helpSectionImages('标注', { id: 'project-entry' }).length)
})
