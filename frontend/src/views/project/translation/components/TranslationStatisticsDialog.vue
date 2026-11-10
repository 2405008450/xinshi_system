<template><ProjectStatisticsDialog :model-value="modelValue" module="translation" @update:model-value="$emit('update:modelValue',$event)" /></template>
<script setup>
import ProjectStatisticsDialog from '@/components/common/ProjectStatisticsDialog.vue'
defineProps({modelValue:Boolean})
defineEmits(['update:modelValue'])
</script>
