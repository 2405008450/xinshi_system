import api from '@/api'
import { uploadEditorScreenshot } from './uploadEditorScreenshot'
import { screenshotIds } from './screenshotReferences'
export const screenshotImageApi={
  async upload(_section,file){const image=await uploadEditorScreenshot(file,'business');return {...image,src:image.reference}},
  read(src,signal){const ids=screenshotIds(src);if(!ids.length)throw new Error('截图引用无效');return api.get(`/editor-screenshots/${ids[0]}`,{responseType:'blob',timeout:60000,screenshotIds:ids,signal})},
  async removeDraft(){ /* 业务图片长期保留，删除编辑框中的引用不会删除图片。 */ }
}
