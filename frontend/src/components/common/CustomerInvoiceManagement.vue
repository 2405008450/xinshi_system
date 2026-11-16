<template>
  <section>
    <CustomerInvoiceProfile :client-id="clientId" :can-write="canWrite" />
    <el-tabs v-model="scope">
      <el-tab-pane label="项目开票记录" name="standard" />
      <el-tab-pane label="特殊结算开票记录" name="special" />
    </el-tabs>
    <CustomerInvoiceRecords :key="scope" :client-id="clientId" :can-write="canWrite"
      :settlement-scope="scope" hide-heading @open-invoice="openInvoice" />
    <ProjectInvoiceDialog v-model="visible" :context="context" :special="context.special" />
  </section>
</template>
<script setup>
import {ref} from 'vue'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import CustomerInvoiceRecords from './CustomerInvoiceRecords.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const visible=ref(false),context=ref({}),scope=ref('standard')
function openInvoice(row){context.value={projectId:row.root_id||row.id,orderId:row.id,special:row.special};visible.value=true}
</script>
