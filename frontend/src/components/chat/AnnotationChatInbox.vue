<template>
  <el-config-provider :z-index="favoritesZ">
  <el-popover title="收藏夹" :z-index="favoritesZ" v-model:visible="favoritesVisible" trigger="click" placement="bottom-end" :width="400" popper-class="annotation-favorites-popover">
    <template #reference>
      <el-badge is-dot :hidden="!favoriteBadgeTotal">
        <el-button class="annotation-favorites-trigger" text :circle="!menuLayout" aria-label="收藏夹" :title="favoriteBadgeTotal ? `收藏夹 · ${favoriteBadgeTotal} 条未读 @我` : '收藏夹 · 已收藏的会话与关注的项目'" @click.stop="toggleFavorites">
          <el-icon :size="18"><Star /></el-icon><span v-if="menuLayout">收藏夹</span>
        </el-button>
      </el-badge>
    </template>
    <div v-if="allowed" class="annotation-favorites-tabs" role="tablist" aria-label="收藏夹分类">
      <button type="button" role="tab" :aria-selected="activeTab === 'sessions'" :class="{ 'is-active': activeTab === 'sessions' }" @click="activeTab = 'sessions'">收藏的会话 ({{ starredSessions.length }})</button>
      <button type="button" role="tab" :aria-selected="activeTab === 'annotation'" :class="{ 'is-active': activeTab === 'annotation' }" @click="activeTab = 'annotation'">关注的标注项目 ({{ followed.length }})</button>
    </div>
    <template v-if="activeTab === 'sessions' || !allowed">
      <div class="annotation-favorites-heading"><strong>收藏的会话</strong><span>{{ starredSessions.length }} 个会话</span></div>
      <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
      <el-empty v-else-if="!starredSessions.length" description="在会话列表右键或点击 ⋯ 选择“收藏”，即可把常用群聊保存到这里" :image-size="50" />
      <div class="annotation-favorites-list">
        <div v-for="item in pagedStarred" :key="item.key" class="annotation-favorite-row" :class="{ 'is-pinned': item.pinned }">
          <el-icon v-if="item.pinned" class="annotation-favorite-pin-corner" title="已置顶"><Top /></el-icon>
          <span class="annotation-favorite-avatar" :class="`annotation-favorite-avatar--${item.kind}`" aria-hidden="true">{{ chatAvatarText(item.title || item.subtitle || '会') }}</span>
          <button type="button" class="annotation-favorite-project" :aria-label="`打开会话 ${item.title}`" @click="openStarredSession(item)">
            <span class="annotation-favorite-title">
              <strong>{{ item.title || '未命名会话' }}</strong>
            </span>
            <small>{{ sessionKindLabel(item.kind) }}<template v-if="item.subtitle"> · {{ item.subtitle }}</template></small>
          </button>
          <div class="annotation-favorite-actions">
            <el-badge :value="item.mentionUnread" :hidden="!item.mentionUnread" :max="99">
              <el-button link type="primary" :aria-label="`打开 ${item.title}`" @click="openStarredSession(item)">打开</el-button>
            </el-badge>
            <el-button link :disabled="busyKey === item.key" :title="item.pinned ? '取消置顶' : '置顶'" :aria-label="`${item.pinned ? '取消置顶' : '置顶'} ${item.title}`" @click.stop="toggleStarredPin(item)">{{ item.pinned ? '取消置顶' : '置顶' }}</el-button>
            <el-button link type="danger" :disabled="busyKey === item.key" :aria-label="`取消收藏 ${item.title}`" @click.stop="removeStarredSession(item)">移除</el-button>
          </div>
        </div>
      </div>
      <ChatListPagination v-model:page="starredPage" v-model:page-size="starredPageSize" :total="starredSessions.length" />
    </template>
    <template v-else>
      <div class="annotation-favorites-heading"><strong>关注的项目</strong><span>{{ followed.length }} 个标注项目</span><el-button size="small" type="primary" plain @click="openProjectPicker">项目筛选</el-button></div>
      <div class="annotation-favorites-recovery"><el-button link type="primary" @click="favoritesVisible=false; recoveryVisible=true">恢复取消关注的项目</el-button></div>
      <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
      <el-empty v-else-if="!followed.length" description="在项目沟通中点击关注，即可在这里快速找到" :image-size="50" />
      <div class="annotation-favorites-list">
        <div v-for="item in pagedFavorites" :key="item.projectId" class="annotation-favorite-row" :class="{ 'is-pinned': item.pinned }" @contextmenu.prevent.stop="showFavoriteMenu($event, item)" @keydown.shift.f10.prevent.stop="showFavoriteMenu($event, item)">
          <el-icon v-if="item.pinned" class="annotation-favorite-pin-corner" title="已置顶"><Top /></el-icon>
          <span class="annotation-favorite-avatar annotation-favorite-avatar--annotation" aria-hidden="true">{{ chatAvatarText(item.projectName || item.orderNo || '标') }}</span>
          <button class="annotation-favorite-project" :aria-label="`定位项目 ${item.orderNo}`" @click="locateProject(item)"><strong>{{ item.projectName || '未命名项目' }}</strong><small>{{ orderLabel(item.orderNo) }} · {{ item.orderNo }}</small></button>
          <el-badge :value="item.mentionUnread" :hidden="!item.mentionUnread" :max="99"><el-button link type="primary" :aria-label="`沟通 ${item.orderNo}`" @click="open(item)">沟通</el-button></el-badge>
        </div>
      </div>
      <ChatListPagination v-model:page="favoritesPage" v-model:page-size="favoritesPageSize" :total="followed.length" />
    </template>
  </el-popover>
  <el-popover v-model:visible="favoriteMenuVisible" :virtual-ref="favoriteMenuAnchor" :z-index="favoriteMenuZ" virtual-triggering :trigger="[]" placement="bottom-start" :width="180">
    <el-button text :loading="unfollowing" :disabled="unfollowing" @click="unfollowFavorite">取消关注</el-button>
  </el-popover>
  <ChatAnnotationProjectPicker v-if="allowed" favorite-mode v-model="projectPickerVisible" @joined="refresh" />
  <ChatFavoriteRecovery v-if="allowed" v-model="recoveryVisible" @restored="refresh" />
  </el-config-provider>
