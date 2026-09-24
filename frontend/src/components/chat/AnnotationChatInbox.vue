<template>
  <el-popover v-if="allowed" v-model:visible="favoritesVisible" trigger="click" placement="bottom-end" :width="380" popper-class="annotation-favorites-popover">
    <template #reference><el-button text :icon="Star" aria-label="收藏夹" title="已关注的标注项目">收藏夹</el-button></template>
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
  <el-popover v-if="allowed" v-model:visible="visible" trigger="click" placement="bottom-end" :width="340" popper-class="annotation-members-popover">
    <template #reference><el-button text aria-label="项目消息"><el-badge :value="total" :hidden="!total" :max="99">项目消息</el-badge></el-button></template>
    <strong>项目未读消息</strong>
    <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
    <el-empty v-else-if="!items.length" description="暂无未读消息" :image-size="50" />
    <div v-for="item in items" :key="item.projectId" class="annotation-inbox-item">
      <el-button link @click="open(item)">{{ item.orderNo }} · {{ item.projectName || '未命名项目' }}</el-button><el-tag size="small">{{ item.unread }}</el-tag>
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
const visible = ref(false), items = ref([]), total = ref(0), error = ref('')
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
    items.value = data.items; followed.value = data.followedItems || []; total.value = data.total; error.value = ''
    state.windows.filter(w => w.projectType === 'annotation').forEach(w => { w.unread = data.items.find(item => String(item.projectId) === String(w.projectId))?.unread || 0 })
  } }
  catch { error.value = '未读消息暂时无法加载' } finally { pending = false; if (rerun) { rerun = false; refresh() } }
}
function open(item) { openChat({ projectId: item.projectId, projectType: 'annotation', title: item.projectName, subtitle: item.orderNo }); visible.value = false; favoritesVisible.value = false }
function locateProject(item) { favoritesVisible.value = false; router.push({ path: '/annotation-details', query: { projectId: String(item.projectId), openProgress: '1' } }) }
watch(visible, value => { if (value) refresh() })
watch(favoritesVisible, value => { if (value) refresh() })
onMounted(() => { refresh(); ensureConnected(); cleanup.push(subscribe('annotation_chat_changed', refresh), subscribe('connected', refresh)); timer = setInterval(refresh, 15000) })
onBeforeUnmount(() => { disposed = true; clearInterval(timer); cleanup.forEach(fn => fn()) })
</script>
<style>
.annotation-favorites-popover{max-width:calc(100vw - 24px)!important}
</style>
<style scoped>
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
<style scoped>.annotation-inbox-item{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 0;border-bottom:1px solid #e2e8f0}.annotation-inbox-item .el-button{white-space:normal;text-align:left;line-height:1.5}</style>
