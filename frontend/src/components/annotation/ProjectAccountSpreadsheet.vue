<template>
  <div class="project-spreadsheet" :class="{ 'project-spreadsheet--focus': focusMode }">
    <div class="project-spreadsheet__toolbar">
      <div class="project-spreadsheet__status">
        <el-tag type="success" effect="plain">Univer OSS</el-tag>
        <span v-if="!focusMode">双击单元格编辑，支持区域复制粘贴、撤销/重做和基础样式。</span>
        <el-tag effect="plain">已加载 {{ rows.length }} / {{ totalRows }} 条</el-tag>
        <el-tag v-if="dirtyCount" type="warning">{{ dirtyCount }} 行待保存</el-tag>
      </div>
      <div class="project-spreadsheet__actions">
        <template v-if="selectedRow">
          <span class="selected-label">已选：{{ selectedRow.personName || selectedRow.loginAccount || selectedRow.platformName || '-' }}</span>
          <el-button size="small" @click="$emit('detail', selectedRow)">查看详情</el-button>
          <el-button size="small" :disabled="Boolean(dirtyCount)" title="请先保存或放弃表格修改" @click="$emit('edit', selectedRow)">编辑资产信息</el-button>
        </template>
        <el-button v-if="dirtyCount" :disabled="saving" @click="discardChanges">放弃修改</el-button>
        <el-button type="primary" :loading="saving" :disabled="!dirtyCount" @click="submitChanges">保存修改（{{ dirtyCount }}）<span class="shortcut">Ctrl+S</span></el-button>
      </div>
    </div>
    <el-alert
      v-if="totalRows > maxRows"
      :title="`当前筛选共有 ${totalRows} 条，仅加载前 ${maxRows} 条；请缩小筛选范围后再批量编辑。`"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="missingFieldLabels.length"
      :title="`以下标准列尚未建立项目字段，当前为只读：${missingFieldLabels.join('、')}`"
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
import '@univerjs/preset-sheets-core/lib/index.css'
import '@univerjs/preset-sheets-data-validation/lib/index.css'

const props=defineProps({
  rows:{type:Array,default:()=>[]},
  fields:{type:Array,default:()=>[]},
  talents:{type:Array,default:()=>[]},
  projectName:{type:String,default:'项目账号表'},
  loading:{type:Boolean,default:false},
  saving:{type:Boolean,default:false},
  totalRows:{type:Number,default:0},
  maxRows:{type:Number,default:500},
  saveErrors:{type:Object,default:()=>({})},
  focusMode:{type:Boolean,default:false},
})
const emit=defineEmits(['save','detail','edit','dirty-change'])
const container=ref(null),dirtyRows=ref(new Set()),selectedRow=ref(null),validationMessage=ref('')
let univer=null,univerAPI=null,worksheet=null,disposables=[],rebuildTimer=null,lastSelections=[]

const standardTemplates=[
  ['external_data_no','数据编号','text'],
  ['quality_status','质检状态','text'],
  ['price','价格','number'],
  ['error_feedback','错误点/问题','text'],
  ['highlight_feedback','标红需反馈','text'],
]
const standardKeys=new Set(standardTemplates.map(item=>item[0]))
const fieldByKey=key=>props.fields.find(item=>item.fieldKey===key)
const talentLabel=item=>`${item.resourceCode||''} ${item.fullName||item.personName||''}`.trim()
const talentByLabel=computed(()=>new Map(props.talents.map(item=>[talentLabel(item),item])))
const missingFieldLabels=computed(()=>standardTemplates.filter(([key])=>!fieldByKey(key)).map(([,label])=>label))
const dirtyCount=computed(()=>dirtyRows.value.size)
const saveErrorEntries=computed(()=>Object.entries(props.saveErrors).sort(([left],[right])=>Number(left)-Number(right)))

const sheetColumns=computed(()=>{
  const standard=Object.fromEntries(standardTemplates.map(([key,label,dataType])=>{
    const field=fieldByKey(key)
    return [key,{key,label,dataType,fieldId:field?.id||null,editable:Boolean(field),options:field?.options||[]}]
  }))
  const extra=props.fields.filter(item=>!standardKeys.has(item.fieldKey)).map(item=>({
    key:`custom:${item.id}`,label:item.fieldLabel,dataType:item.dataType,fieldId:item.id,editable:true,options:item.options||[],
  }))
  return [
    standard.external_data_no,
    {key:'platform',label:'平台',editable:false,width:150},
    {key:'login',label:'登录账号',editable:false,width:190},
    {key:'password',label:'密码',editable:false,width:120},
    {key:'person',label:'分配人员',editable:true,dataType:'person',width:180},
    {key:'gender',label:'性别',editable:false,width:80},
    standard.quality_status,
    standard.price,
    standard.error_feedback,
    standard.highlight_feedback,
    {key:'language',label:'语言方向',editable:false,width:140},
    ...extra,
  ]
})

