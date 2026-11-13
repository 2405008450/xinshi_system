<template>
  <section>
    <el-empty v-if="!clientId" description="请先保存客户，再维护各类项目的财务信息" />
    <el-tabs v-else v-model="active">
      <el-tab-pane label="笔译" name="translation">
        <div v-if="active==='translation'" class="customer-finance-section">
          <CustomerStatementTaxPreference :client-id="clientId" :can-write="canWrite" />
          <CustomerTranslationRates :client-id="clientId" :can-write="canWrite" @saved="revision++" />
          <CustomerRateDifferences module="translation" :client-id="clientId" :revision="revision" @saved="revision++" />
          <TranslationFinance v-if="canReadStatements" :client-id="clientId" client-scope />
        </div>
      </el-tab-pane>
      <el-tab-pane label="口译" name="interpretation">
        <div v-if="active==='interpretation'" class="customer-finance-section">
          <InterpretationFinanceEditor scope="client" :target-id="clientId" :can-write="canWrite" @saved="revision++" />
          <InterpretationFinance :key="revision" :client-id="clientId" client-scope />
        </div>
      </el-tab-pane>
      <el-tab-pane label="标注" name="annotation">
        <div v-if="active==='annotation'" class="customer-finance-section">
          <CustomerAnnotationRates :client-id="clientId" :can-write="canWrite" />
          <ProjectFinance v-if="canReadStatements" module="annotation" :client-id="clientId" client-scope />
        </div>
      </el-tab-pane>
      <el-tab-pane label="招聘" name="recruitment">
        <ProjectFinance v-if="active==='recruitment'&&canReadStatements" module="recruitment" :client-id="clientId" client-scope />
        <el-empty v-else-if="active==='recruitment'" description="暂无招聘项目财务查看权限" />
      </el-tab-pane>
      <el-tab-pane label="发票" name="invoice"><CustomerInvoiceManagement v-if="active==='invoice'" :client-id="clientId" :can-write="canWrite" /></el-tab-pane>
      <el-tab-pane label="对账单" name="statements">
        <div data-dialog-field-search-label="对账单">
          <el-empty v-if="!clientId" description="请先保存客户，再查看对账单" />
          <el-empty v-else-if="!canReadStatements" description="暂无财务对账单查看权限" />
          <CustomerStatementHistory v-else-if="active==='statements'" :key="clientId" :client-id="clientId" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
<script setup>
import {defineAsyncComponent,ref} from 'vue'
import {hasPermission} from '@/utils/permission'
import CustomerInvoiceManagement from './CustomerInvoiceManagement.vue'
import CustomerAnnotationRates from './CustomerAnnotationRates.vue'
import CustomerStatementTaxPreference from './CustomerStatementTaxPreference.vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import InterpretationFinanceEditor from './InterpretationFinanceEditor.vue'
defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const revision=ref(0),active=ref('translation')
const canReadStatements=hasPermission('projects:read')
const CustomerStatementHistory=defineAsyncComponent(()=>import('./CustomerStatementHistory.vue'))
const TranslationFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const InterpretationFinance=defineAsyncComponent(()=>import('@/views/project/interpretation/CustomerFinance.vue'))
const ProjectFinance=defineAsyncComponent(()=>import('@/views/project/ProjectCustomerFinance.vue'))
</script>
<style scoped>
.customer-finance-section{display:grid;gap:12px;min-width:0}
</style>
