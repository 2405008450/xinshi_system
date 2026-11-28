<template><div class="payment-proof-pair"><el-form-item label="信实收款截图及备注"><ScreenshotInput :model-value="receiptProofs" type="textarea" :rows="2" :maxlength="20000" placeholder="粘贴、拖入或上传信实收款截图，填写收款备注" @update:model-value="$emit('update:receiptProofs',$event)"/></el-form-item><el-form-item label="客户支付截图及备注"><template #label><span class="proof-title">客户支付截图及备注<slot name="status"/></span></template><ScreenshotInput :model-value="proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="粘贴、拖入或上传客户支付截图，填写付款备注" upload-help="凭证修改或移除后可在付款修改记录中查看。" @update:model-value="$emit('update:proofs',$event)"/></el-form-item></div></template>
<script setup>
import ScreenshotInput from './ScreenshotInput.vue'
defineProps({proofs:{type:String,default:''},receiptProofs:{type:String,default:''}})
defineEmits(['update:proofs','update:receiptProofs'])
</script>
<style scoped>.payment-proof-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.payment-proof-pair>:deep(.el-form-item){min-width:0}.payment-proof-pair>:deep(.el-form-item:first-child){order:2}.payment-proof-pair>:deep(.el-form-item:last-child){order:1}.proof-title{display:flex;align-items:center;gap:8px;flex-wrap:wrap}@media(max-width:700px){.payment-proof-pair{grid-template-columns:1fr}}</style>
