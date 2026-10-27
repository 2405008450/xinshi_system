<template>
  <DraggableFormDialog v-model="visible" width="min(1520px, calc(100vw - 32px))" top="5vh" append-to-body class="talent-region-match-dialog" :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="资源匹配" subtitle="使用人才总库的籍贯、主要成长地、目前所在地匹配" placeholder="搜索匹配设置字段" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template #actions><TableColumnSettings v-model="selectedKeys" settings-key="talent-region-match" :columns="talentTableColumns" :column-count="2" title="匹配人才字段" @reset="reset" /></template></DialogFieldSearchHeader></template>
    <div ref="bodyRef">
      <details ref="settingsSectionRef" class="region-match-settings" :open="settingsOpen" @toggle="settingsOpen=$event.target.open"><summary>数据来源与匹配设置（{{ input.rows.length }} 行）</summary>
        <AppForm :model="settings" label-position="top" @submit.prevent="runMatch">
          <el-form-item label="数据来源"><el-radio-group v-model="mode"><el-radio-button value="file">上传 Excel</el-radio-button><el-radio-button value="paste">粘贴区域</el-radio-button></el-radio-group></el-form-item>
          <div v-if="mode==='file'" class="region-match-source">
            <el-form-item label="上传区域表格">
              <div class="region-file-dropzone" :class="{'is-dragover':fileDragDepth>0}" role="group" aria-label="区域表格文件拖放区" :aria-busy="importing" @dragenter.prevent.stop="enterFileDrag" @dragover.prevent.stop="overFileDrag" @dragleave.prevent.stop="leaveFileDrag" @drop.prevent.stop="dropFiles">
                <input ref="sourceFileInput" type="file" accept=".xlsx,.xlsm,.csv,.tsv" aria-label="上传区域表格" @change="chooseFile" />
                <p class="region-file-drop-hint" aria-live="polite">{{fileDragDepth>0?'松开以读取文件':'可将文件夹、微信中的表格文件拖到这里，也可点击选择文件'}}</p>
                <p v-if="sourceFileName" class="region-file-name">已选择：{{sourceFileName}}</p>
              </div>
              <small>支持.xlsx、.xlsm、CSV、TSV，最多10MB、1000行、50列，一次读取一个文件。旧版.xls请另存为.xlsx。</small>
            </el-form-item>
            <el-form-item v-if="sheets.length" label="工作表"><el-select v-model="sheet" :disabled="importing" @change="readFile"><el-option v-for="name in sheets" :key="name" :value="name" :label="name" /></el-select></el-form-item>
          </div>
          <el-form-item v-else label="粘贴 Excel 区域"><el-input v-model="pasteText" type="textarea" :rows="4" placeholder="从Excel复制一列或多列、多行后粘贴，列之间保留制表符" aria-label="粘贴Excel区域" /><el-button @click="readPaste">读取粘贴区域</el-button></el-form-item>
          <el-form-item label="表头设置"><el-checkbox v-model="hasHeader" @change="readSource">第一行为表头</el-checkbox><span class="muted">空行跳过，原行号保留；未选择的列不参与匹配。</span></el-form-item>
          <el-alert v-if="sourceError" :title="sourceError" type="error" :closable="false" />
          <p v-if="importing">正在读取工作簿…</p>
          <template v-if="input.rows.length">
            <div class="region-match-grid">
              <el-form-item label="人才总库目标字段"><el-checkbox-group v-model="targetFields"><el-checkbox v-for="field in regionFields" :key="field.key" :value="field.key">{{ field.label }}</el-checkbox></el-checkbox-group></el-form-item>
              <el-form-item label="来源列（最多三列）"><el-select v-model="sourceColumns" multiple :multiple-limit="3" placeholder="选择1～3列" @change="syncMappings"><el-option v-for="column in input.columns" :key="column.index" :value="column.index" :label="column.label" /></el-select></el-form-item>
              <el-form-item v-for="index in sourceColumns" :key="index" :label="`${input.columns[index]?.label} → 目标字段`"><el-select v-model="mapping[index]" multiple placeholder="可多选，配置一对一或一对多"><el-option v-for="field in regionFields.filter(field=>targetFields.includes(field.key))" :key="field.key" :value="field.key" :label="field.label" /></el-select></el-form-item>
              <el-form-item label="来源列之间"><el-select v-model="settings.combine"><el-option value="all" label="全部满足（AND）" /><el-option value="any" label="任一满足（OR）" /></el-select></el-form-item>
              <el-form-item label="同一来源列的多个目标字段"><el-select v-model="settings.targetCombine"><el-option value="any" label="任一目标字段包含即可（OR）" /><el-option value="all" label="每个目标字段均须包含（AND）" /></el-select></el-form-item>
              <el-form-item label="匹配条件"><el-radio-group v-model="settings.matchMode"><el-radio value="full">完整匹配</el-radio><el-radio value="trim_suffix">去掉末尾行政区划字样</el-radio></el-radio-group></el-form-item>
              <el-form-item v-if="settings.matchMode==='trim_suffix'" label="可去除的末尾字样"><el-checkbox-group v-model="settings.suffixes"><el-checkbox v-for="suffix in regionSuffixes" :key="suffix" :value="suffix">{{ suffix }}</el-checkbox></el-checkbox-group></el-form-item>
              <el-form-item v-if="settings.matchMode==='trim_suffix'" label="短名称保留规则"><el-checkbox v-model="settings.preserveShort">两个字不去尾字，三个字及以上才去除</el-checkbox></el-form-item>
            </div>
            <p class="muted">来源文字必须连续整体出现在单个目标字段中，不拆字、不跨字段拼接；忽略大小写、全半角和首尾空白，内部空白及标点保留。例如 ABC 不匹配 A…B…C。去末尾字样只处理勾选且位于末尾的一个后缀，三字后缀优先，不递归去除。匹配率按处理后的完整文字计算，符合条件为100%。可勾选来源行，再按字的位置去字后重新匹配。</p>
            <details><summary>查看来源数据预览（前10行，共{{ input.rows.length }}行）</summary><el-table :data="input.rows.slice(0,10)" border max-height="260"><el-table-column prop="source_row" label="原行号" width="80" /><el-table-column v-for="index in sourceColumns" :key="index" :label="input.columns[index]?.label" min-width="160" show-overflow-tooltip><template #default="{row}">{{ row.values[index] || '-' }}</template></el-table-column></el-table></details>
          </template>
        </AppForm>
      </details>
      <div class="region-match-toolbar"><el-button type="primary" :loading="matching" :disabled="importing || !input.rows.length" @click="runMatch">{{ results.length ? '重新匹配' : '开始匹配' }}</el-button><el-button :disabled="importing || !input.rows.length" title="保留来源数据，恢复默认条件并展开设置" @click="resetMatchConditions">重置匹配条件</el-button><el-tag>{{ settings.matchMode==='full'?'连续完整匹配':'去后缀后连续完整匹配' }}</el-tag><el-button title="清除文件、粘贴内容及匹配结果，重新上传文件" @click="clearMatching">清空本次匹配</el-button><span v-if="results.length">{{ results.length }} 行来源数据 · 匹配到 {{ uniqueTotal }} 位人才（跨行去重）</span><el-select v-if="results.length" v-model="resultOrder" class="region-match-order" aria-label="匹配人数排序" @change="applyResultFilters"><el-option label="原行顺序" value="source" /><el-option label="匹配人数：从少到多" value="asc" /><el-option label="匹配人数：从多到少" value="desc" /></el-select></div>
      <div v-if="results.length" class="region-match-result-search"><span class="muted">显示 {{ filteredResults.length }} / {{ results.length }} 行；各来源列表头可单独搜索</span><el-input v-model="resultKeyword" clearable placeholder="搜索所有来源列，空格分隔多个关键词" aria-label="搜索来源数据" @input="resultTextInput" @keyup.enter="applyResultFilters" /><el-button @click="applyResultFilters">查询</el-button><el-button @click="clearResultSearch">清空搜索</el-button><el-button :disabled="matching || !selectedResultRows.length" @click="editRows(selectedResultRows)">选中行去字重匹配（{{ selectedResultRows.length }}）</el-button></div>
      <el-alert v-if="matchError" :title="matchError" type="error" :closable="false" />
      <el-table v-if="results.length" ref="resultTable" :data="visibleResults" border row-key="index" empty-text="暂无符合搜索条件的来源数据" @expand-change="expanded" @selection-change="selectedResultRows=$event">
        <el-table-column type="selection" width="46" :reserve-selection="true" />
        <el-table-column type="expand"><template #default="{row}">
          <div class="region-match-expanded" v-loading="row.loading">
            <el-alert v-if="row.error" :title="row.error" type="error" :closable="false"><el-button link @click="loadRow(row)">重试</el-button></el-alert>
            <TalentMatchRecords :rows="row.items || []" :columns="visibleColumns" settings-key="talent-region-match" :offset="(row.page-1)*row.size" />
            <div class="region-match-paging"><el-pagination v-model:current-page="row.page" v-model:page-size="row.size" :total="row.total" :page-sizes="[10,20,50,100]" layout="total,sizes,prev,pager,next,jumper" @current-change="loadRow(row)" @size-change="row.page=1;loadRow(row)" /><el-button link @click="loadRow(row)">刷新该行</el-button></div>
          </div>
        </template></el-table-column>
        <el-table-column prop="sourceRow" label="原行号" width="88" />
        <el-table-column v-for="index in appliedColumns" :key="index" :label="appliedLabels[index]" min-width="170" show-overflow-tooltip><template #header><ConfiguredColumnHeaderFilter :definition="sourceFilterDefinition(index)" :model-value="sourceFilters[index] || ''" @update:model-value="sourceFilters[index]=$event" @text-input="resultTextInput" @enter="applyResultFilters" @clear="clearSourceFilter(index)" /></template><template #default="{row}"><div>{{ row.values[index] || '-' }}</div><div v-if="row.matchValues[index] !== row.values[index]" class="muted">实际匹配：{{ row.matchValues[index] || '（空，不匹配）' }}</div></template></el-table-column>
        <el-table-column label="匹配人才总数" width="235"><template #default="{row}"><el-button link type="primary" @click="resultTable.toggleRowExpansion(row)">{{ row.total }} 人 · 展开查看</el-button><div class="muted">平均匹配率：{{ formatRegionMatchRate(row.averageRate) }}</div></template></el-table-column>
      <el-table-column label="匹配调整" width="125" fixed="right"><template #default="{row}"><el-button link :disabled="matching" @click="editRows([row])">去字后重匹配</el-button></template></el-table-column>
      </el-table>
      <el-empty v-else-if="!matching" description="读取表格并设置映射后，点击开始匹配" />
    </div>
    <template #footer><span class="muted">只读匹配，不修改人才档案。匹配结果展开后可分页查看；“字段设置”控制人才展示列。</span><el-pagination v-if="results.length" v-model:current-page="resultPage" v-model:page-size="resultSize" :total="filteredResults.length" :page-sizes="[10,20,50,100]" layout="total,sizes,prev,pager,next" @size-change="resultPage=1" /><el-button @click="visible=false">关闭</el-button></template>
    <RegionRowTextEditor ref="rowEditor" :columns="editColumns" :rules="settings" @apply="applyRowEdits" />
  </DraggableFormDialog>
