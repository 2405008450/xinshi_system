<template>
 <DraggableFormDialog v-model="visible" title="口译设置" class="interpretation-settings-dialog" append-to-body width="min(680px, calc(100vw - 32px))" top="8vh" :close-on-click-modal="false" :before-close="beforeClose">
  <el-alert title="所有口译项目共用此设置。编辑窗口保存后自动发送会话；邮件由发送按钮单独触发。" type="info" :closable="false" />
  <AppForm v-loading="loading" :disabled="saving||!canWrite" label-position="top" :model="form" class="interpretation-settings-form">
   <el-form-item label="默认 @人员"><el-select v-model="form.ids" multiple filterable clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="3" style="width:100%" placeholder="选择需要默认提醒的人员"><el-option v-for="user in users" :key="user.id" :value="user.id" :label="user.name" /></el-select></el-form-item>
   <el-button :disabled="loading||saving||!canWrite" @click="form.ids=[...defaultIds]">恢复紫霞、旷娇</el-button>
   <p>当前选择会用于之后的口译项目会话；清空并保存表示不默认 @任何人。</p>
  </AppForm>
  <el-alert v-if="error" :title="error" type="error" :closable="false" />
  <template #footer><el-button :disabled="saving" @click="visible=false">关闭</el-button><el-button type="primary" :loading="saving" :disabled="loading||!ready||!canWrite" @click="save">保存设置</el-button></template>
 </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({canWrite:Boolean})
const visible=defineModel({type:Boolean,default:false})
const form=reactive({ids:[]}),users=ref([]),defaultIds=ref([]),loading=ref(false),saving=ref(false),ready=ref(false),error=ref('')
let revision=0,sequence=0
watch(visible,async opened=>{
 const current=++sequence;if(!opened)return
 loading.value=true;error.value='';ready.value=false
 try{const result=await api.get('/projects/interpretation-settings');if(current!==sequence)return;form.ids=result.mention_user_ids;users.value=result.users;defaultIds.value=result.default_mention_user_ids;revision=result.revision;ready.value=result.ready}
 catch(e){if(current===sequence)error.value=getLocalizedErrorMessage(e,'读取口译设置失败')}
 finally{if(current===sequence)loading.value=false}
})
function beforeClose(done){if(!saving.value)done()}
async function save(){
 if(saving.value||!ready.value||!props.canWrite)return
 saving.value=true;error.value=''
 try{await api.put('/projects/interpretation-settings',{mention_user_ids:form.ids,revision});ElMessage.success('口译设置已保存');visible.value=false}
 catch(e){error.value=getLocalizedErrorMessage(e,'保存口译设置失败')}
 finally{saving.value=false}
}
</script>
<style scoped>.interpretation-settings-form{margin-top:18px}.interpretation-settings-form p{color:var(--el-text-color-secondary);font-size:13px}</style>

<style>
.el-dialog.interpretation-settings-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.interpretation-settings-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.interpretation-settings-dialog>.el-dialog__header,.interpretation-settings-dialog>.el-dialog__footer{flex-shrink:0}
.interpretation-settings-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color-lighter)}
</style>
