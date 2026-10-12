<template>
  <el-dropdown v-if="access.can_collect && eligible" trigger="click" popper-class="chat-topic-select-popper" @command="category => collect(message.id, category)">
    <el-button link size="small" type="primary" @click.stop>收录到开拓问题</el-button>
    <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="category in issueCategories" :key="category.value" :command="category.value">{{ category.label }}</el-dropdown-item></el-dropdown-menu></template>
  </el-dropdown>
</template>
<script setup>
import { computed } from 'vue'
import { issueCategories } from '@/utils/resourceIssues'
import { useResourceIssues } from '@/composables/useResourceIssues'
const props = defineProps({ message: { type: Object, required: true } })
const { access, collect } = useResourceIssues()
const eligible = computed(() => !props.message.recalledAt && props.message.messageType !== 'handover' && props.message.messageType !== 'claim' && (!props.message.messageType || props.message.messageType === 'user') && !!props.message.content?.trim())
</script>
