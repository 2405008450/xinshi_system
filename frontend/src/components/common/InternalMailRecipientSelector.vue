<template>
  <div class="internal-recipient-selector" :class="{ 'has-selection': selectedIds.length }">
    <div class="recipient-summary">
      <div class="summary-toolbar">
        <div class="summary-copy">
          <span class="selected-badge">已选 {{ selectedIds.length }} 人</span>
          <span class="summary-hint">已选成员会在下方完整显示</span>
        </div>
        <el-popover
          v-model:visible="panelVisible"
          placement="bottom-start"
          trigger="click"
          :width="560"
          :show-arrow="false"
          :popper-style="popperStyle"
          :popper-class="popperClass"
        >
          <template #reference>
            <el-button type="primary" plain>
              {{ selectedIds.length ? '管理成员' : '选择成员' }}
            </el-button>
          </template>

          <div class="recipient-panel">
            <div class="panel-header">
              <div
                class="panel-drag-handle"
                title="按住并拖动窗口"
                @pointerdown="startPanelDrag"
              >
                <div class="panel-title">选择内部成员</div>
                <div class="panel-subtitle">
                  已选 {{ selectedIds.length }} 人 · 按住标题栏拖动 · 拖拽右下角缩放
                </div>
              </div>
              <el-button link type="primary" @click="panelVisible = false">完成</el-button>
            </div>

            <div class="panel-search">
              <el-input
                v-model="searchKeyword"
                clearable
                placeholder="搜索姓名、账号、邮箱或部门"
              />
            </div>

            <div class="member-filters">
              <div v-if="mailGroups.length" class="filter-row" role="group" aria-label="按邮件组筛选">
                <span class="filter-label">邮件组</span>
                <div class="filter-chips">
                  <button
                    v-for="group in mailGroups"
                    :key="group.id"
                    type="button"
                    class="department-chip mail-group-chip"
                    :class="{ active: activeMailGroup === group.id }"
                    :title="`筛选“${group.name}”成员后可全选当前结果`"
                    @click="selectMailGroup(group.id)"
                  >
                    {{ group.name }} {{ group.userIds.length }}
                  </button>
                </div>
              </div>
              <div class="filter-row" role="group" aria-label="按部门筛选">
                <span class="filter-label">部门</span>
                <div class="filter-chips">
                  <button
                    type="button"
                    class="department-chip"
                    :class="{ active: !activeDepartment && !activeMailGroup }"
                    @click="showAllUsers"
                  >
                    全部成员 {{ availableUsers.length }}
                  </button>
                  <button
                    v-for="group in departmentGroups"
                    :key="group.key"
                    type="button"
                    class="department-chip"
                    :class="{ active: activeDepartment === group.key && !activeMailGroup }"
                    @click="selectDepartment(group.key)"
                  >
                    {{ group.label }} {{ group.users.length }}
                  </button>
                </div>
              </div>
            </div>

            <div class="panel-actions">
              <span>当前显示 {{ filteredUsers.length }} 人</span>
              <div class="panel-action-buttons">
                <el-button
                  link
                  type="primary"
                  :disabled="!filteredUsers.length || allFilteredSelected"
                  @click="selectFiltered"
                >
                  全选当前结果
                </el-button>
                <el-button
                  link
                  :disabled="!hasFilteredSelection"
                  @click="clearFiltered"
                >
                  取消当前结果
                </el-button>
                <el-button v-if="selectedIds.length" link type="danger" @click="clearSelected">
                  清空全部
                </el-button>
              </div>
            </div>

            <div v-if="filteredUsers.length" class="user-grid">
              <el-checkbox
                v-for="user in filteredUsers"
                :key="user.id"
                class="user-card"
                :class="{ selected: selectedIdSet.has(user.id) }"
                :model-value="selectedIdSet.has(user.id)"
                @change="setUserSelected(user.id, $event)"
              >
                <span class="user-avatar">{{ userInitial(user) }}</span>
                <span class="user-details">
                  <span class="user-name-row">
                    <strong>{{ displayName(user) }}</strong>
                    <small>{{ departmentLabel(user) }}</small>
                  </span>
                  <span class="user-email">{{ user.email }}</span>
                </span>
              </el-checkbox>
            </div>
            <el-empty v-else :image-size="56" description="没有找到匹配的成员" />
          </div>
        </el-popover>
      </div>

      <div v-if="selectedUsers.length" class="selected-user-list" aria-live="polite">
        <el-tag
          v-for="user in selectedUsers"
          :key="user.id"
          closable
          effect="light"
          :title="userLabel(user)"
          @close="removeUser(user.id)"
        >
          {{ displayName(user) }}
        </el-tag>
      </div>
      <div v-else class="empty-selection">{{ placeholder }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  excludedUserIds: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择内部用户' },
})
const emit = defineEmits(['update:modelValue'])

