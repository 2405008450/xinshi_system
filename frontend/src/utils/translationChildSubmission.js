import {splitLanguagePairs} from './languagePair.js'
import {createEmptyWordCountMatrix,normalizeWordCountMatrix} from './wordCountMatrix.js'

// 与后端目录导入使用相同的逐层、路径排序和兄弟序号，预览不发起写入。
export function pendingFolderRows(form){
  const plan=form.pendingFolderImport
  if(!plan?.entries?.length)return []
  const entries=plan.entries.map(entry=>({...entry,relativePath:entry.relativePath.replace(/\\/g,'/')}))
  const root=entries.find(entry=>!entry.relativePath.includes('/'))?.relativePath
  if(!root)return []
  const rows=[],owners=new Map([[root,'']]),counts=new Map()
  const next=parent=>{const number=(counts.get(parent)||0)+1;counts.set(parent,number);return [parent,String(number).padStart(3,'0')].filter(Boolean).join('.')}
  const add=(suffix,name,path,folderInfo=null)=>rows.push({id:suffix,subOrderNo:(form.orderNo||'待生成母订单')+'.'+suffix,subProjectName:name,languagePair:(rows.find(row=>row.id===suffix.slice(0,suffix.lastIndexOf('.')))||form).languagePair,wordCountMatrix:createEmptyWordCountMatrix(),serviceContent:form.serviceContent,customerRequirementProfessional:form.customerRequirementProfessional,customerRequirementSpecial:form.customerRequirementSpecial,remarks:form.remarks,fileTypeSecondary:form.fileTypeSecondary,customerDeadlineTime:form.customerDeadlineTime,status:form.projectStatus,networkFilePath:path,folderInfo,...form.pendingSubOrderDetails?.[suffix]})
  const pathFor=parts=>plan.rootPath.replace(/[\\/]$/,'')+(parts.length?'\\'+parts.join('\\'):'')
  entries.sort((a,b)=>a.relativePath.split('/').length-b.relativePath.split('/').length||(a.relativePath<b.relativePath?-1:a.relativePath>b.relativePath?1:0))
  for(const entry of entries){
    if(!entries.some(child=>(child.relativePath===entry.relativePath||child.relativePath.startsWith(entry.relativePath+'/'))&&child.files?.length))continue
    let parent=owners.get(entry.relativePath)
    if(entry.relativePath!==root){
      parent=next(owners.get(entry.relativePath.slice(0,entry.relativePath.lastIndexOf('/'))));owners.set(entry.relativePath,parent)
      add(parent,entry.relativePath.split('/').pop(),pathFor(entry.relativePath.split('/').slice(1)),{rootPath:plan.rootPath,relativePath:entry.relativePath,sourceKind:plan.sourceKind,files:entry.files})
    }
    for(const name of entry.files||[])add(next(parent),name,pathFor([...entry.relativePath.split('/').slice(1),name]))
  }
  return rows
}

export function isDirectionOnlySplit(form){
  return !form.pendingFolderImport&&!String(form.initialSubOrderNamesText||'').trim()&&splitLanguagePairs(form.languagePair).length>1
}

export function pendingChildRows(form){
  const names=String(form.initialSubOrderNamesText||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean)
  const directions=splitLanguagePairs(form.languagePair)
  const rows=pendingFolderRows(form)
  const offset=rows.filter(row=>!row.id.includes('.')).length
  const base=form.orderNo||'待生成母订单'
  const pad=n=>String(n).padStart(3,'0')
  const add=(suffix,name,languagePair,copyFrom=null,sourceLabel='上级订单',sourcePath=undefined,previousSourcePath=undefined)=>{
    const detail=form.pendingSubOrderDetails?.[suffix]||{}
    const copied=copyFrom?normalizeWordCountMatrix(copyFrom):null
    const row={id:suffix,subOrderNo:base+'.'+suffix,subProjectName:name,languagePair,wordCountMatrix:createEmptyWordCountMatrix(),serviceContent:form.serviceContent,customerRequirementProfessional:form.customerRequirementProfessional,customerRequirementSpecial:form.customerRequirementSpecial,remarks:form.remarks,fileTypeSecondary:form.fileTypeSecondary,customerDeadlineTime:form.customerDeadlineTime,status:form.projectStatus,...form.pendingSubOrderDefaults,...(copied?{wordCountMatrix:normalizeWordCountMatrix(copied)}:{}),...detail,wordCountCopyBaseline:copied,wordCountCopySourceLabel:sourceLabel}
    if(sourcePath!==undefined&&(!Object.hasOwn(detail,'networkFilePath')||detail.networkFilePath===previousSourcePath))row.networkFilePath=sourcePath
    // 旧版预览曾把自动生成的空矩阵也写进明细；首次复制时补齐这类空白。
    // 新版已保存复制基准后，主动清空仍是独立修改，不能再次补回。
    if(sourceLabel==='母订单'&&copied&&!form.pendingDirectionWordCountMatrix&&detail.wordCountMatrix&&!Object.values(normalizeWordCountMatrix(detail.wordCountMatrix)).some(values=>Object.values(values).some(value=>value!==null)))row.wordCountMatrix=normalizeWordCountMatrix(copied)
    rows.push(row)
    return row
  }
  if(names.length){
    names.forEach((name,i)=>{
      const parent=add(pad(offset+i+1),name,form.languagePair)
      const childDirections=splitLanguagePairs(parent.languagePair)
      if(childDirections.length>1)childDirections.forEach((direction,j)=>add(pad(offset+i+1)+'.'+pad(j+1),name,direction,parent.wordCountMatrix,'上级订单','同上一级订单',parent.networkFilePath))
    })
  }else if(!form.pendingFolderImport&&directions.length>1){
    const source=form.wordCountMatrixSource==='suborder_aggregate'?form.pendingDirectionWordCountMatrix:form.wordCountMatrix
    directions.forEach((direction,i)=>add(pad(i+1),form.sourceFileName||form.projectName,direction,source,'母订单','同上一级订单',form.originalStoragePath||form.networkFilePath||''))
  }
  return rows
}

