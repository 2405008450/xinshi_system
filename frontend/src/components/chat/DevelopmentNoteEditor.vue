<template>
  <article class="development-note-editor" :aria-label="note.title" :data-unsaved-section="draft.title||'开发笔记'" data-auto-draft="off">
    <header>
      <el-input v-if="editable" v-model="draft.title" data-unsaved-field="title" data-unsaved-label="笔记标题" maxlength="200" aria-label="开发笔记标题" :disabled="saving" />
      <strong v-else>{{ note.title }}</strong>
      <el-button :disabled="saving" @click="openHistory">保存历史</el-button>
    </header>
    <template v-if="editable">
      <RichTextComposer :key="editorGeneration" ref="composer" v-model="draft.document" data-unsaved-field="document" data-unsaved-label="笔记正文" format-colors :image-api="imageApi" :image-section-id="note.id" :disabled="saving||uploading" placeholder="记录开发事项，可粘贴截图并在图片前后填写说明" min-height="180px" @uploading-change="value=>{imageUploading=value;emit('busy',value)}" />
      <div class="development-note-actions">
        <el-button :disabled="saving||uploading||imageUploading" @click="fileInput.click()">上传文件</el-button>
        <input ref="fileInput" type="file" multiple hidden @change="chooseFiles" />
        <el-button type="primary" :loading="saving" :disabled="uploading||imageUploading" @click="save">保存笔记</el-button>
      </div>
    </template>
    <RichTextContent v-else :document="note.document" :image-api="imageApi" />
    <ul class="development-note-files"><li v-for="file in shownFiles" :key="file.id"><el-button link type="primary" @click="download(file.id,file.filename)">{{ file.filename }}</el-button><span>{{ Math.max(1,Math.ceil(file.size/1024)) }} KB</span><el-button v-if="editable" link type="danger" :disabled="saving" @click="removeFile(file.id)">移除</el-button></li></ul>
    <footer aria-live="polite">{{ uploading?'文件上传中…':note.saved_at?'最近保存：'+formatTime(note.saved_at)+' · 第'+note.revision+'版':'尚未保存正文' }}<span v-if="editable"> · 未保存修改自动保留草稿</span></footer>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <DraggableFormDialog v-model="historyVisible" title="开发笔记 · 保存历史" width="min(850px, calc(100vw - 32px))" append-to-body>
      <el-alert v-if="historyError" :title="historyError" type="error" :closable="false" />
      <div v-loading="historyLoading" class="development-note-history">
        <el-empty v-if="!historyLoading&&!history.length" description="暂无保存记录" :image-size="64" />
        <section v-for="entry in history" :key="entry.revision"><header><strong>第{{ entry.revision }}版 · {{ entry.title }}</strong><span>{{ entry.saved_by }} · {{ formatTime(entry.saved_at) }}</span></header><RichTextContent :document="entry.document" :image-api="imageApi" /><el-button v-for="(id,i) in entry.attachment_ids" :key="id" link type="primary" @click="download(id,entry.files?.find(file=>file.id===id)?.filename||'笔记附件')">{{entry.files?.find(file=>file.id===id)?.filename||'下载附件 '+(i+1)}}</el-button></section>
      </div>
      <template #footer><el-button v-if="history.length<historyTotal" :loading="historyLoading" @click="loadHistory(true)">加载更多</el-button><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </article>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { useFormDraft } from '@/composables/useFormDraft'
import { formatBusinessDateTime as formatTime } from '@/utils/dateTime'
const props=defineProps({note:{type:Object,required:true},editable:Boolean})
const emit=defineEmits(['saved','busy'])
const draft=reactive(JSON.parse(JSON.stringify(props.note)))
const saving=ref(false),uploading=ref(false),imageUploading=ref(false),error=ref(''),composer=ref(),fileInput=ref(),editorGeneration=ref(0)
const historyVisible=ref(false),history=ref([]),historyTotal=ref(0),historyLoading=ref(false),historyError=ref('')
let saveAttempt,disposed=false
const clone=value=>JSON.parse(JSON.stringify(value))
const {beginDraft,clearDraft,startFreshDraft}=useFormDraft({namespace:'development-note',form:draft,createDefault:()=>clone(props.note),
  applyDraft:value=>{if(value.id===props.note.id&&value.owner_id===props.note.owner_id){const revision=draft.revision;Object.assign(draft,value,{revision:Math.min(value.revision,revision)})}},
  validateDraft:value=>value.form?.id===props.note.id&&value.form.owner_id===props.note.owner_id})
