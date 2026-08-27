<template>
  <div class="project-spreadsheet" :class="{ 'project-spreadsheet--focus': focusMode }">
    <div class="project-spreadsheet__toolbar">
      <div class="project-spreadsheet__status">
        <div class="project-spreadsheet__status-info">
          <el-tag type="success" effect="plain">Univer OSS</el-tag>
          <span>直接编辑已有行，或从首个空白行录入新账号；自定义列仅属于当前项目。</span>
          <el-tag effect="plain">已加载 {{ rows.length }} / {{ totalRows }} 条</el-tag>
          <el-tag v-if="dirtyCount" type="warning">{{ dirtyCount }} 行待保存</el-tag>
        </div>
        <div v-if="!deleteMode" class="project-spreadsheet__save-actions">
          <el-button v-if="dirtyCount" size="small" :disabled="saving" @click="discardChanges">放弃修改</el-button>
          <el-button class="save-button" size="small" type="primary" :loading="saving" :disabled="!dirtyCount" @click="submitChanges">保存修改（{{ dirtyCount }}）<span class="shortcut">Ctrl+S</span></el-button>
        </div>
      </div>
      <div v-if="deleteMode || selectedImageCell || selectedRow" class="project-spreadsheet__actions">
        <div class="project-spreadsheet__context-actions">
          <span v-if="deleteMode" class="delete-mode-tip">请在表格中选择需要删除的已有账号行，可拖动选择多行</span>
          <template v-if="!deleteMode && selectedImageCell">
            <span class="selected-label" :title="`图片字段：${selectedImageCell.column.label}（第 ${selectedImageCell.rowIndex+1} 行）`">图片字段：{{ selectedImageCell.column.label }}（第 {{ selectedImageCell.rowIndex+1 }} 行）</span>
            <el-upload :show-file-list="false" :http-request="handleImageUpload" accept="image/jpeg,image/png,image/gif,image/webp">
              <el-button :loading="imageUploading">{{ selectedImageId ? '替换图片' : '插入图片' }}</el-button>
            </el-upload>
            <el-button v-if="selectedImageId" type="danger" link @click="removeSelectedImage">删除图片</el-button>
          </template>
          <template v-else-if="!deleteMode && selectedRow">
            <span class="selected-label" :title="selectedRow.personName || selectedRow.loginAccount || selectedRow.platformName || '-'">已选：{{ selectedRow.personName || selectedRow.loginAccount || selectedRow.platformName || '-' }}</span>
            <el-button @click="$emit('detail', selectedRow)">查看详情</el-button>
            <el-button :disabled="Boolean(dirtyCount)" title="请先保存或放弃表格修改" @click="$emit('edit', selectedRow)">编辑资产信息</el-button>
          </template>
        </div>
      </div>
    </div>
    <el-alert
      v-if="totalRows > maxRows"
      :title="`当前筛选共有 ${totalRows} 条，仅加载前 ${maxRows} 条；请缩小筛选范围后再批量编辑。`"
      type="warning"
      :closable="false"
      show-icon
    />
    <div v-if="saveErrorEntries.length" class="save-error-summary">
      <el-alert :title="`${saveErrorEntries.length} 行保存失败；首个错误：第 ${Number(saveErrorEntries[0][0])+1} 行，${saveErrorEntries[0][1]}`" type="error" :closable="false" show-icon />
      <el-button size="small" type="danger" plain @click="focusFirstSaveError">定位首个错误</el-button>
    </div>
    <el-alert v-if="validationMessage" :title="validationMessage" type="error" :closable="false" show-icon />
    <div ref="container" class="project-spreadsheet__canvas" v-loading="loading" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets'
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import { UniverSheetsDataValidationPreset } from '@univerjs/preset-sheets-data-validation'
import UniverPresetSheetsDataValidationZhCN from '@univerjs/preset-sheets-data-validation/locales/zh-CN'
import { UniverSheetsDrawingPreset } from '@univerjs/preset-sheets-drawing'
import UniverPresetSheetsDrawingZhCN from '@univerjs/preset-sheets-drawing/locales/zh-CN'
import { deletePendingCustomFieldImage, getCustomFieldImageBlob, uploadCustomFieldImage } from '@/api/annotationOps'
import '@univerjs/preset-sheets-core/lib/index.css'
import '@univerjs/preset-sheets-data-validation/lib/index.css'
import '@univerjs/preset-sheets-drawing/lib/index.css'

