import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { formatBusinessDateTime } from '../src/utils/dateTime.js'

test('编辑时间将 UTC 和带偏移时间转换成 UTC+8，正确处理跨日和午夜', () => {
  assert.equal(formatBusinessDateTime('2026-10-09T09:18:43Z'), '2026/10/09 17:18:43')
  assert.equal(formatBusinessDateTime('2026-10-09T02:18:43-07:00'), '2026/10/09 17:18:43')
  assert.equal(formatBusinessDateTime('2026-10-09T17:18:43+08:00'), '2026/10/09 17:18:43')
  assert.equal(formatBusinessDateTime('2026-10-09T16:00:00Z'), '2026/10/10 00:00:00')
})

test('历史无时区业务时间不随浏览器本地时区改变，也不会重复加八小时', () => {
  for (const timeZone of ['UTC', 'America/Los_Angeles', 'Asia/Shanghai']) {
    const previous = process.env.TZ
    try {
      process.env.TZ = timeZone
      assert.equal(formatBusinessDateTime('2026-10-09T17:18:43.787825'), '2026/10/09 17:18:43')
      assert.equal(formatBusinessDateTime('2026-10-09 17:18:43'), '2026/10/09 17:18:43')
      assert.equal(formatBusinessDateTime(new Date('2026-10-09T09:18:43Z')), '2026/10/09 17:18:43')
    } finally {
      if (previous === undefined) delete process.env.TZ
      else process.env.TZ = previous
    }
  }
})

test('编辑时间为空或无效时显示占位符', () => {
  for (const value of [null, undefined, '', 'invalid', new Date(NaN)]) {
    assert.equal(formatBusinessDateTime(value), '-')
  }
})

test('技术开发组件使用与实际文件名一致的日期工具路径', () => {
  const components = [
    '../src/components/common/TechnicalTaskReference.vue',
    '../src/views/technology/AllocationProgressEditor.vue',
    '../src/views/technology/DevelopmentFeedback.vue',
    '../src/views/technology/TaskAllocationViewer.vue',
    '../src/views/technology/TaskCompletionHistory.vue',
    '../src/views/technology/TechnicalDevelopment.vue'
  ]
  for (const component of components) {
    const source = readFileSync(fileURLToPath(new URL(component, import.meta.url)), 'utf8')
    assert.ok(source.includes("from '@/utils/dateTime'"), component)
    assert.ok(!source.includes("from '@/utils/datetime'"), component)
  }
})
