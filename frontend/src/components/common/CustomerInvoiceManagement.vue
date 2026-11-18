<template>
  <section>
    <CustomerInvoiceProfile :client-id="clientId" :can-write="canWrite" />
    <section v-if="clientId" class="sub-client-invoice-profiles" v-loading="loadingBuyers">
      <strong>子客户开票信息</strong>
      <el-select v-if="subClients.length" v-model="subClientId" filterable
        aria-label="选择子客户" placeholder="请选择子客户">
        <el-option v-for="buyer in subClients" :key="buyer.id" :value="buyer.id" :label="buyerLabel(buyer)" />
      </el-select>
      <el-alert v-if="buyerError" type="error" :closable="false" :title="buyerError">
        <el-button link @click="loadBuyers">重试</el-button>
      </el-alert>
      <small v-else-if="!loadingBuyers && !subClients.length">暂无子客户</small>
      <CustomerInvoiceProfile v-if="subClientId" :key="subClientId" :client-id="clientId"
        :sub-client-id="subClientId" :can-write="canWrite" />
    </section>
    <el-tabs v-model="scope">
      <el-tab-pane label="项目开票记录" name="standard" />
      <el-tab-pane label="特殊结算开票记录" name="special" />
    </el-tabs>
    <CustomerInvoiceRecords :key="scope" :client-id="clientId" :can-write="canWrite"
      :settlement-scope="scope" :invoice-buyers="buyers" hide-heading @open-invoice="openInvoice" />
    <ProjectInvoiceDialog v-model="visible" :context="context" :special="context.special" />
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {buyerLabel,getClientInvoiceBuyers} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import CustomerInvoiceProfile from './CustomerInvoiceProfile.vue'
import CustomerInvoiceRecords from './CustomerInvoiceRecords.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const visible=ref(false),context=ref({}),scope=ref('standard')
const buyers = ref(null)
const subClients = computed(() => buyers.value?.sub_clients || [])
const subClientId = ref('')
const loadingBuyers = ref(false)
const buyerError = ref('')
let controller

async function loadBuyers() {
  controller?.abort()
  if (!props.clientId) return
  const request = controller = new AbortController()
  loadingBuyers.value = true
  buyerError.value = ''
  try {
    const result = await getClientInvoiceBuyers(props.clientId, { signal: request.signal })
    if (!request.signal.aborted) {
      buyers.value = result
      if (!subClients.value.some(buyer => buyer.id === subClientId.value)) subClientId.value = subClients.value[0]?.id || ''
    }
  } catch (error) {
    if (!request.signal.aborted) buyerError.value = getLocalizedErrorMessage(error, '加载开票对象失败')
  } finally {
    if (!request.signal.aborted) loadingBuyers.value = false
  }
}

watch(() => props.clientId, () => {
  buyers.value = null
  subClientId.value = ''
  loadingBuyers.value = false
  void loadBuyers()
}, { immediate: true })
onBeforeUnmount(() => controller?.abort())
function openInvoice(row){context.value={projectId:row.root_id||row.id,orderId:row.id,special:row.special};visible.value=true}
</script>
<style scoped>
.sub-client-invoice-profiles { margin: 16px 0; padding: 12px; border: 1px solid var(--el-border-color-lighter); }
.sub-client-invoice-profiles > .el-select { width: min(350px, 100%); margin-inline-start: 12px; }
.sub-client-invoice-profiles > small { margin-inline-start: 12px; color: var(--el-text-color-secondary); }
</style>
