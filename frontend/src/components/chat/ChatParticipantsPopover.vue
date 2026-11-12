<template>
<el-popover ref="participantsPopover" :append-to="participantsPopoverTarget" title="会话信息" :z-index="zIndex" @show="show" trigger="click" placement="bottom-end" :width="460" popper-class="annotation-members-popover annotation-participants-popover">
        <template #reference><slot name="reference" /></template>
        <p class="participants-note">仅会话参与人可以查看和发言。<template v-if="showFollowNote"><br>取消关注只停止未读提醒，不会退出会话。</template></p>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <div v-loading="loading">
        <section class="participants-section">
          <div class="participants-section__heading"><span>会话成员</span><span class="participants-section__count">{{ members.length }} 人</span></div>
          <div class="group-members participants-members">
            <el-button v-for="member in members" :key="member.id" text :disabled="String(member.id) === String(currentUserId)" :title="member.name" @click="$emit('member-click', member)">
              <span class="participants-member__avatar" aria-hidden="true">{{ Array.from(member.name || '?')[0] }}</span>
              <span class="participants-member__name">{{ member.name }}</span>
              <span v-if="String(member.id) === String(currentUserId)" class="participants-member__self">我</span>
            </el-button>
          </div>
        </section>
        <section class="participants-section participants-invite">
          <label class="participants-section__heading" :for="inviteInputId">邀请新成员</label>
        <el-select
          :id="inviteInputId" ref="inviteSelect" :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" multiple filterable clearable collapse-tags
          :max-collapse-tags="2" :teleported="true" :append-to="inviteDropdownTarget" placement="top-start"
          @visible-change="updateInviteDropdownTarget"
          :popper-style="{ zIndex: Math.max(100010, zIndex + 1) }"
          popper-class="chat-invite-users-popper"
          placeholder="搜索并选择邀请用户"
          :no-data-text="invitableUsers.length ? '未找到匹配用户' : '暂无可邀请的用户'" no-match-text="未找到匹配用户"
          :disabled="loading || inviting" style="width:100%"
        >
          <el-option v-for="user in invitableUsers" :key="user.id" :value="user.id" :label="user.name" />
        </el-select>
        <el-button type="primary" class="participants-invite__submit" :loading="inviting" :disabled="loading || !modelValue.length" @click="$emit('invite')">{{ modelValue.length ? `邀请 ${modelValue.length} 人参与会话` : '邀请参与会话' }}</el-button>
        </section>
        <div class="participants-management">
        <slot name="management" />
        </div>
        </div>
      </el-popover>
</template>
<script setup>
import { ref, useId } from 'vue'
defineProps({
  members: { type: Array, default: () => [] },
  invitableUsers: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
  zIndex: { type: Number, default: 2110 },
  currentUserId: [String, Number],
  loading: Boolean, inviting: Boolean, error: String, showFollowNote: Boolean,
})
const emit = defineEmits(['update:modelValue', 'show', 'invite', 'member-click'])
const participantsPopover = ref(null)
// 嵌套在更多菜单时挂到菜单浮层根节点，避免选人时外层菜单误判为外部点击。
// 通过实际触发元素查找，也覆盖工具栏 Teleport 到更多菜单中的标注会话。
const participantsPopoverTarget = ref('body')
function show() {
  participantsPopoverTarget.value = participantsPopover.value?.popperRef?.triggerRef?.closest('.chat-header-more-popper') || 'body'
  emit('show')
}
const inviteSelect = ref(null)
const inviteInputId = `chat-invite-${useId()}`
const inviteDropdownTarget = ref('body')
function updateInviteDropdownTarget(visible) {
  // 下拉层挂到浮窗根节点，避免被内容滚动区裁切，同时保留浮窗内点击语义。
  if (visible) inviteDropdownTarget.value = inviteSelect.value?.$el?.closest('.annotation-participants-popover') || 'body'
}
</script>
<style>
/* 下拉层挂到浮窗根节点，避开正文滚动裁切，且点击选项不会触发浮窗的外部关闭。 */
.annotation-members-popover.annotation-participants-popover{overflow:visible}
.el-popover.annotation-participants-popover{max-width:calc(100vw - 32px)!important;padding:20px;max-height:min(700px,calc(100vh - 32px));border-radius:12px;box-shadow:var(--shadow-dropdown)}
.annotation-participants-popover .app-window-popover__header{min-height:40px;padding-bottom:14px}
.annotation-participants-popover .app-window-popover__title{font-size:17px;font-weight:600}
.annotation-participants-popover .app-window-popover__body{padding-top:16px}
.participants-note{margin:0 0 20px;color:var(--color-text-muted);font-size:13px;line-height:1.8}
.participants-section__heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;color:var(--color-text-primary);font-size:14px;font-weight:600}
.participants-section__count{color:var(--color-text-muted);font-size:12px;font-weight:400}
.annotation-participants-popover .participants-members{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:208px;margin:0;padding-right:6px;overflow-y:auto}
.annotation-participants-popover .participants-members>.el-button{justify-content:flex-start;width:100%;height:46px;margin:0;padding:8px;border-radius:8px;color:var(--color-text-secondary)}
.participants-members>.el-button>span{display:flex;align-items:center;gap:8px;min-width:0;width:100%}
.participants-member__avatar{display:grid;place-items:center;flex-shrink:0;width:28px;height:28px;border-radius:9px;background:var(--color-surface-muted);color:var(--color-primary);font-size:12px;font-weight:600}
.participants-member__name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.participants-member__self{flex-shrink:0;font-size:11px;color:var(--color-text-muted)}
.annotation-participants-popover .participants-members>.el-button.is-disabled{color:var(--color-text-muted)}
.participants-invite{margin-top:20px;padding-top:18px;border-top:1px solid var(--color-border)}
.participants-invite .el-select__wrapper{min-height:40px;border-radius:8px}
.participants-invite__submit{width:100%;min-height:38px;margin:12px 0 0;border-radius:8px}
.participants-management{display:flex;flex-wrap:wrap;gap:12px;margin-top:20px;padding-top:16px;border-top:1px solid var(--color-border)}
.participants-management>.el-button{flex:1;min-height:36px;margin:0;border-radius:8px;font-size:13px}
@media(max-width:480px){.el-popover.annotation-participants-popover{padding:16px}.annotation-participants-popover .participants-members{grid-template-columns:repeat(2,minmax(0,1fr))}}
.chat-invite-users-popper .el-select-dropdown__wrap{max-height:min(274px,calc(100vh - 96px))}
</style>
