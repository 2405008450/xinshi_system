<template>
  <div class="discussion-search" data-auto-draft="off" aria-label="讨论聊天记录搜索">
    <div class="discussion-search__tabs" role="tablist" aria-label="聊天记录类型">
      <button v-for="tab in tabs" :key="tab.value" type="button" role="tab" :aria-selected="kind === tab.value" :class="{'is-active':kind === tab.value}" @click="emit('update:kind',tab.value)">{{ tab.label }}</button>
    </div>
    <div class="discussion-search__keyword">
      <el-input :model-value="keyword" clearable maxlength="200" placeholder="搜索消息、附件名、发送人或链接（多关键词）" aria-label="搜索讨论聊天记录" @update:model-value="emit('update:keyword',$event)" @keyup.enter="emit('search')" />
      <el-button type="primary" plain @click="emit('search')">查询</el-button>
      <el-button @click="emit('reset')">重置</el-button>
      <el-button @click="emit('close')">关闭</el-button>
    </div>
    <div class="discussion-search__conditions">
      <el-select :model-value="sender" clearable filterable :loading="loadingSenders" placeholder="发送人（全部）" aria-label="按发送人筛选" @update:model-value="emit('update:sender',$event || '')">
        <el-option v-for="person in senders" :key="person.id" :value="person.id" :label="person.name" />
      </el-select>
      <el-date-picker :model-value="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="按日期筛选" clearable @update:model-value="emit('update:dates',$event || [])" />
      <el-select :model-value="formats" multiple clearable collapse-tags placeholder="文字格式（多选同时满足）" aria-label="文字格式筛选" @update:model-value="emit('update:formats',$event)"><el-option v-for="option in formatSearchOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select>
      <el-checkbox :model-value="favorites" @update:model-value="emit('update:favorites',$event)">消息收藏</el-checkbox>
    </div>
  </div>
</template>
<script setup>
import {formatSearchOptions} from '@/utils/chatTextFormat'
defineProps({keyword:String,kind:String,sender:String,dates:Array,favorites:Boolean,formats:Array,senders:{type:Array,default:()=>[]},loadingSenders:Boolean})
const emit=defineEmits(['update:keyword','update:kind','update:sender','update:dates','update:favorites','update:formats','search','reset','close'])
const tabs=[{value:'all',label:'全部'},{value:'file',label:'文件'},{value:'media',label:'图片与视频'},{value:'link',label:'链接'},{value:'miniapp',label:'小程序'}]
</script>
<style scoped>
.discussion-search{flex:none;padding:8px 12px;background:white;border-bottom:1px solid #e2e8f0;display:flex;flex-direction:column;gap:8px;min-width:0}
.discussion-search__tabs{display:flex;gap:18px;overflow-x:auto;flex:none}.discussion-search__tabs button{flex:none;border:0;border-bottom:3px solid transparent;background:transparent;padding:5px 0 7px;color:#64748b;font:inherit;cursor:pointer;white-space:nowrap}.discussion-search__tabs .is-active{border-bottom-color:var(--el-color-primary);color:var(--el-color-primary);font-weight:600}
.discussion-search__keyword,.discussion-search__conditions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}.discussion-search__keyword>.el-input{flex:1;min-width:180px}.discussion-search__keyword>.el-button{margin:0}.discussion-search__conditions>.el-select{width:190px;flex:none}.discussion-search__conditions :deep(.el-date-editor){width:280px;max-width:100%;flex:0 1 280px;min-width:220px}
@media(max-width:600px){.discussion-search__conditions>.el-select{width:100%;flex:1 1 100%}.discussion-search__keyword>.el-input{flex-basis:100%}.discussion-search__conditions :deep(.el-date-editor){flex:1 1 100%;width:100%}}
</style>