const props=defineProps({
  rows:{type:Array,default:()=>[]},
  fields:{type:Array,default:()=>[]},
  talents:{type:Array,default:()=>[]},
  platforms:{type:Array,default:()=>[]},
  users:{type:Array,default:()=>[]},
  languageItems:{type:Array,default:()=>[]},
  projectId:{type:String,default:''},
  currentUserId:{type:String,default:''},
  projectName:{type:String,default:'项目账号表'},
  loading:{type:Boolean,default:false},
  saving:{type:Boolean,default:false},
  totalRows:{type:Number,default:0},
  maxRows:{type:Number,default:500},
  saveErrors:{type:Object,default:()=>({})},
  focusMode:{type:Boolean,default:false},
  deleteMode:{type:Boolean,default:false},
})
const emit=defineEmits(['save','detail','edit','dirty-change','selection-change'])
const container=ref(null),dirtyRows=ref(new Set()),selectedRow=ref(null),selectedCell=ref(null),validationMessage=ref('')
const imageDrafts=ref(new Map()),imageUploading=ref(false)
let univer=null,univerAPI=null,worksheet=null,disposables=[],lastSelections=[],imageRenderDepth=0,disposed=false,rebuildSequence=0,rebuildQueue=Promise.resolve()
const imageObjectUrls=new Map(),imageBlobPromises=new Map(),pendingImageIds=new Set()

const talentLabel=item=>`${item.resourceCode||''} ${item.fullName||item.personName||''}`.trim()
const talentByLabel=computed(()=>new Map(props.talents.map(item=>[talentLabel(item),item])))
const platformLabel=item=>{
  const name=item.platformName||item.platformUrl||'未命名平台'
  if(!item.platformName||!item.platformUrl)return name
  try{return `${name}（${new URL(item.platformUrl).hostname}）`}catch{return `${name}（${item.platformUrl}）`}
}
const userLabel=item=>{
  const name=item.fullName||item.full_name||item.username||'-'
  return item.username&&item.username!==name?`${name}（${item.username}）`:name
}
const languageLabel=item=>item.display||item.languageName||'-'
const platformByLabel=computed(()=>new Map(props.platforms.map(item=>[platformLabel(item),item])))
const userByLabel=computed(()=>new Map(props.users.map(item=>[userLabel(item),item])))
const languageByLabel=computed(()=>new Map(props.languageItems.map(item=>[languageLabel(item),item])))
const accountStatusLabels={available:'可用',assigned:'已分配',suspended:'暂停',banned:'封禁',retired:'已退役'}
const accountStatusByLabel=new Map(Object.entries(accountStatusLabels).map(([value,label])=>[label,value]))
const dirtyCount=computed(()=>dirtyRows.value.size)
const saveErrorEntries=computed(()=>Object.entries(props.saveErrors).sort(([left],[right])=>Number(left)-Number(right)))
const selectedImageCell=computed(()=>selectedCell.value?.column?.dataType==='image'&&selectedCell.value.rowIndex>=0?selectedCell.value:null)
const imageCellKey=(rowIndex,fieldId)=>`${rowIndex}:${fieldId}`
const imageValueAt=(rowIndex,fieldId)=>{
  const key=imageCellKey(rowIndex,fieldId)
  if(imageDrafts.value.has(key))return imageDrafts.value.get(key)
  return props.rows[rowIndex]?.assignmentCustomValues?.[fieldId]||null
}
const selectedImageId=computed(()=>selectedImageCell.value?imageValueAt(selectedImageCell.value.rowIndex,selectedImageCell.value.column.fieldId):null)

const sheetColumns=computed(()=>{
  const custom=props.fields.map(item=>({
    key:`custom:${item.id}`,label:item.fieldLabel,dataType:item.dataType,fieldId:item.id,editable:true,isRequired:Boolean(item.isRequired),options:item.options||[],width:item.dataType==='image'?128:undefined,
  }))
  return [
    {key:'platform',label:'平台',editable:true,dataType:'platform',width:180},
    {key:'nickname',label:'账号昵称',editable:true,dataType:'text',width:150},
    {key:'login',label:'登录账号',editable:true,dataType:'text',width:190},
    {key:'password',label:'密码',editable:true,dataType:'text',width:150},
    {key:'person',label:'分配人员',editable:true,dataType:'person',width:180},
    {key:'gender',label:'性别',editable:false,width:80},
    {key:'age',label:'年龄',editable:false,width:80},
    {key:'language',label:'语言方向',editable:true,dataType:'language',width:160},
    {key:'accountStatus',label:'账号状态',editable:true,dataType:'account_status',width:100},
    {key:'owner',label:'负责人',editable:true,dataType:'user',width:140},
    {key:'expiresOn',label:'到期日',editable:true,dataType:'date',width:120},
    ...custom,
  ]
})

