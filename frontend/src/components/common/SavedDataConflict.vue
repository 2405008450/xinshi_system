<template>
  <el-alert v-if="changes.length" type="warning" :closable="false" show-icon class="saved-data-conflict">
    <template #title>源数据已更新，{{changes.length}} 个字段有未保存修改，当前输入已保留。</template>
    <el-button link type="primary" @click="visible=true">查看差异并处理</el-button>
  </el-alert>
  <DraggableFormDialog v-model="visible" title="处理数据更新差异" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body>
    <p>未发生冲突的字段已同步。以下选择只调整当前编辑内容，仍需点击原窗口的保存按钮。</p>
    <el-table :data="changes" border max-height="480"><el-table-column label="字段" width="160"><template #default="{row}">{{label(row.path)}}</template></el-table-column><el-table-column label="我的未保存内容"><template #default="{row}"><pre>{{text(row.current)}}</pre></template></el-table-column><el-table-column label="最新保存内容"><template #default="{row}"><pre>{{text(row.latest)}}</pre></template></el-table-column><el-table-column label="选择" width="180"><template #default="{row}"><el-button link type="primary" @click="resolve(row,false)">保留我的输入</el-button><el-button link @click="resolve(row,true)">采用最新值</el-button></template></el-table-column></el-table>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {modelSavedConflicts,resolveSavedConflict} from '@/utils/savedDataRegistry'
const props=defineProps({model:{default:null},fields:{type:Array,default:()=>[]}}),visible=ref(false)
const changes=computed(()=>props.model?modelSavedConflicts(props.model):[])
const label=path=>props.fields.find(field=>String(field.prop)===path||path.startsWith(String(field.prop)+'.'))?.label||path
const text=value=>value==null?'（空）':typeof value==='object'?JSON.stringify(value,null,2):String(value)
function resolve(row,accept){resolveSavedConflict(props.model,row.path,accept);if(!changes.value.length)visible.value=false}
defineExpose({checkBeforeSave:()=>{if(!changes.value.length)return true;visible.value=true;return false}})
</script>
<style scoped>
.saved-data-conflict{margin-bottom:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:180px;overflow:auto;margin:0}
</style>
