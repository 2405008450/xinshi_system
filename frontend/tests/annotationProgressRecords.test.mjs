import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/components/annotation/AnnotationProgressSearchDialog.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/annotationOps.js', import.meta.url), 'utf8')

test('项目进度记录入口和分页接口已接入', () => {
  assert.match(page, />进度记录<\/el-button>/)
  assert.match(dialog, /title="项目进度记录"/)
  assert.match(api, /getRecentStatusHistory = \(params = \{\}, config = \{\}\)/)
  assert.match(dialog, /getRecentStatusHistory\(\{ skip, limit \}, config\)/)
})

test('提供10、20、50、100和全部五个显示档位', () => {
  for (const size of [10, 20, 50, 100]) {
    assert.match(dialog, new RegExp(`value: ${size}, label: '${size} 条/页'`))
  }
  assert.match(dialog, /value: 'all', label: '全部（逐步加载）'/)
  assert.match(dialog, /pageSizeMode !== 'all' && pagination\.total > pagination\.limit/)
  assert.match(dialog, /const handlePageChange = async \(\) =>/)
})

test('全部档位每批100条并在接近末尾时自动追加', () => {
  assert.match(dialog, /const ALL_BATCH_SIZE = 100/)
  assert.match(dialog, /append \? rows\.value\.length : 0/)
  assert.match(dialog, /new IntersectionObserver/)
  assert.match(dialog, /rootMargin: '200px 0px'/)
  assert.match(dialog, /existingIds\.has\(String\(item\.id\)\)/)
  assert.match(dialog, /allLoadError\.value = true/)
  assert.match(dialog, /const retryLoadAll = \(\) =>/)
})

test('清空、重置和上下文返回遵循状态恢复约定', () => {
  assert.match(dialog, /if \(!value\?\.trim\(\)\) return loadRecent\(true\)/)
  assert.match(dialog, /const resetSearch = \(\) =>[\s\S]*?loadRecent\(true\)/)
  assert.match(dialog, /pageSizeMode\.value = 10/)
  assert.match(dialog, /defineExpose\(\{ preserveNextOpen \}\)/)
  assert.match(page, /progressSearchDialogRef\.value\?\.preserveNextOpen\(\)/)
})
