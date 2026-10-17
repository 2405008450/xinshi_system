import assert from 'node:assert/strict'
import test from 'node:test'
import { copyLanguageRegions, normalizeLanguageRegions } from '../src/utils/annotationLanguageRegions.js'

test('地区字段独立选填，去除首尾空白并丢弃全空行', () => {
  assert.deepEqual(normalizeLanguageRegions([
    { city: ' 广州 ', district: ' 越秀区 ', street: ' ' },
    { district: '禅城区' },
    { street: '祖庙街道' },
    { city: '', district: null },
  ]), [
    { city: '广州', district: '越秀区', street: null },
    { city: null, district: '禅城区', street: null },
    { city: null, district: null, street: '祖庙街道' },
  ])
})

test('编辑与下级复制不共享地区对象，空地区可显式清除', () => {
  const original = [{ city: '广州', district: '越秀区' }]
  const copied = copyLanguageRegions(original)
  copied[0].city = '佛山'
  assert.equal(original[0].city, '广州')
  assert.deepEqual(normalizeLanguageRegions([]), [])
  assert.deepEqual(copyLanguageRegions(), [])
})
