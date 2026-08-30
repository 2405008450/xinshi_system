<template>
  <el-button type="primary" size="small" @click="$emit('click', $event)">编辑</el-button>
</template>

<script setup>
defineEmits(['click'])
</script>
