<template>
  <DraggableFormDialog :model-value="true" title="开发笔记" width="min(1440px, calc(100vw - 32px))" top="4vh" append-to-body :close-on-click-modal="false" :before-close="close" @update:model-value="value=>{if(!value)close()}">
    <p class="development-notes-hint">仅赵震锋、黄运坚可查看。各自编辑自己的区域；支持多个编辑框、截图和附件，每次保存保留历史版本与时间。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
    <div v-loading="loading" class="development-notes-columns">
      <section v-for="owner in owners" :key="owner.id" :aria-label="owner.name+'的开发笔记'">
        <header><strong>{{owner.name}}</strong><el-tag size="small" :type="owner.can_edit?'primary':'info'">{{owner.can_edit?'我的区域':'只读区域'}}</el-tag><el-button v-if="owner.can_edit" type="primary" plain size="small" :disabled="busyIds.size>0||adding" @click="add(owner)">增加编辑框</el-button></header>
        <el-empty v-if="!owner.blocks.length" description="暂无笔记" :image-size="60" />
        <DevelopmentNoteEditor v-for="note in owner.blocks" :key="note.id" :note="note" :editable="owner.can_edit" @saved="value=>Object.assign(note,value)" @busy="value=>setBusy(note.id,value)" />
      </section>
    </div>
    <template #footer><span class="development-notes-hint">保存时间统一为香港时间（UTC+8）；关闭后保留未保存草稿。</span><el-button :disabled="busyIds.size>0||adding" @click="close()">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import DevelopmentNoteEditor from './DevelopmentNoteEditor.vue'
const emit=defineEmits(['close'])
const owners=ref([]),loading=ref(false),adding=ref(false),error=ref(''),busyIds=ref(new Set())
let addRequest,controller
function setBusy(id,value){const set=new Set(busyIds.value);if(value)set.add(id);else set.delete(id);busyIds.value=set}
async function load(){controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{owners.value=(await api.get('/development-notes',{signal:controller.signal})).owners}catch(e){if(e.code!=='ERR_CANCELED')error.value=e.detail||'开发笔记加载失败'}finally{loading.value=false}}
async function add(owner){if(adding.value)return;adding.value=true;error.value='';addRequest||=crypto.randomUUID();try{const note=await api.post('/development-notes/blocks',{request_id:addRequest});owner.blocks.push(note);addRequest=undefined}catch(e){error.value=e.detail||'增加编辑框失败'}finally{adding.value=false}}
function close(done){if(busyIds.value.size||adding.value){ElMessage.warning('正在保存或上传，请稍候');return}if(typeof done==='function')done();emit('close')}
onMounted(load)
onBeforeUnmount(()=>controller?.abort())
</script>
<style scoped>
.development-notes-hint{font-size:12px;color:#64748b;line-height:1.8}.development-notes-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;align-items:start}.development-notes-columns>section{min-width:0;padding:12px;background:#f5f8fc;border-radius:10px}.development-notes-columns>section>header{display:flex;align-items:center;gap:8px;flex-wrap:wrap;position:sticky;top:0;background:#f5f8fc;z-index:1;padding:6px 0}.development-notes-columns>section>header>.el-button{margin-left:auto}@media(max-width:1000px){.development-notes-columns{grid-template-columns:minmax(0,1fr)}}
</style>
