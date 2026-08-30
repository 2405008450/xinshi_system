<template>
  <div class="ui-zoom-control">
    <el-button
      class="ui-zoom-step"
      text
      title="缩小界面"
      :disabled="!canStepDown"
      @click="stepDown"
    >
      <el-icon :size="16"><ZoomOut /></el-icon>
    </el-button>
    <el-button
      class="ui-zoom-step"
      text
      title="放大界面"
      :disabled="!canStepUp"
      @click="stepUp"
    >
      <el-icon :size="16"><ZoomIn /></el-icon>
    </el-button>
    <el-popover
      v-model:visible="panelVisible"
      placement="bottom-end"
      :width="300"
      trigger="click"
      popper-class="ui-zoom-popover"
    >
      <template #reference>
        <el-button class="ui-zoom-trigger" text title="选择缩放比例">
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
  </div>
</template>

<script setup>
import { ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { useUiZoom } from '../composables/useUiZoom'

const {
  zoom,
  zoomPercent,
  panelVisible,
  levels,
  setZoom,
  resetZoom,
  canStepDown,
  canStepUp,
  stepDown,
  stepUp,
  openPanel,
} = useUiZoom()

defineExpose({ open: openPanel })
</script>

<style scoped>
.ui-zoom-control {
  display: inline-flex;
  align-items: center;
}

.ui-zoom-step,
.ui-zoom-trigger {
  color: var(--color-text-secondary);
  font-weight: 500;
}

.ui-zoom-step {
  min-width: 36px;
  padding: 6px 12px;
}

.ui-zoom-trigger {
  min-width: 48px;
  padding: 6px 8px;
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
</style>
