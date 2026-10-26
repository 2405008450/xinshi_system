<template>
  <el-popover v-model:visible="visible" persistent trigger="click" placement="bottom-end" :width="190" popper-class="chat-header-more-popper">
    <template #reference><el-button link aria-label="更多会话操作" title="更多操作" @mousedown.stop @dblclick.stop><el-icon><MoreFilled /></el-icon></el-button></template>
    <div class="chat-header-more" @mousedown.stop @dblclick.stop>
      <slot />
      <el-button v-if="canDuplicate" link @click="command('duplicate')"><el-icon><CopyDocument /></el-icon>另开一窗</el-button>
      <el-button link @click="command('multiple')"><el-icon><Grid /></el-icon>多窗平铺</el-button>
      <ChatProjectActions :project-id="projectId" :project-type="projectType" menu-layout />
    </div>
  </el-popover>
</template>
<script setup>
import {ref} from 'vue'
import {MoreFilled,CopyDocument,Grid} from '@element-plus/icons-vue'
import ChatProjectActions from './ChatProjectActions.vue'
defineProps({projectId:String,projectType:String,canDuplicate:Boolean})
const emit=defineEmits(['duplicate','multiple'])
const visible=ref(false)
function command(value){visible.value=false;emit(value)}
</script>
<style>
.chat-header-more-popper{z-index:100000!important;max-width:calc(100vw - 32px)}
.chat-header-more,.chat-header-more .chat-project-actions{display:flex;flex-direction:column;align-items:stretch;gap:2px}
.chat-header-more .el-button{width:100%;height:34px;min-height:34px;justify-content:flex-start;margin:0;padding:8px 10px;font-size:13px;border-radius:4px;color:var(--el-text-color-primary)}
.chat-header-more .el-button>span{display:flex;align-items:center;gap:10px}
.chat-header-more .el-button .el-icon{font-size:16px;width:16px;height:16px;flex:none}
.chat-header-more .el-button:hover{background:var(--el-color-primary-light-9);color:var(--el-color-primary)}
.chat-header-more .chat-header-session-tools,.chat-header-more .group-toolbar--menu{display:flex;flex-direction:column;align-items:stretch;gap:2px;padding:0;margin:0;border:0;width:100%}
.chat-header-more .el-badge{display:block;width:100%}
.chat-header-more .group-toolbar--menu .group-member-count{position:static;margin-left:auto;font-size:11px;line-height:16px;height:auto}
</style>
