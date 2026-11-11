<template><el-descriptions :column="2" border size="small" class="invoice-party-details"><el-descriptions-item v-for="field in invoicePartyFields" :key="field.key" :label="field.label"><span>{{party?.[field.key]||'待填写'}}</span></el-descriptions-item></el-descriptions></template>
<script setup>
import {invoicePartyFields} from '@/api/invoiceParties'
defineProps({party:Object})
</script>
<style scoped>.invoice-party-details{margin:8px 0}.invoice-party-details span{white-space:pre-wrap;overflow-wrap:anywhere;user-select:text}.invoice-party-details :deep(.el-descriptions__table){table-layout:fixed}</style>
