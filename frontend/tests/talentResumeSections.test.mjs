import test from 'node:test'
import assert from 'node:assert/strict'
import {resumeNames,resumeNamesWithAliases,emptyResumeSupplements,professionalDomains} from '../src/utils/talentResumeSections.js'
import {resumeProfileForm,ensureResumeVersion,educationFormRows} from '../src/utils/talentResumeProfile.js'

test('纯外文姓名不占中文姓名；没有中文名时不臆造',()=>{
  assert.deepEqual(resumeNames({fullName:'Alice Smith',englishName:'Alice Smith'}),{chineseName:'',englishName:'Alice Smith'})
  assert.equal(resumeNames({fullName:'张三'}).chineseName,'张三')
  assert.equal(resumeNames({fullName:'张三 Alice'}).chineseName,'')
  assert.deepEqual(resumeNames({fullName:'Alice',chineseName:'Alice'}),{chineseName:'',englishName:'Alice'})
  assert.deepEqual(resumeNamesWithAliases({chineseName:'Alice A',englishName:'Alice B',otherNames:['旧别名']}),{chineseName:'',englishName:'Alice B',otherNames:['旧别名','Alice A']})
})
test('新分区和外文版本保持独立；旧字段不被重建',()=>{
  const profile=resumeProfileForm({selfAssessment:'自述',campusPositions:[{id:'stable',description:'校园职务'}],versions:{en:{interests:'Music'}}})
  assert.equal(profile.campusPositions[0].id,'stable')
  const en=ensureResumeVersion(profile,'en');en.training.push({description:'New training'})
  assert.equal(profile.training.length,0);assert.equal(en.interests,'Music')
  assert.ok(Object.values(emptyResumeSupplements()).every(v=>v===''||Array.isArray(v)))
})
test('专业领域兼容已有字段，明确清空不重新回填；教育行ID及年份保留',()=>{
  assert.deepEqual(professionalDomains({}, {domainSkills:['法律']}),['法律'])
  assert.deepEqual(professionalDomains({professionalDomains:[]},{domainSkills:['法律']}),[])
  const original={id:'old-education',educationLevel:'other',institution:'旧学校',graduationYear:1994}
  assert.equal(educationFormRows([original])[0].graduationYear,1994)
  assert.equal(educationFormRows([original])[0].id,'old-education')
})
