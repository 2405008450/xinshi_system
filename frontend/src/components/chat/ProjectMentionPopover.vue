<template>
  <span class="project-mention-entry" @click.stop @mousedown.stop @keydown.stop>
    <el-popover v-model:visible="visible" trigger="click" placement="bottom-start" :width="360"
      popper-class="project-mention-popover" @show="emit('browse', session)">
      <template #reference>
        <button type="button" class="project-mention-entry__button" :aria-label="compact ? '消息列表' : `查看 ${session.mentionHistoryCount} 条历史提及`">
          {{ compact ? '消息列表' : `@我 · ${session.mentionHistoryCount} 条历史提及` }}
        </button>
      </template>
      <div class="project-mention-list" role="region" aria-label="项目内提及消息">
        <strong>{{ session.title }}</strong>
        <small>历史提及 · {{ current ? model.total : session.mentionHistoryCount }} 条 · 从新到旧</small>
        <p v-if="current && model.error" role="alert">{{ model.error }} <el-button link @click="emit('retry')">重试</el-button></p>
        <p v-if="!current || (model.loading && !model.items.length)" role="status">正在加载…</p>
        <p v-else-if="!model.items.length && !model.error">暂无可查看的提及消息</p>
        <button v-for="item in current ? model.items : []" :key="item.messageId" type="button"
          class="project-mention-list__item" :class="{ 'is-active': model.selectedId === item.messageId }"
          @click="select(item)">
          <span><b>{{ item.senderName }}</b><em v-if="item.unread">未读</em><time>{{ formatBusinessDateTime(item.createdAt) }}</time></span>
          <span class="project-mention-list__preview">{{ item.preview }}</span>
        </button>
        <el-button v-if="current && model.hasMore" link type="primary" :loading="model.loading" @click="emit('more')">加载更多</el-button>
      </div>
    </el-popover>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props = defineProps({ session: { type: Object, required: true }, model: { type: Object, required: true }, compact: Boolean })
const emit = defineEmits(['browse', 'select', 'more', 'retry'])
const visible = ref(false)
const current = computed(() => props.model.project?.key === props.session.key)
function select(item) { visible.value = false; emit('select', item) }
</script>

<style>
.project-mention-popover.el-popover{max-width:calc(100vw - 32px);box-sizing:border-box;z-index:100010!important}
</style>
<style scoped>
.project-mention-entry{display:inline-flex;max-width:100%}
.project-mention-entry__button{border:0;background:none;color:#5479be;font:inherit;font-size:11px;cursor:pointer;padding:2px 0;text-align:left}
.project-mention-entry__button:hover{text-decoration:underline}
.project-mention-entry__button:focus-visible{outline:2px solid #5479be;outline-offset:2px}
.project-mention-list{display:flex;flex-direction:column;gap:8px;max-height:min(480px,calc(100dvh - 120px));overflow-y:auto;overscroll-behavior:contain}
.project-mention-list>strong{overflow-wrap:anywhere}.project-mention-list>small{color:#64748b}
.project-mention-list__item{border:0;border-radius:6px;padding:10px;background:#f8fafc;text-align:left;cursor:pointer;color:#334155}
.project-mention-list__item:hover,.project-mention-list__item.is-active{background:#e9eff9}
.project-mention-list__item>span:first-child{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:12px}
.project-mention-list__item time{color:#64748b;font-size:11px}.project-mention-list__item em{color:#b91c1c;font-style:normal}
.project-mention-list__preview{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere;margin-top:6px;line-height:1.5}
</style>
