<template>
  <div v-if="topics.ready" class="chat-topic-navigation">
    <el-popover v-if="compact" trigger="click" placement="bottom-start" :width="300" popper-class="chat-topic-popover">
      <template #reference><el-button text size="small">讨论主题 ▾</el-button></template>
      <TopicMenu />
    </el-popover>
    <TopicMenu v-else />
    <DraggableFormDialog :z-index="100002" v-model="resultsVisible" :title="`${selected?.path || '讨论主题'} · 消息检索`" width="min(820px, calc(100vw - 32px))" top="5vh" class="issue-dialog chat-topic-results-dialog" append-to-body destroy-on-close>
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
        <el-button v-if="nextBefore" :loading="loading" @click="load(true)">加载更多</el-button>
      </div>
      <template #footer><el-button @click="resultsVisible = false">关闭</el-button></template>
    </DraggableFormDialog>
    <ChatTopicManager ref="managerRef" />
  </div>
</template>
<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElMessage } from 'element-plus'
import { useChatTopics } from '@/composables/useChatTopics'
import { useResourceIssues } from '@/composables/useResourceIssues'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { orderedTopicRoots, topicSearchParams } from '@/utils/chatTopics'
import { topicApi } from '@/api/chatTopics'
import { issueCategories } from '@/utils/resourceIssues'
import { formatBusinessDateTime } from '@/utils/dateTime'
import ChatTopicManager from './ChatTopicManager.vue'
import '@/views/resource/components/issueDialogs.css'
const props = defineProps({ compact: Boolean, allAllowed: Boolean, projectId: { type: [String, Number], default: '' }, projectType: { type: String, default: '' } })
const emit = defineEmits(['annotation'])
const route = useRoute(), { topics, refresh } = useChatTopics(), { access, collect, refreshIssueAccess } = useResourceIssues()
const { openChat, setLayout } = useProjectChatDock()
const roots = computed(() => orderedTopicRoots(topics.items, route.meta.chatContext))
const resultsVisible = ref(false), managerRef = ref(), selected = ref(), scope = ref('current'), keyword = ref('')
const items = ref([]), total = ref(0), nextBefore = ref(null), loading = ref(false), error = ref('')
let controller, generation = 0, timer
const menuElements = new Set()
async function choose(row) {
  if (row.kind === 'annotation') { setLayout('workspace'); emit('annotation'); window.dispatchEvent(new CustomEvent('chat-topic-show-annotation')); return }
  if (!props.projectId && !props.allAllowed) { ElMessage.info('请先选择一个会话'); return }
  selected.value = row; keyword.value = ''; scope.value = props.projectId ? 'current' : 'all'
  resultsVisible.value = true; query()
}
const TopicMenu = defineComponent({ setup: () => () => h('div', { class: 'chat-topic-menu', ref: element => { if (element) menuElements.add(element) } }, [
  ...roots.value.map(root => h('div', { class: 'chat-topic-root', key: root.id }, [
    h(ElButton, { text: true, size: 'small', title: root.description, onClick: () => choose(root) }, () => root.name),
    ...topics.items.filter(row => row.parent_id === root.id && row.active).map(row => h(ElButton, { text: true, size: 'small', class: 'chat-topic-child', title: row.description, onClick: () => choose(row), key: row.id }, () => row.name)),
  ])),
  access.can_collect ? h('div', { class: 'chat-topic-add' }, [h('small', '新增开拓事项'), ...issueCategories.map(category => h(ElButton, { link: true, size: 'small', onClick: () => collect('', category.value) }, () => category.label))]) : null,
  topics.can_manage ? h(ElButton, { text: true, size: 'small', onClick: () => managerRef.value.open().catch(e => ElMessage.error(e.message)) }, () => '管理主题菜单') : null,
]) })
async function load(append = false) {
  clearTimeout(timer); controller?.abort(); const seq = ++generation
  controller = new AbortController(); const activeController = controller
  loading.value = true; error.value = ''
  if (!append) { items.value = []; total.value = 0; nextBefore.value = null }
  try {
    const data = await topicApi.search(topicSearchParams({ topicId: selected.value.id, scope: scope.value, projectId: props.projectId, projectType: props.projectType, keyword: keyword.value, before: append ? nextBefore.value : null }), activeController.signal)
    if (seq !== generation || !resultsVisible.value) return
    items.value = append ? [...items.value, ...data.items] : data.items; total.value = data.total; nextBefore.value = data.next_before
  } catch (e) { if (seq === generation && !activeController.signal.aborted) error.value = e.message }
  finally { if (seq === generation) loading.value = false }
}
function query() { if (resultsVisible.value) load() }
function locate(item) { resultsVisible.value = false; openChat({ projectId: item.conversation_id, projectType: item.conversation_type, title: item.source_title, subtitle: '主题消息', messageId: item.id }) }
watch(keyword, value => { clearTimeout(timer); controller?.abort(); generation++; if (!value) query(); else timer = setTimeout(query, 400) })
watch(() => [props.projectId, props.projectType], () => { if (resultsVisible.value && scope.value === 'current') query() })
watch(() => route.meta.chatContext, () => nextTick(() => menuElements.forEach(element => { element.scrollTop = 0 })))
watch(resultsVisible, value => { if (!value) { clearTimeout(timer); controller?.abort(); generation++ } })
onMounted(() => { refresh().catch(() => {}); refreshIssueAccess().catch(() => {}) })
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); generation++ })
</script>
<style scoped>
.chat-topic-search-controls{display:flex;gap:8px;flex-wrap:wrap}.chat-topic-search-controls>.el-input{flex:1;min-width:180px}.chat-topic-search-controls>.el-select{width:190px}.chat-topic-results article{padding:12px 0;border-bottom:1px solid var(--el-border-color-lighter)}.chat-topic-results article>div{display:flex;gap:8px;flex-wrap:wrap}.chat-topic-results p{white-space:pre-wrap;overflow-wrap:anywhere}.chat-topic-results small,.chat-topic-search-hint{color:var(--el-text-color-secondary)}.chat-topic-results .el-button{margin-left:12px}
</style>
<style>
.chat-topic-menu{max-height:min(400px,calc(100vh - 160px));overflow-y:auto;overflow-x:hidden}.chat-topic-root{display:flex;flex-direction:column;align-items:stretch}.chat-topic-root>.el-button{margin-left:0;justify-content:flex-start}.chat-topic-root>.chat-topic-child{padding-left:24px}.chat-topic-add{display:flex;gap:8px;flex-wrap:wrap;padding:8px}.chat-topic-add small{width:100%}.chat-workspace__sessions .chat-topic-navigation{border-bottom:1px solid var(--el-border-color-lighter);padding:4px 0}.chat-workspace__sessions .chat-topic-menu{max-height:260px}
</style>