</template>
<script setup>
defineProps({menuLayout:Boolean})
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ChatAnnotationProjectPicker from './ChatAnnotationProjectPicker.vue'
import ChatFavoriteRecovery from './ChatFavoriteRecovery.vue'
import ChatListPagination from './ChatListPagination.vue'
import { annotationChatRequest, chatRequest } from '@/api/projectChat'
import { chatAvatarText } from '@/utils/chatLayout'
import { compareSessionActivity } from '@/utils/chatSessionList'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { Star, Top } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { hasPermission } from '@/utils/permission'
const emit = defineEmits(['conversation-opened','navigate'])
const favoritesZ = ref(2110)
function toggleFavorites(event) { favoritesZ.value = chatOverlayZIndex(event.currentTarget); favoritesVisible.value = !favoritesVisible.value }
const { openChat } = useProjectChatDock()
const { followed, sessions, mentionTotal, error, refresh } = useAnnotationFollowed()
const starredSessions = computed(() => [...sessions.value.filter(item => item.starred)].sort(compareSessionActivity))
const favoriteBadgeTotal = computed(() => {
  const keys = new Set()
  let sum = 0
  for (const item of [...starredSessions.value, ...(allowed.value ? followed.value : [])]) {
    const key = item.key || `annotation:${item.projectId}`
    if (keys.has(key)) continue
    keys.add(key)
    sum += Number(item.mentionUnread) || 0
  }
  return sum || (allowed.value ? mentionTotal.value : 0)
})
const activeTab = ref('sessions')
const starredPage = ref(1), starredPageSize = ref(20), busyKey = ref('')
const pagedStarred = computed(() => starredSessions.value.slice((starredPage.value - 1) * starredPageSize.value, starredPage.value * starredPageSize.value))
watch(() => starredSessions.value.length, total => { starredPage.value = Math.min(starredPage.value, Math.max(1, Math.ceil(total / starredPageSize.value))) })
const favoritesPage=ref(1),favoritesPageSize=ref(20)
const pagedFavorites=computed(()=>followed.value.slice((favoritesPage.value-1)*favoritesPageSize.value,favoritesPage.value*favoritesPageSize.value))
watch(()=>followed.value.length,total=>{favoritesPage.value=Math.min(favoritesPage.value,Math.max(1,Math.ceil(total/favoritesPageSize.value)))})
const favoritesVisible = ref(false)
const recoveryVisible = ref(false)
const projectPickerVisible = ref(false), favoriteMenuVisible = ref(false), favoriteMenuAnchor = ref(null), favoriteMenuItem = ref(null), favoriteMenuZ = ref(2110), unfollowing = ref(false)
const router = useRouter()
const allowed = computed(() => hasPermission('projects:read'))
const sessionKindLabel = kind => kind === 'discussion' ? '讨论' : kind === 'direct' ? '私聊' : kind === 'annotation' ? '标注' : '笔译'
function open(item) { openChat({ projectId: item.projectId, projectType: 'annotation', title: item.projectName, subtitle: item.orderNo }); favoritesVisible.value = false; emit('conversation-opened') }
function openStarredSession(item) {
  openChat({ projectId: item.projectId, projectType: item.kind, title: item.title, subtitle: item.subtitle, syncSidebar: true })
  favoritesVisible.value = false
  emit('conversation-opened')
}
async function updateStarredPreference(item, data, successMessage) {
  if (busyKey.value) return
  busyKey.value = item.key
  try {
    const path = item.kind === 'discussion' ? `discussions/${item.projectId}/preferences` : `sessions/${item.kind}/${item.projectId}/preferences`
    await chatRequest(path, { method: 'put', data })
    await refresh()
    ElMessage.success(successMessage)
  } catch (e) {
    ElMessage.error(e.detail || e.message || '操作失败，请重试')
  } finally {
    busyKey.value = ''
  }
}
function toggleStarredPin(item) {
  return updateStarredPreference(item, { pinned: !item.pinned }, item.pinned ? '已取消置顶' : '已置顶会话')
}
function removeStarredSession(item) {
  return updateStarredPreference(item, { starred: false }, `已从收藏夹移除「${item.title || '会话'}」`)
}
function orderLabel(orderNo) {
  const depth = String(orderNo || '').split('.').length - 1
  return depth > 1 ? '孙订单' : depth === 1 ? '子订单' : '主订单'
}
function locateProject(item) { favoritesVisible.value = false; emit('navigate'); router.push({ path: '/annotation-details', query: { projectId: String(item.projectId), tab: 'chat' } }) }
function openProjectPicker() { favoriteMenuVisible.value = false; favoritesVisible.value = false; projectPickerVisible.value = true }
function showFavoriteMenu(event, item) {
  favoriteMenuAnchor.value = event.currentTarget; favoriteMenuItem.value = item
  favoriteMenuZ.value = chatOverlayZIndex(event.currentTarget); favoriteMenuVisible.value = true
}
async function unfollowFavorite() {
  const item = favoriteMenuItem.value
  if (!item || unfollowing.value) return
  unfollowing.value = true
  try {
    await annotationChatRequest(item.projectId, 'following', { method: 'put', data: { following: false } })
    favoriteMenuVisible.value = false
    await refresh()
    ElMessage.success(`已取消关注 ${item.orderNo}`)
  } catch (e) { ElMessage.error(e.detail || e.message || '取消关注失败，请重试') }
  finally { unfollowing.value = false }
}
watch(favoritesVisible, value => {
  if (value) {
    refresh()
    if (!allowed.value) activeTab.value = 'sessions'
    else if (!starredSessions.value.length && followed.value.length) activeTab.value = 'annotation'
    else activeTab.value = 'sessions'
  } else {
    favoriteMenuVisible.value = false
  }
})
</script>
<style>
.annotation-favorites-popover{max-width:calc(100vw - 24px)!important}
</style>
<style scoped>
.annotation-favorites-trigger{color:var(--color-text-secondary)}
.annotation-favorites-tabs{display:flex;gap:6px;padding:0 0 10px;border-bottom:1px solid #eef2f6}
.annotation-favorites-tabs button{flex:1;padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;color:#475569;font-size:12px;cursor:pointer;transition:all .14s ease}
.annotation-favorites-tabs button:hover{background:#eff6ff;border-color:#bfdbfe;color:#1d4ed8}
.annotation-favorites-tabs button.is-active{background:var(--color-primary-soft, #eff6ff);border-color:var(--color-primary, #2563eb);color:var(--color-primary, #2563eb);font-weight:600}
.annotation-favorites-recovery{display:flex;justify-content:flex-end;padding:8px 0}
.annotation-favorites-heading{display:flex;align-items:center;justify-content:space-between;padding:8px 0 10px;border-bottom:1px solid #eef2f6}
.annotation-favorites-heading span{font-size:12px;color:#94a3b8}
.annotation-favorites-list{max-height:min(420px,calc(100vh - 180px));overflow-y:auto;padding:4px 0}
.annotation-favorite-row{position:relative;display:flex;align-items:center;gap:10px;padding:9px 10px;margin-bottom:2px;border-radius:8px;transition:background-color .14s ease}
.annotation-favorite-row:hover{background:#eef3f8}
.annotation-favorite-row.is-pinned{background:#fef9c3;box-shadow:inset 3px 0 0 #eab308}
.annotation-favorite-row.is-pinned:hover{background:#fef08a}
.annotation-favorite-pin-corner{position:absolute;top:4px;left:5px;font-size:11px;color:#d97706}
.annotation-favorite-avatar{display:grid;flex:none;place-items:center;width:36px;height:36px;border-radius:10px;background:#e4ebf4;color:#3b526b;font-size:14px;font-weight:600}
.annotation-favorite-avatar--annotation{background:#e2f0ea;color:#2b6b56}
.annotation-favorite-avatar--direct{border-radius:50%;background:#ebe6f5;color:#62508a}
.annotation-favorite-project{display:flex;flex:1;min-width:0;flex-direction:column;gap:3px;text-align:left;background:none;border:0;padding:0;cursor:pointer;color:#334155;font:inherit}
.annotation-favorite-title{display:flex;align-items:center;gap:4px;min-width:0}
.annotation-favorite-project strong{font-size:13px;font-weight:600;color:var(--color-text-primary, #1e293b);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.annotation-favorite-project small{color:#94a3b8;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.annotation-favorite-project:hover strong{color:var(--color-primary-hover)}
.annotation-favorite-actions{display:flex;flex:none;align-items:center;gap:6px}
</style>
