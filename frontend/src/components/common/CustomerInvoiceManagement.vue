<template><section><CustomerInvoiceProfile :client-id="clientId" :can-write="canWrite" /><CustomerInvoiceRecords :client-id="clientId" @open-invoice="openInvoice" /><ProjectInvoiceDialog v-model="visible" :context="context" /></section></template>
<script setup>
import {ref} from 'vue'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import CustomerInvoiceRecords from './CustomerInvoiceRecords.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const visible=ref(false),context=ref({})
function openInvoice(row){context.value={projectId:row.root_id||row.id,orderId:row.id};visible.value=true}
</script>
