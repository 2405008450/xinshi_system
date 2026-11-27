// 聊天格式与正文分开保存，不向正文插入标签或控制字符。
export const formatColors={red:'#dc2626',blue:'#2563eb',black:'#111827',lightBlue:'#dbeafe',yellow:'#fef08a'}
export function formatRuns(doc){
 const result=[]
 function visit(node){if(node?.type==='text'&&typeof node.text==='string')result.push({text:node.text,marks:node.marks||[]});else if(node?.type==='hardBreak')result.push({text:'\n',marks:[]});else (node?.content||[]).forEach(visit)}
 if(doc?.type==='doc')doc.content?.forEach((node,i)=>{if(i)result.push({text:'\n',marks:[]});visit(node)})
 return result
}
export const formatText=doc=>formatRuns(doc).map(run=>run.text).join('')
export const hasTextFormatting=doc=>formatRuns(doc).some(run=>run.marks.length>0)
export function documentFromRuns(runs){return {type:'doc',content:[{type:'paragraph',content:runs.filter(r=>r.text).map(r=>({type:'text',text:r.text,...(r.marks?.length?{marks:r.marks}:{} )}))}]}}
export function applyTextFormat(text,doc,start,end,type,color){
 const runs=formatText(doc)===text?formatRuns(doc):[{text,marks:[]}]
 const result=[];let offset=0
 const allSelected=runs.filter(r=>{const hit=offset<end&&offset+r.text.length>start;offset+=r.text.length;return hit}).every(r=>r.marks.some(m=>m.type===type&&(!color||m.attrs?.color===color)))
 offset=0
 for(const run of runs){const left=Math.max(start-offset,0),right=Math.min(end-offset,run.text.length);offset+=run.text.length
  if(right<=left){result.push(run);continue}
  if(left)result.push({...run,text:run.text.slice(0,left)})
  const marks=type==='clear'?[]:run.marks.filter(m=>m.type!==type)
  if(type!=='clear'&&!allSelected)marks.push({type,...(color?{attrs:{color}}:{})})
  result.push({text:run.text.slice(left,right),marks})
  if(right<run.text.length)result.push({...run,text:run.text.slice(right)})
 }
 return documentFromRuns(result)
}
export function rebaseTextFormat(doc,oldText,newText){
 if(!newText)return null
 if(!hasTextFormatting(doc))return null
 if(formatText(doc)!==oldText)return null
 let start=0;while(start<oldText.length&&start<newText.length&&oldText[start]===newText[start])start++
 let suffix=0;while(suffix<oldText.length-start&&suffix<newText.length-start&&oldText.at(-1-suffix)===newText.at(-1-suffix))suffix++
 const runs=formatRuns(doc),before=[],after=[];let offset=0,marks=[]
 for(const run of runs){const end=offset+run.text.length
  if(offset<start)before.push({...run,text:run.text.slice(0,Math.min(run.text.length,start-offset))})
  if(offset<start&&end>=start)marks=run.marks
  if(end>oldText.length-suffix)after.push({...run,text:run.text.slice(Math.max(0,oldText.length-suffix-offset))})
  offset=end
 }
 return documentFromRuns([...before,{text:newText.slice(start,newText.length-suffix),marks},...after])
}
export function runStyle(marks){const style={};for(const mark of marks||[]){const color=mark.attrs?.color
 if(mark.type==='bold')style.fontWeight='700'
 if(mark.type==='textColor'&&Object.values(formatColors).includes(color))style.color=color
 if(mark.type==='highlight'&&[formatColors.lightBlue,formatColors.yellow,'#fff59d'].includes(color))style.backgroundColor=color
 if(mark.type==='underline'){style.textDecorationLine='underline';style.textDecorationColor=[formatColors.red,formatColors.blue,formatColors.black].includes(color)?color:formatColors.black;style.textUnderlineOffset='3px'}
 }return style}

export const formatSearchOptions=[['text_red','红字'],['text_blue','蓝字'],['highlight_blue','浅蓝高亮'],['highlight_yellow','黄色高亮'],['bold','加粗'],['underline_black','黑色下划线'],['underline_red','红色下划线'],['underline_blue','蓝色下划线']].map(([value,label])=>({value,label}))
