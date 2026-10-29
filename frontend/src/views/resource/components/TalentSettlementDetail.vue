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
      <el-table-column prop="amount" label="金额" min-width="110" />
      <el-table-column label="计价单位" min-width="110"><template #default="{row}">{{ settlementLabel(settlementUnitOptions,row.unit) }}</template></el-table-column>
      <el-table-column label="货币" min-width="120"><template #default="{row}">{{ settlementLabel(settlementCurrencyOptions,row.currency) }}</template></el-table-column>
    </el-table>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import PaymentCodeField from '@/components/common/PaymentCodeField.vue'
import {emptySettlement,settlementLabel,settlementCategoryOptions,settlementUnitOptions,settlementCurrencyOptions} from '@/utils/talentSettlement'
const props=defineProps({value:Object})
const data=computed(()=>props.value||emptySettlement())
</script>
<style scoped>.settlement-code-details{margin-top:12px}.settlement-code-details h5{margin:10px 0}.talent-settlement-detail :deep(.el-descriptions__content){overflow-wrap:anywhere;word-break:break-word}</style>
