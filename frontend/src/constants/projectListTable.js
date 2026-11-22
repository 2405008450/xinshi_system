// 五大业务板块（新咨询、笔译、口译、标注、招聘）共用的统一列宽基准。
// 以 24 寸 1080p（1920×1080 / 1920×924）100% 缩放为准：短字段定宽避免虚胖拉伸，名称/描述类列弹性吸收剩余宽度。
export const PROJECT_LIST_COLUMN_WIDTHS = Object.freeze({
  selection: 48,
  // 两位数序号在 44px 内仍可完整居中，为业务编号释放横向空间。
  index: 44,
  // 序号后带“展开 + 子项数量”徽标的列表使用该宽度，两位数序号与两位数徽标仍可同行显示。
  indexExpandable: 84,
  orderNo: 164,
  consultationCode: 148,
  projectName: 170,
  longText: 130,
  projectStatus: 104,
  clientShortName: 116,
  personName: 96,
  languageDirection: 110,
  workload: 104,
  booleanFlag: 108,
  shortCount: 96,
  dateShort: 112,
  dateTime: 146,
  deadlineTime: 158,
  actions: 96,
  singleAction: 76,
})
