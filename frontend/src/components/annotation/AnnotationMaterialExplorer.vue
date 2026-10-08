<template>
  <div class="material-explorer" @keydown="navigationKey">
    <div class="explorer-commandbar">
      <div v-if="!readonly" class="explorer-commands">
        <el-button class="explorer-desktop-action" size="small" :icon="FolderAdd" :disabled="disabled" @click="$emit('create', 1)">新建一级文件夹</el-button>
        <el-button class="explorer-desktop-action" size="small" :icon="FolderAdd" :disabled="disabled || !folders.some(folder => !folder.parent_id)" @click="$emit('create', 2)">新建二级文件夹</el-button>
        <el-dropdown class="explorer-mobile-action" trigger="click" :disabled="disabled" @command="level => $emit('create', level)">
          <el-button size="small" :icon="FolderAdd" :disabled="disabled" aria-label="新建文件夹">新建</el-button>
          <template #dropdown><el-dropdown-menu><el-dropdown-item :command="1">新建一级文件夹</el-dropdown-item><el-dropdown-item :command="2" :disabled="!folders.some(folder => !folder.parent_id)">新建二级文件夹</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
        <label class="explorer-upload" :class="{ disabled }"><el-icon><Upload /></el-icon>上传文件<input type="file" multiple :disabled="disabled" aria-label="上传项目资料" @change="uploadFiles"></label>
      </div>
      <div class="explorer-commands explorer-selection-actions">
        <el-button size="small" :icon="Download" :disabled="!selectedFile" @click="$emit('download', selectedFile)">下载</el-button>
        <el-button class="explorer-desktop-action" size="small" :disabled="!selectedFile" @click="$emit('history', selectedFile)">历史版本</el-button>
        <el-button v-if="!readonly" class="explorer-desktop-action" size="small" :disabled="disabled || !selectedFile || hasReplacement(selectedFile.file_id)" @click="replaceFile(selectedFile)">上传新版</el-button>
        <el-button v-if="!readonly" class="explorer-desktop-action" size="small" type="danger" plain :disabled="disabled || !selectedFile" @click="$emit('remove', selectedFile)">移除</el-button>
        <el-dropdown class="explorer-mobile-action" trigger="click" :disabled="!selectedFile" @command="command => entryCommand(command, selectedEntry)">
          <el-button size="small" :disabled="!selectedFile" aria-label="选中文件的更多操作">更多</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="history">历史版本</el-dropdown-item>
            <el-dropdown-item v-if="!readonly" command="replace" :disabled="disabled || !selectedFile || hasReplacement(selectedFile.file_id)">上传新版</el-dropdown-item>
            <el-dropdown-item v-if="!readonly" command="remove" :disabled="disabled" divided>移除文件</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </div>
    <div class="explorer-addressbar">
      <div class="explorer-navigation">
        <el-button :icon="ArrowLeft" size="small" aria-label="后退" title="后退（Alt+左箭头）" :disabled="historyIndex === 0" @click="travel(-1)" />
        <el-button :icon="ArrowRight" size="small" aria-label="前进" title="前进（Alt+右箭头）" :disabled="historyIndex >= navigationHistory.length - 1" @click="travel(1)" />
        <el-button :icon="Top" size="small" aria-label="返回上一级" title="返回上一级（Alt+上箭头）" :disabled="!folderId" @click="goUp" />
        <el-button class="explorer-mobile-action" :icon="Folder" size="small" aria-label="目录树" :aria-expanded="mobileTreeExpanded" title="展开或收起目录树" @click="mobileTreeExpanded = !mobileTreeExpanded" />
      </div>
      <nav class="explorer-breadcrumb" aria-label="资料路径">
        <el-icon class="explorer-path-icon"><FolderOpened /></el-icon>
        <template v-for="(crumb, index) in breadcrumbs" :key="crumb.id || '@root'">
          <span v-if="index" class="explorer-path-divider">›</span>
          <button type="button" :aria-current="index === breadcrumbs.length - 1 ? 'location' : undefined" :title="crumb.name" @click="navigate(crumb.id)">{{ crumb.name }}</button>
        </template>
      </nav>
    </div>
    <div class="material-directory-layout">
      <nav class="material-folder-tree" :class="{ 'mobile-expanded': mobileTreeExpanded }" aria-label="项目资料目录">
        <el-tree :data="folderTree" node-key="key" :props="{ label: 'name', children: 'children' }" :current-node-key="folderId || '@root'" highlight-current default-expand-all :expand-on-click-node="false" @node-click="folder => navigate(folder.id)">
          <template #default="{ data }"><span class="explorer-tree-node" :title="data.name"><el-icon class="explorer-folder-icon"><Folder /></el-icon><span>{{ data.name }}</span><span v-if="data.pending" class="explorer-pending-dot" title="待保存" /></span></template>
        </el-tree>
      </nav>
      <div ref="directoryArea" class="material-directory-files" tabindex="0" aria-label="当前目录文件区" :class="{ 'is-dragging': dragDepth > 0 }" @keydown="listKey" @dragenter="dragEnter" @dragleave="dragLeave" @dragover.prevent="dragOver" @drop.prevent.stop="dropFiles">
        <div v-if="dragDepth > 0" class="explorer-drop-overlay"><el-icon><Upload /></el-icon><span>松开上传到“{{ breadcrumbs.at(-1).name }}”</span></div>
        <div class="explorer-table-scroll">
          <table class="explorer-table" aria-label="当前目录内容">
            <thead><tr><th scope="col">名称</th><th scope="col" class="explorer-modified">修改时间</th><th scope="col" class="explorer-type">类型</th><th scope="col" class="explorer-size">大小</th><th scope="col" class="explorer-more"><span class="explorer-sr-only">操作</span></th></tr></thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.key" :data-entry-key="entry.key" :data-entry-kind="entry.kind" :class="{ 'is-selected': selectedKey === entry.key }" :aria-selected="selectedKey === entry.key" tabindex="0" @click="selectEntry(entry)" @dblclick="openEntry(entry)" @contextmenu.prevent.stop="contextEntry(entry)" @keydown.enter.prevent="openEntry(entry)" @keydown.space.prevent="selectEntry(entry)">
                <td class="explorer-name">
                  <div class="explorer-name-content"><el-icon :class="entry.kind === 'folder' ? 'explorer-folder-icon' : 'explorer-file-icon'"><component :is="entryIcon(entry)" /></el-icon><span :title="entry.name">{{ entry.name }}</span><el-tag v-if="entry.kind === 'folder' && entry.folder.pending" size="small" type="info">待保存</el-tag><el-tag v-if="entry.kind === 'pending'" size="small" :type="entry.upload.status === 'failed' ? 'danger' : 'info'">{{ entry.upload.fileId ? '待保存新版' : '待保存新文件' }}</el-tag></div>
                  <template v-if="entry.kind === 'pending'">
                    <el-progress v-if="entry.upload.status === 'uploading'" :percentage="entry.upload.progress" :stroke-width="4" />
                    <small v-else :class="{ 'explorer-error': entry.upload.status === 'failed' }">{{ entry.upload.status === 'queued' ? '等待上传' : entry.upload.error || '已暂存，等待保存项目' }}</small>
                  </template>
                  <span v-if="entry.kind === 'file'" class="explorer-sr-only">V{{ entry.file.version_no }} · {{ entry.file.uploader_name }}</span>
                </td>
                <td class="explorer-modified">{{ entry.kind === 'pending' ? '-' : formatTime(entry.folder?.created_at || entry.file?.created_at) }}</td>
                <td class="explorer-type">{{ entry.kind === 'folder' ? '文件夹' : materialFileType(entry.name).label }}</td>
                <td class="explorer-size">{{ entry.kind === 'folder' ? '-' : formatSize(entry.file?.file_size ?? entry.upload?.file.size) }}</td>
                <td class="explorer-more" @click.stop @dblclick.stop>
                  <el-dropdown :ref="element => registerDropdown(entry.key, element)" trigger="click" @command="command => entryCommand(command, entry)">
                    <el-button link :icon="MoreFilled" :aria-label="`${entry.name}的更多操作`" @click="selectEntry(entry)" />
                    <template #dropdown><el-dropdown-menu>
                      <el-dropdown-item v-if="entry.kind === 'folder'" command="open">打开文件夹</el-dropdown-item>
                      <template v-if="entry.kind === 'file'">
                        <el-dropdown-item command="download">下载</el-dropdown-item>
                        <el-dropdown-item command="history">历史版本</el-dropdown-item>
                        <el-dropdown-item v-if="!readonly" command="replace" :disabled="disabled || hasReplacement(entry.file.file_id)">上传新版</el-dropdown-item>
                        <el-dropdown-item v-if="!readonly" command="remove" :disabled="disabled" divided>移除文件</el-dropdown-item>
                      </template>
                      <template v-if="entry.kind === 'pending' && !readonly">
                        <el-dropdown-item v-if="entry.upload.status === 'failed'" command="retry" :disabled="disabled">重试</el-dropdown-item>
                        <el-dropdown-item command="discard" :disabled="disabled">取消上传</el-dropdown-item>
                      </template>
                    </el-dropdown-menu></template>
                  </el-dropdown>
                  <template v-if="entry.kind === 'pending' && !readonly"><el-button v-if="entry.upload.status === 'failed'" link type="primary" :disabled="disabled" @click="$emit('retry', entry.upload)">重试</el-button><el-button link :disabled="disabled" @click="$emit('discard', entry.upload)">取消上传</el-button></template>
                  <input v-if="entry.kind === 'file' && !readonly" :ref="element => registerReplacement(entry.file.file_id, element)" class="explorer-file-input" type="file" tabindex="-1" :disabled="disabled || hasReplacement(entry.file.file_id)" :aria-label="`为${entry.name}上传新版`" @change="replacementFiles($event, entry.file)">
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!entries.length" class="explorer-empty"><el-icon><FolderOpened /></el-icon><span>此文件夹为空</span><small v-if="!readonly">可新建文件夹，或将文件拖到这里上传</small></div>
        </div>
      </div>
    </div>
    <div class="explorer-statusbar"><span>{{ childFolders.length }} 个文件夹 · {{ files.length + pending.filter(upload => !upload.fileId).length }} 个文件</span><span v-if="selectedFile">已选中：{{ selectedFile.original_name }} · V{{ selectedFile.version_no }} · {{ selectedFile.uploader_name }}</span><span v-else-if="selectedEntry">已选中：{{ selectedEntry.name }}</span><span v-else>{{ readonly ? '双击文件夹打开，双击文件下载' : '双击打开 · 支持拖放文件上传' }}</span></div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, Top, Folder, FolderAdd, FolderOpened, Upload, Download, Document, Picture, Headset, Film, MoreFilled } from '@element-plus/icons-vue'
