import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildScreenshotCacheKey, createScreenshotCache } from '../src/utils/screenshotCache.js'

test('screenshotCache 命中缓存零重复请求、合并并发并在超出上限时按 LRU 释放 URL', async () => {
  let seq = 0
  const revoked = []
  const cache = createScreenshotCache({
    maxEntries: 2,
    maxConcurrency: 2,
    createObjectURL: () => `blob:item-${++seq}`,
    revokeObjectURL: url => revoked.push(url),
  })

  let loaderCalls = 0
  const loader = async () => {
    loaderCalls += 1
    return { type: 'image/webp' }
  }

  const keyA = buildScreenshotCacheKey({ userId: 'u1', id: 'a', variant: 'thumb' })
  const keyB = buildScreenshotCacheKey({ userId: 'u1', id: 'b', variant: 'thumb' })
  const keyC = buildScreenshotCacheKey({ userId: 'u1', id: 'c', variant: 'thumb' })

  const [a1, a2] = await Promise.all([cache.fetch(keyA, loader), cache.fetch(keyA, loader)])
  assert.equal(loaderCalls, 1)
  assert.equal(a1.url, a2.url)

  const b = await cache.fetch(keyB, loader)
  assert.equal(cache.size(), 2)
  // 重新访问 A，使 B 成为最旧项
  assert.equal(cache.get(keyA).url, a1.url)
  await cache.fetch(keyC, loader)
  assert.equal(cache.size(), 2)
  assert.deepEqual(revoked, [b.url])

  cache.clear()
  assert.equal(cache.size(), 0)
  assert.equal(revoked.length, 3)
})

test('screenshotCache 限制最大并发拉取数量', async () => {
  let inFlight = 0
  let peak = 0
  const cache = createScreenshotCache({
    maxEntries: 10,
    maxConcurrency: 2,
    createObjectURL: () => `blob:${Math.random()}`,
    revokeObjectURL: () => {},
  })

  const tasks = ['1', '2', '3', '4', '5'].map(id => cache.fetch(id, async () => {
    inFlight += 1
    peak = Math.max(peak, inFlight)
    await new Promise(resolve => setTimeout(resolve, 15))
    inFlight -= 1
    return { type: 'image/webp' }
  }))
  await Promise.all(tasks)
  assert.equal(peak, 2)
})

test('ScreenshotText 启用视口懒加载、缩略图优先及点击预览升级原图', () => {
  const source = readFileSync(new URL('../src/components/common/ScreenshotText.vue', import.meta.url), 'utf8')
  assert.match(source, /IntersectionObserver/)
  assert.match(source, /variant === 'thumb'/)
  assert.match(source, /upgradePreviewOriginals/)
  assert.match(source, /screenshotCache\.fetch/)
})
