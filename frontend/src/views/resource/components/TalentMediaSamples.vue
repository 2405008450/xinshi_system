<template>
  <div class="talent-media-samples">
    <el-upload v-if="editable" :file-list="pending" :auto-upload="false" :disabled="files.length>=10" multiple :accept="sampleAccept" :limit="Math.max(0,10-files.length)" :on-change="checkFile" :on-exceed="exceed" @update:file-list="$emit('update:pending',$event)">
      <el-button :disabled="files.length>=10">上传样音</el-button>
      <template #tip><div class="el-upload__tip">支持 MP3、WAV、FLAC、M4A、MP4、MOV、MKV 等音视频，单个≤200MB，每个区域最多10个；保存后上传。</div></template>
    </el-upload>
    <div v-for="file in files" :key="file.id" class="media-sample-row">
      <span class="media-sample-name">{{ file.originalName }}</span><span class="media-sample-size">{{ sizeLabel(file.fileSize) }}</span>
      <el-button type="primary" link @click="preview(file)">播放预览</el-button>
      <el-button type="primary" link :loading="!!downloading[file.id]" @click="download(file)">下载</el-button>
      <el-button v-if="editable" type="danger" link @click="$emit('remove',file)">移除</el-button>
    </div>
    <span v-if="!editable&&!files.length" class="media-sample-empty">暂无样音</span>
    <DraggableFormDialog v-model="previewVisible" width="min(900px,calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close @closed="clearPreview">
      <template #header><span class="media-preview-title" @mousedown.stop>{{ previewFile?.originalName || '样音预览' }}</span></template>
      <div v-loading="loading" class="media-preview-content">
        <video v-if="previewUrl&&sampleIsVideo(previewFile?.originalName)" :src="previewUrl" controls preload="metadata" @error="playbackError=true" />
        <audio v-else-if="previewUrl" :src="previewUrl" controls preload="metadata" @error="playbackError=true" />
        <el-alert v-if="playbackError" title="当前浏览器无法播放此格式或编码，可下载后使用本地播放器打开。" type="info" :closable="false" />
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </div>
      <template #footer><el-button :loading="!!downloading[previewFile?.id]" @click="download(previewFile)">下载文件</el-button><el-button @click="previewVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import { computed,onBeforeUnmount,reactive,ref } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getTalentAttachmentBlob } from '@/api/talents'
import { sampleAccept,sampleIsVideo,validSample } from '@/utils/talentMediaSamples'
const props=defineProps({personId:String,category:{type:String,required:true},attachments:{type:Array,default:()=>[]},pending:{type:Array,default:()=>[]},editable:Boolean})
const emit=defineEmits(['update:pending','remove'])
const files=computed(()=>props.attachments.filter(file=>file.category===props.category))
const downloading=reactive({}),previewVisible=ref(false),previewFile=ref(null),previewUrl=ref(''),loading=ref(false),error=ref(''),playbackError=ref(false)
let controller
const sizeLabel=value=>value==null?'':value<1024*1024?`${(value/1024).toFixed(1)} KB`:`${(value/1024/1024).toFixed(1)} MB`
function checkFile(file,rows){if(file.raw&&!validSample(file.raw)){emit('update:pending',rows.filter(row=>row.uid!==file.uid));ElMessage.warning('请选择非空且不超过200MB的音频或视频文件')}}
function exceed(){ElMessage.warning('每个区域最多保存10个样音文件')}
function clearPreview(){controller?.abort();if(previewUrl.value)URL.revokeObjectURL(previewUrl.value);previewUrl.value='';previewFile.value=null}
async function preview(file){clearPreview();previewFile.value=file;previewVisible.value=true;loading.value=true;error.value='';playbackError.value=false;controller=new AbortController();const request=controller;try{const blob=await getTalentAttachmentBlob(props.personId,file.id,{signal:request.signal,timeout:300000});if(!request.signal.aborted)previewUrl.value=URL.createObjectURL(blob)}catch(failure){if(failure.code!=='ERR_CANCELED')error.value=failure.detail||'样音加载失败，请重试'}finally{if(request===controller)loading.value=false}}
async function download(file){if(!file||downloading[file.id])return;downloading[file.id]=true;try{const blob=await getTalentAttachmentBlob(props.personId,file.id,{timeout:300000});const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=file.originalName;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}catch(failure){ElMessage.error(failure.detail||'下载失败')}finally{delete downloading[file.id]}}
onBeforeUnmount(clearPreview)
</script>
<style scoped>
.talent-media-samples{width:100%;margin:10px 0 16px}.media-sample-row{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:8px 0;border-bottom:1px solid var(--el-border-color-lighter)}
.media-sample-name{overflow-wrap:anywhere;min-width:0}.media-sample-size,.media-sample-empty{color:var(--el-text-color-secondary);font-size:12px}.media-preview-title{user-select:text;cursor:text;overflow-wrap:anywhere}
.media-preview-content{min-height:100px;max-height:65vh;overflow:auto}.media-preview-content video{display:block;width:100%;max-height:55vh}.media-preview-content audio{width:100%}
</style>
