<template>
  <section class="chat-session-directory" :aria-label="mine ? '我的项目' : '全部群聊'">
    <div class="chat-session-directory__scroll">
    <p role="status">{{ mine ? '我的项目' : '全部群聊' }} · {{ total }} 个</p>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
    <p v-if="loading">加载中…</p>
    <el-empty v-else-if="!items.length && !error" description="没有符合条件的会话" :image-size="48" />
    <button v-for="item in items" draggable="true" @dragstart="dragChatSession($event,{...item,projectType:item.kind})" :key="item.key" type="button" class="chat-session-directory__item" :class="{'is-pinned':item.pinned}" @click="$emit('open', { ...item, projectType: item.kind })">
      <strong>{{ item.title }}</strong><small><span v-if="item.pinned" class="chat-session-directory__pin">↑ 已置顶 · </span>{{ item.subtitle }} · {{actionLabel}}</small>
    </button>
    </div>
    <ChatListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
  </section>
</template>
<script setup>
import {dragChatSession} from '@/utils/chatPersonalFolders'
import { ref, watch, onBeforeUnmount } from 'vue'
import ChatListPagination from './ChatListPagination.vue'
import { chatRequest } from '@/api/projectChat'
const props = defineProps({ keyword: String, revision: Number, preferencesRevision: String, active: Boolean, mine: Boolean, actionLabel:{type:String,default:'点击查看聊天记录'} })
defineEmits(['open'])
const items = ref([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), error = ref('')
let controller, generation = 0
async function load() {
  controller?.abort()
  const version = ++generation, identity = localStorage.getItem('user_id')
  loading.value = false
  if (!props.active) return
  const current = new AbortController(); controller = current
  loading.value = true; error.value = ''; items.value = []
  try {
    const data = await chatRequest('sessions/history', { params: { keyword: props.keyword || '', mine: props.mine, groups_only: true, offset: (page.value - 1) * pageSize.value, limit: pageSize.value }, signal: current.signal })
    if (version !== generation || identity !== localStorage.getItem('user_id')) return
    total.value = data.total || 0
    const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (page.value > lastPage) { page.value = lastPage; return load() }
    items.value = data.items || []
  } catch (e) { if (version === generation && !current.signal.aborted) error.value = e.detail || e.message || '全部群聊暂时无法加载' }
  finally { if (version === generation) loading.value = false }
}
watch(() => [props.keyword, props.revision, props.preferencesRevision, props.active, props.mine], () => { page.value = 1; total.value = 0; items.value = []; load() }, { immediate: true })
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style scoped>
.chat-session-directory{display:flex;flex-direction:column;height:100%;min-height:0;overflow:hidden;box-sizing:border-box;padding:0;font-size:12px;color:#64748b}.chat-session-directory__scroll{flex:1;min-height:0;overflow-y:auto;padding:4px 8px;overscroll-behavior:contain}.chat-session-directory__item{display:flex;flex-direction:column;gap:6px;width:100%;padding:12px 8px;text-align:left;border:0;border-bottom:1px solid #e2e8f0;background:transparent;color:#334155;cursor:pointer}.chat-session-directory__item:hover{background:#e8eef7}.chat-session-directory__item strong{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chat-session-directory__item small{color:#64748b}
</style>
<style scoped>
.chat-session-directory__item.is-pinned{background:#f1f5f9}
.chat-session-directory__pin{color:var(--el-color-primary);font-weight:600}
</style>
