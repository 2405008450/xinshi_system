<template>
  <el-popover v-model:visible="visible" trigger="click" placement="left" width="min(760px, calc(100vw - 32px))"
    :popper-options="{modifiers:[{name:'preventOverflow',options:{altAxis:true,tether:false,padding:16}}]}"
    :title="`${label} · ${current.orderNo||row.orderNo||''}`" popper-class="project-task-popover"
    @show="load" @hide="cancelEdit">
    <template #reference>
      <button type="button" class="project-task-preview business-clickable-cell" :aria-label="`查看${label} · ${row.orderNo||''}`" @click.stop>
        {{row[field]||'查看'+label}}
      </button>
    </template>
    <div>
      <div v-loading="loading" class="project-task-content">
        <el-alert v-if="error" :title="error" type="error" :closable="false">
          <el-button link type="primary" @click="load">重新加载</el-button>
        </el-alert>
        <InlineTextField v-else :model-value="current[field]" :editable="editable&&!loading" :label="label" multiline
          :save-field="save" @conflict="load" @editing-change="editing=$event" />
      </div>
      <div class="project-task-footer"><el-button size="small" @click="close">关闭</el-button></div>
    </div>
  </el-popover>
</template>

<script setup>
import {computed,onBeforeUnmount,ref} from 'vue'
import {ElMessageBox} from 'element-plus'
import * as interpretation from '@/api/interpretationProjects'
import * as annotation from '@/api/annotationProjects'
import * as recruitment from '@/api/recruitmentProjects'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import InlineTextField from './InlineTextField.vue'

const props=defineProps({row:{type:Object,required:true},module:{type:String,required:true},editable:Boolean})
const emit=defineEmits(['saved'])
const services={
  interpretation:{read:interpretation.getInterpretationProject,write:interpretation.updateInterpretationProjectTextField},
  annotation:{read:annotation.getAnnotationProject,write:annotation.updateAnnotationProjectTextField},
  recruitment:{read:recruitment.getRecruitmentProject,write:recruitment.updateRecruitmentProjectTextField},
}
const field=computed(()=>props.module==='recruitment'?'jobDescription':'taskDescription')
const label=computed(()=>props.module==='recruitment'?'职位说明':props.module==='interpretation'?'工作内容':'具体任务')
const visible=ref(false),detail=ref(null),loading=ref(false),editing=ref(false),error=ref('')
const current=computed(()=>detail.value||props.row)
let sequence=0
async function load(){
  const seq=++sequence
  loading.value=true;error.value=''
  try{
    const result=await services[props.module].read(props.row.id)
    if(seq===sequence)detail.value=result
  }catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'任务详情加载失败')}
  finally{if(seq===sequence)loading.value=false}
}
async function save(value){
  const result=await services[props.module].write(props.row.id,field.value,value,current.value.updatedAt)
  detail.value=result
  emit('saved',result)
  return result
}
function cancelEdit(){
  sequence++
  loading.value=false
  window.dispatchEvent(new CustomEvent('business-inline-text-edit',{detail:'popover-hidden'}))
}
async function close(){
  if(editing.value){
    try{await ElMessageBox.confirm('任务内容尚未保存，是否关闭？','关闭任务详情')}catch{return}
  }
  visible.value=false
}
onBeforeUnmount(()=>sequence++)
</script>

<style scoped>
.project-task-preview{display:block;width:100%;max-width:100%;padding:0;border:0;background:none;color:var(--el-color-primary);font:inherit;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.project-task-content{min-height:55px;max-height:min(560px,calc(100vh - 190px));overflow-y:auto;overflow-wrap:anywhere}
.project-task-footer{display:flex;justify-content:flex-end;margin-top:12px}
</style>
<style>
.project-task-popover{max-width:calc(100vw - 32px);box-sizing:border-box}
</style>