import { buildFolderTree, folderBreadcrumbs, materialFileType } from '@/utils/annotationMaterialFolders'

const props = defineProps({ folders: { type: Array, default: () => [] }, folderId: { type: String, default: null }, files: { type: Array, default: () => [] }, pending: { type: Array, default: () => [] }, readonly: Boolean, disabled: Boolean, formatSize: { type: Function, required: true }, formatTime: { type: Function, required: true } })
const emit = defineEmits(['update:folderId', 'create', 'upload', 'replace', 'download', 'history', 'remove', 'retry', 'discard'])
const folderTree = computed(() => buildFolderTree(props.folders))
const breadcrumbs = computed(() => folderBreadcrumbs(props.folders, props.folderId))
const childFolders = computed(() => props.folders.filter(folder => (folder.parent_id || null) === props.folderId))
const entries = computed(() => [
  ...childFolders.value.map(folder => ({ key: `folder:${folder.id}`, kind: 'folder', name: folder.name, folder })),
  ...props.files.map(file => ({ key: `file:${file.file_id}`, kind: 'file', name: file.original_name, file })),
  ...props.pending.map(upload => ({ key: `pending:${upload.key}`, kind: 'pending', name: upload.file.name, upload })),
])
const selectedKey = ref(''), selectedEntry = computed(() => entries.value.find(entry => entry.key === selectedKey.value))
const selectedFile = computed(() => selectedEntry.value?.file || null)
const navigationHistory = ref([props.folderId]), historyIndex = ref(0), dragDepth = ref(0)
const directoryArea = ref(null)
const mobileTreeExpanded = ref(false)
const replacementInputs = new Map(), dropdowns = new Map()
const hasReplacement = id => props.pending.some(upload => upload.fileId === id)
const entryIcon = entry => entry.kind === 'folder' ? Folder : ({ image: Picture, audio: Headset, video: Film }[materialFileType(entry.name).family] || Document)

