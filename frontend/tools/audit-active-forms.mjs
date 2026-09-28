// 仅做静态盘点。输出的“待验证”不能作为运行测试通过的证明。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const activeRoots = {
  工作台: ['views/schedule/WorkDashboard.vue'],
  新咨询管理: ['views/client/Consultations.vue'],
  笔译项目: ['views/project/translation/ProjectDetails.vue', 'views/project/translation/SubOrderManagement.vue'],
  口译项目: ['views/project/interpretation/InterpretationProjectDetails.vue'],
  招聘项目: ['views/project/RecruitmentProjects.vue'],
  标注项目: ['views/project/AnnotationWorkspace.vue'],
  稿件安排: ['views/manuscript/ManuscriptArrangements.vue'],
  客户信息: ['views/client/Clients.vue'],
  资源需求管理: ['views/resource/ResourceRequests.vue', 'views/resource/components/ResourceRequestDailyNotesDialog.vue'],
  人才资源库: ['views/resource/TalentOverview.vue', 'views/resource/TalentPool.vue', 'views/resource/ResourceDevelopment.vue'],
  个人中心: ['views/profile/Profile.vue'],
  系统管理: ['views/system/Users.vue', 'views/system/Roles.vue', 'views/system/MailSettings.vue'],
}
const attr = (node, name) => {
  const value = node.props?.find(p => p.type === 6 && p.name === name)
  return value ? value.value?.content ?? true : undefined
}
const directive = (node, name, arg) => node.props?.find(p => p.type === 7 && p.name === name && (!arg || p.arg?.content === arg))?.exp?.content
const prop = (node, name) => attr(node, name) ?? directive(node, 'bind', name)
const files = new Map()
function visit(relative, module) {
  const file = path.resolve(root, 'src', relative)
  if (!file.startsWith(path.join(root, 'src') + path.sep) || !fs.existsSync(file)) return
  if (files.has(file)) { files.get(file).modules.add(module); return }
  const source = fs.readFileSync(file, 'utf8')
  const { descriptor } = parse(source)
  const result = { file: path.relative(root, file).replaceAll('\\', '/'), modules: new Set([module]), forms: [], actions: [] }
  files.set(file, result)
  const walk = (node, currentForm = null, dialog = null) => {
    if (['DraggableFormDialog', 'el-dialog'].includes(node.tag)) dialog = prop(node, 'title') || directive(node, 'model') || node.tag
    if (['AppForm', 'el-form'].includes(node.tag)) {
      currentForm = { line: (descriptor.template?.loc.start.line || 1) + node.loc.start.line - 1, ref: attr(node, 'ref') || '', model: prop(node, 'model') || '', rules: prop(node, 'rules') || '', dialog, fields: [], status: '待验证' }
      result.forms.push(currentForm)
    }
    if (node.tag === 'el-form-item' && currentForm) currentForm.fields.push({ label: prop(node, 'label') || '', prop: prop(node, 'prop') || '', required: prop(node, 'required') ?? null, rules: prop(node, 'rules') || '' })
    const handler = directive(node, 'on', 'click') || directive(node, 'on', 'submit')
    if (handler && /save|submit|confirm|assign|import|upload|send|claim|complete|handover|approve|reject|add|update/i.test(handler)) {
      result.actions.push({ line: (descriptor.template?.loc.start.line || 1) + node.loc.start.line - 1, handler, dialog, status: '待审查：区分打开入口与实际提交' })
    }
    for (const child of node.children || []) walk(child, currentForm, dialog)
  }
  if (descriptor.template) walk(baseParse(descriptor.template.content))
  const script = [descriptor.script?.content, descriptor.scriptSetup?.content].filter(Boolean).join('\n')
  for (const match of script.matchAll(/(?:from\s*|import\s*\()\s*['"]([^'"]+\.vue)['"]/g)) {
    const target = match[1].startsWith('@/') ? path.join(root, 'src', match[1].slice(2)) : path.resolve(path.dirname(file), match[1])
    visit(path.relative(path.join(root, 'src'), target), module)
  }
}
for (const [module, roots] of Object.entries(activeRoots)) for (const file of roots) visit(file, module)
const result = [...files.values()].filter(item => item.forms.length || item.actions.length).map(item => ({ ...item, modules: [...item.modules] }))
const output = process.argv[2]
if (output) fs.writeFileSync(path.resolve(output), JSON.stringify(result, null, 2) + '\n', 'utf8')
console.log(JSON.stringify({ files: result.length, forms: result.reduce((n, item) => n + item.forms.length, 0), candidateActions: result.reduce((n, item) => n + item.actions.length, 0), output: output || null }))
for (const item of result) console.log(`${item.modules.join('/')} | ${item.file} | 表单 ${item.forms.length} | 待审查入口 ${item.actions.length}`)
