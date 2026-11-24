<template>
  <el-popover trigger="click" placement="bottom-end" width="min(700px, calc(100vw - 32px))"
    title="口译项目类型说明" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }">
    <template #reference><el-button link type="primary" size="small" @click.stop>类型说明</el-button></template>
    <div class="interpretation-type-help">
      <p>按主要场景和传译方式选择，可多选；具体工作内容请填写在“具体任务”。</p>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in projectTypeOptions" :key="item.value" :label="item.label">
          {{ projectTypeDescriptions[item.value] }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-popover>
</template>

<script setup>
import { projectTypeOptions, projectTypeDescriptions } from '@/utils/interpretationProjectDetail'
</script>

<style scoped>
.interpretation-type-help { max-height: min(520px, calc(100vh - 180px)); overflow-y: auto; overflow-wrap: anywhere; }
.interpretation-type-help p { margin: 8px 0 12px; color: var(--el-text-color-secondary); }
</style>
