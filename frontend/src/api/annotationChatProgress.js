import { updateAnnotationProjectStatus } from '@/api/annotationProjects'
import { createCustomerProgress,createAnnotatorProgress } from '@/api/annotationOps'

export function saveAnnotationChatProgress({projectId,track,projectStatus,changeNote,effectiveOn,chatDelivery}) {
  if(!projectId || !['project','customer','annotator'].includes(track))throw new Error('请选择有效的标注订单和进度类型')
  const note=String(changeNote||'').trim()
  if(!note || note.length>10000)throw new Error('具体进度不能为空，且最多10000字')
  const payload={changeNote:note,effectiveOn:effectiveOn.replace(' ','T')+'+08:00',...(chatDelivery?{chatDelivery}:{})}
  if(track==='annotator')return createAnnotatorProgress(projectId,payload)
  return track==='customer'?createCustomerProgress(projectId,payload):updateAnnotationProjectStatus(projectId,{...payload,projectStatus,progressOnly:true})
}
