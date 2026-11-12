<template>
  <DraggableFormDialog class="received-notifications-dialog" :model-value="true" title="收到的通知"
    width="min(880px, calc(100vw - 32px))" top="6vh" @update:model-value="emit('close')">
    <AppForm :model="filters" class="received-filters" :inline="true" @submit.prevent="query()">
      <el-form-item class="received-search">
        <el-input v-model="filters.keyword" clearable maxlength="500" placeholder="搜索通知标题、内容、订单号或需求编号"
          aria-label="搜索通知" @input="keywordInput" @keyup.enter="query()" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="filters.category" aria-label="通知分类" @change="changeCategory">
          <el-option label="全部分类" value="" />
          <el-option v-for="category in categories" :key="category.value" v-bind="category" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="filters.category === 'conversation_saved'" label="保存类型">
        <el-select v-model="filters.summaryCategory" aria-label="会话保存类型" @change="query()">
          <el-option label="全部保存类型" value="" />
          <el-option v-for="category in issueCategories" :key="category.value" v-bind="category" />
          <el-option label="未细分" value="other" />
        </el-select>
      </el-form-item>
      <el-form-item label="阅读状态">
        <el-select v-model="filters.readStatus" aria-label="阅读状态" @change="query()">
          <el-option label="全部" value="all" />
          <el-option label="未读" value="unread" />
          <el-option label="已读" value="read" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="query()">查询</el-button>
        <el-button @click="reset()">重置</el-button>
      </el-form-item>
    </AppForm>

    <div v-loading="loading" class="received-list">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="pageChanged()">重试</el-button></el-alert>
      <el-empty v-else-if="!loading && !items.length" description="暂无符合条件的通知" :image-size="72" />
      <article v-for="item in items" :key="item.id" class="received-item" :class="{'is-unread': !item.is_read}">
        <div class="received-item-heading">
          <strong>{{ item.title }}</strong>
          <el-tag size="small" effect="plain">{{ categoryLabel(item.category) }}</el-tag>
          <el-tag v-if="item.summary_category && item.summary_category !== 'other'" size="small" type="info" effect="plain">{{ issueCategoryLabel(item.summary_category) }}</el-tag>
        </div>
        <p>{{ item.content }}</p>
        <div class="received-item-footer">
          <time>{{ formatTime(item.created_at) }}</time>
          <span>{{ item.is_read ? '已读' : '未读' }}</span>
          <el-button v-if="!item.is_read" link type="primary" :loading="reading.has(item.id)" @click="markRead(item)">标记已读</el-button>
          <el-button v-if="hasTarget(item)" link type="primary" @click="emit('open', item)">查看关联业务</el-button>
        </div>
      </article>
    </div>
    <template #footer>
      <el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" :pager-count="5"
        layout="total,prev,pager,next" @current-change="pageChanged" />
      <el-button @click="emit('close')">关闭</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatRequestNotifications } from '@/composables/useChatRequestNotifications'
import { issueCategories, issueCategoryLabel } from '@/utils/resourceIssues'
import { formatBusinessDateTimeMinute as formatTime } from '@/utils/dateTime'

defineProps({ hasTarget: { type: Function, required: true } })
const emit = defineEmits(['close', 'open'])
const { items, loading, error, total, page, pageSize, filters, read, query, keywordInput, reset, pageChanged } = useChatRequestNotifications({ allBusiness: true })
const categories = [
  { value: 'translation', label: '笔译项目' },
  { value: 'interpretation', label: '口译项目' },
  { value: 'annotation', label: '标注项目' },
  { value: 'recruitment', label: '招聘项目' },
  { value: 'conversation_saved', label: '会话分类保存' },
  { value: 'resource_request', label: '资源需求' },
  { value: 'invoice', label: '发票需求' },
  { value: 'administration', label: '行政考勤' },
  { value: 'other', label: '其他' },
]
const categoryLabel = value => categories.find(item => item.value === value)?.label || '其他'
const reading = reactive(new Set())
function changeCategory() {
  filters.summaryCategory = ''
  return query()
}
async function markRead(item) {
  if (reading.has(item.id)) return
  reading.add(item.id)
  try { await read(item) }
  catch (error) { ElMessage.error(error.detail || error.message || '标记已读失败') }
  finally { reading.delete(item.id) }
}
</script>

<style scoped>
:global(.received-notifications-dialog) { display: flex; flex-direction: column; height: min(760px, 88vh); max-height: 88vh; overflow: hidden; }
:global(.received-notifications-dialog .el-dialog__body) { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
:global(.received-notifications-dialog .el-dialog__footer) { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex: none; border-top: 1px solid var(--el-border-color-lighter); }
.received-filters { flex: none; display: flex; flex-wrap: wrap; gap: 8px 12px; padding-bottom: 12px; }
.received-filters :deep(.el-form-item) { margin: 0; }
.received-filters :deep(.el-select) { width: 126px; }
.received-search { flex: 1 1 100%; }
.received-list { flex: 1; min-height: 0; overflow-y: auto; }
.received-item { padding: 12px 14px; margin-bottom: 8px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.received-item.is-unread { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-7); }
.received-item-heading, .received-item-footer { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.received-item-heading strong { flex: 1 1 160px; overflow-wrap: anywhere; }
.received-item p { margin: 6px 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.received-item-footer { color: var(--el-text-color-secondary); font-size: 12px; }
.received-item-footer time { margin-right: auto; }
</style>
