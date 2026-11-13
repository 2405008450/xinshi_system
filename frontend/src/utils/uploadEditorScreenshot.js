import api from '@/api'
import { screenshotIds } from './screenshotReferences'

export async function uploadInvoiceFile(file, extension, requestId) {
  if (file.size > 10 * 1024 * 1024) throw new Error('发票文件最大支持 10 MB')
  const data = new FormData()
  data.append('file', file)
  if (requestId) data.append('request_id', requestId)
  const saved = await api.post(`/editor-screenshots/invoice-${extension}`, data, {
    headers: {'Content-Type': 'multipart/form-data'},
    timeout: 60000,
  })
  screenshotIds(saved.reference)
  return saved
}

export async function uploadEditorScreenshot(file,retention='business',options={}){
  const accountToken=localStorage.getItem('token')
  if (retention === 'chat') {
    if (!['image/png','image/jpeg','image/webp','image/gif'].includes(file.type) || !file.size || file.size > 20*1024*1024) throw new Error('聊天图片须为20MB以内的 PNG、JPEG、GIF 或 WebP 图片；10MB以内保留原图')
    options.signal?.throwIfAborted()
    const data = new FormData(); data.append('file', file); data.append('retention', retention)
    const saved = await api.post('/editor-screenshots', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000, signal: options.signal })
    if (localStorage.getItem('token') !== accountToken) throw new Error('登录账号已变化，请重新上传截图')
    screenshotIds(saved.reference)
    return saved
  }
  if(!['image/png','image/jpeg','image/webp','image/gif'].includes(file.type)||file.size>10*1024*1024)throw new Error('截图须为10MB以内的 PNG、JPEG、GIF 或 WebP 图片')
  const image=await createImageBitmap(file)
  try{
    if(image.width*image.height>40000000)throw new Error('截图尺寸过大，请裁剪后重试')
    const scale=Math.min(1,1920/Math.max(image.width,image.height)),canvas=document.createElement('canvas')
    canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height)
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.85))
    if(!blob||blob.size>2*1024*1024)throw new Error('截图压缩后仍超过2MB，请裁剪后再试')
    if(localStorage.getItem('token')!==accountToken)throw new Error('登录账号已变化，请重新上传截图')
    const data=new FormData();data.append('file',new File([blob],'截图.webp',{type:'image/webp'}));data.append('retention',retention)
    options.signal?.throwIfAborted()
    const saved=await api.post('/editor-screenshots',data,{headers:{'Content-Type':'multipart/form-data'},timeout:60000,signal:options.signal});screenshotIds(saved.reference);return saved
  }finally{image.close()}
}
