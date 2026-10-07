<template>
  <ElementForm
    ref="innerFormRef"
    v-bind="$attrs"
    :scroll-to-error="false"
    :scroll-into-view-options="scrollOptions"
  >
    <el-alert v-if="serverError" :title="serverError" type="error" show-icon :closable="false" class="app-form-server-error" />
    <slot />
  </ElementForm>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { ElForm as ElementForm } from 'element-plus'
// 包装组件使用别名，按需插件无法识别 ElementForm，必须显式引入表单布局样式。
import 'element-plus/theme-chalk/el-form.css'
import { focusFirstInvalidField } from '../../utils/formValidation'
import { resolveServerFieldErrors } from '../../utils/formServerErrors.js'

defineOptions({
  name: 'AppForm',
  inheritAttrs: false,
})

const innerFormRef = ref(null)
const serverError = ref('')
const scrollOptions = { behavior: 'smooth', block: 'center', inline: 'nearest' }

const locateFirstError = async () => {
  await nextTick()
  return await focusFirstInvalidField(innerFormRef.value?.$el, scrollOptions)
}

const validate = async (callback) => {
  if (!innerFormRef.value) return false
  serverError.value = ''

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
