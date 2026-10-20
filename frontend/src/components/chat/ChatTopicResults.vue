<template>
  <section class="chat-topic-results-panel">
    <template v-if="topic">
      <header class="chat-topic-results-heading"><strong>{{ topic.path || topic.name }}</strong><span>主题消息</span></header>
      <div class="chat-topic-search-controls">
        <el-input v-model="keyword" clearable placeholder="搜索主题下的消息内容" @keyup.enter="query" />
        <el-select popper-class="chat-topic-select-popper" v-if="allAllowed" v-model="scope" aria-label="主题检索范围" @change="query"><el-option label="当前会话" value="current" :disabled="!projectId" /><el-option label="全部可访问会话" value="all" /></el-select>
        <el-button @click="query">查询</el-button>
      </div>
      <p class="chat-topic-search-hint">{{ scope === 'all' ? '全部可访问会话' : '当前会话' }} · 共 {{ total }} 条消息</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button text @click="query">重试</el-button></el-alert>
      <div v-loading="loading" class="chat-topic-results">
        <el-empty v-if="!items.length && !loading && !error" description="暂无相关消息" :image-size="50" />
        <article v-for="item in items" :key="item.id">
          <div><strong>{{ item.source_title }}</strong><el-tag size="small" effect="plain">{{ item.topic_path }}</el-tag></div>
          <p>{{ item.content || '（附件消息）' }}</p>
          <small>{{ item.sender_name }} · {{ formatBusinessDateTime(item.created_at) }}</small>
          <el-button link type="primary" @click="locate(item)">定位原消息</el-button>
        </article>
        <el-button v-if="nextBefore" :disabled="loading" :loading="loading" @click="load(true)">加载更多</el-button>
      </div>
    </template>
    <el-empty v-else description="请选择讨论主题" :image-size="64" />
  </section>
</template>
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { topicApi } from '@/api/chatTopics'
import { topicSearchParams } from '@/utils/chatTopics'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
const props = defineProps({ topic: Object, active: Boolean, allAllowed: Boolean, projectId: { type: [String, Number], default: '' }, projectType: { type: String, default: '' } })
const emit = defineEmits(['locate'])
const { openChat } = useProjectChatDock()
const keyword = ref(''), scope = ref('all'), items = ref([]), total = ref(0), nextBefore = ref(null), loading = ref(false), error = ref('')
let controller, generation = 0, timer
async function load(append = false) {
  clearTimeout(timer); controller?.abort(); const seq = ++generation
  controller = new AbortController(); const activeController = controller
  loading.value = true; error.value = ''
  if (!append) { items.value = []; total.value = 0; nextBefore.value = null }
  try {
    const data = await topicApi.search(topicSearchParams({ topicId: props.topic.id, scope: scope.value, projectId: props.projectId, projectType: props.projectType, keyword: keyword.value, before: append ? nextBefore.value : null }), activeController.signal)
    if (seq !== generation || !props.active) return
    items.value = append ? [...items.value, ...data.items] : data.items; total.value = data.total; nextBefore.value = data.next_before
  } catch (e) { if (seq === generation && !activeController.signal.aborted) error.value = e.message }
  finally { if (seq === generation) loading.value = false }
}
function query() { if (props.active && props.topic) load() }
function locate(item) { emit('locate'); openChat({ projectId: item.conversation_id, projectType: item.conversation_type, title: item.source_title, subtitle: '主题消息', messageId: item.id }) }
watch(keyword, value => {
  clearTimeout(timer); controller?.abort(); generation++; loading.value = false
  items.value = []; total.value = 0; nextBefore.value = null; error.value = ''
  if (!value) query(); else timer = setTimeout(query, 400)
})
watch(() => [props.projectId, props.projectType], () => {
  if (!props.projectId && props.allAllowed) scope.value = 'all'
  if (props.active && (scope.value === 'current' || !props.projectId)) query()
})

watch(() => [props.topic?.id, props.active], () => {
  clearTimeout(timer); controller?.abort(); generation++; loading.value = false
  if (!props.active || !props.topic) return
  keyword.value = ''; scope.value = props.allAllowed ? 'all' : 'current'; query()
}, { immediate: true })
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); generation++ })
</script>
<style scoped>
.chat-topic-results-panel{height:100%;min-height:0;display:flex;flex-direction:column;box-sizing:border-box;padding:20px;background:var(--el-bg-color);overflow:hidden}
.chat-topic-results-heading{display:flex;gap:12px;align-items:baseline;margin-bottom:20px;overflow-wrap:anywhere}.chat-topic-results-heading strong{font-size:18px}.chat-topic-results-heading span,.chat-topic-search-hint,small{font-size:12px;color:var(--el-text-color-secondary)}
.chat-topic-search-controls{display:flex;gap:8px;flex-wrap:wrap}.chat-topic-search-controls>.el-input{flex:1;min-width:150px}.chat-topic-search-controls>.el-select{width:180px}
.chat-topic-results{flex:1;min-height:0;overflow-y:auto}.chat-topic-results article{padding:16px 0;border-bottom:1px solid var(--el-border-color-lighter)}.chat-topic-results article>div{display:flex;gap:8px;flex-wrap:wrap}.chat-topic-results p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}.chat-topic-results .el-button{margin-left:12px}
</style>
