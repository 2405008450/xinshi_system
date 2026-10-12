<template>
  <DocumentSectionAttachments :section-id="sectionId" :can-edit="canEdit" :adapter="adapter" />
</template>
<script setup>
import DocumentSectionAttachments from '@/components/common/DocumentSectionAttachments.vue'
import { listAttachments, uploadAttachment, downloadAttachment, deleteAttachment } from '@/api/companyManagement'
defineProps({ sectionId: { type: String, required: true }, canEdit: { type: Boolean, default: false } })
const adapter = { list: listAttachments, upload: uploadAttachment, download: downloadAttachment, remove: deleteAttachment }
</script>
