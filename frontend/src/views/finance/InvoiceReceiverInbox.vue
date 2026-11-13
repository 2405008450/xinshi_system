<template>
  <el-card shadow="never">
    <template #header><strong>开票通知</strong></template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="notifications" row-key="id" empty-text="暂无开票通知">
      <el-table-column label="通知" min-width="230">
        <template #default="{row}">
          <el-button link type="primary" @click="open(row)">{{ row.title }}</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="230" />
      <el-table-column label="时间" width="165">
        <template #default="{row}">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
  </el-card>
  <InvoiceRequestDialog v-if="requestId" :key="requestId" :request-id="requestId" @close="requestId = ''" />
</template>

<script setup>
import {onBeforeUnmount, onMounted, ref} from 'vue'
import {getNotificationPage, markNotificationRead} from '@/api/notifications'
import {formatBusinessDateTimeMinute as formatTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {subscribe} from '@/utils/realtimeSocket'
import InvoiceRequestDialog from '@/components/common/InvoiceRequestDialog.vue'

const notificationTypes = ['invoice_request','invoice_delivered','invoice_receipt']
const notifications = ref([]), page = ref(1), total = ref(0), loading = ref(false), error = ref('')
const requestId = ref('')
let controller, unsubscribe
async function load() {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  error.value = ''
  try {
    const data = await getNotificationPage({notification_types:notificationTypes, skip:(page.value-1)*20, limit:20}, {signal:current.signal})
    if (current.signal.aborted) return
    notifications.value = data.items
    total.value = data.total
  } catch (e) {
    if (!current.signal.aborted) error.value = getLocalizedErrorMessage(e, '加载开票通知失败')
  } finally {
    if (!current.signal.aborted) loading.value = false
  }
}
function open(row) {
  requestId.value = row.related_entity_id
  if (!row.is_read) void markNotificationRead(row.id).then(() => { row.is_read = true }).catch(() => {})
}
onMounted(() => {
  void load()
  unsubscribe = subscribe('notification', event => {
    if (notificationTypes.includes(event?.notification?.notification_type)) void load()
  })
})
onBeforeUnmount(() => { controller?.abort(); unsubscribe?.() })
</script>
