<template>
  <section class="chat-session-directory" :aria-label="mine ? '我的项目' : '全部会话'">
    <p class="chat-session-directory__status" role="status">{{ mine ? '我的项目' : '全部会话' }} · {{ total }} 个</p>
    <p v-if="error" class="chat-session-directory__error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
    <p v-if="loading" class="chat-session-directory__loading">加载中…</p>
    <el-empty v-else-if="!displayItems.length && !error" description="没有符合条件的会话" :image-size="48" />
    <div
      v-for="session in displayItems"
      :key="session.key"
      class="chat-history-session"
      :class="{
        'is-active': session.key === activeKey,
        'is-pinned': session.pinned,
        'has-unread-mention': !!session.mentionUnread,
      }"
      role="button"
      tabindex="0"
      :title="[session.title || '未命名会话', session.subtitle, session.projectType !== 'direct' && Number.isFinite(session.memberCount) ? `${session.memberCount}人` : ''].filter(Boolean).join(' · ')"
      @click="emit(session.opened ? 'select' : 'open', session)"
      @contextmenu.prevent.stop="emit('menu', { event: $event, session })"
      @keydown.shift.f10.prevent.stop="emit('menu', { event: $event, session })"
      @keydown.enter.self="emit(session.opened ? 'select' : 'open', session)"
      @keydown.space.self.prevent="emit(session.opened ? 'select' : 'open', session)"
    >
      <span class="chat-history-session__left">
        <span class="chat-history-session__avatar" :class="`chat-history-session__avatar--${session.projectType}`" aria-hidden="true">{{ chatAvatarText(session.title || session.subtitle || '会') }}</span>
      </span>
      <span class="chat-history-session__main">
        <span class="chat-history-session__title">
          <strong>{{ session.title || session.subtitle || '未命名会话' }}</strong>
          <el-icon v-if="session.starred" title="已收藏" class="chat-history-session__star"><StarFilled /></el-icon>
          <time v-if="session.lastMessage?.createdAt" :title="formatBusinessDateTime(session.lastMessage.createdAt)">{{ chatDateLabel(session.lastMessage.createdAt) }}</time>
        </span>
        <span v-if="(['annotation', 'translation'].includes(session.projectType) && session.subtitle) || (session.projectType !== 'direct' && Number.isFinite(session.memberCount)) || (session.projectType === 'direct' && session.subtitle)" class="chat-history-session__sub">
          <ChatOrderIdentity v-if="['annotation', 'translation'].includes(session.projectType) && session.subtitle" :order-no="session.subtitle" :project-type="session.projectType" />
          <span v-else-if="session.projectType === 'direct' && session.subtitle" class="chat-history-session__member">{{ session.subtitle }}</span>
          <span v-if="session.projectType !== 'direct' && Number.isFinite(session.memberCount)" class="chat-history-session__member" :aria-label="`当前会话 ${session.memberCount} 人`">{{ typeLabel(session.projectType) }} · {{ session.memberCount }}人</span>
        </span>
        <span class="chat-history-session__preview-row">
          <b v-if="personalUnread(session)" class="chat-history-session__mention-label">[@我]</b>
          <b v-if="session.mentionAllUnread" class="chat-history-session__mention-broadcast">[@所有人]</b>
          <small class="chat-history-session__preview">
            <template v-if="session.lastMessage">
              <mark v-if="!session.mentionUnread && session.lastMessage.mentionsMe" class="chat-history-session__mention-preview" :class="{ 'chat-history-session__mention-broadcast': session.lastMessage.mentionAll }">{{ session.lastMessage.mentionAll ? '[@所有人]' : '[@我]' }}</mark>
              <span v-if="isUrgentPreview(session.lastMessage.preview)" class="chat-history-session__urgent">急</span>{{ `${session.lastMessage.senderName}：${cleanPreviewText(session.lastMessage.preview)}` }}
            </template>
            <template v-else>{{ session.subtitle && session.projectType !== 'direct' ? `${session.subtitle} · 点击查看聊天记录` : '点击查看聊天记录' }}</template>
          </small>
          <span v-if="session.mentionUnread" class="chat-history-session__unread" :aria-label="`${session.mentionUnread} 条未读提及`" title="未读提及">{{ session.mentionUnread > 99 ? '99+' : session.mentionUnread }}</span>
          <span v-if="sessionUnreadSignal(session).ordinary" class="chat-history-session__unread-dot" :class="{ 'is-manual': session.manualUnread }" role="status" :aria-label="session.manualUnread ? '已标为未读' : '有普通未读消息'" :title="session.manualUnread ? '已标为未读' : '有普通未读消息'" />
        </span>
      </span>
      <el-icon v-if="session.pinned" title="已置顶" class="chat-history-session__pin"><Top /></el-icon>
      <span class="chat-history-session__controls" @click.stop @keydown.stop @mousedown.stop>
        <button v-if="session.projectType !== 'direct'" type="button" class="chat-history-session__ctrl-btn" title="在分组中定位" :aria-label="`在分组中定位 ${session.title}`" @click="emit('locate', session)"><el-icon><Aim /></el-icon></button>
        <button type="button" class="chat-history-session__ctrl-btn chat-session-more-btn" aria-label="会话操作" title="会话操作" @click="emit('menu', { event: $event, session })">⋯</button>
      </span>
    </div>
    <ChatListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
  </section>
