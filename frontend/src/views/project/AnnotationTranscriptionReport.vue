<template>
  <div class="transcription-report">
    <iframe
      class="transcription-report__frame"
      title="小语种转写报告"
      :src="reportUrl"
      sandbox="allow-scripts allow-downloads"
      referrerpolicy="no-referrer"
    />
  </div>
</template>

<script setup>
// 保持报告及语种明细的相对目录，隔离原报告脚本与系统页面。
const reportUrl = `${import.meta.env.BASE_URL}reports/minority-transcription-20261113/综合分析报告.html`
</script>

<style scoped>
.transcription-report {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.transcription-report__frame {
  display: block;
  width: 100%;
  height: calc(100vh - 180px);
  min-height: 420px;
  border: 0;
}

@media (max-width: 768px) {
  .transcription-report__frame {
    height: calc(100dvh - 160px);
    min-height: 320px;
  }
}
</style>
