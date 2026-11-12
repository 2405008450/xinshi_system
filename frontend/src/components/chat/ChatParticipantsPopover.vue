<template>
  <el-popover ref="participantsPopover" :append-to="participantsPopoverTarget" title="会话成员" :z-index="zIndex" @show="show" trigger="click" placement="bottom-end" :width="420" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }" popper-class="annotation-members-popover annotation-participants-popover">
    <template #reference><slot name="reference" /></template>
    <div v-loading="loading" class="participants-content">
      <div class="participants-section__heading"><span>已加入 · {{ members.length }} 人</span><el-button v-if="members.length > 6" link size="small" @click="membersExpanded = !membersExpanded">{{ membersExpanded ? '收起' : '展开全部' }}</el-button></div>
      <div class="participants-members">
        <el-button v-for="member in visibleMembers" :key="member.id" text size="small" :disabled="String(member.id) === String(currentUserId)" :title="member.name" @click="$emit('member-click', member)">{{ member.name }}<small v-if="String(member.id) === String(currentUserId)">我</small></el-button>
      </div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <section class="participants-invite">
        <div class="participants-section__heading"><span>添加成员</span><span class="participants-hint">勾选部门可整组添加</span></div>
        <el-input v-model="keyword" clearable placeholder="搜索姓名、账号或部门" aria-label="搜索可邀请成员" :disabled="inviting" />
        <div v-if="directoryError" class="participants-directory-error" role="alert">部门加载失败，仍可按姓名选人。<el-button link size="small" @click="loadDirectory">重试</el-button></div>
        <div v-loading="directoryLoading" class="participants-groups" aria-label="按部门选择成员">
          <section v-for="group in groups" :key="group.name" class="participants-department">
            <div class="participants-department__heading">
              <el-checkbox :model-value="groupSelected(group) === group.people.length" :indeterminate="groupSelected(group) > 0 && groupSelected(group) < group.people.length" :disabled="loading || inviting" :aria-label="`选择${group.name}全部人员`" @update:model-value="select(group.people, $event)">{{ group.name }}<span class="participants-hint">{{ group.people.length }} 人</span></el-checkbox>
              <el-button link size="small" :aria-label="`${isExpanded(group.name) ? '收起' : '展开'}${group.name}人员`" @click="toggleExpanded(group.name)">{{ isExpanded(group.name) ? '收起' : '展开' }}</el-button>
            </div>
            <div v-if="isExpanded(group.name)" class="participants-department__people">
              <el-checkbox v-for="person in group.people" :key="person.id" :model-value="selectedIds.has(String(person.id))" :disabled="loading || inviting" :title="person.name" @update:model-value="select([person], $event)">{{ person.name }}</el-checkbox>
            </div>
          </section>
          <p v-if="!groups.length && !loading && !directoryLoading" class="participants-empty">{{ keyword ? '没有匹配的人员或部门' : '暂无可邀请的人员' }}</p>
        </div>
      </section>
      <div class="participants-footer">
        <div class="participants-submit"><span>已选 {{ modelValue.length }} 人<el-button v-if="modelValue.length" link size="small" :disabled="inviting" @click="$emit('update:modelValue', [])">清空</el-button></span><el-button type="primary" size="small" :loading="inviting" :disabled="loading || !modelValue.length" @click="$emit('invite')">{{ modelValue.length ? `邀请 ${modelValue.length} 人` : '邀请加入' }}</el-button></div>
        <div class="participants-management"><span class="participants-hint" :title="showFollowNote ? '仅成员可查看和发言；取消关注只停止提醒，不会退出会话。' : '仅会话成员可查看和发言。'">仅成员可查看和发言</span><div><slot name="management" /></div></div>
      </div>
    </div>
  </el-popover>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api/index'