</template>
<script setup>
import { computed,ref,reactive,watch,onBeforeUnmount,nextTick } from 'vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { selectRegionMatchResults,formatRegionMatchRate } from '@/utils/regionMatchResults'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useTableColumns } from '@/composables/useTableColumns'
import { talentTableColumns,talentDefaultColumns } from '@/utils/talentTableColumns'
import { regionFields,regionSuffixes,prepareRegionSource,parsePastedRegions,buildRegionPayload } from '@/utils/regionMatchInput'
import { importTalentRegions,matchTalentRegions,getRegionMatchPage } from '@/api/talents'
import TalentMatchRecords from './TalentMatchRecords.vue'
import RegionRowTextEditor from './RegionRowTextEditor.vue'
const visible=ref(false),bodyRef=ref(),mode=ref('file'),hasHeader=ref(true),pasteText=ref(''),sheet=ref(''),sheets=ref([]),importing=ref(false),sourceError=ref(''),input=reactive({columns:[],rows:[]})
const fileDragDepth=ref(0),sourceFileName=ref('')
const settingsSectionRef=ref(),sourceFileInput=ref()
const settingsOpen=ref(true)
const sourceColumns=ref([]),targetFields=ref(regionFields.map(field=>field.key)),mapping=reactive({}),settings=reactive({threshold:100,combine:'all',targetCombine:'any',matchMode:'full',suffixes:[],preserveShort:true})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,locateDialogFieldByLabel,clearFieldSearch}=useDialogFieldSearch(bodyRef)
const {selectedKeys,reset}=useTableColumns('talent-region-match',talentTableColumns,talentDefaultColumns)
const visibleColumns=computed(()=>talentTableColumns.filter(column=>selectedKeys.value.includes(column.key)))
const results=ref([]),uniqueTotal=ref(0),matching=ref(false),matchError=ref(''),resultPage=ref(1),resultSize=ref(20),resultTable=ref(),appliedColumns=ref([]),appliedLabels=ref({})
const resultOrder=ref('source'),resultKeyword=ref(''),sourceFilters=reactive({}),appliedResultSearch=ref({keyword:'',columnFilters:{}})
const filteredResults=computed(()=>selectRegionMatchResults(results.value,appliedColumns.value,{...appliedResultSearch.value,order:resultOrder.value}))
const visibleResults=computed(()=>filteredResults.value.slice((resultPage.value-1)*resultSize.value,resultPage.value*resultSize.value))
let resultSearchTimer
function sourceFilterDefinition(index){return {key:`source_${index}`,label:appliedLabels.value[index],type:'text',placeholder:'搜索该来源列，空格分隔多个关键词',headerWidth:300}}
function applyResultFilters(){clearTimeout(resultSearchTimer);resultSearchTimer=null;appliedResultSearch.value={keyword:resultKeyword.value.trim(),columnFilters:Object.fromEntries(appliedColumns.value.map(index=>[index,String(sourceFilters[index]||'').trim()]))};resultPage.value=1}
function resultTextInput(value){clearTimeout(resultSearchTimer);if(!String(value||'').trim())return applyResultFilters();resultSearchTimer=setTimeout(applyResultFilters,400)}
function clearSourceFilter(index){delete sourceFilters[index];applyResultFilters()}
function clearResultSearch(){resultKeyword.value='';for(const key of Object.keys(sourceFilters))delete sourceFilters[key];applyResultFilters()}
function resetResultView(){clearResultSearch();resultOrder.value='source'}
let sourceFile=null,importController,importSequence=0,matchController,matchSequence=0,appliedPayload=null
const rowRequests=new Map()
const rowOverrides=ref({}),selectedResultRows=ref([]),rowEditor=ref()
const editColumns=computed(()=>appliedColumns.value.map(index=>({index,label:appliedLabels.value[index]})))
function editRows(rows){rowEditor.value.open(rows,rowOverrides.value)}
async function applyRowEdits(changes){const merged={...rowOverrides.value};for(const [index,values] of Object.entries(changes))merged[index]={...merged[index],...values};await runMatch(merged,true)}
function cancelRows(){for(const request of rowRequests.values())request.controller.abort();rowRequests.clear();for(const row of results.value)row.loading=false}
function invalidate(){selectedResultRows.value=[];resetResultView();matchController?.abort();matchSequence++;matching.value=false;cancelRows();results.value=[];uniqueTotal.value=0;appliedPayload=null;matchError.value=''}
function clearInput(){rowOverrides.value={};invalidate();settingsOpen.value=true;input.columns=[];input.rows=[];sourceColumns.value=[];for(const key of Object.keys(mapping))delete mapping[key]}
function restoreMatchDefaults(){
 targetFields.value=regionFields.map(field=>field.key)
 sourceColumns.value=input.columns.length?[input.columns[0].index]:[]
 for(const key of Object.keys(mapping))delete mapping[key]
 for(const index of sourceColumns.value)mapping[index]=[...targetFields.value]
 rowOverrides.value={}
 Object.assign(settings,{threshold:100,combine:'all',targetCombine:'any',matchMode:'full',suffixes:[],preserveShort:true})
 resultPage.value=1;appliedColumns.value=[];appliedLabels.value={}
 clearFieldSearch()
}
async function showMatchSettings(label){
 settingsOpen.value=true
 await nextTick()
 await locateDialogFieldByLabel(label)
}
async function resetMatchConditions(){
 if(importing.value||!input.rows.length)return
 invalidate();restoreMatchDefaults()
 await showMatchSettings('人才总库目标字段')
}
async function clearMatching(){
 importController?.abort();importSequence++;importing.value=false
 clearInput();sourceFile=null;sourceFileName.value='';fileDragDepth.value=0
 mode.value='file';pasteText.value='';sheet.value='';sheets.value=[];hasHeader.value=true;sourceError.value=''
 if(sourceFileInput.value)sourceFileInput.value.value=''
 restoreMatchDefaults()
 await showMatchSettings('上传区域表格')
}
function syncMappings(){for(const index of sourceColumns.value){const kept=(mapping[index]||[]).filter(field=>targetFields.value.includes(field));mapping[index]=kept.length?kept:[...targetFields.value]}}
watch(targetFields,syncMappings,{deep:true})
watch([sourceColumns,targetFields,mapping,settings],invalidate,{deep:true})
watch(pasteText,()=>{if(mode.value==='paste'){clearInput();sourceError.value=''}})
watch(mode,()=>{importController?.abort();importSequence++;importing.value=false;sourceFile=null;sourceFileName.value='';fileDragDepth.value=0;sheet.value='';sheets.value=[];sourceError.value='';hasHeader.value=mode.value==='file';clearInput()})
function applyInput(data){input.columns=data.columns;input.rows=data.rows;sourceColumns.value=data.columns.length?[0]:[];syncMappings()}
async function selectFile(file){if(!file)return;sourceFile=file;sourceFileName.value=file.name;sheet.value='';sheets.value=[];await readFile()}
async function chooseFile(event){const file=event.target.files?.[0];event.target.value='';await selectFile(file)}
function isFileDrag(event){const data=event.dataTransfer;return Array.from(data?.types||[]).includes('Files')||Array.from(data?.items||[]).some(item=>item.kind==='file')}
function enterFileDrag(event){if(isFileDrag(event))fileDragDepth.value++}
function overFileDrag(event){if(event.dataTransfer)event.dataTransfer.dropEffect=isFileDrag(event)?'copy':'none'}
function leaveFileDrag(){fileDragDepth.value=Math.max(0,fileDragDepth.value-1)}
async function dropFiles(event){
 fileDragDepth.value=0
 const data=event.dataTransfer,items=Array.from(data?.items||[]).filter(item=>item.kind==='file')
 if(items.some(item=>item.webkitGetAsEntry?.()?.isDirectory)){sourceError.value='请拖入表格文件，不支持文件夹';return}
 const files=Array.from(data?.files||[])
 if(!files.length)files.push(...items.map(item=>item.getAsFile?.()).filter(Boolean))
 if(files.length>1){sourceError.value='一次只能读取一个表格文件，请重新拖入';return}
 if(!files.length){sourceError.value='未收到可读取的文件。若从微信拖入失败，请先将文件保存到文件夹，再拖入此处';return}
 await selectFile(files[0])
}
async function readFile(){
 importController?.abort();const current=++importSequence;importing.value=false;clearInput();sourceError.value=''
 if(!sourceFile)return
 if(!/\.(xlsx|xlsm|csv|tsv)$/i.test(sourceFile.name)){sourceError.value='请选择.xlsx、.xlsm、CSV或TSV文件，旧版.xls请另存为.xlsx';return}
 if(sourceFile.size>10*1024*1024){sourceError.value='文件不能超过10MB';return}
 const controller=new AbortController();importController=controller;importing.value=true
 try{const data=await importTalentRegions(sourceFile,sheet.value,hasHeader.value,{signal:controller.signal});if(current!==importSequence)return;sheets.value=data.sheets;sheet.value=data.selected_sheet;applyInput(data)}
 catch(error){if(current===importSequence&&error.code!=='ERR_CANCELED')sourceError.value=error.detail||error.message||'文件读取失败'}
 finally{if(current===importSequence)importing.value=false}
}
function readPaste(){clearInput();sourceError.value='';try{applyInput(parsePastedRegions(pasteText.value,hasHeader.value))}catch(error){sourceError.value=error.message}}
function readSource(){if(mode.value==='file')void readFile();else readPaste()}
async function runMatch(overrides=rowOverrides.value,preserveView=false){
 // @click 传入的是事件；只有编辑器传入的对象才作为逐行覆盖。
 if(!preserveView)overrides=rowOverrides.value
 let payload
 try{payload=buildRegionPayload(input,sourceColumns.value,mapping,settings.threshold,settings.combine,settings.targetCombine,settings,overrides)}catch(error){matchError.value=error.message;return}
 if(!preserveView)invalidate();else{matchController?.abort();cancelRows();matchError.value=''}
 const current=++matchSequence;const controller=new AbortController();matchController=controller;matching.value=true
 const sourceRows=input.rows.map(row=>({sourceRow:row.source_row,values:[...row.values]}))
 try{
  const data=await matchTalentRegions(payload,{signal:controller.signal});if(current!==matchSequence)return
  rowOverrides.value=overrides;selectedResultRows.value=[];appliedPayload=payload;appliedColumns.value=[...sourceColumns.value];appliedLabels.value=Object.fromEntries(input.columns.map(column=>[column.index,column.label]))
  results.value=data.items.map(item=>({...sourceRows[item.index],index:item.index,matchValues:payload.rows[item.index].map(value=>prepareRegionSource(value,settings)),total:item.total,averageRate:item.averageRate,page:1,size:20,items:null,error:'',loading:false}));uniqueTotal.value=data.uniqueTotal;resultPage.value=1;settingsOpen.value=false
  if(preserveView)await nextTick().then(()=>resultTable.value?.clearSelection())
 }catch(error){if(current===matchSequence&&error.code!=='ERR_CANCELED')matchError.value=error.detail||error.message||'匹配失败，请重试'}
 finally{if(current===matchSequence)matching.value=false}
}
async function loadRow(row){
 if(!appliedPayload)return
 rowRequests.get(row.index)?.controller.abort();const controller=new AbortController(),marker={controller};rowRequests.set(row.index,marker);row.loading=true;row.error=''
 try{
  const data=await getRegionMatchPage({...appliedPayload,rows:[appliedPayload.rows[row.index]]},{skip:(row.page-1)*row.size,limit:row.size},{signal:controller.signal});if(rowRequests.get(row.index)!==marker)return
  const last=Math.max(1,Math.ceil(data.total/row.size));if(row.page>last){row.page=last;return await loadRow(row)}
  row.items=data.items;row.total=data.total;row.averageRate=data.averageRate
 }catch(error){if(rowRequests.get(row.index)===marker&&error.code!=='ERR_CANCELED')row.error=error.detail||error.message||'匹配人才加载失败'}
 finally{if(rowRequests.get(row.index)===marker){row.loading=false;rowRequests.delete(row.index)}}
}
function expanded(row,rows){if(rows.some(item=>item.index===row.index)){if(!row.items)void loadRow(row)}else{rowRequests.get(row.index)?.controller.abort();rowRequests.delete(row.index);row.loading=false}}
watch(visible,value=>{if(!value){if(resultSearchTimer)applyResultFilters();fileDragDepth.value=0;importController?.abort();importSequence++;importing.value=false;matchController?.abort();matchSequence++;matching.value=false;cancelRows()}})
onBeforeUnmount(()=>{clearTimeout(resultSearchTimer);importController?.abort();matchController?.abort();cancelRows()})
function open(){visible.value=true;clearFieldSearch()}
defineExpose({open})
</script>
<style>
.talent-region-match-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.talent-region-match-dialog>.el-dialog__header,.talent-region-match-dialog>.el-dialog__footer{flex-shrink:0}
.talent-region-match-dialog>.el-dialog__body{flex:1;min-height:0;overflow:auto;padding:10px 18px}
.talent-region-match-dialog>.el-dialog__footer{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;border-top:1px solid var(--el-border-color-light);padding:8px 18px;background:var(--el-fill-color-light)}
.region-match-settings>summary{cursor:pointer;font-weight:600;margin:0 0 10px}.region-match-settings .el-form-item{margin-bottom:12px}
.region-match-order.el-select{width:190px;margin-left:auto;flex-shrink:0}
.region-match-result-search{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:8px 0}.region-match-result-search>.muted{margin-right:auto}.region-match-result-search>.el-input{width:340px;max-width:100%}
.region-match-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 16px}.region-match-grid .el-select{width:100%}
.region-match-grid .el-slider{margin:0 16px 22px;width:calc(100% - 32px)}
.region-match-source{display:flex;gap:16px;flex-wrap:wrap}.region-match-source small{display:block;width:100%;color:var(--el-text-color-secondary)}
.region-match-source>.el-form-item{max-width:100%;min-width:0}.region-file-dropzone{box-sizing:border-box;width:100%;padding:16px;border:1px dashed var(--el-border-color);border-radius:8px;transition:border-color .15s,background-color .15s}.region-file-dropzone.is-dragover{border-color:var(--el-color-primary);background:var(--el-color-primary-light-9)}.region-file-dropzone input{max-width:100%}.region-file-drop-hint{margin:10px 0 0;color:var(--el-text-color-secondary);font-size:13px;line-height:1.6}.region-file-name{margin:8px 0 0;font-size:13px;overflow-wrap:anywhere;color:var(--el-text-color-primary)}
.region-match-toolbar,.region-match-paging{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}.region-match-expanded{padding:10px 12px;background:var(--el-fill-color-lighter)}
.talent-region-match-dialog .muted{font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}.region-match-paging .el-pagination{max-width:100%;overflow:auto}
@media(max-width:760px){.region-match-grid{grid-template-columns:1fr}.talent-region-match-dialog>.el-dialog__footer{justify-content:flex-end}}
</style>