const shownFiles=computed(()=>props.editable?(draft.files||[]).filter(file=>draft.attachment_ids.includes(file.id)):props.note.files||[])
async function upload(file){
  if(file.size>20*1024*1024)throw new Error('单个文件最多20MB')
  const data=new FormData();data.append('file',file)
  return api.post(`/development-notes/blocks/${props.note.id}/files`,data,{timeout:120000,headers:{'Content-Type':'multipart/form-data'}})
}
const imageApi={
  async upload(_section,file){const result=await upload(file);if(!result.content_type.startsWith('image/'))throw new Error('请选择有效的PNG、JPEG或WebP图片');return result},
  read(src,signal){if(!/^\/api\/development-notes\/files\/[0-9a-f-]{36}$/.test(src))throw new Error('截图地址无效');return api.get(src.slice(4),{responseType:'blob',signal})},
  async removeDraft(){}
}
async function chooseFiles(event){
  const files=[...event.target.files];event.target.value='';uploading.value=true;emit('busy',true);error.value=''
  try{for(const file of files){const result=await upload(file);draft.files.push(result);draft.attachment_ids.push(result.id)}}catch(e){error.value=e.detail||e.message||'文件上传失败'}finally{uploading.value=false;emit('busy',false)}
}
function removeFile(id){draft.attachment_ids=draft.attachment_ids.filter(value=>value!==id)}
async function download(id,filename){
  try{const blob=await api.get(`/development-notes/files/${id}`,{responseType:'blob'});if(disposed)return;const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){ElMessage.error(e.detail||'下载失败')}
}
async function save(){
  if(saving.value||uploading.value||imageUploading.value)return
  if(!draft.title.trim()){error.value='请填写笔记标题';return}
  saving.value=true;emit('busy',true);error.value=''
  const values={revision:draft.revision,title:draft.title,document:clone(draft.document),attachment_ids:[...draft.attachment_ids]}
  const signature=JSON.stringify(values)
  if(saveAttempt?.signature!==signature)saveAttempt={signature,id:crypto.randomUUID()}
  try{const result=await api.put(`/development-notes/blocks/${props.note.id}`,{...values,request_id:saveAttempt.id});await composer.value?.markImagesSaved(result.document);clearDraft();Object.assign(draft,result);emit('saved',result);saveAttempt=undefined;startFreshDraft(`edit:${props.note.id}`);ElMessage.success('笔记已保存，已记录保存时间')}catch(e){error.value=e.detail||'保存失败，当前内容保留。若版本冲突，请先复制当前内容再重新打开核对'}finally{saving.value=false;emit('busy',false)}
}
async function openHistory(){history.value=[];historyVisible.value=true;await loadHistory()}
async function loadHistory(more=false){historyLoading.value=true;historyError.value='';try{const result=await api.get(`/development-notes/blocks/${props.note.id}/history`,{params:{skip:more?history.value.length:0,limit:20}});history.value=more?[...history.value,...result.items]:result.items;historyTotal.value=result.total}catch(e){historyError.value=e.detail||'历史读取失败'}finally{historyLoading.value=false}}
onMounted(async()=>{if(props.editable){await beginDraft(`edit:${props.note.id}`);await nextTick();editorGeneration.value++}})
onBeforeUnmount(()=>{disposed=true})
</script>
<style scoped>
.development-note-editor{border:1px solid #dce4ed;border-radius:10px;padding:14px;margin-top:12px;min-width:0;background:#fff}.development-note-editor>header{display:flex;align-items:center;gap:8px;margin-bottom:12px}.development-note-editor>header>.el-input{flex:1;min-width:0}.development-note-editor>header>strong{flex:1;overflow-wrap:anywhere}.development-note-actions{display:flex;justify-content:flex-end;gap:8px;margin:12px 0}.development-note-actions .el-button{margin:0}.development-note-editor>footer{font-size:12px;color:#64748b;line-height:1.8}.development-note-files{padding:0;list-style:none}.development-note-files li{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.development-note-files .el-button{white-space:normal;overflow-wrap:anywhere}.development-note-history section{padding:12px 0;border-bottom:1px solid #e2e8f0}.development-note-history header{display:flex;flex-direction:column;gap:5px;margin-bottom:10px}.development-note-history header span{font-size:12px;color:#64748b}.development-note-editor :deep(.rich-editor__toolbar){gap:4px;flex-wrap:wrap;min-width:0}.development-note-editor :deep(.rich-editor__content){max-height:460px;overflow:auto}
</style>
