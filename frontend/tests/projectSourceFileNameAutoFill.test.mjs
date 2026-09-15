import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('原文路径支持自动读取并填充母订单文件名称', () => {
  const component = read('src/views/project/translation/components/ProjectFilesTab.vue')
  const projectDetails = read('src/views/project/translation/ProjectDetails.vue')
  const api = read('src/api/projectFiles.js')

  assert.match(api, /source-path\/inspect/)
  assert.match(component, /@blur="handleSourcePathBlur"/)
  assert.match(component, />\s*读取文件名\s*</)
  assert.match(component, /emit\('update:sourceFileName', response\.source_file_name \|\| ''\)/)
  assert.match(component, /fillSourceFileNameFromPath,/)
  assert.match(projectDetails, /await projectFilesTabRef\.value\?\.fillSourceFileNameFromPath/)
})
