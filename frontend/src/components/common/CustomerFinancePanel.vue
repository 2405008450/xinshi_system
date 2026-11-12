<template>
  <section>
    <CustomerStatementTaxPreference :client-id="clientId" :can-write="canWrite" />
    <el-tabs v-model="active">
      <el-tab-pane label="笔译" name="translation"><template v-if="active==='translation'"><CustomerTranslationRates :client-id="clientId" :can-write="canWrite" @saved="revision++" /><CustomerRateDifferences v-if="clientId" module="translation" :client-id="clientId" :revision="revision" @saved="revision++" /><p v-if="!clientId">请先保存客户，再维护财务信息。</p></template></el-tab-pane>
      <el-tab-pane label="口译" name="interpretation"><template v-if="active==='interpretation'"><InterpretationFinanceEditor scope="client" :target-id="clientId" :can-write="canWrite" @saved="revision++" /></template></el-tab-pane>
      <el-tab-pane label="标注" name="annotation"><CustomerAnnotationRates v-if="active==='annotation'" :client-id="clientId" :can-write="canWrite" /></el-tab-pane>
      <el-tab-pane label="招聘" name="recruitment"><el-empty description="暂无招聘财务配置" /></el-tab-pane>
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
</script>
