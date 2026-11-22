<template>
  <span class="statement-editable-cell" :data-dialog-field-search-label="label">
    <textarea v-if="multiline" :value="modelValue??''" :aria-label="label" rows="2" maxlength="5000" @input="emit('update:modelValue',$event.target.value)" />
    <input v-else :value="modelValue??''" :aria-label="label" :type="type" :maxlength="5000" @input="emit('update:modelValue',$event.target.value)" />
  </span>
</template>
<script setup>
defineProps({modelValue:[String,Number],label:{type:String,required:true},type:{type:String,default:'text'},multiline:Boolean})
const emit=defineEmits(['update:modelValue'])
</script>
<style scoped>.statement-editable-cell{display:inline-block;width:100%;min-width:0}.statement-editable-cell input,.statement-editable-cell textarea{box-sizing:border-box;width:100%;min-width:60px;border:1px solid transparent;background:#fff;color:inherit;font:inherit;text-align:inherit;border-radius:3px;padding:4px;outline:none}.statement-editable-cell textarea{resize:vertical;vertical-align:middle}.statement-editable-cell input:hover,.statement-editable-cell textarea:hover{border-color:#cbd5e1}.statement-editable-cell input:focus,.statement-editable-cell textarea:focus{border-color:var(--el-color-primary);box-shadow:0 0 0 1px var(--el-color-primary)}.statement-editable-cell input:disabled,.statement-editable-cell textarea:disabled{cursor:wait}</style>
