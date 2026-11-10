<template>
  <div class="billing-tax-choice" data-dialog-field-search-label="计费口径" data-dialog-field-search-aliases="含税 不含税 结算金额">
    <span>计费口径</span>
    <el-radio-group v-if="choices.length>1" :model-value="effective" :disabled="disabled" size="small" aria-label="计费口径" @update:model-value="$emit('update:modelValue',$event)"><el-radio-button v-for="mode in choices" :key="mode" :value="mode">{{billingTaxLabel(mode)}}</el-radio-button></el-radio-group>
    <ReadonlyField v-else :model-value="choices.length?`${billingTaxLabel(effective)}（自动）`:'请先填写金额'" source="auto" />
    <small>用于本订单计费及新生成的对账单</small>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import ReadonlyField from './ReadonlyField.vue'
import {billingTaxChoices,effectiveBillingTaxMode,billingTaxLabel} from '@/utils/billingTaxMode'
const props=defineProps({modelValue:String,order:{type:Object,required:true},disabled:Boolean})
defineEmits(['update:modelValue'])
const choices=computed(()=>billingTaxChoices(props.order))
const effective=computed(()=>effectiveBillingTaxMode({...props.order,billingTaxMode:props.modelValue}))
</script>
<style scoped>
.billing-tax-choice{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}.billing-tax-choice>.el-input{width:150px}.billing-tax-choice>small{font-size:11px;color:var(--el-text-color-secondary)}
</style>
