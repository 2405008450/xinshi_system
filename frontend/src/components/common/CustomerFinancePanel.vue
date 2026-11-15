<template>
  <section>
    <el-empty v-if="!clientId" description="请先保存客户，再维护各类项目的财务信息" />
    <el-tabs v-else v-model="active" class="customer-finance-tabs">
      <el-tab-pane label="笔译" name="translation">
        <div v-if="active==='translation'" class="customer-finance-section">
          <el-card ref="settingsSection" shadow="never">
            <template #header><strong>对账单设置</strong></template>
            <CustomerStatementTaxPreference :client-id="clientId" :can-write="canWrite" />
          </el-card>
          <el-card ref="ratesSection" shadow="never">
            <template #header><strong>客户单价</strong></template>
            <div class="customer-finance-section">
              <CustomerTranslationRates :client-id="clientId" :can-write="canWrite" :open-on-mount="initialSection==='rates'" @saved="revision++" />
              <CustomerRateDifferences module="translation" :client-id="clientId" :revision="revision" @saved="revision++" />
            </div>
          </el-card>
          <TranslationFinance v-if="canReadStatements" :client-id="clientId" client-scope collapsible />
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
          <template v-else-if="active==='statements'">
            <el-button @click="specialSettlementVisible=true">特殊结算</el-button>
            <CustomerStatementHistory :key="clientId" :client-id="clientId" />
            <CustomerStatementDialog v-if="specialSettlementVisible" v-model="specialSettlementVisible" title="特殊结算"
              settlement-scope="special" :client-context="{id:clientId}" />
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
<script setup>
import {defineAsyncComponent,onMounted,ref} from 'vue'
import {hasPermission} from '@/utils/permission'
import {scrollFormTarget} from '@/utils/formNavigation'
import CustomerInvoiceManagement from './CustomerInvoiceManagement.vue'
import CustomerAnnotationRates from './CustomerAnnotationRates.vue'
import CustomerStatementTaxPreference from './CustomerStatementTaxPreference.vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import InterpretationFinanceEditor from './InterpretationFinanceEditor.vue'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean,initialSection:String})
const settingsSection=ref(),ratesSection=ref()
onMounted(()=>{
  const section=props.initialSection==='rates'?ratesSection.value:props.initialSection==='settings'?settingsSection.value:null
  if(section)scrollFormTarget(section.$el)
})
const revision=ref(0),active=ref('translation')
const canReadStatements=hasPermission('projects:read')
const CustomerStatementHistory=defineAsyncComponent(()=>import('./CustomerStatementHistory.vue'))
const CustomerStatementDialog=defineAsyncComponent(()=>import('./CustomerStatementDialog.vue'))
const specialSettlementVisible=ref(false)
const TranslationFinance=defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue'))
const InterpretationFinance=defineAsyncComponent(()=>import('@/views/project/interpretation/CustomerFinance.vue'))
const ProjectFinance=defineAsyncComponent(()=>import('@/views/project/ProjectCustomerFinance.vue'))
</script>
<style scoped>
.customer-finance-section{display:grid;gap:12px;min-width:0}
</style>
