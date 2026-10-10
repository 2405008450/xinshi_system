<template><ChatConversation ref="panel" v-bind="$attrs" project-type="annotation" @unread="$emit('unread')" @add-to-progress="$emit('add-to-progress', $event)" /></template>
<script setup>
import { ref } from 'vue'
import ChatConversation from './ChatConversation.vue'
defineEmits(['unread', 'add-to-progress'])
const panel = ref(null)
defineExpose({ openSearch: () => panel.value?.openSearch(), locate: id => panel.value?.locate(id), toggleFilters: () => panel.value?.openSearch() })
</script>
