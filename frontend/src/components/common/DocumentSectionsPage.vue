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
          <el-button v-if="canEdit" @click="managerVisible = true">栏目管理</el-button>
          <el-button :disabled="editorVisible || managerVisible" @click="loadTree">刷新</el-button>
        </div>
      </div>
    </template>

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
      <el-select v-model="activeId" class="notice-page__mobile-select" placeholder="请选择主题" @change="selectSectionById">
        <template v-for="root in noticeTree" :key="root.id">
          <el-option v-if="root.hasContent || allowGroupSelection" :label="root.title" :value="root.id" />
          <el-option-group v-if="root.children?.length" :label="root.title">
            <el-option v-for="child in root.children" :key="child.id" :label="child.title" :value="child.id" />
          </el-option-group>
        </template>
      </el-select>

      <div v-if="activeNotice" class="notice-layout">
        <nav class="notice-nav" :aria-label="`${pageTitle}主题`">
          <div v-for="root in noticeTree" :key="root.id" class="notice-nav__root">
            <div class="notice-nav__row">
              <button
                type="button"
                :class="[root.hasContent ? 'notice-nav__item' : 'notice-nav__group', { 'is-active': root.id === activeId, 'has-active-child': rootHasActiveChild(root) }]"
                :aria-expanded="root.children?.length ? isExpanded(root.id) : undefined"
                @click="(root.hasContent || allowGroupSelection) ? selectSection(root) : toggleRoot(root.id)"
              >
                <span>{{ root.title }}</span>
                <el-icon v-if="!root.hasContent && !allowGroupSelection && root.children?.length" class="notice-nav__arrow" :class="{ 'is-expanded': isExpanded(root.id) }"><ArrowDown /></el-icon>
              </button>
              <button
                v-if="(root.hasContent || allowGroupSelection) && root.children?.length"
                type="button"
                class="notice-nav__toggle"
                :aria-label="`${isExpanded(root.id) ? '收起' : '展开'}${root.title}`"
                :aria-expanded="isExpanded(root.id)"
                @click="toggleRoot(root.id)"
              >
                <el-icon class="notice-nav__arrow" :class="{ 'is-expanded': isExpanded(root.id) }"><ArrowDown /></el-icon>
              </button>
            </div>
            <el-collapse-transition>
              <div v-show="isExpanded(root.id)" v-if="root.children?.length" class="notice-nav__children">
                <button
                  v-for="child in root.children"
                  :key="child.id"
                  type="button"
                  :class="['notice-nav__item', 'notice-nav__item--child', { 'is-active': child.id === activeId }]"
                  @click="selectSection(child)"
                >{{ child.title }}</button>
              </div>
            </el-collapse-transition>
          </div>
        </nav>

        <section class="notice-content" v-loading="detailLoading">
          <div class="notice-content__heading">
            <div>
              <h3>{{ activeNotice.title }}</h3>
              <div class="notice-content__meta">
                <template v-if="activeDetail?.updatedAt">
                  最近由 {{ activeDetail.updatedByName || '未知用户' }} 编辑于 {{ formatDateTime(activeDetail.updatedAt) }}
                </template>
                <template v-else>尚未编辑</template>
              </div>
            </div>
            <el-button v-if="canEdit && activeNotice.hasContent" type="primary" @click="openEditor">编辑内容</el-button>
          </div>

          <RichTextContent
            enable-links
            v-if="activeNotice.hasContent && hasContent(activeDetail?.contentJson)"
            :document="activeDetail.contentJson"
            class="notice-content__document"
          />
          <el-empty v-else-if="!detailLoading && activeNotice.hasContent" description="暂无内容，等待补充" :image-size="96" />
          <slot name="attachments" :section="activeNotice" :can-edit="canEdit" :refresh-key="refreshKey" />
        </section>
      </div>
      <el-empty v-else-if="!loading" :description="`${pageTitle}暂无栏目，请通过栏目管理添加`" />
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
    <RichTextComposer v-if="editorVisible" v-model="draftContent" format-colors plain-text-paste enable-links min-height="360px" placeholder="请输入需要团队注意的事项…" />
    <template #footer>
      <el-button :disabled="saving" @click="requestEditorClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveNotice">保存</el-button>
    </template>
  </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onActivated, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import DocumentSectionManager from '@/components/common/DocumentSectionManager.vue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { hasPermission } from '@/utils/permission'

