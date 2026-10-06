<template>
  <DocumentSectionManager v-bind="$attrs" page-title="标注须知" :adapter="adapter" />
</template>
<script setup>
import DocumentSectionManager from '@/components/common/DocumentSectionManager.vue'
import * as notices from '@/api/annotationNotices'
const adapter = {
  create: notices.createAnnotationNotice,
  updateStructure: notices.updateAnnotationNoticeStructure,
  remove: notices.deleteAnnotationNotice,
  reorder: notices.reorderAnnotationNotices
}
</script>