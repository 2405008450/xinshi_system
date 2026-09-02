<template>
  <ElementForm
    ref="innerFormRef"
    v-bind="$attrs"
    :scroll-to-error="true"
    :scroll-into-view-options="scrollOptions"
  >
    <slot />
  </ElementForm>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { ElForm as ElementForm } from 'element-plus'
import { focusFirstInvalidField } from '../../utils/formValidation'

defineOptions({
  name: 'AppForm',
  inheritAttrs: false,
})

const innerFormRef = ref(null)
const scrollOptions = { behavior: 'smooth', block: 'center', inline: 'nearest' }

const locateFirstError = async () => {
  await nextTick()
  focusFirstInvalidField(innerFormRef.value?.$el, scrollOptions)
}

const validate = async (callback) => {
  if (!innerFormRef.value) return false

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

defineExpose({
  validate,
  validateField: callInnerForm('validateField'),
  resetFields: callInnerForm('resetFields'),
  clearValidate: callInnerForm('clearValidate'),
  scrollToField: callInnerForm('scrollToField'),
  getField: callInnerForm('getField'),
  setInitialValues: callInnerForm('setInitialValues'),
  locateFirstError,
})
</script>
