<template>
  <DraggableFormDialog
    v-model="visible"
    title="标注须知栏目管理"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    class="annotation-notice-manager-dialog"
    :close-on-click-modal="false"
  >
    <div class="notice-manager-toolbar">
      <el-button type="primary" :icon="Plus" @click="openCreate(null)">新增一级栏目</el-button>
      <el-button :disabled="!selected || selected.parentId" @click="openCreate(selected?.id)">新增二级栏目</el-button>
      <span>可拖拽调整同级顺序，或将无子栏目的栏目移动到其他一级栏目。</span>
    </div>
    <div class="notice-manager-layout" v-loading="savingOrder">
      <div class="notice-manager-tree">
        <el-tree
          :data="localTree"
          node-key="id"
          default-expand-all
          draggable
          highlight-current
          :allow-drop="allowDrop"
          @node-click="selectSection"
          @node-drop="saveOrder"
        >
          <template #default="{ data }">
            <span class="notice-manager-node">
              <span>{{ data.displayTitle }}</span>
              <el-tag v-if="!data.hasContent" size="small" effect="plain">仅分组</el-tag>
            </span>
          </template>
        </el-tree>
      </div>
      <div class="notice-manager-editor">
        <template v-if="selected">
          <h3>编辑栏目</h3>
          <AppForm ref="editFormRef" :model="editForm" :rules="rules" label-width="92px">
            <el-form-item label="栏目名称" prop="title">
              <el-input v-model="editForm.title" maxlength="100" show-word-limit />
            </el-form-item>
            <el-form-item label="栏目层级">
              <span>{{ selected.parentId ? '二级栏目' : '一级栏目' }}</span>
            </el-form-item>
            <el-form-item label="正文内容">
              <el-switch v-model="editForm.hasContent" active-text="允许编辑正文" />
            </el-form-item>
          </AppForm>
          <div class="notice-manager-editor__actions">
            <el-button type="danger" plain :icon="Delete" @click="removeSelected">删除栏目</el-button>
            <el-button type="primary" :loading="savingEdit" @click="saveEdit">保存修改</el-button>
          </div>
        </template>
        <el-empty v-else description="请选择需要编辑的栏目" :image-size="80" />
      </div>
    </div>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog
    v-model="createVisible"
    :title="createForm.parentId ? '新增二级栏目' : '新增一级栏目'"
    width="min(520px, calc(100vw - 32px))"
    append-to-body
    :close-on-click-modal="false"
  >
    <AppForm ref="createFormRef" :model="createForm" :rules="rules" label-width="92px">
      <el-form-item label="栏目名称" prop="title">
        <el-input v-model="createForm.title" maxlength="100" show-word-limit placeholder="请输入栏目名称，无需填写字母编号" />
      </el-form-item>
      <el-form-item label="正文内容">
        <el-switch v-model="createForm.hasContent" active-text="允许编辑正文" />
      </el-form-item>
    </AppForm>
    <template #footer>
      <el-button @click="createVisible = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="createSection">确定</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createAnnotationNotice,
  deleteAnnotationNotice,
  reorderAnnotationNotices,
  updateAnnotationNoticeStructure
} from '@/api/annotationNotices'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  tree: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'refresh'])

const visible = ref(false)
const localTree = ref([])
const selected = ref(null)
const editFormRef = ref(null)
const createFormRef = ref(null)
const createVisible = ref(false)
const savingEdit = ref(false)
const savingOrder = ref(false)
const creating = ref(false)
const editForm = reactive({ title: '', hasContent: true })
const createForm = reactive({ title: '', parentId: null, hasContent: true })
const rules = { title: [{ required: true, message: '请输入栏目名称', trigger: 'blur' }] }

const cloneTree = value => JSON.parse(JSON.stringify(value || []))

watch(() => props.modelValue, value => { visible.value = value }, { immediate: true })
watch(visible, value => emit('update:modelValue', value))
watch(() => props.tree, value => { localTree.value = cloneTree(value) }, { immediate: true, deep: true })

function selectSection(data) {
  selected.value = data
  editForm.title = data.title
  editForm.hasContent = data.hasContent
}

