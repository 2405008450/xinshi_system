<template>
  <el-select :model-value="modelValue" clearable filterable popper-class="chat-topic-select-popper" :disabled="disabled || !topics.ready" :placeholder="placeholder" aria-label="讨论主题" @update:model-value="$emit('update:modelValue', $event || null)" @change="$emit('change', $event || null)">
    <el-option-group v-for="root in roots" :key="root.id" :label="root.name">
      <el-option :value="root.id" :label="root.path" :disabled="!root.selectable" />
      <el-option v-for="row in topics.items.filter(item => item.parent_id === root.id)" :key="row.id" :value="row.id" :label="row.path" :disabled="!row.selectable" />
    </el-option-group>
  </el-select>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { useChatTopics } from '@/composables/useChatTopics'
defineProps({ modelValue: { type: String, default: null }, disabled: Boolean, placeholder: { type: String, default: '讨论主题（可选）' } })
defineEmits(['update:modelValue', 'change'])
const { topics, refresh } = useChatTopics()
const roots = computed(() => topics.items.filter(row => !row.parent_id && row.kind === 'topic'))
onMounted(() => { refresh().catch(() => {}) })
</script>
<style>.chat-topic-select-popper{z-index:100010!important;max-width:calc(100vw - 32px)}</style>
