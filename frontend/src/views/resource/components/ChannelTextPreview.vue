<template>
  <el-popover v-if="text" v-model:visible="visible" trigger="click" placement="left" :width="760" :popper-options="channelPopoverOptions" :title="`${name} · 情况说明`" popper-class="channel-text-popover">
    <template #reference>
      <button type="button" class="channel-text-preview" :aria-label="`查看${name}情况说明全文`">
        <span class="channel-text-summary">{{ text }}</span>
        <span class="channel-text-more">查看全文</span>
      </button>
    </template>
    <div class="channel-text-body"><el-descriptions :column="2" border size="small"><el-descriptions-item label="情况说明" :span="2">{{ text }}</el-descriptions-item></el-descriptions></div>
    <div class="channel-text-footer"><el-button text @click="visible = false">关闭</el-button></div>
  </el-popover>
  <span v-else>-</span>
</template>

<script setup>
import { ref } from 'vue'
import { channelPopoverOptions } from '@/utils/resourceChannels'
const visible = ref(false)
defineProps({ text: { type: String, default: '' }, name: { type: String, default: '渠道' } })
</script>

<style>
.channel-text-preview { display:block; width:100%; padding:0; border:0; background:transparent; color:var(--el-text-color-regular); text-align:left; font:inherit; cursor:pointer; }
.channel-text-summary { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.5; }
.channel-text-more { display:inline-block; color:var(--el-color-primary); font-size:12px; margin-top:3px; }
.channel-text-preview:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:2px; }
.channel-text-popover { max-width:calc(100vw - 32px); box-sizing:border-box; }
.channel-text-body { max-height:min(560px,calc(100vh - 140px)); overflow-y:auto; user-select:text; }
.channel-text-body .el-descriptions__table { table-layout:fixed; }
.channel-text-body .el-descriptions__cell { white-space:pre-wrap; overflow-wrap:anywhere; }
.channel-text-footer { display:flex; justify-content:flex-end; margin-top:8px; }
@media (max-width:640px) { .channel-text-preview { max-width:max(24px,min(100px,calc(100vw - 282px))); } }
</style>
