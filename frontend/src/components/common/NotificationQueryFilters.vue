<template>
 <AppForm data-auto-draft="off" :model="feed.filters" inline class="notification-query-filters" @submit.prevent="feed.query()">
  <el-form-item label="关键词" class="keyword"><el-input v-model="feed.filters.keyword" clearable maxlength="500" placeholder="搜索标题、内容、项目或需求编号" aria-label="搜索通知" @input="feed.keywordInput" @keyup.enter="feed.query()"/></el-form-item>
  <el-form-item label="类型"><el-select :teleported="false" v-model="feed.filters.notificationType" clearable aria-label="通知类型" placeholder="全部类型" @change="feed.query()"><el-option label="全部类型" value=""/><el-option v-for="kind in feed.options.value.types" :key="kind" :value="kind" :label="typeLabel(kind)"/></el-select></el-form-item>
  <el-form-item label="阅读状态"><el-select :teleported="false" v-model="feed.filters.readStatus" aria-label="通知阅读状态" @change="feed.query()"><el-option label="全部" value="all"/><el-option label="未读" value="unread"/><el-option label="已读" value="read"/></el-select></el-form-item>
  <el-form-item label="发送人"><el-select :teleported="false" v-model="feed.filters.senderUserId" filterable clearable aria-label="通知发送人" placeholder="全部发送人" @visible-change="$event && feed.refreshOptions()" @change="feed.query()"><el-option v-for="person in feed.options.value.senders" :key="person.id" :value="person.id" :label="person.name"/></el-select></el-form-item>
  <el-form-item label="执行状态"><el-select :teleported="false" v-model="feed.filters.executionStatus" clearable aria-label="通知执行状态" placeholder="全部执行状态" @change="feed.query()"><el-option v-for="(label,value) in states" :key="value" :value="value" :label="label"/></el-select></el-form-item>
  <slot/>
  <el-form-item><el-button type="primary" @click="feed.query()">查询</el-button><el-button @click="feed.reset()">重置</el-button></el-form-item>
 </AppForm>
</template>
<script setup>
defineProps({feed:{type:Object,required:true}})
const states={pending:'待执行',received:'已收到',in_progress:'执行中',completed:'已执行/已完成',cancelled:'已取消',not_applicable:'不涉及执行/无状态记录'}
const labels={resource_request_dispatch:'资源需求及回执',chat_summary:'总结同步',meeting_invitation:'会议安排',meeting_task:'会议任务',workflow_handover_pending:'待确认的任务交接',project_manager_handover_pending:'项目经理交接待确认',client_manager_handover_pending:'客户经理交接待确认',project_manager_handover_accepted:'项目经理交接已接收',client_manager_handover_accepted:'客户经理交接已接收',workflow:'工作流通知',invoice_request:'发票需求',invoice:'发票通知'}
const typeLabel=kind=>labels[kind]||kind
</script>
<style scoped>
.notification-query-filters{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;flex:none;padding:10px 12px;margin-bottom:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px}.notification-query-filters :deep(.el-form-item){margin:0}.keyword{flex:1 1 260px}.keyword :deep(.el-form-item__content){flex:1}.notification-query-filters :deep(.el-select){width:160px}
</style>