const panelVisible = ref(false)
const searchKeyword = ref('')
const activeDepartment = ref('')
const activeMailGroup = ref('')
const dragPosition = ref(null)
let dragContext = null
let previousBodyUserSelect = ''

const popperClass = computed(() => `internal-recipient-popper${dragPosition.value ? ' is-dragged' : ''}`)
const popperStyle = computed(() => ({
  maxWidth: 'calc(100vw - 32px)',
  padding: '0',
  ...(dragPosition.value
    ? {
        '--recipient-panel-left': `${dragPosition.value.left}px`,
        '--recipient-panel-top': `${dragPosition.value.top}px`,
      }
    : {}),
}))

const excludedSet = computed(() => new Set(props.excludedUserIds || []))
const availableUsers = computed(() => (props.users || [])
  .filter((user) => user?.id && user.is_active && user.email && !excludedSet.value.has(user.id))
  .sort((left, right) => userLabel(left).localeCompare(userLabel(right), 'zh-CN')))
const availableIdSet = computed(() => new Set(availableUsers.value.map((user) => user.id)))
const mailGroups = computed(() => (props.groups || [])
  .filter((group) => group?.id && group.is_active !== false)
  .map((group) => ({
    id: group.id,
    name: group.name || '未命名邮件组',
    userIds: [...new Set(group.user_ids || [])].filter((id) => availableIdSet.value.has(id)),
  }))
  .filter((group) => group.userIds.length)
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')))
const selectedIds = computed(() => [...new Set(props.modelValue || [])].filter((id) => availableIdSet.value.has(id)))
const selectedIdSet = computed(() => new Set(selectedIds.value))
const selectedUsers = computed(() => {
  const order = new Map(selectedIds.value.map((id, index) => [id, index]))
  return availableUsers.value
    .filter((user) => selectedIdSet.value.has(user.id))
    .sort((left, right) => order.get(left.id) - order.get(right.id))
})
const departmentGroups = computed(() => {
  const grouped = new Map()
  availableUsers.value.forEach((user) => {
    const label = departmentLabel(user)
    if (!grouped.has(label)) grouped.set(label, [])
    grouped.get(label).push(user)
  })
  return [...grouped.entries()]
    .sort(([left], [right]) => left.localeCompare(right, 'zh-CN'))
    .map(([label, users]) => ({ key: label, label, users }))
})
const filteredUsers = computed(() => {
  const keyword = searchKeyword.value.trim().toLocaleLowerCase('zh-CN')
  const mailGroup = activeMailGroup.value
    ? mailGroups.value.find((group) => group.id === activeMailGroup.value)
    : null
  const mailGroupUserIds = mailGroup ? new Set(mailGroup.userIds) : null
  return availableUsers.value.filter((user) => {
    if (mailGroupUserIds && !mailGroupUserIds.has(user.id)) return false
    if (activeDepartment.value && departmentLabel(user) !== activeDepartment.value) return false
    if (!keyword) return true
    return [user.full_name, user.username, user.email, user.department]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase('zh-CN').includes(keyword))
  })
})
const allFilteredSelected = computed(() => filteredUsers.value.length > 0
  && filteredUsers.value.every((user) => selectedIdSet.value.has(user.id)))
const hasFilteredSelection = computed(() => filteredUsers.value.some((user) => selectedIdSet.value.has(user.id)))