</template>
<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { Aim, StarFilled, Top } from '@element-plus/icons-vue'
import ChatListPagination from './ChatListPagination.vue'
import ChatOrderIdentity from './ChatOrderIdentity.vue'
import { chatRequest } from '@/api/projectChat'
import { chatAvatarText, chatDateLabel } from '@/utils/chatLayout'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { screenshotPreview } from '@/utils/screenshotReferences'
import { sessionUnreadSignal } from '@/utils/chatSessionList'

const props = defineProps({
  keyword: String,
  revision: Number,
  active: Boolean,
  mine: Boolean,
  sessions: { type: Array, default: () => [] },
  activeKey: { type: String, default: '' },
})
const emit = defineEmits(['open', 'select', 'locate', 'menu'])
const items = ref([]), total = ref(0), page = ref(1), pageSize = ref(20), loading = ref(false), error = ref('')
let controller, generation = 0

const typeLabel = type => type === 'discussion' ? '讨论' : type === 'direct' ? '私聊' : type === 'annotation' ? '标注' : '笔译'
const isUrgentPreview = text => /^\s*\*\*急\*\*/.test(String(text || ''))
const cleanPreviewText = text => screenshotPreview(String(text || '').replace(/^\s*\*\*急\*\*\s*/, ''))
const personalUnread = session => (Number(session.mentionUnread) || 0) > (Number(session.mentionAllUnread) || 0)

const liveByKey = computed(() => new Map(props.sessions.map(row => [row.key, row])))
const displayItems = computed(() => items.value.map(item => {
  const live = liveByKey.value.get(item.key)
  return {
    ...item,
    ...(live || {}),
    key: item.key,
    projectId: String(item.projectId),
    projectType: item.kind,
    title: live?.title || item.title || '',
    subtitle: live?.subtitle || item.subtitle || '',
    memberCount: item.memberCount ?? live?.memberCount,
    deletionProtected: item.deletionProtected ?? live?.deletionProtected,
  }
}))

