<template>
  <div class="annotation-office-route" v-loading="loading" element-loading-text="正在读取项目资料…">
    <AnnotationOfficeEditor v-if="request" :key="generation" standalone :editor-request="request" @close="finish" />
    <el-result v-else-if="error" icon="error" title="无法打开文档" :sub-title="error">
      <template #extra><el-button @click="returnToProject">返回项目</el-button><el-button type="primary" @click="load">重试</el-button></template>
    </el-result>
    <el-result v-else-if="completed" :icon="completed.saved ? 'success' : 'info'"
      :title="completed.saved ? '文件已保存' : '编辑已结束'"
      :sub-title="completed.saved ? '资料版本已更新，项目资料列表会自动刷新。' : '本次会话已关闭，未提交的修改已放弃。'">
      <template #extra><el-button @click="returnToProject">返回项目</el-button><el-button v-if="completed.saved" type="primary" @click="continueEditing">继续编辑</el-button></template>
    </el-result>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AnnotationOfficeEditor from '@/components/annotation/AnnotationOfficeEditor.vue'
import * as api from '@/api/annotationMaterials'
import { folderPath } from '@/utils/annotationMaterialFolders'
import { onlineEditBlocker, onlineEditKind } from '@/utils/materialDocument'
import { hasPermission } from '@/utils/permission'

const route = useRoute(), router = useRouter()
const request = ref(null), loading = ref(false), error = ref(''), completed = ref(null), generation = ref(0)
let controller
const text = value => typeof value === 'string' ? value : ''

async function load() {
  controller?.abort()
  const current = ++generation.value
  controller = new AbortController()
  const signal = controller.signal
  request.value = null; completed.value = null; error.value = ''; loading.value = true
  try {
    const projectId = text(route.query.project), fileId = text(route.query.file), kind = text(route.query.create), folderId = text(route.query.folder) || null
    if (!projectId || Boolean(fileId) === Boolean(kind)) throw new Error('文档地址不完整，请从项目资料重新打开')
    const rows = await api.listMaterials(projectId, { signal })
    let next
    if (fileId) {
      const file = rows.find(row => row.file_id === fileId && row.category === 'project')
      if (!file) throw new Error('文件不存在或已被移除，请返回项目刷新资料')
      if (!['docx', 'xlsx'].includes(onlineEditKind(file.original_name))) throw new Error('独立页面支持 Word（.docx）和 Excel（.xlsx）')
      const reason = onlineEditBlocker(file)
      if (reason) throw new Error(reason)
      next = { projectId, file }
      document.title = `${file.original_name} - 在线编辑`
    } else {
      if (!['docx', 'xlsx'].includes(kind) || !hasPermission('projects:write')) throw new Error('不支持此文档类型或没有新建权限')
      const folders = await api.listMaterialFolders(projectId, { signal })
      if (folderId && !folders.some(folder => folder.id === folderId)) throw new Error('文件夹不存在或尚未保存，请返回项目确认')
      next = { projectId, create: { kind, folderId, folderName: folderPath(folders, folderId),
        siblingNames: rows.filter(row => row.category === 'project' && (row.folder_id || null) === folderId).map(row => row.original_name) } }
    }
    if (!signal.aborted && current === generation.value) request.value = next
  } catch (failure) { if (!signal.aborted && current === generation.value) error.value = failure.detail || failure.message || '读取项目资料失败，请重试' }
  finally { if (current === generation.value) loading.value = false }
}
function finish(result) { request.value = null; completed.value = result }
function returnToProject() {
  // 用户可保留编辑结果页，也可以回到项目；关闭浏览器标签页同样会释放会话。
  void router.replace({ path: '/annotation-details', query: { projectId: text(route.query.project) } })
}
async function continueEditing() {
  if (route.query.file) { await load(); return }
  loading.value = true
  try {
    const rows = await api.listMaterials(text(route.query.project))
    const file = rows.find(row => row.id === completed.value.versionId)
    if (!file) throw new Error('无法定位已保存文件，请返回项目资料打开')
    await router.replace({ path: '/annotation-office', query: { project: text(route.query.project), file: file.file_id } })
  } catch (failure) { error.value = failure.detail || failure.message || '读取项目资料失败' }
  finally { loading.value = false }
}
watch(() => route.fullPath, load, { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<style scoped>
.annotation-office-route { width: 100%; height: 100%; min-height: 0; overflow: hidden; background: #fff; }
.annotation-office-route > .el-result { height: 100%; box-sizing: border-box; overflow-y: auto; }
</style>
