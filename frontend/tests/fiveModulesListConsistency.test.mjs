import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const pages = [
  { name: '新咨询管理', path: 'src/views/client/Consultations.vue' },
  { name: '笔译项目', path: 'src/views/project/translation/ProjectDetails.vue' },
  { name: '口译项目', path: 'src/views/project/interpretation/InterpretationProjectDetails.vue' },
  { name: '标注项目', path: 'src/views/project/AnnotationProjects.vue' },
  { name: '招聘项目', path: 'src/views/project/RecruitmentProjects.vue' },
]

const commonCss = read('src/styles/common.css')

test('五大业务板块默认分页条数统一为 10 条', () => {
  for (const { name, path } of pages) {
    const source = read(path)
    assert.match(source, /pagination\s*=\s*reactive\(\{\s*page:\s*1,\s*limit:\s*10,\s*total:\s*0,?\s*\}\)/s, `${name} 默认每页条数应为 10`)
  }
})

test('五大业务板块统一使用紧凑查询栏结构与状态多选折叠标签', () => {
  for (const { name, path } of pages) {
    const source = read(path)
    assert.match(source, /class="search-form project-list-search-form"/, `${name} 应接入统一查询栏类`)
    assert.match(source, /class="project-list-primary-filters"/, `${name} 应接入统一主筛选区`)
    assert.match(source, /class="project-list-search-actions"/, `${name} 应接入统一查询按钮区`)
    assert.match(source, /<ListFilterSelect[^>]*:max-collapse-tags="1"/, `${name} 状态多选应限制最多展开 1 个标签`)
  }
  assert.match(commonCss, /\.project-list-primary-filters \.project-list-keyword-filter\s*\{[^}]*max-width:\s*340px;/s)
  assert.match(commonCss, /\.project-list-primary-filters \.project-list-status-filter\s*\{[^}]*max-width:\s*210px;/s)
})

test('五大业务板块均支持跨页连续序号且不出现过度拉伸的短字段列', () => {
  for (const { name, path } of pages) {
    const source = read(path)
    assert.match(source, /\(pagination\.page - 1\) \* pagination\.limit/, `${name} 序号应使用跨页连续编号`)
  }
  const translation = read('src/views/project/translation/ProjectDetails.vue')
  assert.match(translation, /statementRequired:\s*\{\s*width:\s*PROJECT_LIST_COLUMN_WIDTHS\.booleanFlag\s*\}/)
  assert.match(translation, /projectStatus:\s*\{\s*label:\s*'项目状态',\s*width:\s*PROJECT_LIST_COLUMN_WIDTHS\.projectStatus/)
  assert.match(translation, /clientShortName:\s*\{\s*width:\s*PROJECT_LIST_COLUMN_WIDTHS\.clientShortName\s*\}/)
  assert.doesNotMatch(translation, /clientShortName:\s*\{\s*minWidth:\s*180\s*\}/)
})

test('五大业务板块切页与切页大小均退出删除模式并重置页码', () => {
  const translation = read('src/views/project/translation/ProjectDetails.vue')
  const interpretation = read('src/views/project/interpretation/InterpretationProjectDetails.vue')
  const recruitment = read('src/views/project/RecruitmentProjects.vue')
  assert.match(translation, /handlePageSizeChange\s*=\s*\(\)\s*=>\s*\{\s*exitDeleteMode\(\)\s*pagination\.page = 1/s)
  assert.match(interpretation, /handlePageSizeChange\s*=\s*\(\)\s*=>\s*\{\s*exitDeleteMode\(\);\s*pagination\.page = 1/)
  assert.match(recruitment, /handleSizeChange\s*=\s*\(\)\s*=>\s*\{\s*exitDeleteMode\(\);\s*pagination\.page=1/)
})

test('公共筛选组件中的空值筛选项统一使用“(空白)”', () => {
  const filterFiles = [
    'src/components/common/ConfiguredColumnHeaderFilter.vue',
    'src/components/common/GroupedColumnFilterContent.vue',
    'src/components/common/ListFilterControl.vue',
    'src/components/common/ListFilterSelect.vue',
    'src/views/client/Clients.vue',
  ]
  for (const file of filterFiles) {
    const source = read(file)
    assert.doesNotMatch(source, /为空白/, `${file} 不应保留“为空白”文案`)
  }
  assert.match(read('src/components/common/ConfiguredColumnHeaderFilter.vue'), />\(空白\)<\/el-checkbox>/)
  assert.match(read('src/components/common/GroupedColumnFilterContent.vue'), />\(空白\)<\/el-checkbox>/)
  assert.match(read('src/components/common/ListFilterControl.vue'), />\(空白\)<\/el-checkbox>/)
  assert.match(read('src/components/common/ListFilterSelect.vue'), /label="\(空白\)"/)
  assert.match(read('src/views/client/Clients.vue'), /\?\s*'\(空白\)'/)
})