function navigate(id) { emit('update:folderId', id || null) }
function selectEntry(entry) { selectedKey.value = entry.key }
function registerDropdown(key, element) { if (element) dropdowns.set(key, element); else dropdowns.delete(key) }
function contextEntry(entry) {
  selectEntry(entry)
  dropdowns.forEach(dropdown => dropdown.handleClose())
  dropdowns.get(entry.key)?.handleOpen()
}
function openEntry(entry) {
  selectEntry(entry)
  if (entry.kind === 'folder') navigate(entry.folder.id)
  else if (entry.kind === 'file') emit('download', entry.file)
}
function goUp() { navigate(props.folders.find(folder => folder.id === props.folderId)?.parent_id || null) }
function travel(step) {
  const next = historyIndex.value + step
  if (next < 0 || next >= navigationHistory.value.length) return
  historyIndex.value = next
  navigate(navigationHistory.value[next])
}
function navigationKey(event) {
  if (!event.altKey || event.target.closest('input,textarea,[contenteditable="true"]')) return
  if (event.key === 'ArrowLeft') { event.preventDefault(); travel(-1) }
  if (event.key === 'ArrowRight') { event.preventDefault(); travel(1) }
  if (event.key === 'ArrowUp') { event.preventDefault(); if (props.folderId) goUp() }
}
function listKey(event) {
  if (event.altKey) return
  if (['ArrowUp', 'ArrowDown'].includes(event.key) && entries.value.length) {
    event.preventDefault()
    const index = entries.value.findIndex(entry => entry.key === selectedKey.value)
    const next = index < 0 ? 0 : Math.max(0, Math.min(entries.value.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))
    selectEntry(entries.value[next])
    directoryArea.value?.querySelectorAll('tbody tr')[next]?.focus({ preventScroll: false })
  } else if (event.key === 'Enter' && event.target === directoryArea.value && selectedEntry.value) {
    event.preventDefault(); openEntry(selectedEntry.value)
  }
}
watch(() => props.folderId, async id => {
  selectedKey.value = ''; dragDepth.value = 0
  // 历史前进/后退只移动游标；从路径或树跳转则截断前进历史。
  if (navigationHistory.value[historyIndex.value] !== id) {
    navigationHistory.value = [...navigationHistory.value.slice(0, historyIndex.value + 1), id]
    historyIndex.value = navigationHistory.value.length - 1
  }
  // 进入目录会替换原列表行，保持键盘焦点，继续支持方向键和Alt导航。
  await nextTick(); directoryArea.value?.focus({ preventScroll: true })
})
watch(entries, list => { if (!list.some(entry => entry.key === selectedKey.value)) selectedKey.value = '' })
function registerReplacement(id, element) { if (element) replacementInputs.set(id, element); else replacementInputs.delete(id) }
function replaceFile(file) { if (file && !props.disabled && !props.readonly) replacementInputs.get(file.file_id)?.click() }
function uploadFiles(event) { const files = Array.from(event.target.files || []); event.target.value = ''; if (!props.disabled && !props.readonly) emit('upload', files) }
function replacementFiles(event, file) { const files = Array.from(event.target.files || []); event.target.value = ''; if (!props.disabled && !props.readonly) emit('replace', { files, fileId: file.file_id }) }
function entryCommand(command, entry) {
  if (!entry) return
  if (command === 'open') openEntry(entry)
  else if (command === 'replace') replaceFile(entry.file)
  else if (['download', 'history'].includes(command)) emit(command, entry.file)
  else if (!props.disabled && !props.readonly) emit(command, entry.file || entry.upload)
}
function isFileDrag(event) { return Array.from(event.dataTransfer?.types || []).includes('Files') }
function dragEnter(event) { if (isFileDrag(event) && !props.disabled && !props.readonly) { event.preventDefault(); dragDepth.value += 1 } }
function dragLeave(event) { if (isFileDrag(event)) dragDepth.value = Math.max(0, dragDepth.value - 1) }
function dragOver(event) { if (event.dataTransfer) event.dataTransfer.dropEffect = props.disabled || props.readonly ? 'none' : 'copy' }
function dropFiles(event) {
  dragDepth.value = 0
  if (props.disabled || props.readonly) return
  const items = Array.from(event.dataTransfer?.items || [])
  const directories = items.filter(item => item.webkitGetAsEntry?.()?.isDirectory)
  if (directories.length) ElMessage.warning('请上传文件；暂不支持拖放整个文件夹')
  const files = items.length ? items.filter(item => item.kind === 'file' && !item.webkitGetAsEntry?.()?.isDirectory).map(item => item.getAsFile()).filter(Boolean) : Array.from(event.dataTransfer?.files || [])
  if (files.length) emit('upload', files)
}
</script>

