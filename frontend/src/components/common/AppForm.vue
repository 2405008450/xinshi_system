<template>
  <ElementForm
    ref="innerFormRef"
    v-bind="$attrs"
    @submit.prevent
    :scroll-to-error="false"
    :scroll-into-view-options="scrollOptions"
  >
    <el-alert v-if="serverError" :title="serverError" type="error" show-icon :closable="false" class="app-form-server-error" />
    <el-alert v-if="clientIdentityError" :title="clientIdentityError" type="error" show-icon :closable="false"><el-button link @click="refreshClientIdentity">重新读取客户信息</el-button></el-alert>
    <el-alert v-if="numbering.error.value" :title="numbering.error.value" type="error" show-icon :closable="false" />
    <el-alert v-if="clientNumbering.error.value" :title="clientNumbering.error.value" type="error" show-icon :closable="false" />
    <div v-if="numberScope" style="display:flex;justify-content:flex-end;gap:16px;margin-bottom:8px">
      <slot name="number-actions" />
      <el-button v-if="numberActive && $attrs.model?.[numberField]" link type="warning" :loading="skipLoading" @click="skipCurrentNumber">释放当前编号并重新取号</el-button>
      <el-button link type="primary" @click="numberHistoryVisible=true">{{ numberScope.startsWith('translation')?'订单删除记录':'编号删除记录' }}</el-button>
    </div>
    <BusinessNumberDeletionHistory v-if="numberHistoryVisible" v-model="numberHistoryVisible" :kind="numberScope" :number="$attrs.model?.[numberField]" />
    <SavedDataConflict ref="savedConflictRef" :model="$attrs.model" :fields="innerFormRef?.fields||[]" />
    <slot />
  </ElementForm>
</template>

<script setup>
import { nextTick, ref, getCurrentInstance, onMounted, onUpdated, onBeforeUnmount, useAttrs, watch,defineAsyncComponent } from 'vue'
import SavedDataConflict from './SavedDataConflict.vue'
import {bindSavedForm,unbindSavedForm} from '@/utils/savedDataRegistry'
import { ElForm as ElementForm, ElMessage, ElMessageBox } from 'element-plus'
// 包装组件使用别名，按需插件无法识别 ElementForm，必须显式引入表单布局样式。
import 'element-plus/theme-chalk/el-form.css'
import { focusFirstInvalidField } from '../../utils/formValidation'
import { resolveServerFieldErrors } from '../../utils/formServerErrors.js'
import { waitForScreenshotUploads } from '../../utils/screenshotUploads.js'
import {useBusinessNumber} from '@/composables/useBusinessNumber'
import {getClient} from '@/api/clients'
import {clientIdentityKeys,fillMissingClientIdentity} from '@/utils/clientIdentity'

defineOptions({
  name: 'AppForm',
  inheritAttrs: false,
})
const props=defineProps({savedSyncEnabled:{type:Boolean,default:true},numberScope:String,numberField:{type:String,default:'orderNo'},numberActive:Boolean,numberParent:String,numberDate:String})

