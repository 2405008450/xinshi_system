<template><ChatConversation ref="panel" v-bind="$attrs" project-type="direct" /></template>
<script setup>
import { ref } from 'vue'
import ChatConversation from './ChatConversation.vue'
const panel = ref(null)
defineExpose({ openSearch: () => panel.value?.openSearch(), locate: id => panel.value?.locate(id) })
</script>