const formatCustomValue=(value,type)=>{
  if(value===null||value===undefined)return ''
  if(type==='image')return ''
  if(Array.isArray(value))return value.join('、')
  if(type==='boolean')return value?'是':'否'
  return value
}
const ageFromBirthDate=value=>{
  const match=String(value||'').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if(!match)return ''
  const birth=new Date(Number(match[1]),Number(match[2])-1,Number(match[3]))
  if(Number.isNaN(birth.getTime()))return ''
  const today=new Date()
  let age=today.getFullYear()-birth.getFullYear()
  if(today.getMonth()<birth.getMonth()||(today.getMonth()===birth.getMonth()&&today.getDate()<birth.getDate()))age--
  return age>=0?age:''
}
const talentForRow=row=>props.talents.find(item=>String(item.id)===String(row?.personId||''))
const rowValue=(row,column)=>{
  if(column.fieldId)return formatCustomValue(row.assignmentCustomValues?.[column.fieldId],column.dataType)
  if(column.key==='platform')return props.platforms.find(item=>String(item.id)===String(row.platformId)) ? platformLabel(props.platforms.find(item=>String(item.id)===String(row.platformId))) : row.platformName||''
  if(column.key==='nickname')return row.nickname||''
  if(column.key==='login')return row.loginAccount||''
  if(column.key==='password')return row.password||''
  if(column.key==='person'){
    const talent=talentForRow(row)
    return talent?talentLabel(talent):(row.personName||'')
  }
  if(column.key==='gender')return talentForRow(row)?.gender||row.personGender||''
  if(column.key==='age')return ageFromBirthDate(talentForRow(row)?.birthDate||row.personBirthDate)
  if(column.key==='language')return row.languageItemIds?.map(id=>props.languageItems.find(item=>String(item.id)===String(id))).filter(Boolean).map(languageLabel).join('、')||row.languageLabels?.join('、')||''
  if(column.key==='accountStatus')return accountStatusLabels[row.accountStatus]||row.accountStatus||''
  if(column.key==='owner')return props.users.find(item=>String(item.id)===String(row.ownerId)) ? userLabel(props.users.find(item=>String(item.id)===String(row.ownerId))) : row.ownerName||''
  if(column.key==='expiresOn')return row.expiresOn||''
  return ''
}
const sourceMatrix=()=>[
  sheetColumns.value.map(column=>column.label),
  ...props.rows.map(row=>sheetColumns.value.map(column=>rowValue(row,column))),
]