const displayName = (user) => user.full_name || user.username || '未命名成员'
const departmentLabel = (user) => String(user.department || '').trim() || '未设置部门'
const userLabel = (user) => `${displayName(user)} · ${user.email}`
const userInitial = (user) => Array.from(displayName(user))[0] || '员'
const updateSelected = (value) => emit('update:modelValue', [...new Set(value || [])].filter((id) => availableIdSet.value.has(id)))
const setUserSelected = (userId, checked) => {
  const next = new Set(selectedIds.value)
  if (checked) next.add(userId)
  else next.delete(userId)
  updateSelected([...next])
}
const removeUser = (userId) => updateSelected(selectedIds.value.filter((id) => id !== userId))
const selectFiltered = () => updateSelected([...selectedIds.value, ...filteredUsers.value.map((user) => user.id)])
const clearFiltered = () => {
  const filteredIdSet = new Set(filteredUsers.value.map((user) => user.id))
  updateSelected(selectedIds.value.filter((id) => !filteredIdSet.has(id)))
}
const clearSelected = () => emit('update:modelValue', [])
const showAllUsers = () => {
  activeMailGroup.value = ''
  activeDepartment.value = ''
}
const selectMailGroup = (groupId) => {
  activeMailGroup.value = activeMailGroup.value === groupId ? '' : groupId
  activeDepartment.value = ''
}
const selectDepartment = (department) => {
  activeDepartment.value = activeDepartment.value === department ? '' : department
  activeMailGroup.value = ''
}

const clampDragPosition = (left, top, width, height) => ({
  left: Math.min(Math.max(8, left), Math.max(8, window.innerWidth - width - 8)),
  top: Math.min(Math.max(8, top), Math.max(8, window.innerHeight - height - 8)),
})
const applyDragPosition = (position) => {
  if (!dragContext?.popper) return
  dragContext.popper.style.setProperty('--recipient-panel-left', `${position.left}px`)
  dragContext.popper.style.setProperty('--recipient-panel-top', `${position.top}px`)
}
const movePanel = (event) => {
  if (!dragContext) return
  const position = clampDragPosition(
    dragContext.originLeft + event.clientX - dragContext.startX,
    dragContext.originTop + event.clientY - dragContext.startY,
    dragContext.width,
    dragContext.height,
  )
  dragPosition.value = position
  applyDragPosition(position)
}
const stopPanelDrag = () => {
  if (!dragContext) return
  document.removeEventListener('pointermove', movePanel)
  document.removeEventListener('pointerup', stopPanelDrag)
  document.removeEventListener('pointercancel', stopPanelDrag)
  document.body.style.userSelect = previousBodyUserSelect
  dragContext = null
}
const startPanelDrag = (event) => {
  if (event.button !== 0) return
  const popper = event.currentTarget.closest('.el-popper')
  if (!popper) return
  event.preventDefault()
  const rect = popper.getBoundingClientRect()
  const initialPosition = clampDragPosition(rect.left, rect.top, rect.width, rect.height)
  dragPosition.value = initialPosition
  popper.classList.add('is-dragged')
  popper.style.setProperty('--recipient-panel-left', `${initialPosition.left}px`)
  popper.style.setProperty('--recipient-panel-top', `${initialPosition.top}px`)
  dragContext = {
    popper,
    startX: event.clientX,
    startY: event.clientY,
    originLeft: initialPosition.left,
    originTop: initialPosition.top,
    width: rect.width,
    height: rect.height,
  }
  previousBodyUserSelect = document.body.style.userSelect
  document.body.style.userSelect = 'none'
  document.addEventListener('pointermove', movePanel)
  document.addEventListener('pointerup', stopPanelDrag)
  document.addEventListener('pointercancel', stopPanelDrag)
}

watch(
  () => [props.excludedUserIds, props.users, props.groups],
  () => {
    const normalized = selectedIds.value
    if (normalized.length !== (props.modelValue || []).length) emit('update:modelValue', normalized)
    if (activeDepartment.value && !departmentGroups.value.some((group) => group.key === activeDepartment.value)) {
      activeDepartment.value = ''
    }
    if (activeMailGroup.value && !mailGroups.value.some((group) => group.id === activeMailGroup.value)) {
      activeMailGroup.value = ''
    }
  },
  { deep: true },
)

watch(panelVisible, (value) => {
  if (!value) {
    searchKeyword.value = ''
    activeDepartment.value = ''
    activeMailGroup.value = ''
  }
})

onBeforeUnmount(stopPanelDrag)
</script>

