import { formatWordCountMatrix } from './wordCountMatrix.js'
import { formatBusinessDateTime as formatDateTime } from './dateTime.js'
export const formatAssignedTranslators = (items, legacyName = '') => {
  if (Array.isArray(items) && items.length) {
    return items
      .map((item) => {
        const name = item.translatorName || item.translator_name || ''
        const scope = item.translationScope || item.translation_scope || ''
        return scope ? `${name}（${scope}）` : name
      })
      .filter(Boolean)
      .join('、')
  }
  return legacyName || '-'
}
export const formatTranslatorReturnTimes = (items) => {
  if (!Array.isArray(items) || !items.length) return '-'
  const values = items
    .map((item) => {
      const time = item.translatorReturnTime || item.translator_return_time
      if (!time) return ''
      const name = item.translatorName || item.translator_name || '译员'
      return `${name}：${formatDateTime(time)}`
    })
    .filter(Boolean)
  return values.length ? values.join('；') : '-'
}
export const formatTranslatorCompletionRemarks = (items) => {
  if (!Array.isArray(items) || !items.length) return '-'
  const values = items
    .map((item) => {
      const remarks = item.completionRemarks || item.completion_remarks
      if (!remarks) return ''
      const name = item.translatorName || item.translator_name || '译员'
      return `${name}：${remarks}`
    })
    .filter(Boolean)
  return values.length ? values.join('；') : '-'
}
export const translationProjectDetailItems = [
  { label: '订单号', key: 'orderNo' },
  { label: '项目名称', key: 'sourceFileName', span: 2, editable: true, required: true, maxlength: 255 },
  { label: '邮件主题预览', key: 'emailSubjectPreview', span: 2, editable: true, multiline: true },
  { label: '服务内容', key: 'serviceContent', span: 2, editable: true, maxlength: 255 },
  { label: '任务类型', key: 'taskType', editable: true, maxlength: 50 },
  { label: '来源咨询 ID', key: 'consultationId' },
  { label: '客户全称', key: 'clientName' },
  { label: '客户简称', key: 'clientShortName' },
  { label: '客户编号', key: 'clientCode' },
  { label: '子客户全称', key: 'subClientName' },
  { label: '子客户简称', key: 'subClientShortName' },
  { label: '子客户编号', key: 'subClientCode' },
  { label: '客户单号', key: 'customerOrderNo', editable: true, maxlength: 100 },
  { label: '项目经理', key: 'projectManagerName' },
  { label: '项目专员', key: 'projectSpecialistName' },
  { label: '项目助理', key: 'projectAssistantName' },
  { label: '排版专员', key: 'layoutSpecialistName' },
  { label: '客户经理', key: 'clientManager' },
  { label: '客户经理联系方式', key: 'managerContact' },
  { label: '项目状态', key: 'projectStatus', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary', editable: true, maxlength: 100 },
  { label: '翻译文本领域一级', key: 'projectFileTranslationDomainLevel1' },
  { label: '翻译文本领域二级', key: 'projectFileTranslationDomainLevel2' },
  { label: '文件类型一级', key: 'projectFileTypeLevel1' },
  { label: '文件类型二级', key: 'projectFileTypeLevel2' },
  { label: '文件格式', key: 'projectFileFormat' },
  { label: '文件属性一级', key: 'projectFileAttributeLevel1' },
  { label: '文件属性二级', key: 'projectFileAttributeLevel2' },
  { label: '文件属性三级', key: 'projectFileAttributeLevel3' },
  { label: '文件难度', key: 'projectFileDifficulty' },
  { label: '合同类型', key: 'projectContractType', editable: true, maxlength: 100 },
  { label: '合同状态', key: 'projectContractStatus', editable: true, maxlength: 100 },
  { label: '需提供报价单', key: 'quotationRequired', formatter: (value) => value ? '是' : '否' },
  { label: '报价单状态', key: 'quotationStatus', editable: true, maxlength: 100 },
  { label: '报价单路径', key: 'quotationPath', span: 2, editable: true, multiline: true },
  { label: '客户专业要求', key: 'customerRequirementProfessional', span: 2, editable: true, multiline: true },
  { label: '客户特殊要求', key: 'customerRequirementSpecial', span: 2, editable: true, multiline: true },
  { label: '备注', key: 'remarks', span: 2, editable: true, multiline: true },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '字数与预估', key: 'wordCountMatrix', span: 2, formatter: (value) => formatWordCountMatrix(value) },
  { label: '客户接单时间', key: 'customerReceptionTime' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: 'PM确认人 ID', key: 'pmConfirmedBy' },
  { label: '客户反馈', key: 'clientFeedback', span: 2, editable: true, multiline: true },
  { label: '大项目经理确认', key: 'majorProjectManagerConfirmation' },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
  { label: '译员回稿时间', key: 'translatorReturnTime', span: 2, formatter: (_value, row) => formatTranslatorReturnTimes(row.assignedTranslators), clickHint: '点击回稿时间编辑译员任务完成情况及价格' },
  { label: '译员任务完成情况', key: 'translatorCompletionRemarks', span: 2, formatter: (_value, row) => formatTranslatorCompletionRemarks(row.assignedTranslators) },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前 QC', key: 'preReviewQcProgress' },
  { label: '审校 1', key: 'review1Progress' },
  { label: '审校 2', key: 'review2Progress' },
  { label: '审校后 QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
