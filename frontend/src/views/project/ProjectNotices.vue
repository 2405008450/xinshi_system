<template>
  <DocumentSectionsPage
    :page-title="`${moduleLabel}须知`"
    :description="`集中查看和维护${moduleLabel}业务中的报价、注意事项及各类操作流程。`"
    write-permission="projects:write"
    navigation-mode="drilldown"
    section-query-key="noticeSectionId"
    route-section="notices"
    allow-group-selection
    :adapter="adapter"
  >
    <template #attachments="{ section, canEdit, refreshKey }">
      <DocumentSectionAttachments
        :key="`${module}:${section.id}:${refreshKey}`"
        :section-id="section.id"
        :can-edit="canEdit"
        :adapter="adapter.attachments"
      />
    </template>
  </DocumentSectionsPage>
</template>

<script setup>
import DocumentSectionsPage from '@/components/common/DocumentSectionsPage.vue'
import DocumentSectionAttachments from '@/components/common/DocumentSectionAttachments.vue'
import { createProjectNoticeAdapter } from '@/api/projectNotices'

const props = defineProps({ module: { type: String, required: true }, moduleLabel: { type: String, required: true } })
const adapter = createProjectNoticeAdapter(props.module)
</script>
