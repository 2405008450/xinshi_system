import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')

test('标注项目进度筛选支持暂存多选并确认后统一查询', () => {
  assert.match(source, /v-model="statusFilterDraft"/)
  assert.match(source, /@click="selectAllStatuses"/)
  assert.match(source, /@click="clearStatusDraft"/)
  assert.match(source, /@click="cancelStatusFilter"/)
  assert.match(source, /@click="confirmStatusFilter"/)
  assert.match(source, /const confirmStatusFilter=.*if\(changed\)handleSearch\(\)/)
  assert.doesNotMatch(source, /v-model="searchForm\.projectStatus"[^>]*@change="handleSearch"/)
})
