<template>
  <aside v-show="visible" class="chat-history" :class="`chat-history--${placement}`" aria-label="聊天记录">
    <header class="chat-history__header">
      <strong>聊天记录</strong>
      <el-button link aria-label="关闭聊天记录" @click="emit('update:visible', false)">关闭</el-button>
    </header>
    <div class="chat-history__filters">
      <el-input
        v-model="filters.keyword"
        clearable
        :placeholder="allowFiles ? '搜索消息、文件名或链接' : '搜索消息或链接'"
        @keyup.enter="searchNow"
      />
      <div class="chat-history__tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.kind"
          type="button"
          role="tab"
          :aria-selected="filters.kind === tab.kind"
          :class="{ 'is-active': filters.kind === tab.kind }"
          @click="filters.kind = tab.kind"
        >
          {{ tab.label }}<span v-if="totals[tab.kind]"> {{ totals[tab.kind] }}</span>
        </button>
      </div>
      <el-select v-model="filters.sender" clearable filterable placeholder="发送人">
        <el-option v-for="user in senders" :key="user.id" :value="user.id" :label="user.name" />
      </el-select>
      <el-date-picker
        v-model="filters.dates"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <div class="chat-history__actions">
        <el-checkbox v-model="filters.favorites">只看收藏</el-checkbox>
        <span class="chat-history__action-buttons">
          <el-button size="small" @click="resetFilters">重置</el-button>
          <el-button size="small" type="primary" @click="searchNow">查询</el-button>
        </span>
      </div>
    </div>
    <div ref="results" class="chat-history__results" @scroll="onScroll">
      <p v-if="error" class="chat-history__error" role="alert">{{ error }} <el-button link @click="searchNow">重试</el-button></p>
      <div v-else-if="loading" class="chat-history__hint">正在检索…</div>
      <el-empty v-else-if="!items.length" description="没有匹配的聊天记录" :image-size="56" />
      <div v-else-if="filters.kind === 'image'" class="chat-history__grid">
        <article v-for="item in items" :key="itemKey(item)" class="chat-history__image">
          <el-image
            v-if="thumbs[item.attachment?.id]"
            :src="thumbs[item.attachment.id]"
            :preview-src-list="previewList"
            :initial-index="previewIndex(item)"
            preview-teleported
            fit="cover"
          />
          <span v-else class="chat-history__hint">图片加载中…</span>
          <div class="chat-history__meta">
            <span>{{ item.senderName }} · {{ formatDateTime(item.createdAt) }}</span>
            <el-button link type="primary" @click="locate(item)">定位</el-button>
          </div>
        </article>
      </div>
      <template v-else>
      <article v-for="item in items" :key="itemKey(item)" class="chat-history__row">
        <div class="chat-history__body">
          <a v-if="item.kind === 'link'" :href="hrefOf(item.url)" target="_blank" rel="noopener noreferrer">{{ item.url }}</a>
          <template v-else-if="item.kind === 'file'">
            <strong>{{ item.attachment?.originalName || '文件' }}</strong>
            <span>{{ sizeLabel(item.attachment?.fileSize) }}</span>
          </template>
          <p v-else>{{ item.summary || '（无文字）' }}</p>
          <div class="chat-history__meta">
            <span>{{ item.senderName || '未知用户' }} · {{ formatDateTime(item.createdAt) }}</span>
            <span>
              <el-button v-if="item.kind === 'file'" link type="primary" @click="download(item)">下载</el-button>
              <el-button link type="primary" @click="locate(item)">定位</el-button>
            </span>
          </div>
        </div>
      </article>
      </template>
      <div v-if="loadingMore" class="chat-history__hint">正在加载更多…</div>
    </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { annotationChatRequest, getProjectChatAttachmentBlob, searchProjectChatHistory } from '@/api/projectChat'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: '' },
  projectType: { type: String, default: 'translation' },
  senders: { type: Array, default: () => [] },
  allowFiles: { type: Boolean, default: false },
  placement: { type: String, default: 'overlay' },
})
const emit = defineEmits(['update:visible', 'locate'])

const filters = reactive({ keyword: '', kind: 'all', sender: '', dates: [], favorites: false })
const items = ref([])
const totals = reactive({ all: 0, image: 0, link: 0, file: 0 })
const thumbs = reactive({})
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const nextCursor = ref('')
const results = ref(null)
let generation = 0
let controller = null
let keywordTimer = 0
let silent = false

const tabs = computed(() => {
  const rows = [
    { kind: 'all', label: '全部' },
    { kind: 'image', label: '图片' },
    { kind: 'link', label: '链接' },
  ]
  if (props.allowFiles) rows.push({ kind: 'file', label: '文件' })
  return rows
})
const previewList = computed(() => items.value.map(item => thumbs[item.attachment?.id]).filter(Boolean))

