import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  getProjectExportConfig, buildProjectExportParams, buildClientReconciliationParams,
  buildProjectExportFilename, downloadProjectWorkbook,
} from '../src/utils/projectExport.js'
import { buildTranslationExportFilename, TRANSLATION_EXPORT_TYPES } from '../src/utils/translationProjectExport.js'

test('各模块菜单使用实际业务名称和时间口径', () => {
  for (const [module, fourth] of [['interpretation', 'translator_reconciliation'], ['annotation', 'personnel_reconciliation'], ['recruitment', 'candidate_tracking']]) {
    const config = getProjectExportConfig(module)
    assert.equal(config.defaultTimeField, 'customer_consultation_time')
    assert.deepEqual(config.modes.map((mode) => mode.type), ['projects', 'reconciliation', 'client_reconciliation', fourth])
    assert.ok(config.timeOptions.some((option) => option.value === 'created_at'))
  }
  assert.equal(getProjectExportConfig('translation').defaultTimeField, 'customer_reception_time')
  assert.ok(getProjectExportConfig('recruitment').modes[3].label.includes('候选人跟进明细'))
  assert.ok(getProjectExportConfig('annotation').timeOptions.some((option) => option.value === 'task_submitted_at'))
  assert.ok(getProjectExportConfig('interpretation').timeOptions.some((option) => option.value === 'scheduled_date'))
})

test('导出覆盖同一时间条件，保留其他筛选、母单范围和排序并去除分页', () => {
  const parentId = 'parent-1'
  const params = buildProjectExportParams({
    keyword: '项目', skip: 20, limit: 10, page: 3, page_size: 10,
    order_scope: 'child', parent_project_id: parentId, sort: 'latest_progress_desc',
    field_filters: JSON.stringify({
      created_at: { op: 'between', from: '2000-01-01', to: '2000-01-02' },
      project_status: { op: 'in', value: ['project_in_progress'] },
      'custom:id': { op: 'contains', value: '自定义条件' },
    }),
  }, { timeField: 'created_at', dateRange: ['2026-10-01', '2026-10-09'] })
  assert.equal(params.parent_project_id, parentId)
  assert.equal(params.order_scope, 'child')
  assert.equal(params.sort, 'latest_progress_desc')
  assert.equal(params.keyword, '项目')
  for (const key of ['skip', 'limit', 'page', 'page_size']) assert.equal(key in params, false)
  const filters = JSON.parse(params.field_filters)
  assert.deepEqual(filters.created_at, { op: 'between', from: '2026-10-01', to: '2026-10-09' })
  assert.equal(filters['custom:id'].value, '自定义条件')
  assert.deepEqual(filters.project_status.value, ['project_in_progress'])
})

test('按客户导出仅提交母客户 ID', () => {
  assert.deepEqual(buildClientReconciliationParams('母客户-id'), { client_id: '母客户-id' })
})

test('共享文件名保留笔译四类已有文件名规则', () => {
  const config = getProjectExportConfig('translation')
  for (const type of Object.values(TRANSLATION_EXPORT_TYPES)) {
    const mode = config.modes.find((item) => item.type === type)
    const form = { timeField: 'created_at', dateRange: ['2026-10-01', '2026-10-09'] }
    assert.equal(buildProjectExportFilename(config, mode, form, '客户/A'), buildTranslationExportFilename(form.timeField, form.dateRange, type, '客户/A'))
  }
})

test('各模块下载名称包含业务类型、时间口径或安全客户名称', () => {
  const config = getProjectExportConfig('recruitment')
  assert.equal(buildProjectExportFilename(config, config.modes[3], { timeField: 'target_onboard_date', dateRange: ['2026-10-01', '2026-10-09'] }), '招聘项目候选人跟进明细_目标入职日期_2026-10-01_至_2026-10-09.xlsx')
  assert.equal(buildProjectExportFilename(config, config.modes[2], {}, '客户/A:*?'), '招聘项目客户对账单_客户_客户_A___.xlsx')
})

test('公共组件具有远程客户搜索、旧响应保护、统一弹窗、校验和取消请求', () => {
  const component = readFileSync(new URL('../src/components/common/ProjectExportMenu.vue', import.meta.url), 'utf8')
  assert.match(component, /<DraggableFormDialog/)
  assert.match(component, /<AppForm/)
  assert.match(component, /filterable remote clearable :remote-method="loadClients"/)
  assert.match(component, /getClientOptions\(/)
  assert.match(component, /current !== clientSequence/)
  assert.match(component, /clientController\?\.abort\(\)/)
  assert.match(component, /exportController\?\.abort\(\)/)
  assert.match(component, /locked\.value = true[\s\S]*formRef\.value\.validate[\s\S]*exporting\.value = true/)
  assert.match(component, /applyServerErrors/)
  assert.match(component, /\.el-dialog__body \{ flex: 1; min-height: 0; overflow-y: auto/)
  assert.match(component, /popper-class="project-export-date-picker"/)
  assert.match(component, /\.project-export-date-picker \.el-date-range-picker__content \{ float: none; width: 100%/)
  assert.doesNotMatch(component, /<el-dialog\b/)
})

test('三个实际页面与标注子单页复用统一组件', () => {
  for (const [path, module] of [
    ['project/interpretation/InterpretationProjectDetails.vue', 'interpretation'],
    ['project/AnnotationProjects.vue', 'annotation'], ['project/RecruitmentProjects.vue', 'recruitment'],
  ]) {
    const page = readFileSync(new URL(`../src/views/${path}`, import.meta.url), 'utf8')
    assert.match(page, new RegExp(`<ProjectExportMenu[^>]*v-if="!deleteMode"[^>]*module="${module}"[^>]*:build-filters="buildFilters"`))
  }
  const childPage = readFileSync(new URL('../src/views/project/AnnotationChildOrders.vue', import.meta.url), 'utf8')
  assert.match(childPage, /<AnnotationProjects order-scope="child"/)
})

test('公共下载请求支持 Blob 错误解析与两分钟超时', () => {
  const api = readFileSync(new URL('../src/api/projectExports.js', import.meta.url), 'utf8')
  assert.match(api, /responseType: 'blob'/)
  assert.match(api, /timeout: 120000/)
  assert.match(api, /normalizeBlobApiError\(error\)/)
  assert.match(api, /candidate-tracking-export/)
  assert.match(api, /personnel-reconciliation-export/)
})

test('下载创建并清理链接和临时 URL', async () => {
  const originalDocument = globalThis.document
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL
  const calls = []
  const link = { click: () => calls.push('click'), remove: () => calls.push('remove') }
  try {
    globalThis.document = { createElement: () => link, body: { appendChild: () => calls.push('append') } }
    URL.createObjectURL = () => 'blob:test'
    URL.revokeObjectURL = (url) => calls.push(url)
    downloadProjectWorkbook(new Blob(['test']), '项目.xlsx')
    assert.equal(link.download, '项目.xlsx')
    assert.equal(link.href, 'blob:test')
    await new Promise((resolve) => setTimeout(resolve, 10))
    assert.deepEqual(calls, ['append', 'click', 'remove', 'blob:test'])
  } finally {
    globalThis.document = originalDocument
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  }
})
