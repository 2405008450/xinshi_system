<template>
  <div class="talent-settlement-detail">
    <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="银行账号">{{ data.bankAccount || '-' }}</el-descriptions-item>
      <el-descriptions-item label="PayPal账号">{{ data.paypalAccount || '-' }}</el-descriptions-item>
      <el-descriptions-item label="Payoneer账户" :span="2">{{ data.payoneerAccount || '-' }}</el-descriptions-item>
      <el-descriptions-item label="对方是否可开票">{{ data.invoiceAvailable===true?'可开票':data.invoiceAvailable===false?'不可开票':'-' }}</el-descriptions-item>
      <el-descriptions-item v-if="data.invoiceAvailable===true" label="开票主体/名义">{{ data.invoiceEntity || '-' }}</el-descriptions-item>
      <el-descriptions-item label="参与灵工平台计算">{{ data.gigPlatformCalculation?'是':'否' }}</el-descriptions-item>
      <el-descriptions-item label="协议状态">待开发</el-descriptions-item>
    </el-descriptions>
    <el-row :gutter="16" class="settlement-code-details">
      <el-col :xs="24" :md="12"><h5>微信支付码</h5><PaymentCodeField :model-value="data.wechatPaymentCode || ''" label="微信支付码" readonly /></el-col>
      <el-col :xs="24" :md="12"><h5>支付宝支付码</h5><PaymentCodeField :model-value="data.alipayPaymentCode || ''" label="支付宝支付码" readonly /></el-col>
    </el-row>
    <h5>价格</h5>
    <el-table :data="data.prices || []" border size="small" empty-text="暂无价格">
      <el-table-column label="价格类型" min-width="100"><template #default="{row}">{{ settlementLabel(settlementCategoryOptions,row.category) }}</template></el-table-column>
      <el-table-column label="服务细分" min-width="100"><template #default="{row}">{{ settlementLabel(settlementServiceOptions,row.serviceType) }}</template></el-table-column>
      <el-table-column label="确认状态" min-width="100"><template #default="{row}">{{ settlementLabel(settlementStatusOptions,row.status || 'confirmed') }}</template></el-table-column>
      <el-table-column label="报价方式" min-width="100"><template #default="{row}">{{ settlementLabel(settlementPriceTypeOptions,row.priceType || 'fixed') }}</template></el-table-column>
      <el-table-column label="金额" min-width="150"><template #default="{row}">{{ settlementPriceAmount(row) }}</template></el-table-column>
      <el-table-column label="计价单位" min-width="110"><template #default="{row}">{{ settlementLabel(settlementUnitOptions,row.unit) }}</template></el-table-column>
      <el-table-column label="货币" min-width="120"><template #default="{row}">{{ row.currency?settlementLabel(settlementCurrencyOptions,row.currency):'待确认' }}</template></el-table-column>
      <el-table-column prop="languagePair" label="适用语言方向" min-width="160" show-overflow-tooltip />
      <el-table-column prop="rawText" label="原始报价" min-width="240"><template #default="{row}"><span class="price-original-text">{{ row.rawText || '-' }}</span></template></el-table-column>
      <el-table-column label="来源" min-width="220"><template #default="{row}">{{ settlementPriceSource(row) }}</template></el-table-column>
      <el-table-column prop="notes" label="报价说明" min-width="240"><template #default="{row}"><span class="price-original-text">{{ row.notes || '-' }}</span></template></el-table-column>
    </el-table>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import PaymentCodeField from '@/components/common/PaymentCodeField.vue'
import {emptySettlement,settlementLabel,settlementCategoryOptions,settlementUnitOptions,settlementCurrencyOptions,settlementServiceOptions,settlementStatusOptions,settlementPriceTypeOptions,settlementPriceAmount,settlementPriceSource} from '@/utils/talentSettlement'
const props=defineProps({value:Object})
const data=computed(()=>props.value||emptySettlement())
</script>
<style scoped>.settlement-code-details{margin-top:12px}.settlement-code-details h5{margin:10px 0}.talent-settlement-detail :deep(.el-descriptions__content){overflow-wrap:anywhere;word-break:break-word}.price-original-text{white-space:pre-wrap;overflow-wrap:anywhere}</style>
