import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceRoot = join(frontendRoot, 'src')
const wrapperPath = join(sourceRoot, 'components', 'common', 'DraggableFormDialog.vue')

const collectVueFiles = (directory) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const path = join(directory, entry.name)
  if (entry.isDirectory()) return collectVueFiles(path)
  return entry.isFile() && entry.name.endsWith('.vue') ? [path] : []
})

test('所有业务 Dialog 统一使用可拖拽公共组件', () => {
  const rawDialogFiles = collectVueFiles(sourceRoot)
    .filter((path) => path !== wrapperPath)
    .filter((path) => /<el-dialog\b/i.test(readFileSync(path, 'utf8')))

  assert.deepEqual(rawDialogFiles, [], `以下文件仍直接使用 el-dialog：\n${rawDialogFiles.join('\n')}`)
})

test('公共弹窗统一启用拖拽、视口边界与打开复位', () => {
  const wrapper = readFileSync(wrapperPath, 'utf8')
  const mainEntry = readFileSync(join(sourceRoot, 'main.js'), 'utf8')

  assert.match(wrapper, /\bdraggable\b/)
  assert.match(wrapper, /:overflow="false"/)
  assert.match(wrapper, /resetPosition/)
  assert.match(wrapper, /@open="handleOpen"/)
  assert.match(mainEntry, /app\.component\(['"]DraggableFormDialog['"], DraggableFormDialog\)/)
})

test('项目进度标题栏中的订单号和项目名称仍可选中复制', () => {
  const projectPage = readFileSync(join(sourceRoot, 'views', 'project', 'AnnotationProjects.vue'), 'utf8')
  const protectedItems = projectPage.match(/progress-dialog-project__item[^>]*@mousedown\.stop/g) || []

  assert.equal(protectedItems.length, 2)
  assert.match(projectPage, /\.progress-dialog-project__item\{[^}]*cursor:text;user-select:text/)
})
