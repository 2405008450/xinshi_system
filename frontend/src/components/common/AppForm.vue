<template>
  <ElementForm
    ref="innerFormRef"
    v-bind="$attrs"
    @submit.prevent
    :scroll-to-error="false"
    :scroll-into-view-options="scrollOptions"
  >
    <el-alert v-if="serverError" :title="serverError" type="error" show-icon :closable="false" class="app-form-server-error" />
    <SavedDataConflict ref="savedConflictRef" :model="$attrs.model" :fields="innerFormRef?.fields||[]" />
    <slot />
  </ElementForm>
</template>

<script setup>
import { nextTick, ref, getCurrentInstance, onMounted, onUpdated, onBeforeUnmount, useAttrs } from 'vue'
import SavedDataConflict from './SavedDataConflict.vue'
import {bindSavedForm,unbindSavedForm} from '@/utils/savedDataRegistry'
import { ElForm as ElementForm } from 'element-plus'
// 包装组件使用别名，按需插件无法识别 ElementForm，必须显式引入表单布局样式。
import 'element-plus/theme-chalk/el-form.css'
import { focusFirstInvalidField } from '../../utils/formValidation'
import { resolveServerFieldErrors } from '../../utils/formServerErrors.js'
import { waitForScreenshotUploads } from '../../utils/screenshotUploads.js'

defineOptions({
  name: 'AppForm',
  inheritAttrs: false,
})

const innerFormRef = ref(null)
const serverError = ref('')
const savedConflictRef=ref(null)
const scrollOptions = { behavior: 'smooth', block: 'center', inline: 'nearest' }
const liveInstance=getCurrentInstance(),liveAttrs=useAttrs()
const bindLiveModel=()=>bindSavedForm(liveInstance,liveAttrs.model)
onMounted(bindLiveModel);onUpdated(bindLiveModel);onBeforeUnmount(()=>unbindSavedForm(liveInstance))

const locateFirstError = async () => {
  await nextTick()
  return await focusFirstInvalidField(innerFormRef.value?.$el, scrollOptions)
}

const validate = async (callback) => {
  if (!innerFormRef.value) return false
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
