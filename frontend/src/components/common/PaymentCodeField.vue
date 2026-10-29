<template>
  <div class="payment-code-field" :aria-label="label">
    <ScreenshotInput v-if="!readonly" :model-value="modelValue" type="textarea" :rows="2" :maxlength="4000" placeholder="点击插入截图，或在此粘贴支付码截图" @update:model-value="$emit('update:modelValue',$event)" />
    <ScreenshotText v-else-if="modelValue" :text="modelValue" />
    <span v-else class="payment-code-empty">未上传支付码</span>
  </div>
</template>
<script setup>
import ScreenshotInput from './ScreenshotInput.vue'
import ScreenshotText from './ScreenshotText.vue'
defineProps({modelValue:{type:String,default:''},label:String,readonly:Boolean})
defineEmits(['update:modelValue'])
</script>
<style scoped>
.payment-code-field{width:100%;min-height:150px;box-sizing:border-box;padding:12px;border:1px solid var(--el-border-color);border-radius:8px;background:#fff;overflow-wrap:anywhere}
.payment-code-field :deep(.el-textarea__inner){box-shadow:none}.payment-code-empty{color:var(--el-text-color-placeholder);font-size:13px}
</style>
