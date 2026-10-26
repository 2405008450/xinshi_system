<template>
  <div class="document-sections-page">
  <el-card class="common-page-card notice-page" shadow="never" v-loading="loading">
    <template #header>
      <div class="notice-page__header">
        <div>
          <h2>{{ pageTitle }}</h2>
          <p>{{ description }}</p>
        </div>
        <div class="notice-page__actions">
          <el-button v-if="canEdit" :disabled="loading || !!treeError" @click="managerVisible = true">栏目管理</el-button>
          <el-button :disabled="editorVisible || managerVisible" @click="loadTree">刷新</el-button>
        </div>
      </div>
    </template>

    <el-alert v-if="treeError" :title="treeError" type="warning" :closable="false" show-icon class="notice-load-error" />
    <div class="notice-search">
      <el-input
        v-model="searchKeyword"
        clearable
        maxlength="100"
        placeholder="搜索栏目名称或内容"
        @input="handleSearchInput"
        @keyup.enter="runSearch(true, false)"
      />
      <el-button type="primary" @click="runSearch(true, false)">查询</el-button>
    </div>

    <section v-if="searchActive" class="notice-search-results" v-loading="searching">
      <div class="notice-search-results__heading">
        <span>搜索结果</span>
        <span v-if="searched">共找到 {{ searchPagination.total }} 个栏目</span>
      </div>
      <template v-if="searchRows.length">
        <article v-for="row in searchRows" :key="row.id" class="notice-search-result">
          <div class="notice-search-result__heading">
            <div>
              <b>{{ row.displayTitle }}</b>
              <span>{{ row.breadcrumb }}</span>
            </div>
            <el-button type="primary" link @click="openSearchResult(row)">查看栏目</el-button>
          </div>
          <p>
            <template v-for="(segment, index) in highlight(row.snippet)" :key="`${row.id}:${index}`">
              <mark v-if="segment.matched">{{ segment.text }}</mark><span v-else>{{ segment.text }}</span>
            </template>
          </p>
          <div class="notice-search-result__tags">
            <el-tag v-if="row.matchedTitle" size="small" effect="plain">栏目名称命中</el-tag>
            <el-tag v-if="row.matchedContent" size="small" type="success" effect="plain">正文命中</el-tag>
          </div>
        </article>
      </template>
      <el-empty v-else-if="searched && !searching" description="未找到匹配的栏目或内容" :image-size="88" />
      <el-empty v-else-if="!searching" description="输入关键词后开始搜索" :image-size="88" />
      <el-pagination
        v-if="searchPagination.total > searchPagination.limit"
        v-model:current-page="searchPagination.page"
        :page-size="searchPagination.limit"
        :total="searchPagination.total"
        layout="total, prev, pager, next, jumper"
        @current-change="runSearch(false, false)"
      />
    </section>

    <template v-else>
      <el-breadcrumb v-if="isDrilldown" separator="/" class="notice-breadcrumb" aria-label="栏目路径">
        <el-breadcrumb-item>
          <button v-if="activeNotice" type="button" class="notice-breadcrumb__link" @click="navigateSection(null)">{{ pageTitle }}</button>
          <span v-else aria-current="page">{{ pageTitle }}</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-for="(item, index) in activePath" :key="item.id">
          <button v-if="index < activePath.length - 1" type="button" class="notice-breadcrumb__link" @click="navigateSection(item.id)">{{ item.title }}</button>
          <span v-else aria-current="page">{{ item.title }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>

      <div v-if="isDrilldown && !activeNotice && noticeTree.length" class="notice-section-cards" aria-label="一级栏目">
        <article
          v-for="root in noticeTree"
          :key="root.id"
          class="notice-section-card"
          role="link"
          tabindex="0"
          @click="openCard($event, root)"
          @keydown="onCardKeydown($event, root)"
        >
          <span class="notice-section-card__heading">
            <span class="notice-section-card__title">{{ root.title }}</span>
            <span v-if="formatCardDate(root.updatedAt)" class="notice-section-card__meta">更新于 {{ formatCardDate(root.updatedAt) }}</span>
          </span>
          <p v-if="root.hasContent" class="notice-section-card__preview" :class="{ 'is-empty': !root.preview }">{{ root.preview || '暂无内容' }}</p>
          <div v-if="root.children?.length" class="notice-section-card__children">
            <button
              v-for="child in previewChildren(root)"
              :key="child.id"
              type="button"
              class="notice-section-card__child"
              @click.stop="selectSection(child)"
            >{{ child.title }}</button>
            <button
              v-if="root.children.length > CHILD_PREVIEW_LIMIT"
              type="button"
              class="notice-section-card__more"
              @click.stop="selectSection(root)"
            >查看全部 {{ root.children.length }} 个子栏目 ></button>
          </div>
        </article>
      </div>

      <el-select v-if="!isDrilldown" v-model="activeId" class="notice-page__mobile-select" placeholder="请选择主题" @change="selectSectionById">
        <el-option v-for="node in flatNotices.filter(item=>item.hasContent || allowGroupSelection)" :key="node.id" :label="sectionPath(noticeTree,node.id).map(item=>item.title).join(' / ')" :value="node.id" />
      </el-select>

      <div v-if="activeNotice" class="notice-layout" :class="{ 'notice-layout--drilldown': isDrilldown }">
        <nav v-if="!isDrilldown" class="notice-nav" :aria-label="`${pageTitle}主题`">
          <DocumentSectionNav :nodes="noticeTree" :active-id="activeId" :expanded-ids="expandedIds" :allow-group-selection="allowGroupSelection" @select="selectSection" @toggle="toggleRoot" />
        </nav>

        <section class="notice-content" v-loading="detailLoading">
          <div v-if="isDrilldown && activeNotice.children?.length" class="notice-section-cards notice-section-cards--children" aria-label="下级栏目">
            <article
              v-for="(child, index) in activeNotice.children"
              :key="child.id"
              class="notice-section-card"
              role="link"
              tabindex="0"
              @click="openCard($event, child)"
              @keydown="onCardKeydown($event, child)"
            >
              <span class="notice-section-card__heading">
                <span class="notice-section-card__title">{{ child.title }}</span>
                <span v-if="formatCardDate(child.updatedAt)" class="notice-section-card__meta">更新于 {{ formatCardDate(child.updatedAt) }}</span>
              </span>
              <p v-if="child.hasContent" class="notice-section-card__preview" :class="[`is-tint-${index % 4}`, { 'is-empty': !child.preview }]">{{ child.preview || '暂无内容' }}</p>
            </article>
          </div>
          <div class="notice-content__heading">
            <div>
              <h3>{{ activeNotice.title }}</h3>
              <div v-if="activeNotice.hasContent" class="notice-content__meta">
                <template v-if="activeDetail?.updatedAt">
                  最近由 {{ activeDetail.updatedByName || '未知用户' }} 编辑于 {{ formatDateTime(activeDetail.updatedAt) }}
                </template>
                <template v-else>尚未编辑</template>
              </div>
            </div>
            <el-button v-if="canEdit && activeNotice.hasContent" type="primary" @click="openEditor">编辑内容</el-button>
          </div>

          <RichTextContent
            :image-api="adapter.images || null"
            enable-links
            v-if="activeNotice.hasContent && hasContent(activeDetail?.contentJson)"
            :document="activeDetail.contentJson"
            class="notice-content__document"
          />
          <el-empty v-else-if="!detailLoading && activeNotice.hasContent" description="暂无内容，等待补充" :image-size="96" />
          <slot name="attachments" :section="activeNotice" :can-edit="canEdit" :refresh-key="refreshKey" />
        </section>
      </div>
      <el-empty v-else-if="!loading && !treeError && (!isDrilldown || !noticeTree.length)" :description="`${pageTitle}暂无栏目，请通过栏目管理添加`" />
    </template>
  </el-card>

  <DocumentSectionManager :page-title="pageTitle" :adapter="adapter" v-model="managerVisible" :tree="noticeTree" @refresh="handleStructureRefresh" />

  <DraggableFormDialog
    v-model="editorVisible"
    :title="`编辑${pageTitle} · ${activeNotice?.title || ''}`"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    class="annotation-notice-dialog"
    :close-on-click-modal="false"
    :before-close="beforeEditorClose"
  >
    <RichTextComposer ref="composerRef" v-if="editorVisible" v-model="draftContent" :image-api="adapter.images || null" :image-section-id="activeId" :disabled="saving" @uploading-change="imageUploading = $event" format-colors plain-text-paste enable-links min-height="360px" placeholder="请输入需要团队注意的事项…" />
    <template #footer>
      <el-button :disabled="saving" @click="requestEditorClose">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="imageUploading" @click="saveNotice">保存</el-button>
    </template>
  </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onActivated, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import DocumentSectionManager from '@/components/common/DocumentSectionManager.vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { hasPermission } from '@/utils/permission'
import { formatBusinessDateTime as formatDateTime } from '@/utils/dateTime'
import DocumentSectionNav from './DocumentSectionNav.vue'
import { sectionPath, sectionQuery, flattenSections } from '@/utils/documentSectionNavigation'

const props = defineProps({
  pageTitle: { type: String, required: true },
  description: { type: String, default: '' },
  adapter: { type: Object, required: true },
  writePermission: { type: String, default: '' },
  allowAllUsersEdit: { type: Boolean, default: false },
  allowGroupSelection: { type: Boolean, default: false },
  navigationMode: { type: String, default: 'drilldown' },
  sectionQueryKey: { type: String, default: 'documentSectionId' },
  routeSection: { type: String, default: '' }
})
const route = useRoute()
const router = useRouter()
const pagePath = route.path
const isCurrentPage = computed(() => route.path === pagePath && (!props.routeSection || route.query.section === props.routeSection))
const isDrilldown = computed(() => props.navigationMode === 'drilldown')
const treeReady = ref(false)
const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const noticeTree = ref([])
const activeId = ref(null)
const expandedIds = ref(new Set())
const detailCache = ref({})
const detailLoading = ref(false)
const loading = ref(false)
const treeError = ref('')
const refreshKey = ref(0)
const saving = ref(false)
const composerRef = ref(null)
const imageUploading = ref(false)
const editorVisible = ref(false)
const managerVisible = ref(false)
const draftContent = ref(emptyDocument())
const originalContent = ref('')
const searchKeyword = ref('')
const searchRows = ref([])
const searching = ref(false)
const searched = ref(false)
const searchPagination = reactive({ page: 1, limit: 20, total: 0 })
let searchTimer
let searchController
let searchRequestId = 0
let detailRequestId = 0
let closingAfterSave = false
let firstActivation = true

const CHILD_PREVIEW_LIMIT = 4
const canEdit = computed(() => props.allowAllUsersEdit || (Boolean(props.writePermission) && hasPermission(props.writePermission)))
const previewChildren = section => (section?.children || []).slice(0, CHILD_PREVIEW_LIMIT)
function formatCardDate(value) {
  const formatted = formatDateTime(value)
  if (!formatted || formatted === '-') return ''
  return formatted.split(/\s+/)[0]
}
function openCard(event, section) {
  if (event.target.closest('button, a')) return
  selectSection(section)
}
function onCardKeydown(event, section) {
  if (event.target !== event.currentTarget || (event.key !== 'Enter' && event.key !== ' ')) return
  event.preventDefault()
  selectSection(section)
}
function plainPreview(document, size = 120) {
  const chunks = []
  const visit = node => {
    if (!node || typeof node !== 'object') return
    if (node.type === 'text' && typeof node.text === 'string') chunks.push(node.text)
    else if (['hardBreak', 'paragraph', 'heading', 'listItem'].includes(node.type) && chunks.length) chunks.push('\n')
    ;(node.content || []).forEach(visit)
  }
  visit(document)
  const text = chunks.join('').replace(/\s+/g, ' ').trim()
  return text.length > size ? `${text.slice(0, size)}…` : text
}
function patchTreePreview(id, saved) {
  const visit = nodes => {
    for (const node of nodes || []) {
      if (node.id === id) {
        node.preview = plainPreview(saved?.contentJson)
        node.updatedAt = saved?.updatedAt || node.updatedAt
        node.updatedByName = saved?.updatedByName || node.updatedByName
        return true
      }
      if (visit(node.children)) return true
    }
    return false
  }
  visit(noticeTree.value)
}
const flatNotices = computed(() => flattenSections(noticeTree.value))
const activeNotice = computed(() => flatNotices.value.find(item => item.id === activeId.value) || null)
const activePath = computed(() => sectionPath(noticeTree.value, activeId.value))
const activeDetail = computed(() => activeId.value ? detailCache.value[activeId.value] || null : null)
const isDirty = computed(() => editorVisible.value && JSON.stringify(draftContent.value) !== originalContent.value)
const searchActive = computed(() => Boolean(searchKeyword.value.trim()))

const cloneDocument = value => JSON.parse(JSON.stringify(value || emptyDocument()))
const isExpanded = id => expandedIds.value.has(id)
const rootHasActiveChild = root => (root.children || []).some(child => child.id === activeId.value)

function toggleRoot(id) {
  const next = new Set(expandedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedIds.value = next
}

function hasContent(document) {
  const containsText = node => Boolean(node?.text?.trim()) || node?.type === 'image' || (node?.content || []).some(containsText)
  return Boolean(document && containsText(document))
}

async function loadTree() {
  refreshKey.value += 1
  detailCache.value = {}
  loading.value = true
  treeError.value = ''
  try {
    const result = await props.adapter.tree()
    noticeTree.value = Array.isArray(result) ? result : []
    treeReady.value = true
    expandedIds.value = new Set(flattenSections(noticeTree.value).filter(item => item.children?.length).map(item => item.id))
    if (isDrilldown.value) {
      await syncRouteSection()
    } else {
      const activeStillExists = flatNotices.value.some(item => item.id === activeId.value && (item.hasContent || props.allowGroupSelection))
      if (!activeStillExists) activeId.value = flatNotices.value.find(item => item.hasContent || props.allowGroupSelection)?.id || null
      if (activeId.value) await loadDetail(activeId.value)
    }
  } catch (error) {
    treeError.value = getLocalizedErrorMessage(error, props.pageTitle + '加载失败')
    ElMessage.error(treeError.value)
  } finally {
    loading.value = false
  }
}

async function loadDetail(id, force = false) {
  const current = ++detailRequestId
  if (!id || (!force && detailCache.value[id])) { detailLoading.value = false; return }
  detailLoading.value = true
  try {
    const detail = await props.adapter.detail(id)
    if (current !== detailRequestId) return
    detailCache.value = { ...detailCache.value, [id]: detail }
  } catch (error) {
    if (current === detailRequestId) ElMessage.error(getLocalizedErrorMessage(error, '栏目内容加载失败'))
  } finally {
    if (current === detailRequestId) detailLoading.value = false
  }
}

async function selectSection(item) {
  if (!item) return
  if (isDrilldown.value) return navigateSection(item.id)
  if (!item.hasContent && !props.allowGroupSelection) return toggleRoot(item.id)
  activeId.value = item.id
  await loadDetail(item.id)
}

async function navigateSection(id) {
  await router.push({ path: route.path, query: sectionQuery(route.query, id, props.sectionQueryKey) })
}

async function syncRouteSection() {
  if (!isDrilldown.value || !treeReady.value || !isCurrentPage.value) return
  const requested = route.query[props.sectionQueryKey]
  const path = sectionPath(noticeTree.value, requested)
  activeId.value = path.at(-1)?.id || null
  if (requested != null && !path.length) {
    await router.replace({ path: route.path, query: sectionQuery(route.query, null, props.sectionQueryKey) })
  }
  await loadDetail(activeId.value)
}

watch(() => [route.query[props.sectionQueryKey], route.query.section, route.path], syncRouteSection)

function selectSectionById(id) {
  const item = flatNotices.value.find(row => row.id === id)
  if (item) selectSection(item)
}

function openEditor() {
  if (!activeDetail.value) return
  draftContent.value = cloneDocument(activeDetail.value.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
  imageUploading.value = false
  editorVisible.value = true
}

async function confirmDiscard() {
  if (!isDirty.value && !imageUploading.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '放弃修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑'
    })
    return true
  } catch {
    return false
  }
}

async function guardEditorNavigation(to) {
  if (!isDrilldown.value || !editorVisible.value) return true
  if (to.path === route.path && to.query.section === route.query.section && to.query[props.sectionQueryKey] === route.query[props.sectionQueryKey]) return true
  if (saving.value || !await confirmDiscard()) return false
  editorVisible.value = false
  return true
}

onBeforeRouteUpdate(guardEditorNavigation)
onBeforeRouteLeave(guardEditorNavigation)

async function requestEditorClose() {
  if (saving.value) return
  if (await confirmDiscard()) editorVisible.value = false
}

async function beforeEditorClose(done) {
  if (saving.value && !closingAfterSave) return
  if (closingAfterSave || await confirmDiscard()) done()
}

async function saveNotice() {
  if (!activeId.value || saving.value || imageUploading.value) return
  saving.value = true
  try {
    const saved = await props.adapter.saveContent(activeId.value, draftContent.value, activeDetail.value?.updatedAt)
    detailCache.value = { ...detailCache.value, [activeId.value]: saved }
    patchTreePreview(activeId.value, saved)
    composerRef.value?.markImagesSaved(saved.contentJson)
    closingAfterSave = true
    editorVisible.value = false
    ElMessage.success(props.pageTitle + '已保存')
  } catch (error) {
    const errorMessage = getLocalizedErrorMessage(error, props.pageTitle + '保存失败')
    if (errorMessage.includes('字体颜色格式无效') || errorMessage.includes('高亮颜色无效')) {
      ElMessage.error('粘贴内容可能包含不兼容的 Word 格式，请全选编辑器内容，点击“清除格式”后重新设置字体颜色或高亮')
    } else {
      ElMessage.error(error?.response?.status === 409 ? '该栏目已被他人更新，请取消编辑并刷新后重试' : errorMessage)
    }
  } finally {
    saving.value = false
    closingAfterSave = false
  }
}

function clearSearch() {
  clearTimeout(searchTimer)
  searchController?.abort()
  searchRequestId += 1
  searchRows.value = []
  searchPagination.total = 0
  searched.value = false
  searching.value = false
}

async function runSearch(resetPage = true, silent = false) {
  clearTimeout(searchTimer)
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    clearSearch()
    if (!silent) ElMessage.warning('请输入搜索关键词')
    return
  }
  if (resetPage) searchPagination.page = 1
  searchController?.abort()
  searchController = new AbortController()
  const current = ++searchRequestId
  searching.value = true
  try {
    const result = await props.adapter.search({
      keyword,
      skip: (searchPagination.page - 1) * searchPagination.limit,
      limit: searchPagination.limit
    }, { signal: searchController.signal })
    if (current !== searchRequestId) return
    searchRows.value = Array.isArray(result?.items) ? result.items : []
    searchPagination.total = result?.total || 0
    searched.value = true
  } catch (error) {
    if (current !== searchRequestId || error?.code === 'ERR_CANCELED') return
    ElMessage.error(getLocalizedErrorMessage(error, props.pageTitle + '搜索失败'))
  } finally {
    if (current === searchRequestId) searching.value = false
  }
}

