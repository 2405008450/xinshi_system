<template>
  <div class="company-management">
  <RouteSectionNavigation :items="navigation" label="公司管理二级导航" />
  <router-view v-if="route.name === 'DevelopmentFeedback'" />
  <DocumentSectionsPage v-else
    page-title="公司管理"
    description="集中查看公司制度、行政财务规范与常用资料。"
    allow-all-users-edit
    allow-group-selection
    navigation-mode="drilldown"
    section-query-key="companySectionId"
    :adapter="adapter"
  >
    <template #attachments="{ section, canEdit, refreshKey }">
      <CompanyManagementAttachments :key="`${section.id}:${refreshKey}`" :section-id="section.id" :can-edit="canEdit" />
    </template>
  </DocumentSectionsPage>
  </div>
</template>
<script setup>
import DocumentSectionsPage from '@/components/common/DocumentSectionsPage.vue'
import CompanyManagementAttachments from '@/components/company/CompanyManagementAttachments.vue'
import { adapter } from '@/api/companyManagement'
import { useRoute } from 'vue-router'
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'
const route = useRoute()
const navigation = [{ path: '/company-management', label: '公司资料' }, { path: '/company-management/development-feedback', label: '开发反馈' }]
</script>
<style scoped>.company-management{display:flex;flex-direction:column;gap:16px;min-width:0}</style>
