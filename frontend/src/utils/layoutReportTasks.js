export const defaultLayoutTasks=['专检','排版','稽查']
export function layoutTaskExtra(text,choices=[]){
  const value=String(text||''),prefix=choices.join('、')
  return prefix&&value===prefix?'':prefix&&value.startsWith(`${prefix}；`)?value.slice(prefix.length+1):value
}
export function layoutTaskContent(choices=[],extra=''){
  return [choices.join('、'),extra].filter(Boolean).join('；')
}
