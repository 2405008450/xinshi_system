<template>
  <DocumentSectionsPage
    page-title="公司管理"
    description="集中查看公司制度、行政财务规范与常用资料。"
    write-permission="company_management:write"
    allow-group-selection
    :adapter="adapter"
  >
    <template #attachments="{ section, canEdit, refreshKey }">
      <CompanyManagementAttachments :key="`${section.id}:${refreshKey}`" :section-id="section.id" :can-edit="canEdit" />
    </template>
  </DocumentSectionsPage>
</template>
<script setup>
import DocumentSectionsPage from '@/components/common/DocumentSectionsPage.vue'
import CompanyManagementAttachments from '@/components/company/CompanyManagementAttachments.vue'
import { adapter } from '@/api/companyManagement'
</script>
