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
          <el-card v-if="subClients.length" shadow="never">
            <template #header><strong>子客户结算设置</strong></template>
            <div class="sub-client-finance-selectors">
              <el-select v-model="subClientId" aria-label="子客户" placeholder="选择子客户" filterable>
                <el-option v-for="child in subClients" :key="child.id" :value="child.id" :label="buyerLabel(child)" />
              </el-select>
              <el-date-picker v-model="subClientMonth" type="month" value-format="YYYY-MM" placeholder="选择账单月份"
                aria-label="子客户账单月份" @change="subClientPeriod=undefined" />
              <StatementPeriodSelect v-if="subClientMonth" v-model="subClientPeriod" :month="subClientMonth"
                :client-id="clientId" all-label="整月（不分期）" />
            </div>
            <SubClientFinancePreferences v-if="subClientId" :sub-client-id="subClientId" :can-write="canWrite"
              :month="subClientMonth || undefined" :period="subClientPeriod" />
            <div v-if="subClientId" :key="subClientId" class="customer-finance-section">
              <small>项目优先采用子客户的匹配单价。单独填写且不同的项目单价可在差异中确认同步。</small>
              <CustomerTranslationRates :client-id="clientId" :sub-client-id="subClientId" :can-write="canWrite"
                button-label="子客户语种单价" @saved="revision++" />
              <CustomerRateDifferences module="translation" :client-id="clientId" :sub-client-id="subClientId"
                :revision="revision" @saved="revision++" />
            </div>
          </el-card>
          <TranslationFinance v-if="canReadStatements" :client-id="clientId" client-scope collapsible />
        </div>
      </el-tab-pane>
      <el-tab-pane label="口译" name="interpretation">
        <div v-if="active==='interpretation'" class="customer-finance-section">
          <el-card shadow="never"><template #header><strong>客户结算设置</strong></template><InterpretationCustomerPreferences :client-id="clientId" :can-write="canWrite" /></el-card>
          <el-card v-if="subClients.length" shadow="never"><template #header><strong>子客户结算设置</strong></template><div class="sub-client-finance-selectors"><el-select v-model="subClientId" aria-label="口译子客户" placeholder="选择子客户" filterable><el-option v-for="child in subClients" :key="child.id" :value="child.id" :label="buyerLabel(child)" /></el-select><el-date-picker v-model="subClientMonth" type="month" value-format="YYYY-MM" placeholder="账单月份" /><el-input-number v-model="subClientPeriod" :min="1" :max="999" :controls="false" placeholder="期次（空为整月）" /></div><SubClientFinancePreferences v-if="subClientId" module="interpretation" :sub-client-id="subClientId" :month="subClientMonth||undefined" :period="subClientPeriod" :can-write="canWrite" /></el-card>
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
import {defineAsyncComponent,onMounted,ref,watch} from 'vue'
import {hasPermission} from '@/utils/permission'
import {scrollFormTarget} from '@/utils/formNavigation'
import CustomerInvoiceManagement from './CustomerInvoiceManagement.vue'
import CustomerAnnotationRates from './CustomerAnnotationRates.vue'
import CustomerStatementTaxPreference from './CustomerStatementTaxPreference.vue'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import CustomerTranslationRates from './CustomerTranslationRates.vue'
import InterpretationFinanceEditor from './InterpretationFinanceEditor.vue'
import SubClientFinancePreferences from './SubClientFinancePreferences.vue'
import InterpretationCustomerPreferences from './InterpretationCustomerPreferences.vue'
import StatementPeriodSelect from './StatementPeriodSelect.vue'
import {buyerLabel,getClientInvoiceBuyers} from '@/api/invoiceParties'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean,initialSection:String})
const settingsSection=ref(),ratesSection=ref()
onMounted(()=>{
  const section=props.initialSection==='rates'?ratesSection.value:props.initialSection==='settings'?settingsSection.value:null
  if(section)scrollFormTarget(section.$el)
})
const revision=ref(0),active=ref('translation')
const subClients=ref([]),subClientId=ref(''),subClientMonth=ref(),subClientPeriod=ref()
watch(()=>[props.clientId,active.value],async ([id,tab],_,onCleanup)=>{
  if(!id||tab!=='translation')return
  const request=new AbortController()
  onCleanup(()=>request.abort())
  subClients.value=[]
  try{
    const result=await getClientInvoiceBuyers(id,{signal:request.signal})
    if(request.signal.aborted)return
    subClients.value=result.sub_clients||[]
    if(!subClients.value.some(child=>child.id===subClientId.value))subClientId.value=subClients.value[0]?.id||''
  }catch{/* 主财务内容独立加载。 */}
},{immediate:true})
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
.sub-client-finance-selectors{display:flex;flex-wrap:wrap;gap:8px 12px}.sub-client-finance-selectors .el-select{width:240px;max-width:100%}
</style>