const revokeImageUrl=key=>{
  const url=imageObjectUrls.get(key)
  if(url)URL.revokeObjectURL(url)
  imageObjectUrls.delete(key)
}
const revokeAllImageUrls=()=>{
  imageObjectUrls.forEach(url=>URL.revokeObjectURL(url))
  imageObjectUrls.clear();imageBlobPromises.clear()
}
const fetchImageBlob=id=>{
  if(!imageBlobPromises.has(id))imageBlobPromises.set(id,getCustomFieldImageBlob(id).catch(error=>{imageBlobPromises.delete(id);throw error}))
  return imageBlobPromises.get(id)
}
const clearRenderedImage=(rowIndex,columnIndex)=>{
  if(!worksheet)return
  imageRenderDepth++
  try{worksheet.getRange(rowIndex+1,columnIndex,1,1).clear({contentsOnly:true}).setValues([['']])}finally{imageRenderDepth--}
  revokeImageUrl(imageCellKey(rowIndex,sheetColumns.value[columnIndex]?.fieldId))
}
const renderImageCell=async(rowIndex,columnIndex,imageId)=>{
  const activeWorksheet=worksheet
  if(!activeWorksheet||!imageId)return
  const column=sheetColumns.value[columnIndex]
  if(column?.dataType!=='image')return
  const key=imageCellKey(rowIndex,column.fieldId)
  try{
    const blob=await fetchImageBlob(imageId)
    if(worksheet!==activeWorksheet||imageValueAt(rowIndex,column.fieldId)!==imageId)return
    const file=new File([blob],`image-${imageId}`,{type:blob.type||'image/png'})
    imageRenderDepth++
    activeWorksheet.getRange(rowIndex+1,columnIndex,1,1).clear({contentsOnly:true}).setValues([['']])
    await activeWorksheet.getRange(rowIndex+1,columnIndex,1,1).insertCellImageAsync(file)
    activeWorksheet.setRowHeight(rowIndex+1,76)
    revokeImageUrl(key)
    imageObjectUrls.set(key,URL.createObjectURL(blob))
  }catch(error){
    console.error('加载项目账号图片失败',error)
    if(worksheet===activeWorksheet)activeWorksheet.getRange(rowIndex+1,columnIndex,1,1).setValues([['图片加载失败，点击重试']]).setFontColor('#f56c6c')
  }finally{imageRenderDepth--}
}
const renderAllImages=async()=>{
  const tasks=[]
  sheetColumns.value.forEach((column,columnIndex)=>{
    if(column.dataType!=='image')return
    props.rows.forEach((row,rowIndex)=>{
      const imageId=row.assignmentCustomValues?.[column.fieldId]
      if(imageId)tasks.push(renderImageCell(rowIndex,columnIndex,imageId))
    })
  })
  await Promise.allSettled(tasks)
}
const setImageDraft=(rowIndex,fieldId,value)=>{
  const next=new Map(imageDrafts.value)
  next.set(imageCellKey(rowIndex,fieldId),value||null)
  imageDrafts.value=next
}
const cleanupPendingImage=async id=>{
  if(!id||!pendingImageIds.has(id))return
  pendingImageIds.delete(id)
  try{await deletePendingCustomFieldImage(id)}catch(error){console.warn('清理待保存动态字段图片失败',error)}
}
const cleanupAllPendingImages=async()=>{
  const ids=[...pendingImageIds]
  await Promise.allSettled(ids.map(cleanupPendingImage))
}
const uploadImageFile=async file=>{
  const target=selectedImageCell.value
  if(!target)return ElMessage.warning('请先选择图片动态字段单元格')
  if(!file?.type?.startsWith('image/'))return ElMessage.warning('请选择图片文件')
  if(file.size>10*1024*1024)return ElMessage.warning('单张图片不能超过 10MB')
  imageUploading.value=true
  try{
    const previous=imageValueAt(target.rowIndex,target.column.fieldId)
    const image=await uploadCustomFieldImage(props.projectId,target.column.fieldId,file)
    pendingImageIds.add(image.id)
    if(disposed){await cleanupPendingImage(image.id);return}
    setImageDraft(target.rowIndex,target.column.fieldId,image.id)
    if(previous&&pendingImageIds.has(previous))await cleanupPendingImage(previous)
    await renderImageCell(target.rowIndex,target.columnIndex,image.id)
    markRowsDirty(target.rowIndex+1)
  }catch(error){ElMessage.error(error.detail||error.message||'图片上传失败')}
  finally{imageUploading.value=false}
}
const handleImageUpload=({file})=>uploadImageFile(file)
const removeSelectedImage=async()=>{
  const target=selectedImageCell.value
  if(!target)return
  const previous=imageValueAt(target.rowIndex,target.column.fieldId)
  setImageDraft(target.rowIndex,target.column.fieldId,null)
  clearRenderedImage(target.rowIndex,target.columnIndex)
  await cleanupPendingImage(previous)
  markRowsDirty(target.rowIndex+1)
}
const handlePaste=event=>{
  if(!selectedImageCell.value||props.deleteMode)return
  const file=[...(event.clipboardData?.items||[])].find(item=>item.kind==='file'&&item.type.startsWith('image/'))?.getAsFile()
  event.preventDefault();event.stopPropagation()
  if(!file)return ElMessage.warning('图片字段仅支持粘贴剪贴板图片')
  uploadImageFile(file)
}
const handleCanvasKeydown=event=>{
  if(!selectedImageCell.value||props.deleteMode||!['Delete','Backspace'].includes(event.key))return
  event.preventDefault();event.stopPropagation();removeSelectedImage()
}

