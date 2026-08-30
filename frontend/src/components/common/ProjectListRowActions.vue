<template>
  <div class="project-list-row-actions">
    <PrimaryEditButton v-if="editable" @click="$emit('edit', $event)" />
    <el-dropdown v-if="hasMoreActions" trigger="click" placement="bottom-end" @command="handleCommand">
      <el-button
        class="more-action-button"
        size="small"
        circle
        plain
        aria-label="更多操作"
        title="更多操作"
      >
        <el-icon><MoreFilled /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item v-if="showStartRequest" command="start-request">发起需求</el-dropdown-item>
          <el-dropdown-item
            v-for="item in extraActions"
            :key="item.command"
            :command="item.command"
            :disabled="item.disabled"
          >
            {{ item.label }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'

const props = defineProps({
  editable: { type: Boolean, default: true },
  showStartRequest: { type: Boolean, default: true },
  extraActions: { type: Array, default: () => [] },
})

const emit = defineEmits(['edit', 'start-request', 'extra-command'])
const hasMoreActions = computed(() => props.showStartRequest || props.extraActions.length > 0)

const handleCommand = (command) => {
  if (command === 'start-request') emit('start-request')
  else emit('extra-command', command)
}
</script>

<style scoped>
.project-list-row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
}

.project-list-row-actions :deep(.el-dropdown) {
  display: inline-flex;
}

.more-action-button {
  width: 24px;
  min-width: 24px;
  height: 24px;
  min-height: 24px;
  padding: 0;
}
</style>
