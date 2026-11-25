<template>
  <div v-if="idleMinutes > 60 || lunchWork" class="report-daily-notices">
    <el-alert v-if="idleMinutes > 60" type="error" show-icon :closable="false"
      :title="`当日空闲时间 ${idleMinutes} 分钟，超过 60 分钟`" />
    <el-alert v-if="lunchWork" type="info" show-icon :closable="false" title="有中午工作"
      class="report-lunch-notice" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  idleMinutes: { type: Number, default: null },
  items: { type: Array, default: () => [] },
  hasLunchWork: Boolean,
})
const lunchWork = computed(() => props.hasLunchWork || props.items.some(item => item.display_metadata?.lunch_overtime === true))
</script>

<style scoped>
.report-daily-notices { display: grid; gap: 8px; margin: 12px 0; }
.report-lunch-notice { --el-alert-bg-color: #eff6ff; --el-alert-text-color: #1d4ed8; color: #1d4ed8; }
</style>