const disposeGrid=()=>{
  disposables.forEach(item=>item?.dispose?.())
  disposables=[]
  univerAPI?.dispose?.()
  univer?.dispose?.()
  univer=null;univerAPI=null;worksheet=null;lastSelections=[]
  selectedCell.value=null
  revokeAllImageUrls()
  if(container.value)container.value.innerHTML=''
}
const applyValidation=(column,index,rowCount)=>{
  if(!column.editable||rowCount<1)return
  let options=[]
  if(column.dataType==='person')options=props.talents.map(talentLabel).filter(Boolean)
  else if(column.dataType==='platform')options=props.platforms.map(platformLabel).filter(Boolean)
  else if(column.dataType==='language')options=props.languageItems.map(languageLabel).filter(Boolean)
  else if(column.dataType==='user')options=props.users.map(userLabel).filter(Boolean)
  else if(column.dataType==='account_status')options=Object.values(accountStatusLabels)
  else if(column.dataType==='single_select'||column.dataType==='multi_select')options=(column.options||[]).map(item=>item.value||item.label||item).filter(Boolean)
  else if(column.dataType==='boolean')options=['是','否']
  if(!options.length)return
  const rule=univerAPI.newDataValidation().requireValueInList(options,['multi_select','language'].includes(column.dataType),true).setOptions({allowBlank:true,showErrorMessage:true,error:'请选择有效值'}).build()
  worksheet.getRange(1,index,rowCount,1).setDataValidation(rule)
}
const restoreReadonlyCells=()=>{
  if(!worksheet)return
  const matrix=sourceMatrix()
  const personColumnIndex=sheetColumns.value.findIndex(column=>column.key==='person')
  worksheet.getRange(0,0,1,sheetColumns.value.length).setValues([matrix[0]])
  sheetColumns.value.forEach((column,columnIndex)=>{
    if(column.editable)return
    worksheet.getRange(1,columnIndex,props.maxRows,1).setValues(
      Array.from({length:props.maxRows},(_,rowIndex)=>{
        if(['gender','age'].includes(column.key)&&personColumnIndex>=0){
          const personLabel=worksheet.getRange(rowIndex+1,personColumnIndex,1,1).getValues()[0][0]
          const talent=talentByLabel.value.get(String(personLabel||'').trim())
          if(talent)return [column.key==='gender'?(talent.gender||''):ageFromBirthDate(talent.birthDate)]
          if(!String(personLabel||'').trim())return ['']
        }
        return [rowIndex<props.rows.length?matrix[rowIndex+1][columnIndex]:'']
      })
    )
  })
}
const markRowsDirty=(startRow,endRow=startRow)=>{
  const next=new Set(dirtyRows.value)
  for(let row=Math.max(1,startRow);row<=Math.min(props.maxRows,endRow);row++)next.add(row-1)
  dirtyRows.value=next
  validationMessage.value=''
  emit('dirty-change',next.size)
}
const initializeGrid=async requestSequence=>{
  await cleanupAllPendingImages()
  if(disposed||requestSequence!==rebuildSequence)return false
  disposeGrid()
  if(!container.value||disposed||requestSequence!==rebuildSequence)return false
  imageDrafts.value=new Map()
  const created=createUniver({
    locale:LocaleType.ZH_CN,
    locales:{[LocaleType.ZH_CN]:mergeLocales(UniverPresetSheetsCoreZhCN,UniverPresetSheetsDataValidationZhCN,UniverPresetSheetsDrawingZhCN)},
    presets:[
      UniverSheetsCorePreset({container:container.value}),
      UniverSheetsDataValidationPreset({showEditOnDropdown:false,showSearchOnDropdown:true}),
      UniverSheetsDrawingPreset(),
    ],
  })
  univer=created.univer;univerAPI=created.univerAPI
  const workbook=univerAPI.createWorkbook({name:props.projectName||'项目账号表'})
  worksheet=workbook.getActiveSheet()
  const matrix=sourceMatrix()
  worksheet.getRange(0,0,matrix.length,sheetColumns.value.length).setValues(matrix)
  worksheet.setFrozenRows(1)
  worksheet.setFrozenColumns(1)
  worksheet.setRowHeight(0,36)
  const header=worksheet.getRange(0,0,1,sheetColumns.value.length)
  header.setBackground('#dbeafe').setFontWeight('bold').setFontColor('#1e3a5f').setVerticalAlignment('middle').setHorizontalAlignment('center')
  sheetColumns.value.forEach((column,index)=>{
    worksheet.setColumnWidth(index,column.width||Math.min(240,Math.max(110,column.label.length*18+40)))
    if(!column.editable&&props.rows.length)worksheet.getRange(1,index,props.rows.length,1).setBackground('#f5f7fa').setFontColor('#606266')
    applyValidation(column,index,props.maxRows)
  })
  if(props.rows.length)worksheet.getRange(1,0,props.rows.length,sheetColumns.value.length).setWrap(true).setVerticalAlignment('middle')
  disposables.push(univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart,params=>{
    const column=sheetColumns.value[params.column]
    if(props.deleteMode||params.row===0||!column?.editable||column.dataType==='image'||params.row>props.maxRows)params.cancel=true
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SheetEditEnded,params=>{
    restoreReadonlyCells()
    if(params.isConfirm&&params.row>0&&params.row<=props.maxRows&&sheetColumns.value[params.column]?.editable&&sheetColumns.value[params.column]?.dataType!=='image')markRowsDirty(params.row)
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SelectionChanged,params=>{
    lastSelections=params.selections||[]
    const selected=lastSelections[0]
    const rowIndex=selected?.startRow>0?selected.startRow-1:-1
    const columnIndex=Number.isInteger(selected?.startColumn)?selected.startColumn:-1
    selectedCell.value=rowIndex>=0&&columnIndex>=0?{rowIndex,columnIndex,column:sheetColumns.value[columnIndex]}:null
    selectedRow.value=props.rows[rowIndex]||null
    const selectionRows=[]
    const selectionIds=new Set()
    lastSelections.forEach(selection=>{
      for(let selectedRowIndex=Math.max(1,selection.startRow);selectedRowIndex<=Math.min(props.rows.length,selection.endRow);selectedRowIndex++){
        const row=props.rows[selectedRowIndex-1]
        if(row&&!selectionIds.has(row.id)){selectionIds.add(row.id);selectionRows.push(row)}
      }
    })
    emit('selection-change',selectionRows)
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.CellClicked,async params=>{
    const column=sheetColumns.value[params.column]
    if(params.row>0&&column?.dataType==='image'&&imageValueAt(params.row-1,column.fieldId)){
      const target={rowIndex:params.row-1,columnIndex:params.column,column}
      selectedCell.value=target
      const key=imageCellKey(target.rowIndex,column.fieldId)
      if(!imageObjectUrls.has(key))await renderImageCell(target.rowIndex,target.columnIndex,imageValueAt(target.rowIndex,column.fieldId))
    }
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.ClipboardPasted,()=>{
    lastSelections.forEach(selection=>markRowsDirty(selection.startRow,selection.endRow))
    restoreReadonlyCells()
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute,event=>{
    const uncontrolledDrawingCommands=new Set([
      'sheet.command.insert-cell-image','sheet.command.insert-float-image','sheet.command.insert-sheet-image',
      'sheet.command.remove-sheet-image','sheet.command.delete-drawing','sheet.command.set-sheet-image',
      'sheet.command.set-drawing-arrange','sheet.command.group-sheet-image','sheet.command.ungroup-sheet-image',
    ])
    if(imageRenderDepth===0&&uncontrolledDrawingCommands.has(event.id)){
      event.cancel=true
      ElMessage.warning('图片请通过所选图片字段的插入、替换或删除操作管理')
    }
  }))
  dirtyRows.value=new Set();selectedRow.value=null;validationMessage.value='';emit('dirty-change',0);emit('selection-change',[])
  void renderAllImages()
  return true
}

const requestGridRebuild=()=>{
  const requestSequence=++rebuildSequence
  rebuildQueue=rebuildQueue.catch(error=>console.error('重建项目账号表失败',error)).then(async()=>{
    await nextTick()
    if(disposed||requestSequence!==rebuildSequence)return false
    return initializeGrid(requestSequence)
  })
  return rebuildQueue
}

const parseValue=(value,column)=>{
  const empty=value===null||value===undefined||String(value).trim()===''
  if(empty)return null
  if(column.dataType==='number'){
    const parsed=Number(value)
    if(!Number.isFinite(parsed))throw new Error(`${column.label}必须是数字`)
    return parsed
  }
  if(column.dataType==='boolean'){
    const normalized=String(value).trim().toLowerCase()
    if(['是','true','1','yes'].includes(normalized))return true
    if(['否','false','0','no'].includes(normalized))return false
    throw new Error(`${column.label}只能填写“是”或“否”`)
  }
  if(column.dataType==='multi_select')return String(value).split(/[、,，]/).map(item=>item.trim()).filter(Boolean)
  return String(value).trim()
}
const selectedIds=(value,lookup,label)=>{
  const labels=String(value||'').split(/[、,，]/).map(item=>item.trim()).filter(Boolean)
  return labels.map(item=>{
    const matched=lookup.get(item)
    if(!matched)throw new Error(`${label}“${item}”不在可选范围内`)
    return matched.id
  })
}
const requiredSelection=(value,lookup,items,label,originalId=null)=>{
  const text=String(value||'').trim()
  if(text){
    const matched=lookup.get(text)
    if(!matched)throw new Error(`${label}不在可选范围内`)
    return matched.id
  }
  if(originalId)return originalId
  if(items.length===1)return items[0].id
  throw new Error(`请选择${label}`)
}
const submitChanges=()=>{
  if(!worksheet||!dirtyRows.value.size)return
  try{
    const changes=[...dirtyRows.value].sort((a,b)=>a-b).map(rowIndex=>{
      const original=props.rows[rowIndex]||null
      const values=worksheet.getRange(rowIndex+1,0,1,sheetColumns.value.length).getValues()[0]
      const assignmentCustomValues={...(original?.assignmentCustomValues||{})}
      let personId=original?.personId||null
      let platformId=original?.platformId||null
      let ownerId=original?.ownerId||props.currentUserId||null
      let languageItemIds=[...(original?.languageItemIds||[])]
      let nickname=original?.nickname||null,loginAccount=original?.loginAccount||null,password=original?.password||null
      let accountStatus=original?.accountStatus||'available',expiresOn=original?.expiresOn||null
      sheetColumns.value.forEach((column,columnIndex)=>{
        if(!column.editable)return
        const cellValue=values[columnIndex]
        if(column.key==='platform')platformId=requiredSelection(cellValue,platformByLabel.value,props.platforms,'平台',original?.platformId)
        else if(column.key==='nickname')nickname=String(cellValue||'').trim()||null
        else if(column.key==='login')loginAccount=String(cellValue||'').trim()||null
        else if(column.key==='password')password=String(cellValue||'').trim()||null
        else if(column.key==='person'){
          const label=String(cellValue||'').trim()
          if(!label)personId=null
          else{
            const talent=talentByLabel.value.get(label)
            if(!talent)throw new Error(`第 ${rowIndex+1} 行的分配人员不在可选人才中`)
            personId=talent.id
          }
        }else if(column.key==='language'){
          languageItemIds=selectedIds(cellValue,languageByLabel.value,'语言方向')
          if(!languageItemIds.length){
            if(original?.languageItemIds?.length)languageItemIds=[...original.languageItemIds]
            else if(props.languageItems.length===1)languageItemIds=[props.languageItems[0].id]
            else throw new Error('请选择语言方向')
          }
        }else if(column.key==='accountStatus')accountStatus=accountStatusByLabel.get(String(cellValue||'').trim())||original?.accountStatus||'available'
        else if(column.key==='owner')ownerId=requiredSelection(cellValue,userByLabel.value,props.users,'负责人',original?.ownerId||props.currentUserId)
        else if(column.key==='expiresOn')expiresOn=String(cellValue||'').trim()||null
        else if(column.fieldId&&column.dataType==='image'){
          const imageId=imageValueAt(rowIndex,column.fieldId)
          if(column.isRequired&&!imageId)throw new Error(`第 ${rowIndex+1} 行的${column.label}必须上传图片`)
          assignmentCustomValues[column.fieldId]=imageId||null
        }else if(column.fieldId)assignmentCustomValues[column.fieldId]=parseValue(cellValue,column)
      })
      if(Boolean(loginAccount)!==Boolean(password))throw new Error(`第 ${rowIndex+1} 行的登录账号和密码必须同时填写`)
      if(!original&&!nickname&&!loginAccount&&!personId)throw new Error(`第 ${rowIndex+1} 行请至少填写账号昵称、登录账号或分配人员`)
      if(!platformId)throw new Error(`第 ${rowIndex+1} 行请选择平台`)
      if(!ownerId)throw new Error(`第 ${rowIndex+1} 行请选择负责人`)
      if(!languageItemIds.length)throw new Error(`第 ${rowIndex+1} 行请选择语言方向`)
      return{
        original,personId,languageItemIds,assignmentCustomValues,rowIndex,
        account:{
          platformId,parentAccountId:original?.parentAccountId||null,ownerId,nickname,loginAccount,password,
          accountStatus:personId?'assigned':(accountStatus==='assigned'?'available':accountStatus),
          registrationStatus:original?.registrationStatus||'unregistered',accountSource:original?.accountSource||'client_provided',
          expiresOn,remarks:original?.remarks||null,sequenceNo:original?.sequenceNo||null,customValues:original?.customValues||{},
        },
      }
    })
    emit('save',changes)
  }catch(error){validationMessage.value=error.message||'表格数据校验失败';ElMessage.error(validationMessage.value)}
}

const discardChanges=async()=>{
  if(!dirtyRows.value.size)return
  try{await ElMessageBox.confirm(`确定放弃 ${dirtyRows.value.size} 行未保存修改？`,'放弃表格修改',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}
  await cleanupAllPendingImages()
  await requestGridRebuild()
}
const focusNewRow=()=>{
  if(!worksheet)return
  const usedDraftRows=[...dirtyRows.value].filter(index=>index>=props.rows.length)
  const rowIndex=usedDraftRows.length?Math.max(...usedDraftRows)+1:props.rows.length
  if(rowIndex>=props.maxRows)return ElMessage.warning(`项目账号表最多支持 ${props.maxRows} 行`)
  worksheet.getRange(rowIndex+1,0,1,1).activate()
  ElMessage.info(`已定位到第 ${rowIndex+1} 行，可直接录入新账号`)
}
const focusFirstSaveError=()=>{
  if(!worksheet||!saveErrorEntries.value.length)return
  const rowIndex=Number(saveErrorEntries.value[0][0])
  if(Number.isInteger(rowIndex)&&rowIndex>=0&&rowIndex<props.rows.length)worksheet.getRange(rowIndex+1,0,1,1).activate()
}
const applySaveResults=results=>{
  const savedRows=new Set((results||[]).filter(item=>item.success).map(item=>{
    const matched=String(item.rowKey||'').match(/^project-sheet-(\d+)$/)
    return matched?Number(matched[1]):-1
  }).filter(rowIndex=>rowIndex>=0))
  if(!savedRows.size)return
  imageDrafts.value.forEach((imageId,key)=>{
    const rowIndex=Number(String(key).split(':',1)[0])
    if(savedRows.has(rowIndex)&&imageId)pendingImageIds.delete(imageId)
  })
  dirtyRows.value=new Set([...dirtyRows.value].filter(rowIndex=>!savedRows.has(rowIndex)))
  emit('dirty-change',dirtyRows.value.size)
}
const handleShortcut=event=>{
  if((event.ctrlKey||event.metaKey)&&String(event.key).toLowerCase()==='s'){
    if(!dirtyRows.value.size)return
    event.preventDefault()
    if(!props.saving)submitChanges()
  }
}

watch(()=>[props.rows,props.fields,props.talents],requestGridRebuild,{deep:true})
watch(()=>props.saveErrors,()=>nextTick(()=>{
  if(!worksheet)return
  saveErrorEntries.value.forEach(([row])=>{
    const rowIndex=Number(row)
    if(Number.isInteger(rowIndex)&&rowIndex>=0&&rowIndex<props.rows.length)worksheet.getRange(rowIndex+1,0,1,sheetColumns.value.length).setBackground('#fef0f0')
  })
}),{deep:true})
onMounted(()=>{disposed=false;window.addEventListener('keydown',handleShortcut);container.value?.addEventListener('paste',handlePaste,true);container.value?.addEventListener('keydown',handleCanvasKeydown,true);requestGridRebuild()})
onBeforeUnmount(()=>{disposed=true;rebuildSequence++;window.removeEventListener('keydown',handleShortcut);container.value?.removeEventListener('paste',handlePaste,true);container.value?.removeEventListener('keydown',handleCanvasKeydown,true);cleanupAllPendingImages();disposeGrid()})
defineExpose({applySaveResults,focusNewRow,refreshColumns:requestGridRebuild})
</script>

<style scoped>
.project-spreadsheet{min-width:0}.project-spreadsheet__toolbar{display:flex;align-items:stretch;gap:4px;margin-bottom:6px;flex-direction:column}.project-spreadsheet__status,.project-spreadsheet__status-info,.project-spreadsheet__actions,.project-spreadsheet__context-actions,.project-spreadsheet__save-actions{display:flex;align-items:center;gap:8px}.project-spreadsheet__status{min-height:28px;justify-content:space-between;flex-wrap:nowrap;color:var(--el-text-color-secondary);font-size:13px}.project-spreadsheet__status-info{min-width:0;flex:1;flex-wrap:wrap;gap:6px}.project-spreadsheet__actions{min-height:28px;justify-content:flex-start;overflow-x:auto;overflow-y:hidden}.project-spreadsheet__context-actions,.project-spreadsheet__save-actions{flex:none;white-space:nowrap}.project-spreadsheet__context-actions{min-width:0}.project-spreadsheet__save-actions{margin-left:auto}.project-spreadsheet__actions .el-button{height:28px;min-height:28px;padding:4px 10px;font-size:13px}.project-spreadsheet__save-actions .el-button{height:26px;min-height:26px;padding:3px 8px;font-size:12px}.selected-label{display:inline-block;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--el-text-color-secondary);font-size:13px}.delete-mode-tip{color:var(--el-color-danger);font-size:13px}.shortcut{margin-left:5px;opacity:.68;font-size:10px}.project-spreadsheet :deep(.el-alert){margin-bottom:8px}.save-error-summary{display:flex;align-items:flex-start;gap:8px}.save-error-summary :deep(.el-alert){flex:1}.project-spreadsheet__canvas{height:min(640px,calc(100vh - 294px));min-height:410px;border:1px solid var(--el-border-color);border-radius:6px;overflow:hidden}.project-spreadsheet--focus{display:flex;min-height:0;overflow:hidden;flex-direction:column}.project-spreadsheet--focus .project-spreadsheet__toolbar{flex:none;margin-bottom:2px}.project-spreadsheet--focus .project-spreadsheet__canvas{flex:1;height:auto;min-height:0}
@media(max-width:768px){.project-spreadsheet__status,.project-spreadsheet__actions{align-items:flex-start;flex-direction:column;overflow:visible}.project-spreadsheet__context-actions{max-width:100%;overflow-x:auto}.project-spreadsheet__save-actions{align-self:flex-end}.project-spreadsheet__canvas{height:500px;min-height:400px}}
</style>