function handleSearchInput(value) {
  clearTimeout(searchTimer)
  if (!value?.trim()) return clearSearch()
  searchTimer = setTimeout(() => runSearch(true, true), 400)
}

function highlight(text) {
  const keyword = searchKeyword.value.trim()
  if (!keyword) return [{ text: text || '', matched: false }]
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return String(text || '').split(new RegExp(`(${escaped})`, 'gi')).filter(Boolean).map(value => ({
    text: value,
    matched: value.toLocaleLowerCase() === keyword.toLocaleLowerCase()
  }))
}

async function openSearchResult(row) {
  const item = flatNotices.value.find(section => section.id === row.id)
  if (!item) return
  const parents=sectionPath(noticeTree.value,row.id).slice(0,-1)
  expandedIds.value = new Set([...expandedIds.value,...parents.map(item=>item.id)])
  searchKeyword.value = ''
  clearSearch()
  if (isDrilldown.value || item.hasContent || props.allowGroupSelection) await selectSection(item)
  else if (!isExpanded(item.id)) toggleRoot(item.id)
}

async function handleStructureRefresh() {
  detailCache.value = {}
  await loadTree()
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  searchController?.abort()
  detailRequestId += 1
})

onMounted(loadTree)
onActivated(() => {
  if (firstActivation) { firstActivation = false; return }
  if (!editorVisible.value && !managerVisible.value) loadTree()
})
</script>

