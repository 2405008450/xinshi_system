<template>
  <section class="chat-request-notifications" aria-label="会话业务通知">
    <header><div><h3>通知</h3><p>总结同步、资源需求、取消通知及回执。点击查看完整内容。</p></div><el-button :loading="feed.loading.value" @click="feed.pageChanged()">刷新</el-button></header>
    <AppForm :model="feed.filters" :inline="true" class="chat-request-notifications__filters" @submit.prevent="feed.query()">
      <el-form-item label="关键词" class="notification-keyword"><el-input v-model="feed.filters.keyword" clearable maxlength="500" placeholder="搜索标题、内容、项目或需求编号" aria-label="搜索通知" @input="feed.keywordInput" @keyup.enter="feed.query()" /></el-form-item>
      <el-form-item label="类型"><el-select v-model="feed.filters.notificationType" aria-label="通知类型" placeholder="全部类型" @change="feed.query()"><el-option label="全部类型" value="" /><el-option label="资源需求及回执" value="resource_request_dispatch" /><el-option label="总结同步" value="chat_summary" /></el-select></el-form-item>
      <el-form-item label="阅读状态"><el-select v-model="feed.filters.readStatus" aria-label="通知阅读状态" @change="feed.query()"><el-option label="全部" value="all" /><el-option label="未读" value="unread" /><el-option label="已读" value="read" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="feed.query()">查询</el-button><el-button @click="feed.reset()">重置</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="feed.error.value" :title="feed.error.value" type="error" :closable="false" />
    <div class="chat-request-notifications__list" v-loading="feed.loading.value">
      <el-empty v-if="!feed.loading.value && !feed.items.value.length && !feed.error.value" description="暂无符合条件的通知" :image-size="64" />
      <article v-for="item in feed.items.value" :key="item.id" class="chat-request-notifications__item" :class="{'is-unread':!item.is_read}">
        <button type="button" class="chat-request-notifications__content" @click="open(item)">
        <strong><i v-if="!item.is_read" aria-label="未读" />{{ item.title }}</strong><p>{{ item.content }}</p><time>{{ formatTime(item.created_at) }}</time>
        </button>
        <el-button v-if="item.can_open_resource_request && hasPermission('projects:write')" type="primary" plain class="chat-request-notifications__entry" @click="editRequest(item)">资源需求</el-button>
      </article>
    </div>
    <el-pagination v-model:current-page="feed.page.value" v-model:page-size="feed.pageSize.value" :page-sizes="[10,30,50,100]" :total="feed.total.value" layout="total,sizes,prev,pager,next,jumper" class="chat-request-notifications__pagination" @current-change="feed.pageChanged" @size-change="feed.pageSizeChanged" />
    <el-config-provider :z-index="10000"><ResourceRequestDispatchDialog v-if="batchId" :batch-id="batchId" @close="batchId=''" /><ResourceRequestEditor v-if="requestSource" editor-only :source-request="requestSource" @editor-closed="requestSource=null" /></el-config-provider>
  </section>
</template>
<script setup>
import { defineAsyncComponent, ref } from 'vue'
import { hasPermission } from '@/utils/permission'
import { ElMessage } from 'element-plus'
import { formatBusinessDateTime as formatTime } from '@/utils/dateTime'
const ResourceRequestDispatchDialog = defineAsyncComponent(() => import('@/views/resource/components/ResourceRequestDispatchDialog.vue'))
const props = defineProps({ feed: { type: Object, required: true } })
const ResourceRequestEditor = defineAsyncComponent(() => import('@/views/resource/ResourceRequests.vue'))
const requestSource = ref(null)
const batchId = ref('')
async function editRequest(item) {
  if (!item.can_open_resource_request || !hasPermission('projects:write') || requestSource.value) return
  try { await props.feed.read(item); requestSource.value = { dispatchBatchId: String(item.related_entity_id) } }
  catch (e) { ElMessage.error(e.detail || e.message || '打开资源需求失败') }
}
async function open(item) {
  if (!item.related_entity_id) return
  try { await props.feed.read(item);if(item.notification_type==='chat_summary'){window.dispatchEvent(new CustomEvent('chat-open-summary',{detail:{issueId:item.related_entity_id}}));return} batchId.value = String(item.related_entity_id) }
  catch (e) { ElMessage.error(e.detail || e.message || '打开通知失败') }
}
</script>
<style scoped>
.chat-request-notifications{display:flex;flex-direction:column;height:100%;min-height:0;background:white;padding:18px;box-sizing:border-box}
header{display:flex;gap:12px;align-items:flex-start;justify-content:space-between;flex:none}h3{margin:0 0 8px}header p{margin:0 0 16px;color:#64748b;font-size:12px;line-height:1.7}
.chat-request-notifications__list{flex:1;min-height:0;overflow-y:auto}.chat-request-notifications__item{display:block;width:100%;box-sizing:border-box;padding:14px;margin-bottom:10px;text-align:left;border:1px solid #e2e8f0;border-radius:8px;background:white;color:#334155;cursor:pointer}.chat-request-notifications__item.is-unread{background:#f1f6ff;border-color:#b9cef1}.chat-request-notifications__item strong{line-height:1.7;overflow-wrap:anywhere}.chat-request-notifications__item p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;font-size:13px}.chat-request-notifications__item time{font-size:12px;color:#64748b}.chat-request-notifications__item i{display:inline-block;width:7px;height:7px;background:#dc2626;border-radius:50%;margin-right:8px}
.chat-request-notifications__filters{display:flex;align-items:center;gap:8px 12px;flex-wrap:wrap;flex:none;padding:10px 12px;margin-bottom:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px}
.chat-request-notifications__filters :deep(.el-form-item){margin:0}.notification-keyword{flex:1 1 300px}.notification-keyword :deep(.el-form-item__content){flex:1}.chat-request-notifications__filters :deep(.el-select){width:160px}
.chat-request-notifications__pagination{flex:none;max-width:100%;overflow-x:auto;padding-top:10px}
</style>

<style scoped>
.chat-request-notifications__item{display:flex;align-items:center;gap:16px;cursor:default}.chat-request-notifications__content{flex:1;min-width:0;text-align:left;border:0;padding:0;background:transparent;color:inherit;font:inherit;cursor:pointer}.chat-request-notifications__entry{flex:none}.chat-request-notifications__content:focus-visible{outline:2px solid #93c5fd;outline-offset:4px}
@media(max-width:600px){.chat-request-notifications__item{flex-wrap:wrap}.chat-request-notifications__content{flex-basis:100%}.chat-request-notifications__entry{margin-left:auto}}
</style>
