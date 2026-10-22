<template>
  <el-popover v-if="allowed" v-model:visible="favoritesVisible" trigger="click" placement="bottom-end" :width="380" popper-class="annotation-favorites-popover">
    <template #reference>
      <el-badge is-dot :hidden="!mentionTotal">
        <el-button class="annotation-favorites-trigger" text circle aria-label="收藏夹" :title="mentionTotal ? `收藏夹 · ${mentionTotal} 条未读 @我` : '收藏夹 · 已关注的项目'" @click.stop="favoritesVisible = !favoritesVisible">
          <el-icon :size="18"><Star /></el-icon>
        </el-button>
      </el-badge>
    </template>
    <div class="annotation-favorites-heading"><strong>关注的项目</strong><span>{{ followed.length }} 个标注项目</span><el-button size="small" type="primary" plain @click="openProjectPicker">项目筛选</el-button></div>
    <div class="annotation-favorites-recovery"><el-button link type="primary" @click="favoritesVisible=false; recoveryVisible=true">恢复取消关注的项目</el-button></div>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
    <el-empty v-else-if="!followed.length" description="在项目沟通中点击关注，即可在这里快速找到" :image-size="50" />
    <div class="annotation-favorites-list">
      <div v-for="item in followed" :key="item.projectId" class="annotation-favorite-row" @contextmenu.prevent.stop="showFavoriteMenu($event, item)" @keydown.shift.f10.prevent.stop="showFavoriteMenu($event, item)">
        <button class="annotation-favorite-project" :aria-label="`定位项目 ${item.orderNo}`" @click="locateProject(item)"><span>{{ item.projectName || '未命名项目' }}</span><small>{{ orderLabel(item.orderNo) }} · {{ item.orderNo }}</small></button>
        <el-badge :value="item.mentionUnread" :hidden="!item.mentionUnread" :max="99"><el-button link type="primary" :aria-label="`沟通 ${item.orderNo}`" @click="open(item)">沟通</el-button></el-badge>
      </div>
    </div>
  </el-popover>
  <el-popover v-model:visible="favoriteMenuVisible" :virtual-ref="favoriteMenuAnchor" :z-index="favoriteMenuZ" virtual-triggering :trigger="[]" placement="bottom-start" :width="180">
    <el-button text :loading="unfollowing" :disabled="unfollowing" @click="unfollowFavorite">取消关注</el-button>
  </el-popover>
  <ChatAnnotationProjectPicker v-model="projectPickerVisible" @joined="refresh" />
  <ChatFavoriteRecovery v-model="recoveryVisible" @restored="refresh" />
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ChatAnnotationProjectPicker from './ChatAnnotationProjectPicker.vue'
import ChatFavoriteRecovery from './ChatFavoriteRecovery.vue'
import { annotationChatRequest } from '@/api/projectChat'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
import { Star } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { hasPermission } from '@/utils/permission'
const { openChat } = useProjectChatDock()
const { followed, mentionTotal, error, refresh } = useAnnotationFollowed()
const favoritesVisible = ref(false)
const recoveryVisible = ref(false)
const projectPickerVisible = ref(false), favoriteMenuVisible = ref(false), favoriteMenuAnchor = ref(null), favoriteMenuItem = ref(null), favoriteMenuZ = ref(2110), unfollowing = ref(false)
const router = useRouter()
const allowed = computed(() => hasPermission('projects:read'))
function open(item) { openChat({ projectId: item.projectId, projectType: 'annotation', title: item.projectName, subtitle: item.orderNo }); favoritesVisible.value = false }
function orderLabel(orderNo) {
  const depth = String(orderNo || '').split('.').length - 1
  return depth > 1 ? '孙订单' : depth === 1 ? '子订单' : '主订单'
}
function locateProject(item) { favoritesVisible.value = false; router.push({ path: '/annotation-details', query: { projectId: String(item.projectId), tab: 'chat' } }) }
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
watch(favoritesVisible, value => { if (value) refresh(); else favoriteMenuVisible.value = false })
</script>
<style>
.annotation-favorites-popover{max-width:calc(100vw - 24px)!important}
</style>
<style scoped>
.annotation-favorites-trigger{color:var(--color-text-secondary)}
.annotation-favorites-recovery{display:flex;justify-content:flex-end;padding:8px 0}
.annotation-favorites-heading{display:flex;align-items:center;justify-content:space-between;padding:4px 0 10px;border-bottom:1px solid #eef2f6}
.annotation-favorites-heading span{font-size:12px;color:#94a3b8}
.annotation-favorites-list{max-height:min(420px,calc(100vh - 150px));overflow-y:auto}
.annotation-favorite-row{display:flex;align-items:center;gap:12px;padding:10px 8px;border-bottom:1px solid #f1f5f9;border-radius:6px}
.annotation-favorite-row:hover{background:#f8fafc}
.annotation-favorite-project{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px;text-align:left;background:none;border:0;padding:0;cursor:pointer;color:#334155;font:inherit}
.annotation-favorite-project span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.annotation-favorite-project small{color:#94a3b8;font-size:12px}
.annotation-favorite-project:hover span{color:var(--color-primary-hover)}
</style>
