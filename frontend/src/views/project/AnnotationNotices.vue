<template>
  <DocumentSectionsPage
    page-title="标注须知"
    description="集中查看和维护标注业务中的报价、试标及各类操作流程。"
    write-permission="projects:write"
    navigation-mode="drilldown"
    section-query-key="noticeSectionId"
    route-section="notices"
    allow-group-selection
    :adapter="adapter"
  >
    <template #attachments="{ section, canEdit, refreshKey }">
      <DocumentSectionAttachments :key="`${section.id}:${refreshKey}`" :section-id="section.id" :can-edit="canEdit" :adapter="notices.attachmentAdapter" />
    </template>
  </DocumentSectionsPage>
</template>

<script setup>
import DocumentSectionsPage from '@/components/common/DocumentSectionsPage.vue'
import DocumentSectionAttachments from '@/components/common/DocumentSectionAttachments.vue'
import * as notices from '@/api/annotationNotices'
const adapter = {
  tree: notices.getAnnotationNoticeTree,
  detail: notices.getAnnotationNoticeDetail,
  search: notices.searchAnnotationNotices,
  saveContent: notices.updateAnnotationNoticeContent,
  create: notices.createAnnotationNotice,
  updateStructure: notices.updateAnnotationNoticeStructure,
  remove: notices.deleteAnnotationNotice,
  reorder: notices.reorderAnnotationNotices
}
</script>
