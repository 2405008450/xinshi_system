<template>
  <DraggableFormDialog :model-value="modelValue" title="子订单结构" append-to-body destroy-on-close
    class="sub-order-structure-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh"
    @update:model-value="$emit('update:modelValue', $event)">
    <p v-if="loading" role="status">正在加载子订单结构…</p>
    <template v-else-if="error">
      <el-alert :title="error" type="error" :closable="false" show-icon />
      <el-button link type="primary" @click="load">重试</el-button>
    </template>
    <template v-else-if="project">
      <p v-if="!project.subOrders?.length" class="structure-summary">该母订单暂无子订单</p>
      <el-tree class="structure-tree" :data="tree" node-key="number" :props="{ label: 'number' }" :indent="0"
        :default-expanded-keys="expandedKeys" :current-node-key="selectedOrderNo || project.orderNo"
        highlight-current :expand-on-click-node="false">
        <template #default="{ data }">
          <div class="structure-order">
            <span class="structure-number">{{ data.number }}</span>
            <span class="structure-name">{{ data.name || '-' }}</span>
            <el-tag :type="data.source.type" size="small">{{ data.source.label }}</el-tag>
            <el-tag v-if="data.missingParent" type="warning" size="small">上级订单缺失</el-tag>
            <span v-if="data.direction" class="structure-direction">{{ data.direction }}</span>
          </div>
        </template>
      </el-tree>
    </template>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getProject } from '@/api/projects'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { splitLanguagePairs } from '@/utils/languagePair'

const props = defineProps({ modelValue: Boolean, projectId: String, selectedOrderNo: String })
defineEmits(['update:modelValue'])

const project = ref(null)
const loading = ref(false)
const error = ref('')
let request

async function load() {
  request?.abort()
  const controller = new AbortController()
  request = controller
  project.value = null
  loading.value = true
  error.value = ''
  try {
    const result = await getProject(props.projectId, { signal: controller.signal })
    if (!controller.signal.aborted) project.value = result
  } catch (cause) {
    if (!controller.signal.aborted) error.value = getLocalizedErrorMessage(cause, '加载子订单结构失败')
  } finally {
    if (request === controller) loading.value = false
  }
}

watch(() => [props.modelValue, props.projectId], ([open, id], _, onCleanup) => {
  if (open && id) {
    load()
    onCleanup(() => request?.abort())
  }
}, { immediate: true })

const parentNumber = number => number.slice(0, number.lastIndexOf('.'))
const normalizedPath = value => String(value || '').trim().replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
const normalizedName = value => String(value || '').trim().toLowerCase()
const normalizedDirections = value => splitLanguagePairs(value).map(pair => pair.replace(/\s+/g, '').toLowerCase())
const numberSort = new Intl.Collator('zh-CN', { numeric: true })

function sourceOf(row, parent, root, importedRoots) {
  if (row.folderInfo) return { label: '导入文件夹', type: 'warning' }
  if (row.originalProjectInformation || root.motherSplitReview?.firstSubOrderId === row.id) {
    return { label: '母订单原文件', type: 'info' }
  }
  const path = normalizedPath(row.networkFilePath)
  const parentPath = normalizedPath(parent?.networkFilePath)
  const parentName = parent === root ? root.sourceFileName || root.projectName : parent?.subProjectName
  const parentDirections = normalizedDirections(parent?.languagePair)
  const directions = normalizedDirections(row.languagePair)
  const sameFile = normalizedName(row.subProjectName) === normalizedName(parentName)
  const samePath = path && path === parentPath
  const sharesPath = path === '同上一级订单'
  if (row.subOrderNo.split('.').length === 6 || (
    parent && !parent.folderInfo && !(parent === root && root.folderRoot)
    && parentDirections.length > 1 && directions.length === 1 && parentDirections.includes(directions[0])
    && (sharesPath || (sameFile && samePath))
  )) return { label: '按翻译方向生成', type: 'primary' }

  const fileDirectory = path.slice(0, path.lastIndexOf('/'))
  const fileName = path.slice(path.lastIndexOf('/') + 1)
  const recordedFile = parent?.folderInfo?.files?.some(name => normalizedName(name) === fileName)
  if (path.includes('/') && (
    (parent?.folderInfo && (recordedFile || fileDirectory === parentPath))
    || (parent === root && importedRoots.has(fileDirectory))
  )) return { label: '文件夹内文件', type: 'success' }
  return { label: '来源未记录', type: 'info' }
}