const props = defineProps({
  pageTitle: { type: String, required: true },
  description: { type: String, default: '' },
  adapter: { type: Object, required: true },
  writePermission: { type: String, required: true },
  allowGroupSelection: { type: Boolean, default: false }
})
const emptyDocument = () => ({ type: 'doc', content: [{ type: 'paragraph' }] })
const noticeTree = ref([])
const activeId = ref(null)
const expandedIds = ref(new Set())
const detailCache = ref({})
const detailLoading = ref(false)
const loading = ref(false)
const refreshKey = ref(0)
const saving = ref(false)
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

const canEdit = computed(() => hasPermission(props.writePermission))
const flatNotices = computed(() => noticeTree.value.flatMap(root => [root, ...(root.children || [])]))
const activeNotice = computed(() => flatNotices.value.find(item => item.id === activeId.value) || null)
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
  const containsText = node => Boolean(node?.text?.trim()) || (node?.content || []).some(containsText)
  return Boolean(document && containsText(document))
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).format(date)
}

async function loadTree() {
  refreshKey.value += 1
  detailCache.value = {}
  loading.value = true
  try {
    const result = await props.adapter.tree()
    noticeTree.value = Array.isArray(result) ? result : []
    expandedIds.value = new Set(noticeTree.value.filter(item => item.children?.length).map(item => item.id))
    const activeStillExists = flatNotices.value.some(item => item.id === activeId.value && (item.hasContent || props.allowGroupSelection))
    if (!activeStillExists) activeId.value = flatNotices.value.find(item => item.hasContent || props.allowGroupSelection)?.id || null
    if (activeId.value) await loadDetail(activeId.value)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, props.pageTitle + '加载失败'))
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
  if (!item.hasContent && !props.allowGroupSelection) return toggleRoot(item.id)
  activeId.value = item.id
  await loadDetail(item.id)
}

function selectSectionById(id) {
  const item = flatNotices.value.find(row => row.id === id)
  if (item) selectSection(item)
}

function openEditor() {
  if (!activeDetail.value) return
  draftContent.value = cloneDocument(activeDetail.value.contentJson)
  originalContent.value = JSON.stringify(draftContent.value)
  editorVisible.value = true
}

async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '放弃修改', {
      type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑'
    })
    return true
  } catch {
    return false
  }
}

async function requestEditorClose() {
  if (await confirmDiscard()) editorVisible.value = false
}

async function beforeEditorClose(done) {
  if (closingAfterSave || await confirmDiscard()) done()
}

