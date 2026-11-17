<template>
  <div class="annotation-task-images">
    <slot />
    <div class="task-image-grid"><div v-for="item in items" :key="item.id" class="task-image-item"><el-image v-if="urls[item.id]" :src="urls[item.id]" :preview-src-list="Object.values(urls)" preview-teleported fit="cover" /><span>{{ item.originalName }}</span><el-button v-if="!disabled" link type="danger" @click="remove(item.id)">移除</el-button></div></div>
    <el-alert v-if="error" :title="error" type="error" @close="error=''" />
  </div>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
const props=defineProps({projectId:String,active:Boolean,disabled:Boolean})
const ids=defineModel({type:Array,default:()=>[]}),items=ref([]),urls=ref({}),error=ref('')
let generation=0
function clear(){Object.values(urls.value).forEach(URL.revokeObjectURL);urls.value={};items.value=[]}
async function load(){const current=++generation;clear();error.value='';if(!props.active)return;if(!props.projectId){items.value=ids.value.map(id=>({id,originalName:'已暂存截图（保存后可重新预览）'}));return}
  try{const rows=await api.get(`/projects/annotation/${props.projectId}/task-images`);if(current!==generation)return;items.value=rows
    for(const row of rows){const blob=await api.get(`/projects/annotation/${props.projectId}/materials/${row.fileId}/versions/${row.versionId}/download`,{responseType:'blob'});if(current!==generation)return;urls.value[row.id]=URL.createObjectURL(new Blob([blob],{type:row.contentType}))}
  }catch(e){if(current===generation)error.value=e.detail||'截图加载失败'}
}
function remove(id){ids.value=ids.value.filter(uid=>uid!==id);items.value=items.value.filter(row=>row.id!==id);if(urls.value[id])URL.revokeObjectURL(urls.value[id]);delete urls.value[id]}
watch(()=>[props.projectId,props.active],load,{immediate:true})
watch(ids,value=>{items.value=items.value.filter(row=>value.includes(row.id));for(const id of value)if(!items.value.some(row=>row.id===id))items.value.push({id,originalName:'已暂存截图（保存后可重新预览）'})})
onBeforeUnmount(()=>{++generation;clear()})
defineExpose({validate:()=>!error.value})
</script>
<style scoped>.annotation-task-images{width:100%}.task-image-tools{display:flex;align-items:center;gap:12px;margin:8px 0;color:#64748b}.task-image-tools label{color:var(--el-color-primary);cursor:pointer}.task-image-tools input{display:none}.task-image-grid{display:flex;flex-wrap:wrap;gap:10px}.task-image-item{display:flex;flex-direction:column;width:110px;gap:4px;font-size:11px;overflow-wrap:anywhere}.task-image-item .el-image{width:110px;height:80px;border:1px solid #e2e8f0;border-radius:6px}.task-image-tools small{font-size:11px}</style>
