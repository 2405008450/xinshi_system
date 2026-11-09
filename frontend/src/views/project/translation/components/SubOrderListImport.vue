<template>
  <section class="suborder-list-import">
    <el-alert title="可直接粘贴从 TXT、Word、Excel、可编辑 PDF 复制的内容，也可选择文件。每行一个文件名；带路径的表格请指定对应列，再分析层级。" type="info" :closable="false" />
    <div class="import-actions"><el-button :loading="parsing" @click="picker.click()">选择文件</el-button><span>{{ fileName || '支持 .txt、.docx、.pdf、.xlsx、.xls；不超过20MB' }}</span><input ref="picker" type="file" accept=".txt,.docx,.pdf,.xlsx,.xls" hidden @change="readFile" /></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm label-position="top" :model="mapping">
      <el-form-item v-if="sheets.length" label="工作表"><el-select v-model="sheetIndex" style="width:100%"><el-option v-for="(sheet,index) in sheets" :key="index" :value="index" :label="sheet.name" /></el-select></el-form-item>
      <el-form-item v-else label="复制/粘贴内容"><el-input v-model="text" type="textarea" :rows="7" placeholder="每行一个文件名，或直接粘贴 Excel 表格；也可粘贴完整文件路径" /></el-form-item>
      <el-row :gutter="16">
        <el-col :xs="24" :md="8"><el-form-item label="路径列"><el-select v-model="mapping.pathColumn" style="width:100%"><el-option label="不单独指定（仅文件名或完整路径）" :value="-1" /><el-option v-for="column in columns" :key="column.index" :value="column.index" :label="column.label" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="8"><el-form-item label="文件名列"><el-select v-model="mapping.filenameColumn" style="width:100%"><el-option label="从路径中提取" :value="-1" /><el-option v-for="column in columns" :key="column.index" :value="column.index" :label="column.label" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="8"><el-form-item label="从第几行开始"><el-input-number v-model="mapping.startRow" :min="1" :max="5000" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="根路径（可留空自动识别）"><el-input v-model="mapping.rootPath" clearable placeholder="例如 D:\客户资料；相对路径清单需填写完整根路径" /><small>根路径对应母订单，可调整根路径以改变分级起点。此方式只解析清单，不读取路径中的实际文件。</small></el-form-item>
    </AppForm>
    <el-table v-if="rows.length" :data="rows.slice(0,20).map((cells,index)=>({cells,line:index+1}))" border max-height="260" size="small">
      <el-table-column prop="line" label="原行号" width="72" /><el-table-column v-for="column in columns" :key="column.index" :label="column.letter" min-width="180"><template #default="{row}">{{ row.cells[column.index] || '' }}</template></el-table-column>
    </el-table>
    <p v-if="rows.length">共 {{ rows.length }} 行，原始内容预览最多显示20行。</p>
    <el-button type="primary" :loading="analyzing" :disabled="!rows.length || parsing" @click="analyze">分析文件与路径层级</el-button>
    <template v-if="plan">
      <el-alert v-for="warning in plan.warnings || []" :key="warning" :title="warning" type="warning" :closable="false" />
      <el-alert v-if="plan.kind==='tree'" :title="`识别根路径：${plan.rootPath}。根目录作为母订单；确认导入后，母订单项目名称调整为根目录名。`" type="info" :closable="false" />
      <p>预览将生成 {{ plan.orderCount }} 个子订单<template v-if="plan.emptyFolders?.length">；{{ plan.emptyFolders.length }} 个空文件夹仅记录，不生成订单</template>。</p>
      <el-table :data="previewRows" border max-height="360" size="small">
        <el-table-column prop="levelLabel" label="层级" width="120" /><el-table-column label="文件/文件夹名称" min-width="220"><template #default="{row}"><span :style="{paddingLeft:row.level*12+'px'}">{{ row.name }}</span></template></el-table-column><el-table-column prop="kind" label="类型" width="130" /><el-table-column prop="path" label="完整路径" min-width="300" />
      </el-table>
    </template>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {parseSubOrderListFile,previewSubOrderList} from '@/api/subOrders'
