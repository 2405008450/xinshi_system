<template>
  <div class="statement-file-export" @pointerdown.stop>
    <el-select v-model="format" aria-label="对账单文件格式" style="width:105px" @change="clear"><el-option label="PDF" value="pdf" /><el-option label="Excel" value="excel" /></el-select>
    <el-button :loading="busy" :disabled="disabled" @click="prepare">准备拖出文件</el-button>
    <template v-if="file">
      <span class="statement-file" draggable="true" :title="`拖动 ${file.name} 到文件夹、微信或邮箱附件区`" @dragstart="drag">📄 {{file.name}}</span>
      <el-button v-if="file.url" link @click="download">下载文件</el-button><el-button v-if="folderSave&&file.blob" link @click="saveToFolder">另存到文件夹</el-button>
    </template>
    <span v-if="file" class="statement-file-hint">拖出的是文件；目标不接收时可先下载再拖动。</span>
  </div>
</template>
<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {exportStatementWorkspace,exportStatementWorkspacePdf} from '@/api/customerStatements'
import {statementFileStem,statementFileName} from '@/utils/statementFormatting'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:String,boardId:String,revision:Number,mode:String,name:String,disabled:Boolean,printHtml:Function})
const nativePdf=!!window.xinshiDesktop?.prepareStatementPdf,folderSave=typeof window.showSaveFilePicker==='function'
const format=ref(nativePdf?'pdf':'excel'),file=ref(null),busy=ref(false)
let generation=0
function clear(){generation++;if(file.value?.url)URL.revokeObjectURL(file.value.url);file.value=null}
async function prepare(){
  clear();const seq=generation;busy.value=true
  try{
    const name=statementFileStem(props.name)
    if(format.value==='pdf'){
      // 与“下载 PDF”使用同一文件，避免桌面端再次按 HTML 生成另一种排版。
      const blob=await exportStatementWorkspacePdf(props.clientId,{board_ids:[props.boardId],revision:props.revision,mode:props.mode})
      let native=null
      if(window.xinshiDesktop?.prepareStatementFile){
        try{native=await window.xinshiDesktop.prepareStatementFile({name,format:'pdf',base64:await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)})})}catch{/* 旧桌面端不支持PDF令牌时保留标准文件拖出与下载。 */}
      }
      if(seq===generation)file.value={name:statementFileName(name,'pdf'),token:native?.name?.endsWith('.pdf')?native.token:undefined,blob,url:URL.createObjectURL(blob),mime:'application/pdf'}
    }else{
      const blob=await exportStatementWorkspace(props.clientId,{board_ids:[props.boardId],revision:props.revision,mode:props.mode})
      const native=window.xinshiDesktop?.prepareStatementFile?await window.xinshiDesktop.prepareStatementFile({name,base64:await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)})}):null
      if(seq===generation)file.value={name:native?.name||statementFileName(name,'excel'),token:native?.token,blob,url:URL.createObjectURL(blob),mime:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    }
  }catch(e){if(seq===generation)ElMessage.error(getLocalizedErrorMessage(e,'对账单文件准备失败'))}
  finally{busy.value=false}
}
function drag(event){
  event.stopPropagation();if(!file.value){event.preventDefault();return}
  if(file.value.token&&window.xinshiDesktop?.dragStatementFile){event.preventDefault();window.xinshiDesktop.dragStatementFile(file.value.token);return}
  event.dataTransfer.effectAllowed='copy';event.dataTransfer.setData('DownloadURL',`${file.value.mime}:${file.value.name}:${file.value.url}`)
  if(file.value.blob)event.dataTransfer.items.add(new File([file.value.blob],file.value.name,{type:file.value.mime}))
}
function download(){if(!file.value?.url){ElMessage.info('PDF文件已准备好，可拖到目标文件夹保存');return}const a=document.createElement('a');a.href=file.value.url;a.download=file.value.name;a.click()}
async function saveToFolder(){
  if(!file.value?.blob)return
  try{const handle=await window.showSaveFilePicker({suggestedName:file.value.name,types:[{description:file.value.mime==='application/pdf'?'PDF对账单':'Excel对账单',accept:{[file.value.mime]:[file.value.mime==='application/pdf'?'.pdf':'.xlsx']}}]});const stream=await handle.createWritable();await stream.write(file.value.blob);await stream.close();ElMessage.success('对账单文件已保存')}
  catch(e){if(e.name!=='AbortError')ElMessage.error('文件保存失败')}
}
watch(()=>[props.clientId,props.boardId,props.revision,props.mode],clear)
onBeforeUnmount(clear)
</script>
<style scoped>
.statement-file-export{display:flex;align-items:center;gap:8px;flex-wrap:wrap;width:100%}.statement-file{border:1px solid var(--el-color-primary-light-5);background:var(--el-color-primary-light-9);border-radius:5px;padding:5px 8px;cursor:grab;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.statement-file:active{cursor:grabbing}.statement-file-hint{font-size:11px;color:var(--el-text-color-secondary)}
</style>
