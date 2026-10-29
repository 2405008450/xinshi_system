<template>
  <div class="talent-settlement-editor">
    <el-row :gutter="16">
      <el-col :xs="24" :md="8"><el-form-item label="银行账号" prop="settlement.bankAccount"><el-input v-model="modelValue.bankAccount" maxlength="255" placeholder="请输入银行账号" /></el-form-item></el-col>
      <el-col :xs="24" :md="8"><el-form-item label="PayPal账号" prop="settlement.paypalAccount"><el-input v-model="modelValue.paypalAccount" maxlength="255" /></el-form-item></el-col>
      <el-col :xs="24" :md="8"><el-form-item label="Payoneer账户" prop="settlement.payoneerAccount"><el-input v-model="modelValue.payoneerAccount" maxlength="255" /></el-form-item></el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :xs="24" :md="8"><el-form-item label="对方是否可开票" prop="settlement.invoiceAvailable"><el-select v-model="modelValue.invoiceAvailable" clearable placeholder="请选择" style="width:100%" @change="invoiceChanged"><el-option label="可开票" :value="true" /><el-option label="不可开票" :value="false" /></el-select></el-form-item></el-col>
      <el-col v-if="modelValue.invoiceAvailable===true" :xs="24" :md="16"><el-form-item label="开票主体/名义" prop="settlement.invoiceEntity" :rules="[{required:true,whitespace:true,message:'请填写开票主体/名义',trigger:'blur'}]"><el-input v-model="modelValue.invoiceEntity" maxlength="255" placeholder="请输入公司名称、个人姓名或实际开票主体" /></el-form-item></el-col>
    </el-row>
    <el-form-item label="灵工平台" prop="settlement.gigPlatformCalculation"><el-checkbox v-model="modelValue.gigPlatformCalculation">参与灵工平台计算</el-checkbox></el-form-item>
    <el-form-item label="协议状态"><ReadonlyField model-value="待开发" source="locked" tooltip="协议状态功能待开发" /></el-form-item>
    <el-row :gutter="16">
      <el-col :xs="24" :md="12"><el-form-item label="微信支付码" prop="settlement.wechatPaymentCode"><PaymentCodeField v-model="modelValue.wechatPaymentCode" label="微信支付码" /></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="支付宝支付码" prop="settlement.alipayPaymentCode"><PaymentCodeField v-model="modelValue.alipayPaymentCode" label="支付宝支付码" /></el-form-item></el-col>
    </el-row>
    <div class="settlement-price-heading"><h4>价格</h4><el-button type="primary" plain :disabled="modelValue.prices.length>=100" @click="addPrice">添加价格</el-button></div>
    <div v-for="(row,index) in modelValue.prices" :key="row.id" class="settlement-price-row" data-dialog-field-search-group>
      <div class="settlement-price-row__title"><strong data-dialog-field-search-group-title>价格 {{ index+1 }}</strong><el-button type="danger" link @click="modelValue.prices.splice(index,1)">移除</el-button></div>
      <el-row :gutter="12">
        <el-col :xs="24" :md="6"><el-form-item label="价格类型" :prop="`settlement.prices.${index}.category`" :rules="[{required:true,message:'请选择价格类型',trigger:'change'}]"><el-select v-model="row.category" placeholder="口译/笔译/标注/采集" style="width:100%"><el-option v-for="item in settlementCategoryOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="6"><el-form-item label="金额" :prop="`settlement.prices.${index}.amount`" :rules="[{required:true,type:'number',min:0,message:'请输入不小于0的金额',trigger:'change'}]"><el-input-number v-model="row.amount" :min="0" :precision="6" :controls="false" style="width:100%" /></el-form-item></el-col>
        <el-col :xs="24" :md="6"><el-form-item label="计价单位" :prop="`settlement.prices.${index}.unit`" :rules="[{required:true,message:'请选择计价单位',trigger:'change'},{max:50,message:'计价单位最多50字',trigger:'change'}]"><el-select v-model="row.unit" filterable allow-create default-first-option style="width:100%"><el-option v-for="item in settlementUnitOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="6"><el-form-item label="货币" :prop="`settlement.prices.${index}.currency`" :rules="[{required:true,message:'请选择货币',trigger:'change'}]"><el-select v-model="row.currency" style="width:100%"><el-option v-for="item in settlementCurrencyOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
      </el-row>
    </div>
    <el-empty v-if="!modelValue.prices.length" description="暂无价格，可点击添加价格" :image-size="50" />
  </div>
</template>
<script setup>
import PaymentCodeField from '@/components/common/PaymentCodeField.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { settlementCategoryOptions,settlementUnitOptions,settlementCurrencyOptions,newSettlementPrice } from '@/utils/talentSettlement'
const props=defineProps({modelValue:{type:Object,required:true}})
function addPrice(){props.modelValue.prices.push(newSettlementPrice())}
function invoiceChanged(value){if(value!==true&&value!==false)props.modelValue.invoiceAvailable=null}
</script>
<style scoped>
.settlement-price-heading,.settlement-price-row__title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.settlement-price-row{border:1px solid var(--el-border-color);border-radius:8px;padding:14px;margin-bottom:12px;background:#fff}
</style>
