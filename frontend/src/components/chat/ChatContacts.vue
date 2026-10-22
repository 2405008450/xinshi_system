<template>
  <div class="chat-contacts">
    <div class="chat-contacts__search direct-user-search">
      <el-input v-model="keyword" clearable size="small" placeholder="搜索姓名、账号、部门" :prefix-icon="Search" @keyup.enter="applyKeyword" />
      <el-button size="small" :icon="Search" aria-label="查询通讯录" title="查询" @click="applyKeyword" />
    </div>
    <p v-if="error" class="chat-contacts__error" role="alert">{{ error }} <el-button link @click="retry">重试</el-button></p>
    <div v-if="selfUser" class="chat-contacts__me">
      <span class="chat-contact__avatar" aria-hidden="true">{{ chatAvatarText(selfUser.name) }}</span>
      <span class="chat-contact__text"><strong>我</strong><small>{{ selfDetail }}</small></span>
    </div>
    <div v-loading="loading" class="chat-contacts__list direct-user-list" @keydown="navigate">
      <el-empty v-if="!loading && !groups.length && !error" description="没有匹配的联系人" :image-size="48" />
      <section v-for="group in groups" :key="group.name" class="chat-contacts__group" :data-department="group.name">
        <button type="button" class="chat-contacts__group-title" :aria-expanded="!isCollapsed(group.name)" @click="toggle(group.name)">
          <span>{{ group.name }} · {{ group.items.length }}</span>
          <span aria-hidden="true">{{ isCollapsed(group.name) ? '▸' : '▾' }}</span>
        </button>
        <template v-if="!isCollapsed(group.name)">
          <button v-for="user in group.items" :key="`${group.name}-${user.id}`" type="button" class="chat-contact" :data-contact-id="user.id" :disabled="opening || !phaseOneEnabled" :title="phaseOneEnabled ? `给${user.name}发消息` : '等待聊天数据库迁移'" @click="open(user)">
            <span class="chat-contact__avatar" aria-hidden="true">{{ chatAvatarText(user.name) }}</span>
            <span class="chat-contact__text"><strong>{{ user.name }}</strong><small>{{ detailLine(user) }}</small></span>
            <span class="chat-contact__side">
              <span class="chat-contact__send">发消息</span>
            </span>
          </button>
        </template>
      </section>
      <p v-if="truncated" class="chat-contacts__hint">联系人较多，请继续搜索查找。</p>
      <p v-if="!phaseOneEnabled" class="chat-contacts__hint">私聊暂不可用。</p>
    </div>
  </div>
</template>
<script setup>
import { normalizeDepartment } from '@/constants/departments'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { chatRequest } from '@/api/projectChat'
import { subscribe } from '@/utils/realtimeSocket'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { chatAvatarText } from '@/utils/chatLayout'

const props = defineProps({ active: { type: Boolean, default: false } })
const emit = defineEmits(['opened'])
const { refresh, phaseOneEnabled } = useAnnotationFollowed()
const keyword = ref('')
const appliedKeyword = ref('')
const directory = ref([])
const users = ref([])
const recent = ref([])
const selfUser = ref(null)
const loading = ref(false)
const loaded = ref(false)
const opening = ref(false)
const error = ref('')
const truncated = ref(false)
const collapsed = ref([])
let timer = 0
let controller
let sequence = 0
let recentSequence = 0
let recentController
let stopRecent = () => {}

const selfDetail = computed(() => {
  const user = selfUser.value
  if (!user) return ''
  return [user.name, user.username, normalizeDepartment(user.department)].filter((item, index, list) => item && list.indexOf(item) === index).join(' · ')
})
const detailLine = user => [user.username, normalizeDepartment(user.department)].filter(Boolean).join(' · ')
const groups = computed(() => {
  const departments = new Map()
  users.value.forEach((user) => {
    const name = normalizeDepartment(user.department) || '未分配部门'
    if (!departments.has(name)) departments.set(name, [])
    departments.get(name).push(user)
  })
  const rows = [...departments].sort(([a], [b]) => (a === b ? 0 : a === '未分配部门' ? 1 : b === '未分配部门' ? -1 : a.localeCompare(b, 'zh-CN'))).map(([name, items]) => ({ name, items }))
  if (appliedKeyword.value) return rows
  const contacts = recent.value.map(row => directory.value.find(user => user.id === row.userId) || users.value.find(user => user.id === row.userId)).filter(Boolean)
  return contacts.length ? [{ name: '最近联系', items: contacts }, ...rows] : rows
})
const isCollapsed = name => !appliedKeyword.value && collapsed.value.includes(name)
const toggle = name => {
  if (appliedKeyword.value) return
  collapsed.value = collapsed.value.includes(name) ? collapsed.value.filter(value => value !== name) : [...collapsed.value, name]
}
function patchConversations(rows) {
  const map = new Map((rows || []).map(item => [item.userId, item.conversationId]))
  const patch = list => list.map(user => (map.has(user.id) ? { ...user, conversationId: map.get(user.id) || user.conversationId } : user))
  directory.value = patch(directory.value)
  users.value = patch(users.value)
}

