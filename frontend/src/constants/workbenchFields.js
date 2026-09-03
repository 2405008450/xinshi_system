// 工作台管理层与执行层共享字段名称及项目类型，避免上下表各自维护后产生口径漂移。
export const WORKBENCH_FIELD_LABELS = Object.freeze({
  orderNo: '订单号',
  projectType: '项目类型',
  projectTask: '项目 / 任务',
  client: '客户',
  projectNode: '项目节点',
  projectStatus: '项目状态',
  languageDirection: '语言方向',
  translatorReturn: '译员回稿',
  taskCompletion: '任务完成情况',
  currentAssignee: '当前负责人',
  managementOwnership: '管理归属',
  currentRole: '所属角色',
  assignmentMethod: '任务分配方式',
  operation: '操作'
})

export const WORKBENCH_PROJECT_TYPE_OPTIONS = Object.freeze([
  { label: '笔译项目', value: 'translation' },
  { label: '口译项目', value: 'interpretation' },
  { label: '标注项目', value: 'annotation' },
  { label: '招聘项目', value: 'recruitment' }
])

export const WORKBENCH_PROJECT_TYPE_VALUES = Object.freeze(
  WORKBENCH_PROJECT_TYPE_OPTIONS.map(option => option.value)
)

export const WORKBENCH_PROJECT_TYPE_LABELS = Object.freeze(
  Object.fromEntries(WORKBENCH_PROJECT_TYPE_OPTIONS.map(option => [option.value, option.label]))
)
