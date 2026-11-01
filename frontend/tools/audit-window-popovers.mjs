import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '@vue/compiler-sfc'
import { parse as parseTemplate } from '@vue/compiler-dom'

const defaultRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../src')
const attr = (node, name) => node.props.find(prop => prop.type === 6 && prop.name === name || prop.type === 7 && prop.name === 'bind' && prop.arg?.content === name)
const value = (node, name) => { const prop = attr(node,name); return prop?.value?.content || prop?.exp?.content || '' }
export function isWindowPopover(node) {
  const trigger = value(node,'trigger') || 'hover'
  const controlled = Boolean(attr(node,'visible')) || node.props.some(prop => prop.type === 7 && prop.name === 'model' && prop.arg?.content === 'visible')
  const width = value(node,'width'), number = Number(width.match(/\d+/)?.[0])
  // 点击/受控的大型详情、表单、筛选面板；不把小型菜单和普通悬停提示当作窗口。
  return (trigger === 'click' || controlled) && (number >= 300 || width && !number)
}
export function auditWindowPopovers(root = defaultRoot) {
  const result = { popovers:0, windowPopovers:0, dialogs:0, issues:[] }
  function walk(dir) {
    for(const entry of readdirSync(dir,{withFileTypes:true})) {
      const file = resolve(dir,entry.name)
      if(entry.isDirectory()) { walk(file); continue }
      if(!/\.(?:vue|js)$/.test(file)) continue
      const source = readFileSync(file,'utf8'), commonPopover=file.endsWith('common/WindowPopover.vue') || file.endsWith('common\\WindowPopover.vue')
      if(!commonPopover && /import\s*\{[^}]*\bElPopover\b[^}]*\}\s*from\s*['"]element-plus['"]/.test(source)) result.issues.push({file,reason:'业务代码绕过公共 WindowPopover'})
      if(!file.endsWith('.vue')) continue
      const template = parse(source).descriptor.template
      if(!template) continue
      let ast
      try { ast=parseTemplate(template.content) } catch { result.issues.push({file,reason:'模板解析失败，不能完成审计'}); continue }
      function scan(node) {
        if(node.type===1) {
          if(node.tag==='DraggableFormDialog')result.dialogs++
          if(node.tag==='el-dialog' && !file.endsWith('common/DraggableFormDialog.vue') && !file.endsWith('common\\DraggableFormDialog.vue')) result.issues.push({file,line:node.loc.start.line,reason:'业务弹窗未使用 DraggableFormDialog'})
          if(node.tag==='el-popover') {
            result.popovers++
            if(isWindowPopover(node)) {
              result.windowPopovers++
              if(!attr(node,'title') || !value(node,'title').trim()) result.issues.push({file,line:node.loc.start.line,reason:'窗口型浮层缺少公共标题栏，无法提供拖动和关闭按钮'})
            }
          }
        }
        for(const child of node.children||[])scan(child)
      }
      scan(ast)
    }
  }
  walk(root)
  return result
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const result=auditWindowPopovers()
  console.log(JSON.stringify(result,null,2))
  if(result.issues.length)process.exitCode=1
}
