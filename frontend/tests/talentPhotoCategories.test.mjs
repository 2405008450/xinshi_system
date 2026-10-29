import test from 'node:test'
import assert from 'node:assert/strict'
import {talentPhotoCategories,photoAttachmentLabel,validTalentPhoto,maxTalentPhotoBytes} from '../src/utils/talentPhotoCategories.js'
test('证件照和生活照独立分类，历史照片保留原分类',()=>{
  assert.deepEqual(talentPhotoCategories.map(item=>item.value),['id_photo','life_photo'])
  assert.equal(photoAttachmentLabel('photo'),'未分类照片（历史）')
  assert.equal(photoAttachmentLabel('id_photo'),'证件照')
  assert.equal(photoAttachmentLabel('life_photo'),'生活照')
  assert.ok(validTalentPhoto({name:'证件照.PNG',size:maxTalentPhotoBytes}))
  assert.ok(!validTalentPhoto({name:'生活照.jpg',size:maxTalentPhotoBytes+1}))
  assert.ok(!validTalentPhoto({name:'视频.mp4',size:1}))
})
