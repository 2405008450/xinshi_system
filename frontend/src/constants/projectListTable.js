// 四类项目管理列表共用的基础列宽，以招聘项目管理的紧凑布局为基准。
export const PROJECT_LIST_COLUMN_WIDTHS = Object.freeze({
  // 两位数序号在 44px 内仍可完整居中，为业务编号释放横向空间。
  index: 44,
  // 序号后带“展开 + 子项数量”徽标的列表使用该宽度，两位数序号与两位数徽标仍可同行显示。
  indexExpandable: 84,
  orderNo: 168,
  projectName: 160,
  longText: 120,
  projectStatus: 105,
  clientShortName: 88,
  languageDirection: 115,
  actions: 120,
})
