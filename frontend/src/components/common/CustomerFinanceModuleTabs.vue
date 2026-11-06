<template>
  <slot :name="module" />
</template>
<script setup>
const props=defineProps({module:{type:String,required:true},modelValue:String,clientId:{type:[String,Number],default:''},enabled:{type:Boolean,default:true}})
const emit=defineEmits(['update:modelValue'])
</script>
<style scoped>
.customer-finance-module-tabs { min-width:0; }
.customer-finance-module-tabs :deep(.el-tabs__nav-wrap) { max-width:100%; }
</style>
