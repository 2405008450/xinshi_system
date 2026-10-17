import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, nextTick } from 'vue'
import { useTableColumns } from '../src/composables/useTableColumns.js'
import { annotationRegionRows, annotationRegionSummary, annotationRegionStorageKey, readAnnotationRegionLevel, saveAnnotationRegionLevel } from '../src/utils/annotationRegionDisplay.js'

const row = { languageItems: [
  { display:'粤语', regions:[{city:'广州',district:'越秀区',street:'北京街道'},{city:'佛山',district:'禅城区'}] },
  { display:'英语', regions:[{city:'广州',district:'天河区'}] },
] }

test('地区摘要按层级去重，完整信息保留语种与所有路径', () => {
  assert.deepEqual(annotationRegionSummary(row, 'city'), {text:'广州',extra:1,hasData:true,legacy:false})
  assert.deepEqual(annotationRegionSummary(row, 'district'), {text:'越秀区',extra:2,hasData:true,legacy:false})
  assert.equal(annotationRegionSummary(row, 'street').text, '北京街道')
  assert.equal(annotationRegionRows(row).length, 3)
  assert.equal(annotationRegionRows(row)[2].language, '英语')
})

test('只有区县也可查看，缺失层级不借用其他字段或猜测历史地区', () => {
  assert.equal(annotationRegionSummary({languageItems:[{regions:[{district:'越秀区'}]}]}, 'city').text, '未填写城市')
  assert.deepEqual(annotationRegionSummary({languageRegion:'北美片区',areaLabels:['北美片区','专项组']}, 'street'), {text:'北美片区',extra:1,hasData:true,legacy:true})
  assert.deepEqual(annotationRegionSummary({}), {text:'-',extra:0,hasData:false,legacy:false})
})

const memoryStorage = () => {
  const values = new Map()
  return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}
}

test('展示层级按页面和用户保存，损坏的设置回到城市', () => {
  const storage = memoryStorage()
  const a = annotationRegionStorageKey('annotation-details','甲')
  const b = annotationRegionStorageKey('annotation-details','乙')
  const child = annotationRegionStorageKey('annotation-child-orders','甲')
  saveAnnotationRegionLevel(storage,a,'district')
  assert.equal(readAnnotationRegionLevel(storage,a),'district')
  assert.equal(readAnnotationRegionLevel(storage,b),'city')
  assert.equal(readAnnotationRegionLevel(storage,child),'city')
  storage.setItem(a,'province')
  assert.equal(readAnnotationRegionLevel(storage,a),'city')
  assert.equal(storage.getItem(a),null)
})

test('旧语言地区及片区列合为地区列，保留用户其他列和全部取消的选择', async () => {
  const previous = globalThis.localStorage
  globalThis.localStorage = memoryStorage()
  localStorage.setItem('user_id','列配置测试')
  localStorage.setItem('table-columns:test-region-columns:列配置测试',JSON.stringify(['projectName','areaLabels','languageRegion']))
  const scope = effectScope()
  try {
    const columns = scope.run(()=>useTableColumns('test-region-columns',[{key:'projectName'},{key:'regionSummary'}],['regionSummary'],{keyAliases:{areaLabels:'regionSummary',languageRegion:'regionSummary'}}))
    assert.deepEqual(columns.selectedKeys.value,['projectName','regionSummary'])
    columns.selectedKeys.value=[]
    await nextTick()
    assert.equal(localStorage.getItem('table-columns:test-region-columns:列配置测试'),'[]')
    columns.reset()
    assert.deepEqual(columns.selectedKeys.value,['regionSummary'])
  } finally {
    scope.stop()
    globalThis.localStorage=previous
  }
})