const formatCustomValue=(value,type)=>{
  if(value===null||value===undefined)return ''
  if(Array.isArray(value))return value.join('、')
  if(type==='boolean')return value?'是':'否'
  return value
}
const rowValue=(row,column)=>{
  if(column.fieldId)return formatCustomValue(row.assignmentCustomValues?.[column.fieldId],column.dataType)
  if(column.key==='platform')return row.platformName||''
  if(column.key==='login')return row.loginAccount||''
  if(column.key==='password')return row.password||''
  if(column.key==='person'){
    const talent=props.talents.find(item=>String(item.id)===String(row.personId||''))
    return talent?talentLabel(talent):(row.personName||'')
  }
  if(column.key==='gender')return row.personGender||''
  if(column.key==='language')return row.languageLabels?.join('、')||''
  return ''
}
const sourceMatrix=()=>[
  sheetColumns.value.map(column=>column.label),
  ...props.rows.map(row=>sheetColumns.value.map(column=>rowValue(row,column))),
]

const disposeGrid=()=>{
  disposables.forEach(item=>item?.dispose?.())
  disposables=[]
  univerAPI?.dispose?.()
  univer?.dispose?.()
  univer=null;univerAPI=null;worksheet=null;lastSelections=[]
  if(container.value)container.value.innerHTML=''
}
const applyValidation=(column,index,rowCount)=>{
  if(!column.editable||rowCount<1)return
  let options=[]
  if(column.dataType==='person')options=props.talents.map(talentLabel).filter(Boolean)
  else if(column.dataType==='single_select'||column.dataType==='multi_select')options=(column.options||[]).map(item=>item.value||item.label||item).filter(Boolean)
  else if(column.dataType==='boolean')options=['是','否']
  if(!options.length)return
  const rule=univerAPI.newDataValidation().requireValueInList(options,column.dataType==='multi_select',true).setOptions({allowBlank:true,showErrorMessage:true,error:'请选择有效值'}).build()
  worksheet.getRange(1,index,rowCount,1).setDataValidation(rule)
}
const restoreReadonlyCells=()=>{
  if(!worksheet)return
  const matrix=sourceMatrix()
  worksheet.getRange(0,0,1,sheetColumns.value.length).setValues([matrix[0]])
  if(!props.rows.length)return
  sheetColumns.value.forEach((column,columnIndex)=>{
    if(column.editable)return
    worksheet.getRange(1,columnIndex,props.rows.length,1).setValues(props.rows.map((_,rowIndex)=>[matrix[rowIndex+1][columnIndex]]))
  })
}
const markRowsDirty=(startRow,endRow=startRow)=>{
  const next=new Set(dirtyRows.value)
  for(let row=Math.max(1,startRow);row<=Math.min(props.rows.length,endRow);row++)next.add(row-1)
  dirtyRows.value=next
  validationMessage.value=''
  emit('dirty-change',next.size)
}
const initializeGrid=async()=>{
  disposeGrid()
  if(!container.value)return
  const created=createUniver({
    locale:LocaleType.ZH_CN,
    locales:{[LocaleType.ZH_CN]:mergeLocales(UniverPresetSheetsCoreZhCN,UniverPresetSheetsDataValidationZhCN)},
    presets:[
      UniverSheetsCorePreset({container:container.value}),
      UniverSheetsDataValidationPreset({showEditOnDropdown:false,showSearchOnDropdown:true}),
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
    applyValidation(column,index,props.rows.length)
  })
  if(props.rows.length)worksheet.getRange(1,0,props.rows.length,sheetColumns.value.length).setWrap(true).setVerticalAlignment('middle')
  disposables.push(univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart,params=>{
    const column=sheetColumns.value[params.column]
    if(params.row===0||!column?.editable||params.row>props.rows.length)params.cancel=true
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SheetEditEnded,params=>{
    restoreReadonlyCells()
    if(params.isConfirm&&params.row>0&&params.row<=props.rows.length&&sheetColumns.value[params.column]?.editable)markRowsDirty(params.row)
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SelectionChanged,params=>{
    lastSelections=params.selections||[]
    const selected=lastSelections[0]
    const rowIndex=selected?.startRow>0?selected.startRow-1:-1
    selectedRow.value=props.rows[rowIndex]||null
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.ClipboardPasted,()=>{
    lastSelections.forEach(selection=>markRowsDirty(selection.startRow,selection.endRow))
    restoreReadonlyCells()
  }))
  dirtyRows.value=new Set();selectedRow.value=null;validationMessage.value='';emit('dirty-change',0)
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
const submitChanges=()=>{
  if(!worksheet||!dirtyRows.value.size)return
  try{
    const changes=[...dirtyRows.value].sort((a,b)=>a-b).map(rowIndex=>{
      const original=props.rows[rowIndex]
      const values=worksheet.getRange(rowIndex+1,0,1,sheetColumns.value.length).getValues()[0]
      const assignmentCustomValues={...(original.assignmentCustomValues||{})}
      let personId=original.personId||null
      sheetColumns.value.forEach((column,columnIndex)=>{
        if(!column.editable)return
        if(column.key==='person'){
          const label=String(values[columnIndex]||'').trim()
          if(!label)personId=null
          else{
            const talent=talentByLabel.value.get(label)
            if(!talent)throw new Error(`第 ${rowIndex+1} 行的分配人员不在可选人才中`)
            personId=talent.id
          }
        }else if(column.fieldId)assignmentCustomValues[column.fieldId]=parseValue(values[columnIndex],column)
      })
      return{original,personId,assignmentCustomValues,rowIndex}
    })
    emit('save',changes)
  }catch(error){validationMessage.value=error.message||'表格数据校验失败';ElMessage.error(validationMessage.value)}
}

const discardChanges=async()=>{
  if(!dirtyRows.value.size)return
  try{await ElMessageBox.confirm(`确定放弃 ${dirtyRows.value.size} 行未保存修改？`,'放弃表格修改',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}
  await initializeGrid()
}
const focusFirstSaveError=()=>{
  if(!worksheet||!saveErrorEntries.value.length)return
  const rowIndex=Number(saveErrorEntries.value[0][0])
  if(Number.isInteger(rowIndex)&&rowIndex>=0&&rowIndex<props.rows.length)worksheet.getRange(rowIndex+1,0,1,1).activate()
}
const handleShortcut=event=>{
  if((event.ctrlKey||event.metaKey)&&String(event.key).toLowerCase()==='s'){
    if(!dirtyRows.value.size)return
    event.preventDefault()
    if(!props.saving)submitChanges()
  }
}

watch(()=>[props.rows,props.fields,props.talents],()=>{
  clearTimeout(rebuildTimer)
  rebuildTimer=setTimeout(()=>nextTick(initializeGrid),50)
},{deep:true})
watch(()=>props.saveErrors,()=>nextTick(()=>{
  if(!worksheet)return
  saveErrorEntries.value.forEach(([row])=>{
    const rowIndex=Number(row)
    if(Number.isInteger(rowIndex)&&rowIndex>=0&&rowIndex<props.rows.length)worksheet.getRange(rowIndex+1,0,1,sheetColumns.value.length).setBackground('#fef0f0')
  })
}),{deep:true})
onMounted(()=>{window.addEventListener('keydown',handleShortcut);nextTick(initializeGrid)})
onBeforeUnmount(()=>{window.removeEventListener('keydown',handleShortcut);clearTimeout(rebuildTimer);disposeGrid()})
</script>

<style scoped>
.project-spreadsheet{min-width:0}.project-spreadsheet__toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.project-spreadsheet__status,.project-spreadsheet__actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.project-spreadsheet__status{color:var(--el-text-color-secondary);font-size:13px}.selected-label{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--el-text-color-secondary);font-size:13px}.shortcut{margin-left:6px;opacity:.72;font-size:11px}.project-spreadsheet :deep(.el-alert){margin-bottom:10px}.save-error-summary{display:flex;align-items:flex-start;gap:8px}.save-error-summary :deep(.el-alert){flex:1}.project-spreadsheet__canvas{height:min(640px,calc(100vh - 300px));min-height:440px;border:1px solid var(--el-border-color);border-radius:6px;overflow:hidden}.project-spreadsheet--focus .project-spreadsheet__toolbar{margin-bottom:6px}.project-spreadsheet--focus .project-spreadsheet__canvas{height:calc(100vh - 205px);min-height:560px}
@media(max-width:768px){.project-spreadsheet__toolbar{align-items:flex-start;flex-direction:column}.project-spreadsheet__canvas{height:520px;min-height:420px}}
</style>