<style scoped>
.notice-load-error{margin-bottom:14px}
.notice-breadcrumb{display:flex;flex-wrap:wrap;gap:8px 0;margin:20px 0;line-height:1.6}
.notice-breadcrumb :deep(.el-breadcrumb__inner){white-space:normal;overflow-wrap:anywhere}
.notice-breadcrumb__link{padding:0;border:0;background:transparent;color:var(--el-color-primary);font:inherit;cursor:pointer;text-align:left}
.notice-breadcrumb__link:hover{text-decoration:underline}
.notice-section-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:14px}
.notice-section-cards--children{margin-bottom:24px}
.notice-section-card{display:flex;flex-direction:column;gap:10px;padding:20px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-bg-color);text-align:left;font:inherit;cursor:pointer;min-width:0}
.notice-section-card:hover,.notice-section-card:focus-visible{border-color:var(--el-color-primary);background:var(--el-color-primary-light-9);outline:none}
.notice-section-card__heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.notice-section-card__title{font-weight:600;color:var(--el-text-color-primary);overflow-wrap:anywhere}
.notice-section-card__meta{flex:none;color:var(--el-text-color-secondary);font-size:12px;line-height:1.6;white-space:nowrap}
.notice-section-card__preview{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;margin:0;color:var(--el-text-color-secondary);font-size:13px;line-height:1.6;overflow-wrap:anywhere}
.notice-section-card__preview.is-empty{color:var(--el-text-color-placeholder)}
.notice-section-cards--children .notice-section-card__preview{padding:8px 10px;border-radius:6px}
.notice-section-cards--children .notice-section-card__preview.is-tint-0{background:#e7f0ea}
.notice-section-cards--children .notice-section-card__preview.is-tint-1{background:#e8eef6}
.notice-section-cards--children .notice-section-card__preview.is-tint-2{background:#f3eee6}
.notice-section-cards--children .notice-section-card__preview.is-tint-3{background:#eeeaf3}
.notice-section-card__children{display:flex;flex-direction:column;align-items:stretch;gap:6px;margin-top:auto;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}
.notice-section-card__child,.notice-section-card__more{width:100%;padding:7px 10px;border:0;border-radius:6px;background:transparent;font:inherit;text-align:left;cursor:pointer;overflow-wrap:anywhere}
.notice-section-card__child{color:var(--el-text-color-regular)}
.notice-section-card__child:nth-child(4n+1){background:#e7f0ea}
.notice-section-card__child:nth-child(4n+2){background:#e8eef6}
.notice-section-card__child:nth-child(4n+3){background:#f3eee6}
.notice-section-card__child:nth-child(4n+4){background:#eeeaf3}
.notice-section-card__child:nth-child(4n+1):hover,.notice-section-card__child:nth-child(4n+1):focus-visible{background:#d7e6dc}
.notice-section-card__child:nth-child(4n+2):hover,.notice-section-card__child:nth-child(4n+2):focus-visible{background:#d9e3f1}
.notice-section-card__child:nth-child(4n+3):hover,.notice-section-card__child:nth-child(4n+3):focus-visible{background:#e8e0d4}
.notice-section-card__child:nth-child(4n+4):hover,.notice-section-card__child:nth-child(4n+4):focus-visible{background:#e1dbe9}
.notice-section-card__child:hover,.notice-section-card__child:focus-visible{color:var(--el-text-color-primary)}
.notice-section-card__more{color:var(--el-color-primary)}
.notice-section-card__more:hover,.notice-section-card__more:focus-visible{background:var(--el-color-primary-light-8);color:var(--el-color-primary)}
.notice-layout.notice-layout--drilldown{display:block;min-height:0}
.notice-layout--drilldown .notice-content__document{min-height:0}
@media(max-width:768px){.notice-section-cards{grid-template-columns:minmax(0,1fr)}.notice-section-card__preview{-webkit-line-clamp:2}.notice-section-card__heading{flex-wrap:wrap}.notice-section-card__meta{white-space:normal}}
.notice-page__header,.notice-page__actions,.notice-search,.notice-search-results__heading,.notice-search-result__heading,.notice-search-result__heading>div,.notice-nav__row{display:flex;align-items:center}.notice-page__header{justify-content:space-between;gap:16px;flex-wrap:wrap}.notice-page__header>div{min-width:0}.notice-page__header h2{margin:0;font-size:20px}.notice-page__header p{margin:6px 0 0;color:var(--el-text-color-secondary);font-size:13px}.notice-page__actions{gap:10px}.notice-search{gap:10px;margin-bottom:14px}.notice-search .el-input{max-width:520px;min-width:0}.notice-layout{display:grid;grid-template-columns:240px minmax(0,1fr);min-height:520px;border:1px solid var(--el-border-color-lighter);border-radius:8px;overflow:hidden}.notice-nav{padding:10px;background:var(--el-fill-color-lighter);border-right:1px solid var(--el-border-color-lighter);overflow-y:auto}.notice-nav__row{gap:2px}.notice-nav__item,.notice-nav__group,.notice-nav__toggle{border:0;border-radius:6px;background:transparent;color:var(--el-text-color-regular);font:inherit;cursor:pointer}.notice-nav__item,.notice-nav__group{display:flex;align-items:center;width:100%;padding:11px 12px;text-align:left}.notice-nav__item:hover,.notice-nav__group:hover,.notice-nav__toggle:hover{background:var(--el-fill-color)}.notice-nav__group.is-active,.notice-nav__item.is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:600}.notice-nav__group{justify-content:space-between;font-weight:600}.notice-nav__group.has-active-child{color:var(--el-color-primary)}.notice-nav__toggle{display:flex;flex:0 0 34px;align-items:center;justify-content:center;height:34px}.notice-nav__arrow{transition:transform .2s ease}.notice-nav__arrow.is-expanded{transform:rotate(180deg)}.notice-nav__children{padding:2px 0 4px 10px}.notice-nav__item--child{padding:9px 10px;font-size:14px}.notice-content{min-width:0;padding:24px}.notice-content__heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:18px;border-bottom:1px solid var(--el-border-color-lighter)}.notice-content__heading h3{margin:0;font-size:20px;overflow-wrap:anywhere}.notice-content__heading>div{min-width:0}.notice-content__meta{margin-top:7px;color:var(--el-text-color-secondary);font-size:13px}.notice-content__document{min-height:300px;padding:22px 4px}.notice-page__mobile-select{display:none;width:100%;margin-bottom:14px}.notice-search-results{min-height:420px;padding:18px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.notice-search-results__heading{justify-content:space-between;margin-bottom:14px;font-weight:600}.notice-search-results__heading span+span{color:var(--el-text-color-secondary);font-size:13px;font-weight:400}.notice-search-result{padding:14px 16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.notice-search-result+.notice-search-result{margin-top:10px}.notice-search-result__heading{justify-content:space-between;gap:12px}.notice-search-result__heading>div{min-width:0;gap:10px}.notice-search-result__heading span{overflow:hidden;color:var(--el-text-color-secondary);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.notice-search-result p{margin:10px 0;line-height:1.65;white-space:pre-wrap}.notice-search-result mark{padding:0 2px;background:var(--el-color-warning-light-7);color:inherit}.notice-search-result__tags{display:flex;gap:6px}.notice-search-results .el-pagination{justify-content:flex-end;margin-top:16px}:deep(.notice-content__document ul),:deep(.notice-content__document ol){padding-left:24px}:deep(.notice-content__document h1),:deep(.notice-content__document h2),:deep(.notice-content__document h3){margin:14px 0 8px}:deep(.notice-content__document blockquote){margin:12px 0;padding-left:14px;border-left:3px solid var(--el-border-color);color:var(--el-text-color-secondary)}
@media(max-width:768px){.notice-page__mobile-select{display:block}.notice-layout{display:block;min-height:420px}.notice-nav{display:none}.notice-content{padding:18px}.notice-content__heading{align-items:center}.notice-page__header p{display:none}.notice-search-result__heading,.notice-search-result__heading>div{align-items:flex-start;flex-direction:column}.notice-search-result__heading span{white-space:normal}}
</style>

<style>
.annotation-notice-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.annotation-notice-dialog .el-dialog__header,.annotation-notice-dialog .el-dialog__footer{flex-shrink:0}.annotation-notice-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-notice-dialog .el-dialog__footer{padding-top:14px;border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
</style>