const itemKey = item => `${item.kind}-${item.messageId}-${item.attachment?.id || item.url || ''}`
const previewIndex = item => Math.max(0, previewList.value.indexOf(thumbs[item.attachment?.id]))
const sizeLabel = bytes => (!bytes ? '-' : bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`)
const hrefOf = url => (/^https?:\/\//i.test(url || '') ? url : `https://${url}`)
const detail = value => value?.detail || value?.message || '检索失败，请重试'

const buildParams = cursor => ({
  kind: filters.kind,
  keyword: filters.keyword.trim() || undefined,
  sender_user_id: filters.sender || undefined,
  favorites_only: filters.favorites || undefined,
  date_from: filters.dates?.[0] ? `${filters.dates[0]}T00:00:00` : undefined,
  date_to: filters.dates?.[1] ? `${filters.dates[1]}T23:59:59.999999` : undefined,
  cursor: cursor || undefined,
  limit: 30,
})

function revokeThumbs(exceptIds = new Set()) {
  Object.keys(thumbs).forEach((id) => {
    if (exceptIds.has(id)) return
    URL.revokeObjectURL(thumbs[id])
    delete thumbs[id]
  })
}

async function loadBlob(file) {
  if (props.projectType === 'annotation') {
    try {
      return await annotationChatRequest(props.projectId, `files/${file.id}`, { responseType: 'blob' })
    } catch (error) {
      if (file.contentType?.startsWith('image/')) return getProjectChatAttachmentBlob(file.id)
      throw error
    }
  }
  return getProjectChatAttachmentBlob(file.id)
}

async function ensureThumb(item) {
  const file = item.attachment
  if (!file?.id || thumbs[file.id]) return
  try {
    const blob = await loadBlob(file)
    if (!items.value.some(row => row.attachment?.id === file.id)) return
    thumbs[file.id] = URL.createObjectURL(blob)
  } catch {
    // 单张缩略图失败不阻断其余结果，定位和下载仍可使用。
  }
}

async function runSearch({ append = false } = {}) {
  if (!props.visible || !props.projectId) return
  controller?.abort()
  controller = new AbortController()
  const version = ++generation
  if (append) loadingMore.value = true
  else {
    loading.value = true
    error.value = ''
  }
  try {
    const data = await searchProjectChatHistory(
      props.projectId,
      buildParams(append ? nextCursor.value : undefined),
      props.projectType,
      controller.signal,
    )
    if (version !== generation) return
    const rows = Array.isArray(data?.items) ? data.items : []
    items.value = append ? items.value.concat(rows) : rows
    nextCursor.value = data?.nextCursor || ''
    Object.assign(totals, { all: 0, image: 0, link: 0, file: 0, ...(data?.totals || {}) })
    if (!append) revokeThumbs(new Set(items.value.map(item => item.attachment?.id).filter(Boolean)))
    if (filters.kind === 'image') items.value.forEach(ensureThumb)
    error.value = ''
  } catch (reason) {
    if (controller?.signal.aborted || reason?.code === 'ERR_CANCELED' || reason?.name === 'CanceledError') return
    if (version === generation) error.value = detail(reason)
  } finally {
    if (version === generation) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

function searchNow() {
  window.clearTimeout(keywordTimer)
  return runSearch()
}

function resetFilters() {
  silent = true
  Object.assign(filters, { keyword: '', kind: 'all', sender: '', dates: [], favorites: false })
  nextTick(() => { silent = false })
  return runSearch()
}

function locate(item) {
  if (props.placement !== 'side') emit('update:visible', false)
  emit('locate', item.messageId)
}

async function download(item) {
  try {
    const blob = await loadBlob(item.attachment)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = item.attachment?.originalName || '附件'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (reason) {
    ElMessage.error(detail(reason))
  }
}

function onScroll(event) {
  const el = event.target
  if (!nextCursor.value || loading.value || loadingMore.value) return
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) runSearch({ append: true })
}

watch(() => filters.keyword, (value) => {
  if (silent || !props.visible) return
  window.clearTimeout(keywordTimer)
  if (!value) runSearch()
  else keywordTimer = window.setTimeout(() => runSearch(), 400)
})
watch(() => [filters.kind, filters.sender, filters.favorites, (filters.dates || []).join('|')], () => {
  if (silent || !props.visible) return
  runSearch()
})
watch(() => props.visible, (value) => {
  if (!value) return
  if (!props.allowFiles && filters.kind === 'file') filters.kind = 'all'
  runSearch()
})
watch(() => props.allowFiles, (value) => {
  if (!value && filters.kind === 'file') filters.kind = 'all'
})

onBeforeUnmount(() => {
  window.clearTimeout(keywordTimer)
  controller?.abort()
  revokeThumbs()
})
</script>

<style scoped>
.chat-history {
  display: flex;
  min-height: 0;
  flex-direction: column;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-primary);
}

.chat-history--overlay {
  position: absolute;
  z-index: 6;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(360px, 100%);
  box-shadow: -8px 0 24px rgb(15 23 42 / 12%);
}

.chat-history--side {
  width: 340px;
  flex: none;
}

.chat-history__header,
.chat-history__actions,
.chat-history__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chat-history__header {
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.chat-history__filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.chat-history__filters :deep(.el-date-editor) {
  width: 100%;
  max-width: 100%;
}

.chat-history__tabs {
  display: flex;
  gap: 4px;
}

.chat-history__tabs button {
  flex: 1;
  min-width: 0;
  padding: 4px 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.chat-history__tabs button.is-active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.chat-history__action-buttons {
  display: flex;
  flex: none;
  gap: 6px;
}

.chat-history__results {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 12px 12px;
}

.chat-history__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.chat-history__image,
.chat-history__row {
  min-width: 0;
}

.chat-history__image :deep(.el-image) {
  width: 100%;
  height: 96px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}

.chat-history__row {
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.chat-history__body p,
.chat-history__body a,
.chat-history__body strong {
  display: block;
  margin: 0 0 4px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.chat-history__body p {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.chat-history__meta {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-history__hint,
.chat-history__error {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-history__error {
  color: var(--el-color-danger);
}
</style>
