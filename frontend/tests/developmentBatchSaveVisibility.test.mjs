import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { useDevelopmentFilters } from '../src/composables/useDevelopmentFilters.js'

const pageSource = readFileSync(new URL('../src/views/resource/ResourceDevelopment.vue', import.meta.url), 'utf8')
const dialogSource = readFileSync(new URL('../src/views/resource/components/DevelopmentBatchEntryDialog.vue', import.meta.url), 'utf8')

test('新增保存后清除旧条件并定位成功记录日期及第一页，刷新失败明确提示已保存', async () => {
  const state = useDevelopmentFilters()
  Object.assign(state.filters, { keyword: '旧姓名', owner_id: 'other', range: ['2026-10-01', '2026-10-02'], state: '已添加' })
  state.setColumnFilter('platform_name', ['old-platform'])
  const activeDay = { value: '2026-10-02' }, dayPage = { value: 5 }, recordPage = { value: 8 }
  const requests = [], errors = []
  let failRefresh = false
  const context = vm.createContext({ ...state, activeDay, dayPage, recordPage,
    recordSaved: async () => {
      requests.push({ params: state.params(), day: activeDay.value, dayPage: dayPage.value, recordPage: recordPage.value })
      if (failRefresh) throw new Error('网络异常')
    },
    ElMessage: { error: message => errors.push(message) },
  })
  vm.runInContext(pageSource.match(/async function batchRecordsSaved\(records\) \{[\s\S]*?\n\}/)[0], context)
  const records = [{ id: 'new1', work_date: '2026-11-02' }, { id: 'new2', work_date: '2026-10-15' }]
  await context.batchRecordsSaved(records)
  assert.deepEqual([...state.filters.range], ['2026-10-15', '2026-11-02'])
  assert.deepEqual(state.columnFilters, {})
  assert.equal(state.filters.keyword, '')
  assert.equal(state.filters.owner_id, '')
  assert.equal(state.filters.state, '')
  assert.equal(requests[0].day, '2026-11-02')
  assert.equal(requests[0].dayPage, 1)
  assert.equal(requests[0].recordPage, 1)
  assert.equal(requests[0].params.column_filters, undefined)
  failRefresh = true
  await context.batchRecordsSaved(records)
  assert.match(errors[0], /记录已保存，列表刷新失败：网络异常/)
})

test('部分保存失败时只用成功行定位列表，失败行原内容和错误保留', async () => {
  const first = { id: 'success', work_date: '2026-11-02', _error: '' }
  const failed = { id: 'failed', work_date: '2026-10-01', _error: '' }
  const model = { rows: [first, failed] }, events = []
  const context = vm.createContext({
    saving: { value: false }, visible: { value: true }, model,
    batchFields: { value: [] }, selectedFields: { value: [] },
    entryNeedsEnrollment: () => false, entryPayload: row => ({ ...row }),
    nextTick: async () => {}, formRef: { value: { validate: async () => true } },
    api: {}, props: { options: {} },
    saveEntryRow: async (_api, row) => { if (row.id === 'failed') throw new Error('账号无效') },
    emit: (...args) => events.push(args),
    locateDialogFieldByLabel: async () => {}, ElMessage: { warning() {}, success() {} },
  })
  vm.runInContext(dialogSource.match(/async function save\(\) \{[\s\S]*?\n\}/)[0], context)
  await context.save()
  assert.deepEqual(JSON.parse(JSON.stringify(events)), [['saved', [{ id: 'success', work_date: '2026-11-02' }]]])
  assert.deepEqual(model.rows, [failed])
  assert.equal(failed._error, '账号无效')
  assert.equal(context.visible.value, true)
  assert.equal(context.saving.value, false)
})
