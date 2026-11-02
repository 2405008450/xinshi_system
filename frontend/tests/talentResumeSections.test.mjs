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

test('旧版领域对象转换成可保存的文字，原技能评级保持不变',()=>{
  const written={domainSkills:[{domain:' 法律 ',level:'擅长'},{domain:'医学',level:''},'法律',null,{},' ']}
  const before=structuredClone(written)
  assert.deepEqual(professionalDomains({},written),['法律','医学'])
  assert.deepEqual(resumeProfileForm(null,{writtenProfile:written}).professionalDomains,['法律','医学'])
  assert.deepEqual(written,before)
  assert.deepEqual(professionalDomains({professionalDomains:[]},written),[])
  assert.deepEqual(professionalDomains({professionalDomains:['自述领域']},written),['自述领域'])
  assert.deepEqual(professionalDomains({}, {domainSkills:'旧数据'}),[])
})

test('旧草稿及多语言简历的领域对象在提交前统一规范化',()=>{
  const old={professionalDomains:[{domain:'法律',level:'擅长'}],versions:{en:{professionalDomains:[{domain:'Law',level:'expert'}],name:'Alice'}}}
  const normalized=resumeProfileForm(old)
  assert.deepEqual(normalized.professionalDomains,['法律'])
  assert.deepEqual(normalized.versions.en.professionalDomains,['Law'])
  assert.equal(normalized.versions.en.name,'Alice')
  assert.equal(old.versions.en.professionalDomains[0].level,'expert')
})
