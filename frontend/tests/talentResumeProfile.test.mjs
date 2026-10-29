import test from 'node:test'
import assert from 'node:assert/strict'
import {resumeProfileForm,ensureResumeVersion,educationFormRows} from '../src/utils/talentResumeProfile.js'
import {foreignResumeLanguages,resumeLocaleOptions,resumeLanguageOptions,isResumeRtl} from '../src/utils/talentResumeLocales.js'
test('旧经历原文完整保留，分语言资料独立',()=>{
  const profile=resumeProfileForm(null,{annotationExperience:'旧经历原文\n第二行'})
  assert.equal(profile.annotation[0].description,'旧经历原文\n第二行')
  ensureResumeVersion(profile,'en').name='Alice'
  ensureResumeVersion(profile,'ar').name='ليلى'
  assert.equal(profile.versions.en.name,'Alice')
  const id=crypto.randomUUID()
  assert.equal(educationFormRows([{id,institution:'学校'}],{[id]:'2020–2024'})[0].period,'2020–2024')
})
test('三十余种外文选项完整，包含阿语及东南亚语言',()=>{
  assert.ok(foreignResumeLanguages.length>=30)
  for(const locale of ['en',...foreignResumeLanguages.map(item=>item.value)]){
    const options=resumeLocaleOptions(locale)
    assert.equal(options.gender.length,4);assert.equal(options.degree.length,10);assert.equal(options.employment.length,6)
    assert.ok(Object.values(options).flat().every(item=>item.value&&item.label))
    assert.notEqual(options.employment[0].label,'在校学生')
    assert.ok(resumeLanguageOptions(locale).length>=32)
  }
  assert.ok(isResumeRtl('ar'));assert.ok(!isResumeRtl('en'))
  for(const locale of ['ar','th','vi','id','ms','km','lo','my','fil'])assert.ok(foreignResumeLanguages.some(item=>item.value===locale))
})