export function missingChildStatistics(rows){
  const parents=new Set(rows.map(row=>row.subOrderNo.slice(0,row.subOrderNo.lastIndexOf('.'))))
  return rows.filter(row=>!parents.has(row.subOrderNo)&&!['company','customer'].some(dim=>Object.values(row.wordCountMatrix?.[dim]||{}).some(value=>value!==null&&value!==undefined&&value!=='')))
}

// 子订单预填不是独立表单提交，仍须遵守接口的空值与进度类型。
// 也用于提交历史草稿，不能只在首次生成明细时清理。
export function normalizeInitialChildDetails(details={}){
  const nullable=new Set(['translatorId','customerDeadlineTime','sentToClientTime','translatorAssignmentTime'])
  const progress=new Set(['translatorDeliveryProgress','preReviewQcProgress','reviewProgress','review1Progress','review2Progress','postReviewQcProgress','layoutProgress','consolidationProgress'])
  return Object.fromEntries(Object.entries(details).map(([suffix,data])=>[suffix,Object.fromEntries(
    Object.entries(data).map(([key,value])=>[key,
      nullable.has(key)&&value===''?null:progress.has(key)&&value!=null?String(value):value
    ])
  )]))
}

export function initialChildDetails(rows,form){
  const fields=['serviceContent','customerRequirementProfessional','customerRequirementSpecial','remarks','fileTypeSecondary','customerDeadlineTime','status','wordCountMatrix','languagePair','priority','sentToClientTime','clientFeedback','translatorId','translatorAssignmentTime','translatorDeliveryProgress','preReviewQcProgress','reviewProgress','review1Progress','review2Progress','postReviewQcProgress','layoutProgress','consolidationProgress','networkFilePath','customerChargeItems']
  const inherited=new Set(['serviceContent','customerRequirementProfessional','customerRequirementSpecial','remarks','fileTypeSecondary','customerDeadlineTime','status','languagePair'])
  const byNumber=new Map(rows.map(row=>[row.subOrderNo,row]))
  return normalizeInitialChildDetails(Object.fromEntries(rows.map(row=>{
    const parent=byNumber.get(row.subOrderNo.slice(0,row.subOrderNo.lastIndexOf('.')))||{...form,status:form?.projectStatus}
    return [row.id,Object.fromEntries(fields.filter(key=>key in row&&(!inherited.has(key)||JSON.stringify(row[key]??null)!==JSON.stringify(parent[key]??null))).map(key=>[key,row[key]??null]))]
  })))
}

export function rollUpPendingRows(rows){
  const children=new Map()
  for(const row of rows){const parent=row.subOrderNo.slice(0,row.subOrderNo.lastIndexOf('.'));if(!children.has(parent))children.set(parent,[]);children.get(parent).push(row)}
  for(const row of [...rows].sort((a,b)=>b.subOrderNo.split('.').length-a.subOrderNo.split('.').length)){
    const direct=children.get(row.subOrderNo)
    if(!direct?.length)continue
    const matrix=createEmptyWordCountMatrix()
    for(const dim of Object.keys(matrix))for(const metric of Object.keys(matrix[dim])){
      const values=direct.map(child=>child.wordCountMatrix?.[dim]?.[metric]).filter(value=>value!==null&&value!==undefined&&value!=='')
      matrix[dim][metric]=values.length?values.reduce((sum,value)=>sum+Number(value),0):null
    }
    for(const values of Object.values(matrix))if(values.minutes!==null&&values.hours!==null){values.minutes=Math.round((values.minutes+values.hours*60)*10000)/10000;values.hours=null}
    row.wordCountMatrix=matrix
  }
}

// 加入虚拟母订单，只累计直接子级，避免把多层订单重复相加。
export function aggregatePendingStatistics(rows){
  if(!rows.length)return createEmptyWordCountMatrix()
  const first=rows[0]
  const rootNumber=first.subOrderNo.slice(0,-String(first.id).length-1)
  const root={subOrderNo:rootNumber,wordCountMatrix:createEmptyWordCountMatrix()}
  rollUpPendingRows([root,...rows.map(row=>({...row}))])
  return root.wordCountMatrix
}

// 只让仍继承当前上级的方向跟随；碰到独立方向的分支即停止。
export function inheritPendingLanguage(rows,parentNumber,previous,next){
  for(const row of rows){
    if(row.subOrderNo.slice(0,row.subOrderNo.lastIndexOf('.'))!==parentNumber||row.languagePair!==previous)continue
    row.languagePair=next
    inheritPendingLanguage(rows,row.subOrderNo,previous,next)
  }
}