async function load() {
  controller?.abort()
  const version = ++generation, identity = localStorage.getItem('user_id')
  loading.value = false
  if (!props.active) return
  const current = new AbortController(); controller = current
  loading.value = true; error.value = ''; items.value = []
  try {
    const data = await chatRequest('sessions/history', { params: { keyword: props.keyword || '', mine: props.mine, offset: (page.value - 1) * pageSize.value, limit: pageSize.value }, signal: current.signal })
    if (version !== generation || identity !== localStorage.getItem('user_id')) return
    total.value = data.total || 0
    const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (page.value > lastPage) { page.value = lastPage; return load() }
    items.value = data.items || []
  } catch (e) { if (version === generation && !current.signal.aborted) error.value = e.detail || e.message || '全部会话暂时无法加载' }
  finally { if (version === generation) loading.value = false }
}
watch(() => [props.keyword, props.revision, props.active, props.mine], () => { page.value = 1; total.value = 0; items.value = []; load() }, { immediate: true })
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style scoped>
.chat-session-directory{font-size:12px;color:#64748b}
.chat-session-directory__status{margin:0;padding:2px 10px 6px;font-size:11.5px;color:#64748b}
.chat-session-directory__error{margin:0;padding:4px 10px;color:#b91c1c}
.chat-session-directory__loading{margin:0;padding:8px 10px;color:#64748b}

.chat-history-session{position:relative;display:flex;box-sizing:border-box;width:100%;min-height:64px;padding:9px 10px;align-items:center;gap:10px;border-radius:8px;color:var(--chat-text);cursor:pointer;font:inherit;transition:background-color .14s ease,border-color .14s ease}
.chat-history-session.is-pinned{background:var(--chat-bubble-mention-bg,#fef9ec);box-shadow:inset 3px 0 0 var(--chat-bubble-mention-accent,#d97706)}
.chat-history-session:hover{background:var(--chat-hover-bg)}
.chat-history-session.is-pinned:hover{background:#fef3c7}
.chat-history-session.is-active{background:var(--chat-active-bg)}
.chat-history-session.is-pinned.is-active{background:#fde68a;box-shadow:inset 3px 0 0 #b45309}
.chat-history-session:focus-visible{outline:2px solid var(--color-primary);outline-offset:-2px}
.chat-history-session.has-unread-mention .chat-history-session__title strong{color:#b91c1c}
.chat-history-session__left{display:flex;flex:none;align-items:center;justify-content:center;width:36px}
.chat-history-session__avatar{position:relative;display:grid;flex:none;place-items:center;width:36px;height:36px;border-radius:10px;background:#e4ebf4;color:#3b526b;font-size:14px;font-weight:600}
.chat-history-session__avatar--annotation{background:#e2f0ea;color:#2b6b56}
.chat-history-session__avatar--direct{border-radius:50%;background:#ebe6f5;color:#62508a}
.chat-history-session__main{display:flex;min-width:0;flex:1;flex-direction:column;gap:3px}
.chat-history-session__title,.chat-history-session__preview-row{display:flex;align-items:center;gap:6px;min-width:0}
.chat-history-session__title strong{font-size:13px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--color-text-primary)}
.chat-history-session__title time{flex:none;font-size:11px;color:var(--chat-text-faint);pointer-events:none;font-variant-numeric:tabular-nums;transition:opacity .12s ease}
.chat-history-session__sub{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;font-size:11px;color:var(--chat-text-faint);line-height:1.35}
.chat-history-session__sub :deep(.chat-order-identity){flex:1 1 auto;min-width:0}
.chat-history-session__sub :deep(.chat-order-identity__details){flex-wrap:nowrap;overflow:hidden;white-space:nowrap}
.chat-history-session__sub :deep(.chat-order-identity__number){overflow:hidden;text-overflow:ellipsis;white-space:nowrap;overflow-wrap:normal}
.chat-history-session__member{flex:none;font-size:11px;color:var(--chat-text-faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat-history-session__star{color:#d97706;font-size:12px;flex:none}
.chat-history-session__preview{display:block;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--chat-text-muted)}
.chat-history-session__urgent{display:inline-flex;align-items:center;justify-content:center;margin-right:4px;padding:0 4px;height:15px;border-radius:3px;background:#fee2e2;color:#dc2626;font-size:10px;font-weight:600;line-height:15px;vertical-align:1px}
.chat-history-session__mention-label{flex:none;font-size:11px;white-space:nowrap;color:#dc2626}
.chat-history-session__mention-broadcast{flex:none;font-size:11px;white-space:nowrap;color:#9a3412;background:#ffedd5;border-radius:3px;padding:0 3px}
.chat-history-session__mention-preview{margin-right:4px;padding:0 3px;border-radius:3px;background:#fef3c7;color:#92400e}
.chat-history-session__unread{flex:none;min-width:16px;box-sizing:border-box;padding:1px 5px;border-radius:10px;background:#ef4444;color:#fff;font-size:10px;text-align:center}
.chat-history-session__unread-dot{display:inline-block;flex:none;width:6px;height:6px;border-radius:50%;background:var(--chat-text-faint);margin:0 2px}
.chat-history-session__unread-dot.is-manual{width:8px;height:8px;background:#ef4444}
.chat-history-session__pin{position:absolute;top:4px;left:5px;font-size:11px;color:#d97706}
.chat-history-session__controls{position:absolute;top:8px;right:8px;z-index:2;display:flex;align-items:center;gap:4px;opacity:0;pointer-events:none;transition:opacity .12s ease}
.chat-history-session:hover .chat-history-session__controls,.chat-history-session:has(:focus-visible) .chat-history-session__controls{opacity:1;pointer-events:auto}
.chat-history-session:hover .chat-history-session__title time,.chat-history-session:has(:focus-visible) .chat-history-session__title time{opacity:0}
.chat-history-session__ctrl-btn{display:inline-flex;align-items:center;justify-content:center;width:24px;min-width:24px;height:20px;min-height:20px;padding:0;line-height:18px;border-radius:5px;background:rgba(255,255,255,.94);border:1px solid #dce4ee;color:var(--chat-text-muted);font-size:13px;cursor:pointer}
.chat-history-session__ctrl-btn:hover{background:#fff;border-color:#cbd5e1;color:var(--chat-text)}
.chat-session-directory :deep(.el-pagination){justify-content:center;margin:12px 0}
@media (hover: none){.chat-history-session__controls{position:static;opacity:1;pointer-events:auto}.chat-history-session:hover .chat-history-session__title time,.chat-history-session:focus-within .chat-history-session__title time{opacity:1}}
</style>
