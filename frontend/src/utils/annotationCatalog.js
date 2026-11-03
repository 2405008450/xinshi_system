// 标注项目与客户单价共用项目类型，保持下拉选项一致。
export const annotationProjectTypeOptions = [
  ['audio_collection', '音频采集'], ['audio_annotation', '音频标注'],
  ['audio_evaluation', '音频评测'], ['text_evaluation', '文本评测'],
  ['text_annotation', '文本标注'], ['quality_inspection', '质检'],
  ['listening_test', '测听'], ['slot_deduction', '扣槽'],
  ['generalization', '泛化'], ['translation', '翻译'], ['ai_evaluation', 'ai评测'],
].map(([value, label]) => ({ value, label }))