const innerFormRef = ref(null)
const numberHistoryVisible=ref(false)
const skipLoading=ref(false)
const BusinessNumberDeletionHistory=defineAsyncComponent(()=>import('./BusinessNumberDeletionHistory.vue'))
const serverError = ref('')
const savedConflictRef=ref(null)
const scrollOptions = { behavior: 'smooth', block: 'center', inline: 'nearest' }
const liveInstance=getCurrentInstance(),liveAttrs=useAttrs()
const clientIdentityError=ref('')
let clientIdentityGeneration=0,clientIdentityRequest=Promise.resolve()
function refreshClientIdentity(){
  const model=liveAttrs.model,owner=localStorage.getItem('user_id')||'',generation=++clientIdentityGeneration
  clientIdentityError.value=''
  if(liveAttrs.inline===true||liveAttrs.inline===''||/search-form|filter-form/.test(String(liveAttrs.class||'')))return Promise.resolve()
  clientIdentityRequest=fillMissingClientIdentity(model,{loadClient:getClient,owner,isCurrent:()=>generation===clientIdentityGeneration&&liveAttrs.model===model&&owner===(localStorage.getItem('user_id')||'')})
    .then(changed=>{if(changed)innerFormRef.value?.clearValidate(Object.values(clientIdentityKeys(model)))})
    .catch(()=>{if(generation===clientIdentityGeneration)clientIdentityError.value='客户信息读取失败，请重新读取后保存'})
  return clientIdentityRequest
}
watch(()=>{const model=liveAttrs.model||{},keys=clientIdentityKeys(model);return [model,model[keys.id],model[keys.sub],model[keys.full],model[keys.short]]},refreshClientIdentity,{immediate:true,flush:'post'})
onBeforeUnmount(()=>{clientIdentityGeneration++})
const numbering=useBusinessNumber({model:()=>liveAttrs.model,kind:()=>props.numberScope,field:()=>props.numberField,active:()=>props.numberActive,parent:()=>props.numberParent,date:()=>props.numberDate})
const clientUsesSnakeCase=()=>Object.prototype.hasOwnProperty.call(liveAttrs.model||{},'client_id')
const clientNumbering=useBusinessNumber({model:()=>liveAttrs.model,kind:()=>'client',field:()=>clientUsesSnakeCase()?'client_code':'clientCode',active:()=>props.numberActive&&['translation','interpretation','annotation','recruitment','consultation'].includes(props.numberScope)&&!liveAttrs.model?.[clientUsesSnakeCase()?'client_id':'clientId']&&!!liveAttrs.model?.[clientUsesSnakeCase()?'client_short_name':'clientShortName']?.trim(),parent:()=>null,date:()=>null})
const skipCurrentNumber=async()=>{
  if(skipLoading.value)return
  skipLoading.value=true
  try{
    try{
      await ElMessageBox.confirm('当前编号将释放回编号池，并重新分配一个可用编号。已填写内容会保留，是否继续？','重新取号',{confirmButtonText:'释放并重新取号',cancelButtonText:'保留当前编号',type:'warning'})
    }catch{return}
    if(await numbering.skip()){
      clearValidate()
      ElMessage.success('已换用新编号，已填内容仍保留')
    }else ElMessage.error(numbering.error.value||'重新取号失败')
  }finally{skipLoading.value=false}
}
const bindLiveModel=()=>props.savedSyncEnabled?bindSavedForm(liveInstance,liveAttrs.model):unbindSavedForm(liveInstance)
watch(()=>props.savedSyncEnabled,bindLiveModel,{flush:'sync'})
onMounted(bindLiveModel);onUpdated(bindLiveModel);onBeforeUnmount(()=>unbindSavedForm(liveInstance))

const locateFirstError = async () => {
  await nextTick()
  return await focusFirstInvalidField(innerFormRef.value?.$el, scrollOptions)
}

const validate = async (callback) => {
  if (!innerFormRef.value) return false
  await refreshClientIdentity()
    if(!await numbering.ensure()){if(typeof callback==='function'){await callback(false,{});return false}throw new Error(numbering.error.value||'请等待编号占用完成')}
    if(!await clientNumbering.ensure()){if(typeof callback==='function'){await callback(false,{});return false}throw new Error(clientNumbering.error.value||'请等待客户编号占用完成')}
  if(savedConflictRef.value?.checkBeforeSave()===false){if(typeof callback==='function'){await callback(false,{});return false}throw new Error('请先处理数据更新差异')}
  serverError.value = ''

  if(!await waitForScreenshotUploads(innerFormRef.value.$el)){
    serverError.value='截图上传失败，请处理提示后重新保存。'
    if(typeof callback==='function'){await callback(false,{});return false}
    throw new Error(serverError.value)
  }

  if (typeof callback === 'function') {
    const valid = await innerFormRef.value.validate(callback)
    // Element Plus 会等待页面回调结束；整次校验完成后再设置最终焦点。
    if (!valid) await locateFirstError()
    return valid
  }

  try {
    return await innerFormRef.value.validate()
  } catch (invalidFields) {
    await locateFirstError()
    throw invalidFields
  }
}

const callInnerForm = (method) => (...args) => innerFormRef.value?.[method]?.(...args)

const clearValidate = (...args) => {
  serverError.value = ''
  return innerFormRef.value?.clearValidate(...args)
}
const resetFields = (...args) => {
  serverError.value = ''
  return innerFormRef.value?.resetFields(...args)
}
const applyServerErrors = async (error, aliases = {}) => {
  const { matches, message } = resolveServerFieldErrors(error, innerFormRef.value?.fields || [], aliases)
  serverError.value = message
  for (const { field, message: fieldMessage } of matches) {
    field.validateMessage = fieldMessage
    field.validateState = 'error'
  }
  if (matches.length) await locateFirstError()
  return matches.length > 0
}

defineExpose({
  numberLeaseHeaders: numbering.headers,
  skipNumber: numbering.skip,
  validate,
  validateField: callInnerForm('validateField'),
  resetFields,
  clearValidate,
  scrollToField: callInnerForm('scrollToField'),
  getField: callInnerForm('getField'),
  setInitialValues: callInnerForm('setInitialValues'),
  locateFirstError,
  applyServerErrors,
})
</script>

<style scoped>
.app-form-server-error { margin-bottom: 16px; }
</style>
