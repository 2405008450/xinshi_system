<template>
  <el-popover
    v-model:visible="panelVisible"
    placement="bottom-end"
    :width="300"
    trigger="click"
    popper-class="ui-zoom-popover"
  >
    <template #reference>
      <el-button class="ui-zoom-trigger" text title="界面缩放">
        <el-icon :size="16"><ZoomIn /></el-icon>
        <span>{{ zoomPercent }}%</span>
      </el-button>
    </template>
    <div class="ui-zoom-panel">
      <div class="ui-zoom-panel__header">
        <span>界面缩放</span>
        <el-button v-if="zoom !== 1" link type="primary" @click="resetZoom">恢复默认</el-button>
      </div>
      <div class="ui-zoom-panel__levels">
        <el-button
          v-for="level in levels"
          :key="level"
          size="small"
          :type="zoom === level ? 'primary' : 'default'"
          @click="setZoom(level)"
        >
          {{ Math.round(level * 100) }}%
        </el-button>
      </div>
      <p class="ui-zoom-panel__hint">缩小可在小屏幕上看到更多内容，放大可提高可读性。</p>
    </div>
  </el-popover>
</template>

<script setup>
import { ZoomIn } from '@element-plus/icons-vue'
import { useUiZoom } from '../composables/useUiZoom'

const { zoom, zoomPercent, panelVisible, levels, setZoom, resetZoom, openPanel } = useUiZoom()

defineExpose({ open: openPanel })
</script>

<style scoped>
.ui-zoom-trigger {
  color: var(--color-text-secondary);
  font-weight: 500;
  padding: 6px 10px;
}

.ui-zoom-trigger span {
  margin-left: 4px;
}

.ui-zoom-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  color: var(--color-text-primary);
  font-weight: 600;
}

.ui-zoom-panel__levels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ui-zoom-panel__hint {
  margin: 12px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .ui-zoom-trigger span {
    display: none;
  }
}
</style>
