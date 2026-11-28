<template>
 <DraggableFormDialog v-model="visible" :title="status==='cancelled'?'填写已取消原因':'填写部分取消原因'" width="min(800px, calc(100vw - 32px))" top="6vh" append-to-body class="partial-cancellation-dialog" :close-on-click-modal="false" @close="cancel">
  <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="status==='cancelled'?'填写已取消原因':'填写部分取消原因'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"/></template>
  <div ref="body">
  <AppForm ref="formRef" :model="form" label-position="top">
   <el-form-item v-if="status==='partially_cancelled'" label="部分取消原因（可多选）" prop="reasons" :rules="[{type:'array',required:true,min:1,message:'请至少选择一项原因',trigger:'change'}]"><el-select v-model="form.reasons" multiple placeholder="请选择部分取消原因，可多选" style="width:100%"><el-option v-for="item in partialCancellationOptions" :key="item" :value="item" :label="item"/></el-select></el-form-item>
   <el-form-item v-else label="已取消原因（分级多选）" prop="paths" :rules="[{type:'array',required:true,min:1,message:'请选择具体的分级原因',trigger:'change'}]"><el-cascader v-model="form.paths" :options="treeOptions" :props="{multiple:true,emitPath:true}" clearable filterable placeholder="请选择原因，并展开下一级，可多选" style="width:100%"/></el-form-item>
   <p v-if="status==='cancelled'" class="reason-help">无法找到译员：未能找到可联系、可承接该项目的译员；无法提供合适译员：已有候选人，但语种、资质、时间、预算等条件不匹配。选择任一项都需填写具体原因。</p>
   <template v-for="path in paths" :key="path.join('|')">
    <el-form-item v-if="needsExplanation(path)" :label="path.join(' / ')+' · 具体原因'" :prop="['explanations',path.join('|')]" :rules="[{required:true,whitespace:true,message:'请填写具体原因',trigger:'blur'}]"><el-input v-model="form.explanations[path.join('|')]" type="textarea" :rows="2" maxlength="2000" show-word-limit/></el-form-item>
    <el-form-item v-if="path.includes('译员原因')" :label="path.join(' / ')+' · 对应译员'" :prop="['people',path.join('|')]" :rules="[{type:'array',required:true,min:1,message:'请选择对应译员',trigger:'change'}]"><el-select v-model="form.people[path.join('|')]" multiple placeholder="请选择本项目相应译员"><el-option v-for="person in interpreters" :key="person.translatorId||person.translator_id" :value="person.translatorId||person.translator_id" :label="person.translatorLabel||person.translatorName||person.translator_name||'已登记译员'"/></el-select><small v-if="!interpreters.length">请先在项目中登记对应译员。</small></el-form-item>
   </template>
   <el-form-item label="截图和说明"><ScreenshotInput v-model="form.note" type="textarea" :rows="4" maxlength="7000" placeholder="可填写补充说明，并粘贴、拖入或上传截图（选填）" @uploading-change="uploading=$event"/></el-form-item>
  </AppForm>
  </div>
  <template #footer><el-button @click="cancel">取消</el-button><el-button type="primary" :disabled="uploading" @click="confirm">确认原因</el-button></template>
 </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,reactive,ref} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import ScreenshotInput from './ScreenshotInput.vue'
import {partialCancellationOptions,parsePartialCancellation,cancellationOptions} from '@/utils/partialCancellationReason'
const visible=ref(false),status=ref('partially_cancelled'),interpreters=ref([]),formRef=ref(),uploading=ref(false),form=reactive({reasons:[],paths:[],explanations:{},people:{},note:''});let pending,lastDetails=null
const body=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const treeOptions=cancellationOptions(),paths=computed(()=>status.value==='partially_cancelled'?form.reasons.map(value=>[value]):form.paths)
const needsExplanation=path=>path.at(-1)==='其他原因（自行填写）'||['无法找到译员','无法提供合适译员'].includes(path[0])
function finish(value){const resolve=pending;pending=null;visible.value=false;resolve?.(value)}
function cancel(){finish(null)}
async function open(note='',options={}){if(pending)finish(null);status.value=options.status||'partially_cancelled';clearFieldSearch();interpreters.value=options.interpreters||[];const candidate=options.details;const details=candidate?.reason_paths?.every(path=>status.value==='cancelled'?treeOptions.some(item=>item.value===path[0]):partialCancellationOptions.includes(path[0]))?candidate:null;const parsed=parsePartialCancellation(details?note:note.startsWith('已取消原因：')?'':note);Object.assign(form,{reasons:details?.reason_paths?.map(path=>path[0])||parsed.reasons,paths:details?.reason_paths||[],explanations:{...(details?.explanations||{}),...(!details&&parsed.other?{[partialCancellationOptions[2]]:parsed.other}:{})},people:{},note:details?.note??parsed.note});for(const issue of details?.translator_issues||[])(form.people[issue.reason_path.join('|')]??=[]).push(issue.translator_id);visible.value=true;await nextTick();formRef.value?.clearValidate();return new Promise(resolve=>pending=resolve)}
async function confirm(){if(uploading.value||!await formRef.value.validate().catch(()=>false))return;lastDetails={reason_paths:paths.value.map(path=>[...path]),explanations:Object.fromEntries(paths.value.filter(needsExplanation).map(path=>[path.join('|'),form.explanations[path.join('|')].trim()])),translator_issues:paths.value.filter(path=>path.includes('译员原因')).flatMap(path=>(form.people[path.join('|')]||[]).map(id=>({translator_id:id,reason_path:[...path]}))),note:form.note.trim()};const text=[(status.value==='cancelled'?'已取消原因：':'部分取消原因：')+paths.value.map(path=>path.join(' / ')).join('；'),...Object.entries(lastDetails.explanations).map(([path,value])=>'具体说明（'+path.split('|').join(' / ')+'）：'+value),lastDetails.note?'截图和说明：\n'+lastDetails.note:''].filter(Boolean).join('\n');finish(text)}
onBeforeUnmount(cancel);defineExpose({open,getDetails:()=>JSON.parse(JSON.stringify(lastDetails))})
</script>
<style>.partial-cancellation-dialog{display:flex;flex-direction:column;max-height:88vh;overflow:hidden}.partial-cancellation-dialog>.el-dialog__body{min-height:0;overflow-y:auto;flex:1}.partial-cancellation-dialog>.el-dialog__header,.partial-cancellation-dialog>.el-dialog__footer{flex:none}.partial-cancellation-dialog .reason-help{font-size:13px;color:var(--el-text-color-secondary);line-height:1.7}</style>
