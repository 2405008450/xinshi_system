export const evaluationFields = {
  talent_grade: ['talentGrade'], overall: ['overallScore','overallRating'],
  cooperation: ['cooperationLevel','cooperationNote'], punctuality: ['punctualityLevel','punctualityNote'],
  audio_annotation: ['audioAnnotationScore','audioAnnotationEvaluation'],
  non_audio_annotation: ['nonAudioAnnotationScore','nonAudioAnnotationEvaluation'], collection: ['collectionScore','collectionEvaluation'],
  interpretation: ['interpretationRating','interpretationRatingNote','interpretationDomains'],
  written_translation: ['writtenTranslationScore','writtenTranslationEvaluation'],
  written_profile: ['writtenProfile.qualityScore'],
  interpretation_profile: ['interpretationProfile.interpretationLevel','interpretationProfile.qualityScore','interpretationProfile.evaluationSummary'],
  annotation_profile: ['annotationProfile.qualityScore','annotationProfile.remarks'],
}
export const evaluationFieldLabels = {
  talentGrade:'人才分级',overallScore:'总体评分',overallRating:'具体评价',cooperationLevel:'配合等级',cooperationNote:'配合说明',
  punctualityLevel:'守时等级',punctualityNote:'守时说明',audioAnnotationScore:'音频评分',audioAnnotationEvaluation:'音频评价',
  nonAudioAnnotationScore:'非音频评分',nonAudioAnnotationEvaluation:'非音频评价',collectionScore:'采集评分',collectionEvaluation:'采集评价',
  interpretationRating:'口译员评级',interpretationRatingNote:'口译说明',interpretationDomains:'口译领域',writtenTranslationScore:'笔译评分',writtenTranslationEvaluation:'笔译评价',
  'writtenProfile.qualityScore':'笔译质量评分','interpretationProfile.interpretationLevel':'口译等级','interpretationProfile.qualityScore':'口译质量评分',
  'interpretationProfile.evaluationSummary':'口译评价概述','annotationProfile.qualityScore':'标注质量评分','annotationProfile.remarks':'标注备注',
}
export const evaluationSnapshot = value => Object.fromEntries(Object.entries(evaluationFields).map(([key, paths]) => [key,
  Object.fromEntries(paths.map(path => { const field = path.split('.').reduce((item, part) => item?.[part], value); return [path, typeof field === 'string' ? field.trim() || null : field ?? null] })),
]))
export const evaluationGroupMeta = (value, key) => value?.evaluationMeta?.[key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())]