const tree = computed(() => {
  const root = project.value
  if (!root) return []
  const rows = [...(root.subOrders || [])].sort((a, b) => numberSort.compare(a.subOrderNo, b.subOrderNo))
  const importedRoots = new Set(rows.map(row => normalizedPath(row.folderInfo?.rootPath)).filter(Boolean))
  if (root.folderRoot && root.networkFilePath) importedRoots.add(normalizedPath(root.networkFilePath))
  const rootNode = {
    number: root.orderNo, name: root.projectName, direction: root.languagePair,
    source: { label: '母订单', type: 'info' }, children: [],
  }
  const byNumber = new Map(rows.map(row => [row.subOrderNo, row]))
  const nodes = new Map([[root.orderNo, rootNode]])
  for (const row of rows) {
    const number = row.subOrderNo
    const parentNo = parentNumber(number)
    const parent = parentNo === root.orderNo ? root : byNumber.get(parentNo)
    const node = {
      number, name: row.subProjectName, direction: row.languagePair,
      source: sourceOf(row, parent, root, importedRoots), missingParent: !parent, children: [],
    }
    nodes.set(number, node)
  }
  for (const row of rows) {
    const parent = nodes.get(parentNumber(row.subOrderNo)) || rootNode
    parent.children.push(nodes.get(row.subOrderNo))
  }
  return [rootNode]
})

const expandedKeys = computed(() => {
  if (!tree.value.length) return []
  const [root] = tree.value
  const selectedParts = (props.selectedOrderNo || '').split('.')
  const selectedPath = selectedParts.map((_, index) => selectedParts.slice(0, index + 1).join('.'))
  return [root.number, ...root.children.map(child => child.number), ...selectedPath]
})
</script>

<style>
.sub-order-structure-dialog { display: flex; flex-direction: column; max-height: 90vh; }
.sub-order-structure-dialog > .el-dialog__body { min-height: 0; overflow: auto; }
.sub-order-structure-dialog > .el-dialog__header,
.sub-order-structure-dialog > .el-dialog__footer { flex-shrink: 0; }
.sub-order-structure-dialog .el-tree-node__content { min-height: 34px; height: auto; }
.structure-tree {
  --structure-indent: 24px;
  --structure-branch: 12px;
  --structure-line: var(--el-text-color-placeholder);
}
.structure-tree .el-tree-node__children { padding-inline-start: var(--structure-indent); }
.structure-tree .el-tree-node__children > .el-tree-node,
.structure-tree .el-tree-node__content { position: relative; }
.structure-tree .el-tree-node__children > .el-tree-node:not(:last-child)::before,
.structure-tree .el-tree-node__children > .el-tree-node > .el-tree-node__content::before,
.structure-tree .el-tree-node.is-expanded > .el-tree-node__content:has(.el-tree-node__expand-icon:not(.is-leaf))::after {
  content: '';
  position: absolute;
  border-inline-start: 1px solid var(--structure-line);
  pointer-events: none;
}
.structure-tree .el-tree-node__children > .el-tree-node:not(:last-child)::before {
  inset-block: 0;
  inset-inline-start: calc(-1 * var(--structure-branch));
}
.structure-tree .el-tree-node__children > .el-tree-node > .el-tree-node__content::before {
  inset-block: 0 50%;
  inset-inline-start: calc(-1 * var(--structure-branch));
  width: var(--structure-branch);
  border-block-end: 1px solid var(--structure-line);
}
.structure-tree .el-tree-node.is-expanded > .el-tree-node__content:has(.el-tree-node__expand-icon:not(.is-leaf))::after {
  inset-block: calc(50% + 6px) 0;
  inset-inline-start: var(--structure-branch);
}
.sub-order-structure-dialog .structure-order { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 10px; min-width: 0; padding: 4px 8px 4px 0; white-space: normal; overflow-wrap: anywhere; }
.sub-order-structure-dialog .structure-number { font-variant-numeric: tabular-nums; color: var(--el-text-color-primary); }
.sub-order-structure-dialog .structure-summary,
.sub-order-structure-dialog .structure-direction { color: var(--el-text-color-secondary); }
</style>
