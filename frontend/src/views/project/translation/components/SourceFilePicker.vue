<template>
  <DraggableFormDialog v-model="visible" title="选择原文文件" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body>
    <p class="source-path">{{ path }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-else :title="multiple ? '单选回填当前订单；多选按文件创建子订单，保存项目后生效。每次最多选择100个文件。' : '请选择当前订单对应的一个文件。'" type="info" :closable="false" />
    <div class="picker-toolbar">
      <el-input v-model="keyword" placeholder="搜索文件名" clearable />
      <el-button v-if="multiple" @click="selectAll">全选可用文件</el-button>
      <el-button @click="table?.clearSelection()">清空</el-button>
      <span>已选 {{ selected.length }} 个</span>
    </div>
    <el-table ref="table" v-loading="loading" :data="filtered" row-key="path" border max-height="360" @selection-change="selected = $event">
      <el-table-column type="selection" reserve-selection :selectable="selectable" width="48" />
      <el-table-column prop="name" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column prop="path" label="完整路径" min-width="280" show-overflow-tooltip />
      <el-table-column prop="reason" label="不可选原因" min-width="180" />
    </el-table>
    <p v-if="selected.length > 1">保存后将新增 {{ selected.length }} 个子订单。原订单及已有安排、进度和结算信息保留，新子订单不复制执行数据。</p>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="loading || !selected.length || selected.length > 100" @click="confirm">确认选择（{{ selected.length }}）</el-button>
    </template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { readSubOrderSourceFiles } from '@/api/subOrders'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
const props = defineProps({ modelValue: Boolean, path: String, multiple: Boolean, existing: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue', 'confirm'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const table = ref(), rows = ref([]), selected = ref([]), keyword = ref(''), loading = ref(false), error = ref('')
let controller, requestId = 0
const filtered = computed(() => rows.value.filter(row => row.name.toLowerCase().includes(keyword.value.trim().toLowerCase())))
const selectable = row => row.selectable && (props.multiple || !selected.value.length || selected.value.some(item => item.path === row.path))
function selectAll() { filtered.value.filter(selectable).forEach(row => table.value?.toggleRowSelection(row, true)) }
function confirm() { emit('confirm', selected.value.map(({ name, path }) => ({ name, path }))); visible.value = false }
watch(() => [props.modelValue, props.path], async ([open]) => {
  controller?.abort()
  const id = ++requestId
  if (!open) return
  controller = new AbortController()
  rows.value = []; selected.value = []; keyword.value = ''; error.value = ''; loading.value = true
  table.value?.clearSelection()
  try {
    const result = await readSubOrderSourceFiles(props.path, controller.signal)
    if (id !== requestId) return
    rows.value = result.files.map(row => {
      const duplicate = props.existing.some(item => String(item.subProjectName || item.sub_project_name || '').toLowerCase() === row.name.toLowerCase())
      return duplicate ? { ...row, selectable: false, reason: '已有同名子订单，请核对后选择其他文件' } : row
    })
    await nextTick()
    if (rows.value.length === 1 && rows.value[0].selectable) table.value?.toggleRowSelection(rows.value[0], true)
  } catch (err) {
    if (id === requestId) error.value = getLocalizedErrorMessage(err, '读取失败，请检查路径及共享目录权限')
  } finally { if (id === requestId) loading.value = false }
})
onBeforeUnmount(() => { requestId++; controller?.abort() })
</script>
<style scoped>
.source-path { overflow-wrap: anywhere; }
.picker-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0; }
.picker-toolbar .el-input { width: min(280px, 100%); }
</style>