<style scoped>
.internal-recipient-selector { width: 100%; }
.recipient-summary {
  min-height: 78px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.has-selection .recipient-summary {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-9);
}
.summary-toolbar, .summary-copy, .panel-header, .panel-actions, .panel-action-buttons, .user-name-row {
  display: flex;
  align-items: center;
}
.summary-toolbar, .panel-header, .panel-actions { justify-content: space-between; gap: 12px; }
.summary-copy { gap: 8px; min-width: 0; }
.selected-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}
.summary-hint { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.selected-user-list {
  display: flex;
  align-content: flex-start;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 86px;
  margin-top: 10px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.empty-selection { margin-top: 10px; color: var(--el-text-color-placeholder); font-size: 13px; }

.recipient-panel {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-radius: inherit;
}
.recipient-panel::after {
  position: absolute;
  right: 5px;
  bottom: 5px;
  width: 12px;
  height: 12px;
  border-right: 2px solid var(--el-border-color);
  border-bottom: 2px solid var(--el-border-color);
  border-radius: 0 0 3px;
  content: '';
  opacity: 0.9;
  pointer-events: none;
}
.panel-header { padding: 0 18px 0 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.panel-drag-handle {
  flex: 1;
  min-width: 0;
  padding: 16px 18px 12px;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.panel-drag-handle:active { cursor: grabbing; }
.panel-title { color: var(--el-text-color-primary); font-size: 16px; font-weight: 700; line-height: 1.4; }
.panel-subtitle { margin-top: 2px; color: var(--el-text-color-secondary); font-size: 12px; }
.panel-header, .panel-search, .member-filters, .panel-actions { flex-shrink: 0; }
.panel-search { padding: 12px 16px 8px; }
.member-filters { display: flex; flex-direction: column; gap: 8px; padding: 0 16px 10px; }
.filter-row { display: flex; align-items: flex-start; gap: 9px; }
.filter-label { flex: 0 0 38px; padding-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }
.filter-chips { display: flex; flex: 1; flex-wrap: wrap; gap: 7px; min-width: 0; }
.department-chip {
  min-height: 28px;
  padding: 3px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 999px;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-blank);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  transition: all 0.2s;
}
.department-chip:hover { color: var(--el-color-primary); border-color: var(--el-color-primary-light-5); }
.department-chip.active { color: var(--el-color-primary); border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); font-weight: 600; }
.mail-group-chip { border-style: dashed; }
.mail-group-chip.active { border-style: solid; }
.panel-actions { min-height: 38px; padding: 0 18px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); font-size: 12px; }
.panel-action-buttons { flex-wrap: wrap; justify-content: flex-end; gap: 0 10px; }
.panel-action-buttons :deep(.el-button + .el-button) { margin-left: 0; }
.user-grid {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  min-height: 0;
  padding: 10px 16px 16px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.user-card {
  width: 100%;
  height: auto;
  min-height: 58px;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  transition: border-color 0.2s, background-color 0.2s, box-shadow 0.2s;
}
.user-card:hover { border-color: var(--el-color-primary-light-5); }
.user-card.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); box-shadow: inset 3px 0 0 var(--el-color-primary); }
.user-card :deep(.el-checkbox__label) { display: flex; align-items: center; min-width: 0; width: 100%; padding-left: 9px; }
.user-avatar {
  display: inline-flex;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  margin-right: 9px;
  border-radius: 50%;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-8);
  font-size: 14px;
  font-weight: 700;
}
.user-details { display: flex; min-width: 0; flex: 1; flex-direction: column; line-height: 1.45; }
.user-name-row { min-width: 0; gap: 7px; }
.user-name-row strong { overflow: hidden; color: var(--el-text-color-primary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.user-name-row small { flex-shrink: 0; max-width: 82px; overflow: hidden; color: var(--el-text-color-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.user-email { overflow: hidden; color: var(--el-text-color-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

:global(.internal-recipient-popper) {
  box-sizing: border-box;
  height: min(500px, calc(100vh - 32px));
  min-width: min(460px, calc(100vw - 16px));
  min-height: min(390px, calc(100vh - 16px));
  max-width: calc(100vw - 16px) !important;
  max-height: calc(100vh - 16px);
  overflow: hidden !important;
  resize: both;
  border-radius: var(--el-dialog-border-radius, var(--el-border-radius-base)) !important;
}

:global(.internal-recipient-popper.is-dragged) {
  position: fixed !important;
  inset: auto !important;
  left: var(--recipient-panel-left) !important;
  top: var(--recipient-panel-top) !important;
  margin: 0 !important;
  transform: none !important;
}

@media (max-width: 720px) {
  .summary-hint { display: none; }
  .user-grid { grid-template-columns: 1fr; }
  :global(.internal-recipient-popper) { min-width: min(360px, calc(100vw - 16px)); }
  .panel-actions { align-items: flex-start; flex-direction: column; padding-top: 7px; padding-bottom: 7px; }
  .panel-action-buttons { justify-content: flex-start; }
}
</style>
