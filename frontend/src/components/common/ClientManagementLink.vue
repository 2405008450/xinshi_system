<template>
  <button v-if="target" type="button" class="client-management-link" title="打开客户管理窗口" @click.stop="open">
    {{ label || value }}
  </button>
  <span v-else>{{ label || value || '-' }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { clientManagementRequest, clientManagementTarget } from '@/utils/clientManagementWindow'

const props = defineProps({ value: [String, Number], row: Object, label: String, subClient: Boolean })
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
