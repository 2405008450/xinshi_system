export const talentPhotoCategories = [
  {value:'id_photo',label:'证件照'},
  {value:'life_photo',label:'生活照'},
]
export const photoAttachmentLabel = category => ({photo:'未分类照片（历史）',id_photo:'证件照',life_photo:'生活照',audio:'音频'}[category] || category)
export const maxTalentPhotoBytes = 10*1024*1024
export const validTalentPhoto = file => /\.(jpe?g|png|webp)$/i.test(file?.name||'') && file.size<=maxTalentPhotoBytes
