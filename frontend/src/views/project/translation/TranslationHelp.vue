<template><ProjectOperationHelp class="translation-help" title="笔译操作帮助" module-label="笔译" intro="先登记订单，再补齐统计、安排任务和发送通知。" :sections="translationHelpSections" :updated-at="translationHelpUpdatedAt" id-prefix="translation-help-" search-placeholder="搜索帮助，例如：母订单 子订单、路径、工作量统计、邮件" /></template>
<script setup>
import ProjectOperationHelp from '@/components/common/ProjectOperationHelp.vue'
import {translationHelpSections,translationHelpUpdatedAt} from './translationHelpContent'
</script>