import {folderOrderPreview} from '@/utils/localSubOrderFiles'
const emit=defineEmits(['plan'])
const picker=ref(null),text=ref(''),sheets=ref([]),sheetIndex=ref(0),fileName=ref(''),parsing=ref(false),analyzing=ref(false),error=ref(''),plan=ref(null)
const mapping=reactive({pathColumn:-1,filenameColumn:0,startRow:1,rootPath:''})
let parseId=0,previewId=0,parseController,previewController
const rows=computed(()=>sheets.value.length?sheets.value[sheetIndex.value]?.rows||[]:text.value.replace(/\r\n?/g,'\n').split('\n').map(line=>line.split('\t')).filter(cells=>cells.some(value=>value.trim())))
const letter=index=>{let result='';for(let n=index+1;n>0;n=Math.floor((n-1)/26))result=String.fromCharCode(65+(n-1)%26)+result;return result}
const columns=computed(()=>Array.from({length:Math.min(64,Math.max(1,...rows.value.slice(0,30).map(row=>row.length)))},(_,index)=>({index,letter:letter(index),label:letter(index)+' 列'+(rows.value[mapping.startRow-2]?.[index]?' · '+rows.value[mapping.startRow-2][index].slice(0,50):'')})))
function invalidate(){previewId++;previewController?.abort();analyzing.value=false;plan.value=null;emit('plan',null)}
function guess(){
 mapping.pathColumn=-1;mapping.filenameColumn=0;mapping.startRow=1
 for(const [index,row] of rows.value.slice(0,10).entries()){
  const name=row.findIndex(cell=>/^(文件名|文件名称|项目名称)$/.test(cell.trim()))
  let path=row.findIndex(cell=>/^(完整路径|文件完整路径|文件路径|路径)$/.test(cell.trim()))
  if(path<0)path=row.findIndex(cell=>cell.trim()==='相对路径')
  if(name>=0||path>=0){mapping.filenameColumn=name;mapping.pathColumn=path;mapping.startRow=index+2;return}
 }
}
watch([text,sheetIndex],()=>{invalidate();guess()})
watch(()=>[mapping.pathColumn,mapping.filenameColumn,mapping.startRow,mapping.rootPath],invalidate)
async function readFile(event){
 const file=event.target.files?.[0];event.target.value='';if(!file)return
 parseController?.abort();previewController?.abort();const current=++parseId;parseController=new AbortController();parsing.value=true;error.value='';invalidate()
 try{
  const result=await parseSubOrderListFile(file,{signal:parseController.signal})
  if(current!==parseId)return
  fileName.value=file.name;sheets.value=result.sheets||[];sheetIndex.value=0;text.value=result.text||'';guess()
 }catch(e){if(current===parseId&&e.code!=='ERR_CANCELED'){error.value=e.detail||e.message||'读取清单失败';sheets.value=[];text.value='';fileName.value=''}}
 finally{if(current===parseId)parsing.value=false}
}
async function analyze(){
 invalidate();const current=previewId;previewController=new AbortController();analyzing.value=true;error.value=''
 try{const result=await previewSubOrderList({rows:rows.value,...mapping},{signal:previewController.signal});if(current!==previewId)return;plan.value=result;emit('plan',result)}
 catch(e){if(current===previewId&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'清单分析失败'}
 finally{if(current===previewId)analyzing.value=false}
}
const previewRows=computed(()=>plan.value?.kind==='tree'?folderOrderPreview(plan.value.entries,plan.value.rootPath).map(row=>({...row,levelLabel:row.level===0?'母订单':row.level+'级子订单'})):(plan.value?.fileNames||[]).map(name=>({name,level:1,levelLabel:'一级子订单',kind:'文件',path:'-'})))
onBeforeUnmount(()=>{parseId++;previewId++;parseController?.abort();previewController?.abort()})
</script>
<style scoped>
.import-actions{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:12px 0}.import-actions span,small{font-size:12px;color:#64748b}.suborder-list-import .el-alert{margin:10px 0}.suborder-list-import p{font-size:13px}
</style>