async function load(text = '') {
  window.clearTimeout(timer)
  controller?.abort()
  controller = new AbortController()
  const activeController = controller
  const requestId = ++sequence
  loading.value = true
  error.value = ''
  try {
    const data = await chatRequest('users', { params: { keyword: text, scope: 'directory' }, signal: activeController.signal })
    if (requestId !== sequence) return
    users.value = data.items || []
    recent.value = data.recent || []
    selfUser.value = data.self || selfUser.value
    truncated.value = !!data.truncated
    if (!text) {
      directory.value = users.value
      loaded.value = true
    }
    appliedKeyword.value = text
    error.value = ''
  } catch (reason) {
    if (requestId === sequence && !activeController.signal.aborted) error.value = reason.detail || reason.message || '通讯录加载失败'
  } finally {
    if (requestId === sequence) loading.value = false
  }
}

function applyKeyword() {
  window.clearTimeout(timer)
  const text = keyword.value.trim()
  if (!text) {
    controller?.abort()
    sequence += 1
    appliedKeyword.value = ''
    users.value = directory.value
    truncated.value = false
    loading.value = false
    error.value = ''
    if (!loaded.value) load()
    return
  }
  load(text)
}

async function refreshRecent() {
  recentController?.abort()
  recentController = new AbortController()
  const requestId = ++recentSequence
  try {
    const data = await chatRequest('users', { params: { scope: 'recent' }, signal: recentController.signal })
    if (requestId !== recentSequence) return
    recent.value = data.recent || []
    patchConversations(data.recent)
  } catch {
    // 最近联系刷新失败时保留当前列表。
  }
}

watch(keyword, (value) => {
  window.clearTimeout(timer)
  if (!value) applyKeyword()
  else timer = window.setTimeout(applyKeyword, 400)
})
watch(() => props.active, (active) => {
  if (active && !loaded.value && !loading.value) load()
}, { immediate: true })

function retry() {
  if (keyword.value.trim()) load(keyword.value.trim())
  else load()
}
function navigate(event) {
  if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return
  const buttons = [...event.currentTarget.querySelectorAll('.chat-contact:not(:disabled)')]
  if (!buttons.length) return
  event.preventDefault()
  const current = buttons.indexOf(document.activeElement)
  const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : Math.min(buttons.length - 1, Math.max(0, current + (event.key === 'ArrowUp' ? -1 : 1)))
  buttons[index]?.focus()
}
async function open(user) {
  if (opening.value || !phaseOneEnabled.value) return
  opening.value = true
  try {
    const data = await chatRequest('direct/conversations', { method: 'post', data: { userId: user.id } })
    directory.value = directory.value.map(item => (item.id === user.id ? { ...item, conversationId: data.id } : item))
    users.value = users.value.map(item => (item.id === user.id ? { ...item, conversationId: data.id } : item))
    useProjectChatDock().openChat({ projectId: data.id, projectType: 'direct', title: data.title, subtitle: data.subtitle })
    emit('opened')
    await refresh()
  } catch (reason) {
    ElMessage.error(reason.detail || reason.message || '发起私聊失败')
  } finally {
    opening.value = false
  }
}

stopRecent = subscribe('direct_chat_changed', () => {
  if (loaded.value) refreshRecent()
})
onBeforeUnmount(() => {
  sequence += 1
  recentSequence += 1
  window.clearTimeout(timer)
  controller?.abort()
  recentController?.abort()
  stopRecent()
})
</script>
<style scoped>
.chat-contacts{display:flex;flex:1;min-height:0;flex-direction:column}
.chat-contacts__search{display:flex;gap:6px;padding:0 12px 12px;flex:none}
.chat-contacts__search .el-input{min-width:0;flex:1}
.chat-contacts__search .el-button{flex:none;margin-left:0}
.chat-contacts__me{display:flex;align-items:center;gap:10px;flex:none;padding:4px 14px 10px}
.chat-contacts__list{flex:1;min-height:0;overflow-y:auto;padding:0 8px 12px}
.chat-contacts__group-title{display:flex;justify-content:space-between;width:100%;padding:12px 6px;border:0;background:transparent;text-align:left;color:#64748b;font-size:12px;cursor:pointer}
.chat-contact{display:flex;align-items:center;gap:10px;width:100%;padding:10px 6px;border:0;border-radius:8px;background:transparent;text-align:left;cursor:pointer;color:#334155;font:inherit}
.chat-contact:hover,.chat-contact:focus-visible{background:#edf3ff}
.chat-contact:disabled{cursor:not-allowed;opacity:.6}
.chat-contact__avatar{display:grid;place-items:center;width:36px;height:36px;flex:none;border-radius:50%;background:#e7eef9;color:#4b6b9e}
.chat-contact__text{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px}
.chat-contact__text strong,.chat-contact__text small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-contact__text small{font-size:12px;color:#94a3b8}
.chat-contact__side{display:inline-flex;flex:none;align-items:center;gap:6px}
.chat-contact__send{display:none;color:var(--el-color-primary);font-size:11px}
.chat-contact:hover .chat-contact__send,.chat-contact:focus-visible .chat-contact__send{display:inline}
.chat-contact__unread{background:#ef4444;color:white;border-radius:10px;padding:2px 6px;font-size:11px}
.chat-contacts__error,.chat-contacts__hint{padding:0 12px 8px;font-size:12px;color:#64748b}
.chat-contacts__error{color:#b91c1c}
</style>
