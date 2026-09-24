<template>
  <el-popover v-if="allowed" v-model:visible="favoritesVisible" trigger="click" placement="bottom-end" :width="380" popper-class="annotation-favorites-popover">
    <template #reference>
      <el-badge is-dot :hidden="!total">
        <el-button class="annotation-favorites-trigger" text circle aria-label="收藏夹" :title="total ? `收藏夹 · ${total} 条未读消息` : '收藏夹 · 已关注的项目'">
          <el-icon :size="18"><Star /></el-icon>
        </el-button>
      </el-badge>
    </template>
    <div class="annotation-favorites-heading"><strong>关注的项目</strong><span>{{ followed.length }} 个标注项目</span></div>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
    <el-empty v-else-if="!followed.length" description="在项目沟通中点击关注，即可在这里快速找到" :image-size="50" />
    <div class="annotation-favorites-list">
      <div v-for="item in followed" :key="item.projectId" class="annotation-favorite-row">
        <button class="annotation-favorite-project" :aria-label="`定位项目 ${item.orderNo}`" @click="locateProject(item)"><span>{{ item.projectName || '未命名项目' }}</span><small>{{ item.orderNo }}</small></button>
        <el-badge :value="item.unread" :hidden="!item.unread" :max="99"><el-button link type="primary" :aria-label="`沟通 ${item.orderNo}`" @click="open(item)">沟通</el-button></el-badge>
      </div>
    </div>
  </el-popover>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Star } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { annotationChatRequest } from '@/api/projectChat'
import { subscribe, ensureConnected } from '@/utils/realtimeSocket'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { hasPermission } from '@/utils/permission'
const { openChat, state } = useProjectChatDock()
const total = ref(0), error = ref('')
const favoritesVisible = ref(false), followed = ref([])
const router = useRouter()
const allowed = computed(() => hasPermission('projects:read'))
let timer, pending = false, rerun = false, disposed = false
const cleanup = []
async function refresh() {
  if (!allowed.value || disposed) return
  if (pending) { rerun = true; return }
  pending = true
  try { const data = await annotationChatRequest('', 'unread'); if (!disposed) {
    followed.value = data.followedItems || []; total.value = data.total; error.value = ''
    state.windows.filter(w => w.projectType === 'annotation').forEach(w => { w.unread = data.items.find(item => String(item.projectId) === String(w.projectId))?.unread || 0 })
  } }
  catch { error.value = '未读消息暂时无法加载' } finally { pending = false; if (rerun) { rerun = false; refresh() } }
}
function open(item) { openChat({ projectId: item.projectId, projectType: 'annotation', title: item.projectName, subtitle: item.orderNo }); favoritesVisible.value = false }
function locateProject(item) { favoritesVisible.value = false; router.push({ path: '/annotation-details', query: { projectId: String(item.projectId), openProgress: '1' } }) }
watch(favoritesVisible, value => { if (value) refresh() })
onMounted(() => { refresh(); ensureConnected(); cleanup.push(subscribe('annotation_chat_changed', refresh), subscribe('connected', refresh)); timer = setInterval(refresh, 15000) })
onBeforeUnmount(() => { disposed = true; clearInterval(timer); cleanup.forEach(fn => fn()) })
</script>
<style>
.annotation-favorites-popover{max-width:calc(100vw - 24px)!important}
</style>
<style scoped>
.annotation-favorites-trigger{color:var(--color-text-secondary)}
.annotation-favorites-heading{display:flex;align-items:center;justify-content:space-between;padding:4px 0 10px;border-bottom:1px solid #eef2f6}
.annotation-favorites-heading span{font-size:12px;color:#94a3b8}
.annotation-favorites-list{max-height:min(420px,calc(100vh - 150px));overflow-y:auto}
.annotation-favorite-row{display:flex;align-items:center;gap:12px;padding:10px 8px;border-bottom:1px solid #f1f5f9;border-radius:6px}
.annotation-favorite-row:hover{background:#f8fafc}
.annotation-favorite-project{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px;text-align:left;background:none;border:0;padding:0;cursor:pointer;color:#334155;font:inherit}
.annotation-favorite-project span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.annotation-favorite-project small{color:#94a3b8;font-size:12px}
.annotation-favorite-project:hover span{color:#2563eb}
</style>