import { participantGroups, toggleParticipantSelection } from '@/utils/chatParticipantGroups'
const props = defineProps({
  members: { type: Array, default: () => [] },
  invitableUsers: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
  zIndex: { type: Number, default: 2110 },
  currentUserId: [String, Number],
  loading: Boolean, inviting: Boolean, error: String, showFollowNote: Boolean,
})
const emit = defineEmits(['update:modelValue', 'show', 'invite', 'member-click'])
const participantsPopover = ref(null), participantsPopoverTarget = ref('body')
const directory = ref({}), directoryLoading = ref(false), directoryError = ref(false)
const keyword = ref(''), expanded = ref(new Set()), membersExpanded = ref(false)
const visibleMembers = computed(() => membersExpanded.value ? props.members : props.members.slice(0, 6))
const groups = computed(() => participantGroups(props.invitableUsers, props.members, directory.value, keyword.value))
const selectedIds = computed(() => new Set(props.modelValue.map(String)))
const groupSelected = group => group.people.filter(person => selectedIds.value.has(String(person.id))).length
const isExpanded = name => keyword.value.trim() ? !expanded.value.has(name) : expanded.value.has(name)
watch(keyword, () => { expanded.value = new Set() })
// 部门展开和名册异步返回后重新定位，避免小屏幕底部操作超出视口。
watch([groups, expanded, membersExpanded, directoryLoading], async () => {
  await nextTick()
  participantsPopover.value?.popperRef?.popperInstanceRef?.update()
}, { flush: 'post' })
function toggleExpanded(name) {
  const next = new Set(expanded.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  expanded.value = next
}
function select(people, checked) {
  emit('update:modelValue', toggleParticipantSelection(props.modelValue, people, checked))
}
let controller
async function loadDirectory() {
  controller?.abort()
  const current = controller = new AbortController()
  directoryLoading.value = true; directoryError.value = false
  try {
    const data = await api.get('/departments/organization', { signal: current.signal })
    if (controller === current) directory.value = data
  } catch (e) {
    if (!current.signal.aborted) directoryError.value = true
  } finally { if (controller === current) directoryLoading.value = false }
}
async function show() {
  // 挂到更多菜单根节点，选人时不会被外层菜单判定为外部点击；兼容工具栏 Teleport。
  participantsPopoverTarget.value = participantsPopover.value?.popperRef?.triggerRef?.closest('.chat-header-more-popper') || 'body'
  keyword.value = ''; expanded.value = new Set(); membersExpanded.value = false
  emit('show')
  loadDirectory()
  await nextTick()
  participantsPopover.value?.popperRef?.popperInstanceRef?.update()
}
onBeforeUnmount(() => controller?.abort())
</script>
<style>
.el-popover.annotation-participants-popover{max-width:calc(100vw - 32px)!important;max-height:calc(100vh - 32px);padding:14px 16px;border-radius:10px;box-shadow:var(--shadow-dropdown)}
.annotation-participants-popover .app-window-popover__header{min-height:32px;padding-bottom:6px}
.annotation-participants-popover .app-window-popover__title{font-size:15px;font-weight:600}
.annotation-participants-popover .app-window-popover__body{padding-top:10px}
.annotation-participants-popover .participants-section__heading{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;margin-bottom:6px}
.annotation-participants-popover .participants-hint{font-size:12px;font-weight:400;color:var(--el-text-color-secondary)}
.annotation-participants-popover .participants-members{display:flex;flex-wrap:wrap;gap:4px;max-height:96px;overflow-y:auto;margin-bottom:10px}
.annotation-participants-popover .participants-members>.el-button{margin:0;height:26px;padding:4px 8px;background:var(--el-fill-color-light);border-radius:6px}
.annotation-participants-popover .participants-members small{margin-left:5px;color:var(--el-text-color-secondary)}
.annotation-participants-popover .participants-invite{border-top:1px solid var(--el-border-color-lighter);padding-top:10px}
.annotation-participants-popover .participants-groups{margin-top:6px;max-height:min(260px,35vh);overflow-y:auto;overscroll-behavior:contain}
.annotation-participants-popover .participants-department__heading{display:flex;align-items:center;justify-content:space-between;gap:6px;min-height:34px}
.annotation-participants-popover .participants-department__heading .el-checkbox{flex:1;min-width:0;margin:0}
.annotation-participants-popover .el-checkbox__label{min-width:0;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.annotation-participants-popover .participants-department__heading .participants-hint{margin-left:6px}
.annotation-participants-popover .participants-department__people{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 8px;padding:0 8px 4px 22px}
.annotation-participants-popover .participants-department__people .el-checkbox{margin:0;min-width:0;height:30px}
.annotation-participants-popover .participants-footer{position:sticky;bottom:0;background:var(--el-bg-color);padding-top:8px;border-top:1px solid var(--el-border-color-lighter)}
.annotation-participants-popover .participants-submit{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px}
.annotation-participants-popover .participants-submit .el-button.is-link{margin-left:8px}
.annotation-participants-popover .participants-management{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px}
.annotation-participants-popover .participants-management .el-button{padding:4px;font-size:12px;margin:0}
.annotation-participants-popover .participants-empty,.annotation-participants-popover .participants-directory-error{font-size:12px;color:var(--el-text-color-secondary);padding:8px 0;margin:0}
@media(max-width:480px){.annotation-participants-popover .participants-management{flex-wrap:wrap}.annotation-participants-popover .participants-department__people{padding-left:10px}}
</style>
