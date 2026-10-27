import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_TRANSLATION_PROJECT_SORT,
  TRANSLATION_PROJECT_TIME_SORT_MODES,
  getTranslationSubOrderEarliestReturnTime,
  getTranslationProjectTimeSortTitle,
  hasTranslationSubOrderReturnTime,
  isTranslationProjectTimeSortActive,
  nextTranslationProjectTimeSortMode,
} from '../src/utils/translationProjectTimeSort.js'

test('时间及译员姓名均按升序、降序、不排序循环，切换字段互斥',()=>{
  assert.equal(DEFAULT_TRANSLATION_PROJECT_SORT,'order_no_desc')
  for(const key of ['customerDeadlineTime','translatorReturnTime','assignedTranslators']){
    const asc=nextTranslationProjectTimeSortMode(DEFAULT_TRANSLATION_PROJECT_SORT,key)
    assert.equal(asc,TRANSLATION_PROJECT_TIME_SORT_MODES[key])
    const desc=nextTranslationProjectTimeSortMode(asc,key)
    assert.equal(desc,asc.replace(/_asc$/,'_desc'))
    assert.equal(isTranslationProjectTimeSortActive(desc,key),true)
    assert.equal(nextTranslationProjectTimeSortMode(desc,key),DEFAULT_TRANSLATION_PROJECT_SORT)
  }
  assert.equal(nextTranslationProjectTimeSortMode('customer_deadline_time_desc','translatorReturnTime'),'translator_return_time_asc')
})
test('排序提示明确当前方向及下一步操作',()=>{
  assert.match(getTranslationProjectTimeSortTitle('order_no_desc','customerDeadlineTime','客户回稿时间'),/不排序.*升序/)
  assert.match(getTranslationProjectTimeSortTitle('translator_return_time_asc','translatorReturnTime','译员回稿时间'),/当前时间升序.*降序/)
  assert.match(getTranslationProjectTimeSortTitle('assigned_translator_name_desc','assignedTranslators','已分配译员'),/当前姓名首字母降序.*取消排序/)
})

test('子订单回稿时间过滤兼容新旧字段并忽略空值和无效值', () => {
  const subOrder = {
    assignedTranslators: [
      { translatorReturnTime: '2026-09-12 18:00' },
      { translator_return_time: '2026-09-11 09:00' },
      { translatorReturnTime: '' },
    ],
  }

  assert.equal(hasTranslationSubOrderReturnTime(subOrder), true)
  assert.equal(
    getTranslationSubOrderEarliestReturnTime(subOrder),
    Date.parse('2026-09-11T09:00:00+08:00'),
  )
  assert.equal(hasTranslationSubOrderReturnTime({ assignedTranslators: [] }), false)
  assert.equal(
    hasTranslationSubOrderReturnTime({
      assignedTranslators: [{ translatorReturnTime: '不是日期' }],
    }),
    false,
  )
})