function openCreate(parentId) {
  createForm.title = ''
  createForm.parentId = parentId || null
  createForm.hasContent = true
  createVisible.value = true
}

async function createSection() {
  try {
    await createFormRef.value?.validate()
  } catch {
    return
  }
  creating.value = true
  try {
    await createAnnotationNotice(createForm)
    createVisible.value = false
    ElMessage.success('栏目已新增')
    emit('refresh')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '栏目新增失败'))
  } finally {
    creating.value = false
  }
}

async function saveEdit() {
  try {
    await editFormRef.value?.validate()
  } catch {
    return
  }
  savingEdit.value = true
  try {
    const updated = await updateAnnotationNoticeStructure(selected.value.id, {
      ...editForm,
      expectedStructureUpdatedAt: selected.value.structureUpdatedAt
    })
    selected.value = updated
    editForm.title = updated.title
    editForm.hasContent = updated.hasContent
    ElMessage.success('栏目设置已保存')
    emit('refresh')
  } catch (error) {
    ElMessage.error(error?.response?.status === 409 ? '栏目已被其他用户修改，请刷新后重试' : getLocalizedErrorMessage(error, '栏目保存失败'))
  } finally {
    savingEdit.value = false
  }
}

async function removeSelected() {
  try {
    await ElMessageBox.confirm(`确定删除栏目“${selected.value.displayTitle}”吗？删除后将不再显示。`, '删除栏目', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteAnnotationNotice(selected.value.id)
    selected.value = null
    ElMessage.success('栏目已删除')
    emit('refresh')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '栏目删除失败'))
  }
}

function allowDrop(draggingNode, droppingNode, type) {
  const draggedHasChildren = Boolean(draggingNode.data.children?.length)
  if (type === 'inner') return !droppingNode.data.parentId && !draggedHasChildren
  return !(droppingNode.data.parentId && draggedHasChildren)
}

function collectPlacements(tree) {
  const placements = []
  tree.forEach((root, rootIndex) => {
    placements.push({ id: root.id, parentId: null, sortOrder: rootIndex + 1, expectedStructureUpdatedAt: root.structureUpdatedAt })
    ;(root.children || []).forEach((child, childIndex) => placements.push({
      id: child.id,
      parentId: root.id,
      sortOrder: childIndex + 1,
      expectedStructureUpdatedAt: child.structureUpdatedAt
    }))
  })
  return placements
}

async function saveOrder() {
  savingOrder.value = true
  try {
    localTree.value = await reorderAnnotationNotices(collectPlacements(localTree.value))
    selected.value = null
    ElMessage.success('栏目顺序已保存')
    emit('refresh')
  } catch (error) {
    localTree.value = cloneTree(props.tree)
    ElMessage.error(error?.response?.status === 409 ? '栏目已被其他用户调整，请刷新后重试' : getLocalizedErrorMessage(error, '栏目排序失败'))
  } finally {
    savingOrder.value = false
  }
}
</script>

<style scoped>
.notice-manager-toolbar{display:flex;align-items:center;gap:10px;margin-bottom:14px}.notice-manager-toolbar span{color:var(--el-text-color-secondary);font-size:12px}.notice-manager-layout{display:grid;grid-template-columns:minmax(280px,40%) minmax(0,1fr);min-height:420px;border:1px solid var(--el-border-color-lighter);border-radius:8px;overflow:hidden}.notice-manager-tree{padding:14px;border-right:1px solid var(--el-border-color-lighter);overflow:auto}.notice-manager-node{display:flex;align-items:center;gap:8px}.notice-manager-editor{padding:20px}.notice-manager-editor h3{margin:0 0 20px}.notice-manager-editor__actions{display:flex;justify-content:space-between;margin-top:24px}@media(max-width:768px){.notice-manager-toolbar{align-items:flex-start;flex-wrap:wrap}.notice-manager-layout{display:block}.notice-manager-tree{max-height:300px;border-right:0;border-bottom:1px solid var(--el-border-color-lighter)}}
</style>

<style>
.annotation-notice-manager-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.annotation-notice-manager-dialog .el-dialog__header,.annotation-notice-manager-dialog .el-dialog__footer{flex:none}.annotation-notice-manager-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-notice-manager-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
</style>
