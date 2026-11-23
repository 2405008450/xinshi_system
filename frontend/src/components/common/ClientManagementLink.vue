<template>
  <button v-if="target" type="button" class="client-management-link" :data-field-copy="!label||label===value ? 'true' : undefined" title="打开客户管理窗口" @click.stop="open">
    {{ displayName }}
  </button>
  <span v-else :data-field-copy="!label||label===value ? 'true' : undefined">{{ displayName }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { clientManagementRequest, clientManagementTarget, formatClientWithSubClient } from '@/utils/clientManagementWindow'

const props = defineProps({ value: [String, Number], row: Object, label: String, subClient: Boolean, showSubClient: Boolean })
const displayName = computed(() => props.label ||
  (props.showSubClient && !props.subClient ? formatClientWithSubClient(props.row, props.value) : props.value) || '-')
const target = computed(() => clientManagementRequest(props.row, props.value, props.subClient))
function open() {
  clientManagementTarget.value = target.value
}
</script>

<style scoped>
.client-management-link {
  background: none;
  border: 0;
  padding: 0;
  max-width: 100%;
  color: var(--el-color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  font: inherit;
  text-align: inherit;
  overflow-wrap: anywhere;
}
</style>
