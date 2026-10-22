<template>
  <div class="annotation-task-images" @paste="paste">
    <slot />
    <div class="task-image-tools"><label>添加截图<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple :disabled="disabled||uploading" aria-label="上传具体任务截图" @change="select" /></label><small>可在任务框粘贴截图；最多9张，每张10MB。</small></div>
    <div class="task-image-grid"><div v-for="item in items" :key="item.id" class="task-image-item"><el-image v-if="urls[item.id]" :src="urls[item.id]" :preview-src-list="Object.values(urls)" preview-teleported fit="cover" /><span>{{ item.originalName }}</span><el-button v-if="!disabled" link type="danger" @click="remove(item.id)">移除</el-button></div></div>
    <p v-if="uploading">正在上传截图…</p><el-alert v-if="error" :title="error" type="error" @close="error=''" />
  </div>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
import { uploadMaterial } from '@/api/annotationMaterials'
const props=defineProps({projectId:String,active:Boolean,disabled:Boolean})
const ids=defineModel({type:Array,default:()=>[]}),items=ref([]),urls=ref({}),uploading=ref(false),error=ref('')
let generation=0
function clear(){Object.values(urls.value).forEach(URL.revokeObjectURL);urls.value={};items.value=[]}
async function load(){const current=++generation;clear();error.value='';if(!props.active)return;if(!props.projectId){items.value=ids.value.map(id=>({id,originalName:'已暂存截图（保存后可重新预览）'}));return}
  try{const rows=await api.get(`/projects/annotation/${props.projectId}/task-images`);if(current!==generation)return;items.value=rows
    for(const row of rows){const blob=await api.get(`/projects/annotation/${props.projectId}/materials/${row.fileId}/versions/${row.versionId}/download`,{responseType:'blob'});if(current!==generation)return;urls.value[row.id]=URL.createObjectURL(new Blob([blob],{type:row.contentType}))}
  }catch(e){if(current===generation)error.value=e.detail||'截图加载失败'}
}
async function add(files){if(props.disabled||uploading.value)return;error.value='';uploading.value=true;const current=generation
  try{for(const file of files){if(ids.value.length>=9)throw new Error('最多添加9张截图');if(!['image/png','image/jpeg','image/gif','image/webp'].includes(file.type)||file.size>10*1024*1024)throw new Error('仅支持10MB以内的 PNG、JPEG、GIF、WebP 截图')
      const row=await uploadMaterial(file);if(current!==generation)return;items.value.push({id:row.id,originalName:file.name});urls.value[row.id]=URL.createObjectURL(file);ids.value=[...ids.value,row.id]}
  }catch(e){error.value=e.detail||e.message||'截图上传失败'}finally{uploading.value=false}
}
function select(event){void add(Array.from(event.target.files||[]));event.target.value=''}
function paste(event){const files=Array.from(event.clipboardData?.files||[]).filter(file=>file.type.startsWith('image/'));if(files.length){event.preventDefault();void add(files)}}
function remove(id){ids.value=ids.value.filter(uid=>uid!==id);items.value=items.value.filter(row=>row.id!==id);if(urls.value[id])URL.revokeObjectURL(urls.value[id]);delete urls.value[id]}
watch(()=>[props.projectId,props.active],load,{immediate:true})
watch(ids,value=>{items.value=items.value.filter(row=>value.includes(row.id));for(const id of value)if(!items.value.some(row=>row.id===id))items.value.push({id,originalName:'已暂存截图（保存后可重新预览）'})})
onBeforeUnmount(()=>{++generation;clear()})
defineExpose({validate:()=>!uploading.value&&!error.value})
</script>
<style scoped>.annotation-task-images{width:100%}.task-image-tools{display:flex;align-items:center;gap:12px;margin:8px 0;color:#64748b}.task-image-tools label{color:var(--el-color-primary);cursor:pointer}.task-image-tools input{display:none}.task-image-grid{display:flex;flex-wrap:wrap;gap:10px}.task-image-item{display:flex;flex-direction:column;width:110px;gap:4px;font-size:11px;overflow-wrap:anywhere}.task-image-item .el-image{width:110px;height:80px;border:1px solid #e2e8f0;border-radius:6px}.task-image-tools small{font-size:11px}</style>