async function saveNotice() {
  if (!activeId.value || saving.value) return
  if (saving.value) return
  saving.value = true
  try {
    const saved = await props.adapter.saveContent(activeId.value, draftContent.value, activeDetail.value?.updatedAt)
    detailCache.value = { ...detailCache.value, [activeId.value]: saved }
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
  const parent = noticeTree.value.find(root => (root.children || []).some(child => child.id === row.id))
  if (parent) expandedIds.value = new Set([...expandedIds.value, parent.id])
  searchKeyword.value = ''
  clearSearch()
  if (item.hasContent || props.allowGroupSelection) await selectSection(item)
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
.notice-page__header,.notice-page__actions,.notice-search,.notice-search-results__heading,.notice-search-result__heading,.notice-search-result__heading>div,.notice-nav__row{display:flex;align-items:center}.notice-page__header{justify-content:space-between;gap:16px;flex-wrap:wrap}.notice-page__header>div{min-width:0}.notice-page__header h2{margin:0;font-size:20px}.notice-page__header p{margin:6px 0 0;color:var(--el-text-color-secondary);font-size:13px}.notice-page__actions{gap:10px}.notice-search{gap:10px;margin-bottom:14px}.notice-search .el-input{max-width:520px;min-width:0}.notice-layout{display:grid;grid-template-columns:240px minmax(0,1fr);min-height:520px;border:1px solid var(--el-border-color-lighter);border-radius:8px;overflow:hidden}.notice-nav{padding:10px;background:var(--el-fill-color-lighter);border-right:1px solid var(--el-border-color-lighter);overflow-y:auto}.notice-nav__row{gap:2px}.notice-nav__item,.notice-nav__group,.notice-nav__toggle{border:0;border-radius:6px;background:transparent;color:var(--el-text-color-regular);font:inherit;cursor:pointer}.notice-nav__item,.notice-nav__group{display:flex;align-items:center;width:100%;padding:11px 12px;text-align:left}.notice-nav__item:hover,.notice-nav__group:hover,.notice-nav__toggle:hover{background:var(--el-fill-color)}.notice-nav__group.is-active,.notice-nav__item.is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:600}.notice-nav__group{justify-content:space-between;font-weight:600}.notice-nav__group.has-active-child{color:var(--el-color-primary)}.notice-nav__toggle{display:flex;flex:0 0 34px;align-items:center;justify-content:center;height:34px}.notice-nav__arrow{transition:transform .2s ease}.notice-nav__arrow.is-expanded{transform:rotate(180deg)}.notice-nav__children{padding:2px 0 4px 10px}.notice-nav__item--child{padding:9px 10px;font-size:14px}.notice-content{min-width:0;padding:24px}.notice-content__heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:18px;border-bottom:1px solid var(--el-border-color-lighter)}.notice-content__heading h3{margin:0;font-size:20px;overflow-wrap:anywhere}.notice-content__heading>div{min-width:0}.notice-content__meta{margin-top:7px;color:var(--el-text-color-secondary);font-size:13px}.notice-content__document{min-height:300px;padding:22px 4px}.notice-page__mobile-select{display:none;width:100%;margin-bottom:14px}.notice-search-results{min-height:420px;padding:18px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.notice-search-results__heading{justify-content:space-between;margin-bottom:14px;font-weight:600}.notice-search-results__heading span+span{color:var(--el-text-color-secondary);font-size:13px;font-weight:400}.notice-search-result{padding:14px 16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.notice-search-result+.notice-search-result{margin-top:10px}.notice-search-result__heading{justify-content:space-between;gap:12px}.notice-search-result__heading>div{min-width:0;gap:10px}.notice-search-result__heading span{overflow:hidden;color:var(--el-text-color-secondary);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.notice-search-result p{margin:10px 0;line-height:1.65;white-space:pre-wrap}.notice-search-result mark{padding:0 2px;background:var(--el-color-warning-light-7);color:inherit}.notice-search-result__tags{display:flex;gap:6px}.notice-search-results .el-pagination{justify-content:flex-end;margin-top:16px}:deep(.notice-content__document ul),:deep(.notice-content__document ol){padding-left:24px}:deep(.notice-content__document h1),:deep(.notice-content__document h2),:deep(.notice-content__document h3){margin:14px 0 8px}:deep(.notice-content__document blockquote){margin:12px 0;padding-left:14px;border-left:3px solid var(--el-border-color);color:var(--el-text-color-secondary)}
@media(max-width:768px){.notice-page__mobile-select{display:block}.notice-layout{display:block;min-height:420px}.notice-nav{display:none}.notice-content{padding:18px}.notice-content__heading{align-items:center}.notice-page__header p{display:none}.notice-search-result__heading,.notice-search-result__heading>div{align-items:flex-start;flex-direction:column}.notice-search-result__heading span{white-space:normal}}
</style>

<style>
.annotation-notice-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.annotation-notice-dialog .el-dialog__header,.annotation-notice-dialog .el-dialog__footer{flex-shrink:0}.annotation-notice-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-notice-dialog .el-dialog__footer{padding-top:14px;border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
</style>