<style scoped>
.material-explorer { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; overflow: hidden; background: #fff; }
.explorer-commandbar,.explorer-addressbar,.explorer-commands,.explorer-navigation { display: flex; align-items: center; gap: 8px; }
.explorer-commandbar { flex-wrap: wrap; justify-content: space-between; padding: 10px 12px; background: #f8fafc; border-bottom: 1px solid var(--el-border-color-lighter); }
.explorer-commands { flex-wrap: wrap; gap: 6px; }
.explorer-commands .el-button + .el-button,.explorer-navigation .el-button + .el-button { margin-left: 0; }
.explorer-mobile-action { display: none; }
.explorer-upload { display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 8px; border: 1px solid var(--el-border-color); border-radius: 4px; font-size: 12px; cursor: pointer; position: relative; background: white; }
.explorer-upload input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }
.explorer-upload.disabled { opacity: .5; cursor: not-allowed; }
.explorer-upload:focus-within { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.explorer-addressbar { padding: 8px 12px; border-bottom: 1px solid var(--el-border-color-lighter); }
.explorer-navigation { flex: none; gap: 4px; }
.explorer-navigation .el-button { width: 28px; padding: 0; }
.explorer-breadcrumb { display: flex; align-items: center; gap: 4px; flex: 1; min-width: 0; overflow-x: auto; padding: 3px 8px; border: 1px solid var(--el-border-color-lighter); border-radius: 4px; }
.explorer-breadcrumb button { flex: none; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border: 0; border-radius: 3px; background: transparent; color: var(--el-text-color-regular); padding: 3px 6px; cursor: pointer; font-size: 12px; }
.explorer-breadcrumb button:hover { background: var(--el-color-primary-light-9); }
.explorer-path-icon { flex: none; color: #ca8a04; }
.explorer-path-divider { color: var(--el-text-color-placeholder); }
.material-directory-layout { display: grid; grid-template-columns: 180px minmax(0, 1fr); min-height: 200px; }
.material-folder-tree { padding: 8px 4px; border-right: 1px solid var(--el-border-color-lighter); max-height: 360px; min-width: 0; overflow: auto; }
.explorer-tree-node { display: flex; align-items: center; gap: 5px; min-width: 0; font-size: 12px; }
.explorer-tree-node > span { overflow: hidden; text-overflow: ellipsis; }
.explorer-folder-icon { color: #d9a428; flex: none; font-size: 18px; }
.explorer-pending-dot { flex: none; width: 5px; height: 5px; border-radius: 50%; background: var(--el-color-warning); }
.material-directory-files { position: relative; min-width: 0; min-height: 200px; }
.explorer-table-scroll { max-height: 360px; overflow: auto; min-height: 200px; }
.explorer-table { width: 100%; border-collapse: collapse; table-layout: auto; font-size: 12px; }
.explorer-table th { position: sticky; top: 0; z-index: 1; text-align: left; color: var(--el-text-color-secondary); font-weight: 400; padding: 8px 10px; background: #fafbfc; border-bottom: 1px solid var(--el-border-color-lighter); white-space: nowrap; }
.explorer-table th + th { border-left: 1px solid var(--el-border-color-lighter); }
.explorer-table td { padding: 9px 10px; border-bottom: 1px solid #f1f5f9; }
.explorer-table tbody tr { cursor: default; outline-offset: -2px; }
.explorer-table tbody tr:hover { background: #f5f8fc; }
.explorer-table tbody tr.is-selected { background: var(--el-color-primary-light-9); }
.explorer-name { min-width: 140px; }
.explorer-name-content { display: flex; align-items: center; gap: 7px; }
.explorer-name-content > span { max-width: 280px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.explorer-name-content .el-tag { flex: none; font-size: 10px; }
.explorer-file-icon { color: #7892ad; font-size: 18px; flex: none; }
.explorer-modified { width: 130px; white-space: nowrap; color: var(--el-text-color-secondary); }
.explorer-type { width: 80px; white-space: nowrap; color: var(--el-text-color-secondary); }
.explorer-size { width: 65px; white-space: nowrap; text-align: right !important; color: var(--el-text-color-secondary); }
.explorer-more { width: 32px; white-space: nowrap; }
.explorer-name small { display: block; margin: 4px 0 0 25px; color: var(--el-text-color-secondary); white-space: normal; }
.explorer-name small.explorer-error { color: var(--el-color-danger); }
.explorer-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 32px 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.explorer-empty .el-icon { font-size: 30px; color: #d9a428; }
.explorer-empty small { color: var(--el-text-color-placeholder); }
.explorer-statusbar { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; padding: 7px 12px; background: #fafbfc; border-top: 1px solid var(--el-border-color-lighter); font-size: 11px; color: var(--el-text-color-secondary); }
.explorer-statusbar > span { overflow-wrap: anywhere; }
.explorer-drop-overlay { position: absolute; inset: 0; z-index: 3; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; border: 2px dashed var(--el-color-primary); background: rgb(239 246 255 / 95%); color: var(--el-color-primary); pointer-events: none; font-size: 13px; }
.explorer-drop-overlay .el-icon { font-size: 32px; }
.explorer-sr-only,.explorer-file-input { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 600px) {
  .explorer-desktop-action { display: none; }
  .explorer-mobile-action { display: inline-flex; }
  .explorer-commandbar,.explorer-addressbar { padding: 8px; }
  .explorer-addressbar { flex-wrap: wrap; }
  .explorer-breadcrumb { flex-basis: 100%; }
  .material-directory-layout { grid-template-columns: minmax(0, 1fr); }
  .material-folder-tree { display: none; max-height: 130px; border-right: 0; border-bottom: 1px solid var(--el-border-color-lighter); }
  .material-folder-tree.mobile-expanded { display: block; }
  .explorer-modified,.explorer-type { display: none; }
  .explorer-name-content > span { max-width: 150px; }
  .explorer-table td,.explorer-table th { padding: 8px 6px; }
}
</style>
