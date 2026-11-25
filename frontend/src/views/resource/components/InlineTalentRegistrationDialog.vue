<template>
  <DraggableFormDialog v-model="visible" append-to-body width="min(960px, calc(100vw - 32px))" top="5vh" class="inline-talent-registration" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose" @closed="pauseDraft">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" title="登记新译员 · 人才总库" v-model="fieldSearchKeyword" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <el-alert title="未保存内容会自动暂存，仅当前账号可恢复。点击保存后自动加入人才总库，并回填当前译员。" type="info" :closable="false" class="registration-notice" />
      <el-alert v-if="!canCreate" title="当前账号没有人才总库登记权限，请联系有权限的同事登记。" type="warning" :closable="false" />
      <AppForm ref="formRef" :model="form" :disabled="saving||!canCreate" label-position="top" @submit.prevent="save(false)">
        <h3>姓名</h3>
        <el-row :gutter="16"><el-col v-for="field in inlineTalentNameFields" :key="field.key" :xs="24" :md="8"><el-form-item :label="field.label" :prop="field.key==='chineseName'?'nameGroup':field.key" :rules="field.key==='chineseName'?nameRules:[]"><el-input v-model="form[field.key]" maxlength="255" /></el-form-item></el-col></el-row>
        <el-form-item label="其他名字" prop="otherNamesText"><el-input v-model="form.otherNamesText" type="textarea" :rows="2" placeholder="多个名字可换行填写" /></el-form-item>
        <h3>联系方式</h3>
        <el-row v-if="contactsAllowed" :gutter="16"><el-col v-for="field in inlineTalentContactFields" :key="field.key" :xs="24" :md="12"><el-form-item :label="field.label" :prop="field.key" :rules="['primaryEmail','secondaryEmail'].includes(field.key)?[{type:'email',message:'请输入有效邮箱',trigger:'blur'}]:[]"><el-input v-model="form[field.key]" maxlength="255" /></el-form-item></el-col></el-row>
        <el-alert v-else title="联系方式沿用人才总库权限，仅超级管理员可填写。" type="info" :closable="false" />
        <el-form-item label="简历路径" prop="resumePath"><el-input v-model="form.resumePath" maxlength="4000" placeholder="填写后保存至人才总库的简历路径" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!canCreate" @click="save(false)">保存并选用</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,reactive,ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {useFormDraft} from '@/composables/useFormDraft'
import {hasPermission,isSuperAdmin} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {resolveIdempotencyKey} from '@/utils/idempotency'
import {createTalent} from '@/api/talents'
import {inlineTalentNameFields,inlineTalentContactFields,newInlineTalentForm,inlineTalentPayload} from '@/utils/talentInlineRegistration'
const emit=defineEmits(['saved'])
const visible=ref(false),saving=ref(false),formRef=ref(),bodyRef=ref()
const form=reactive(newInlineTalentForm()),createState={key:'',signature:''}
const canCreate=computed(()=>hasPermission(['talents:write','translators:write']))
const contactsAllowed=computed(()=>isSuperAdmin())
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(bodyRef)
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'interpretation-inline-talent',form,createDefault:newInlineTalentForm,formRef})
const nameRules=[{validator:(_rule,_value,done)=>{try{inlineTalentPayload(form,false);done()}catch(error){done(error)}},trigger:['blur','change']}]
async function open(name){
 if(saving.value)return
 Object.assign(form,newInlineTalentForm(name));createState.key='';createState.signature='';clearFieldSearch();visible.value=true
 await nextTick();await beginDraft('create:'+String(name||'').trim().toLocaleLowerCase());formRef.value?.clearValidate()
}
function beforeClose(done){if(!saving.value)done()}
function completed(person){clearDraft();visible.value=false;emit('saved',person);ElMessage.success('已加入人才总库并选用该译员')}
async function save(allowDuplicate=false){
 if(saving.value||!canCreate.value)return
 if(!await formRef.value.validate().catch(()=>false))return
 saving.value=true
 try{
  const payload=inlineTalentPayload(form,contactsAllowed.value,allowDuplicate)
  const result=await createTalent(payload,{idempotencyKey:resolveIdempotencyKey(createState,payload)})
  completed(result)
 }catch(error){
  const detail=error.rawDetail
  if(detail?.code==='duplicate_talent'&&detail.duplicates?.length){
   const person=detail.duplicates[0];let action
   try{await ElMessageBox.confirm(`联系方式与“${person.fullName||person.full_name||'已有档案'}”相同，是否选用已有档案？`,'疑似重复人才',{confirmButtonText:'选用已有档案',cancelButtonText:'仍然新建',distinguishCancelAndClose:true,type:'warning'});action='existing'}catch(value){action=value}
   if(action==='existing'){clearDraft();visible.value=false;emit('saved',{...person,fullName:person.fullName||person.full_name,resourceCode:person.resourceCode||person.resource_code})}
   else if(action==='cancel'){saving.value=false;await save(true)}
  }else ElMessage.error(getLocalizedErrorMessage(error,'登记人才失败，内容已保留'))
 }finally{saving.value=false}
}
defineExpose({open})
</script>
<style>
.el-dialog.inline-talent-registration{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.inline-talent-registration>.el-dialog__header,.inline-talent-registration>.el-dialog__footer{flex-shrink:0}
.inline-talent-registration>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.inline-talent-registration>.el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
</style>
<style scoped>.registration-notice{margin-bottom:16px}h3{font-size:15px;margin:16px 0 12px}</style>
