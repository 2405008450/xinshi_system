<template>
  <el-button
    class="table-action-button"
    :type="resolvedType"
    :icon="resolvedIcon"
    :aria-label="resolvedLabel"
    :title="resolvedLabel"
    :disabled="disabled"
    size="small"
    circle
    plain
    @click="$emit('click', $event)"
  />
</template>

<script setup>
import { computed } from 'vue'
import {
  Delete,
  EditPen,
  FolderOpened,
  Key,
  Lock,
  Right,
  Setting,
  UserFilled,
  View,
} from '@element-plus/icons-vue'

const ACTION_CONFIG = {
  edit: { label: '编辑', type: 'primary', icon: EditPen },
  delete: { label: '删除', type: 'danger', icon: Delete },
  file: { label: '文件', type: 'success', icon: FolderOpened },
  view: { label: '查看', type: 'info', icon: View },
  enter: { label: '进入', type: 'primary', icon: Right },
  assign: { label: '分配', type: 'success', icon: UserFilled },
  password: { label: '修改密码', type: 'warning', icon: Lock },
  permission: { label: '配置权限', type: 'success', icon: Key },
  settings: { label: '设置', type: 'primary', icon: Setting },
}

const props = defineProps({
  action: { type: String, required: true },
  label: { type: String, default: '' },
  type: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

defineEmits(['click'])

const config = computed(() => ACTION_CONFIG[props.action] || ACTION_CONFIG.settings)
const resolvedLabel = computed(() => props.label || config.value.label)
const resolvedType = computed(() => props.type || config.value.type)
const resolvedIcon = computed(() => config.value.icon)
</script>

<style scoped>
.table-action-button {
  width: 28px !important;
  min-width: 28px;
  height: 28px !important;
  min-height: 28px;
  padding: 0 !important;
  border-radius: 50%;
}

.table-action-button + .table-action-button {
  margin-left: 6px;
}
</style>
