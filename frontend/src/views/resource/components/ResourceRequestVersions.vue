<template>
  <section class="request-versions" aria-label="需求详情版本">
    <div class="request-versions__body">
      <details v-for="(version,index) in model" :key="index" class="request-version" @toggle="openVersion">
        <summary>需求详情（{{ version.name.replace(/版$/, '') }}版）<el-button v-if="editable && !['发帖', '询问'].includes(version.name.replace(/版$/, ''))" link type="danger" :disabled="disabled" :aria-label="`删除${version.name}版需求详情`" @click.stop.prevent="remove(index)">删除</el-button></summary>
        <div v-if="hasTaskCopyNotice(version.content)" class="request-version-copy-note"><strong>{{ TASK_COPY_NOTICE }}</strong><el-button v-if="editable" link type="danger" :disabled="disabled" @click="removeNotice(version)">删除本句话</el-button></div>
        <el-form-item v-if="editable" :label="`需求详情（${version.name.replace(/版$/, '')}版）`" :prop="`requestContent.versions.${index}.content`" label-position="top">
          <el-input :model-value="taskVersionBody(version.content)" @update:model-value="text => updateBody(version,text)" class="request-version-editor" type="textarea" :disabled="disabled" :rows="8" resize="vertical" placeholder="填写此版本需求详情，支持粘贴截图" />
        </el-form-item>
        <ScreenshotText v-else :text="taskVersionBody(version.content) || '暂无内容'" />
      </details>
      <p v-if="!model.length">暂无需求详情版本</p>
      <div v-if="editable" class="request-versions__actions"><el-button size="small" :disabled="disabled" @click="add">增加需求详情版本</el-button></div>
    </div>
  </section>
</template>
<script setup>
import { ElMessageBox } from 'element-plus'
import { nextTick } from 'vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { TASK_COPY_NOTICE, hasTaskCopyNotice, taskVersionBody } from '@/utils/resourceRequestVersions'
const model=defineModel({type:Array,default:()=>[]})
const props=defineProps({editable:Boolean,disabled:Boolean})
function updateBody(version,text){version.content=(hasTaskCopyNotice(version.content)?`${TASK_COPY_NOTICE}\n`:'')+text}
function removeNotice(version){version.content=taskVersionBody(version.content);version.copiedFromTask=false}
async function openVersion(event){
  const panel=event.currentTarget
  if(!props.editable || !panel.open)return
  await nextTick()
  const textarea=panel.querySelector('textarea')
  if(textarea)textarea.style.height=`${Math.round(textarea.getBoundingClientRect().width / 3)}px`
}
async function remove(index){
  if(props.disabled)return
  try { await ElMessageBox.confirm(`删除“${model.value[index].name}版”需求详情及其中内容？`, '删除需求详情版本', {type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'}); model.value=model.value.filter((_,i)=>i!==index) } catch {}
}
async function add(){
  if(props.disabled)return
  try{const {value}=await ElMessageBox.prompt('输入版本名称，例如“内部”或“客户询问”','增加需求详情版本',{inputValidator:value=>{const name=String(value||'').trim().replace(/版$/,'');return name.length>0&&name.length<=49&&!model.value.some(v=>v.name.replace(/版$/,'')===name)||'请填写不重复的版本名称（最多49字）'}});model.value=[...model.value,{name:value.trim().replace(/版$/,''),content:''}]}catch{}
}
</script>
<style scoped>
.request-version-copy-note{display:block;margin:12px 0 8px;color:#dc2626;font-weight:700;line-height:1.8}.request-versions{border:1px solid #dbe3ef;border-radius:8px;padding:0 12px;margin:12px 0}.request-versions summary{cursor:pointer;font-weight:600}.request-versions__actions{padding:8px 0 10px;text-align:left}.request-version{margin:0;border-top:1px solid #e2e8f0;padding:10px 0}.request-version:first-child{border-top:0}.request-version>summary{line-height:24px}.request-version>summary .el-button{float:right;margin-left:12px}.request-version>.el-form-item{margin:12px 0;display:block}.request-version-editor{width:100%}.request-version-editor :deep(textarea){width:100%;height:auto;min-height:120px;aspect-ratio:3 / 1;resize:vertical;overflow-y:auto}.request-version :deep(.screenshot-text){white-space:pre-wrap;overflow-wrap:anywhere}
</style>
