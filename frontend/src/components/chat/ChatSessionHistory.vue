<template>
  <section class="chat-history" aria-label="历史会话">
    <p class="chat-history__hint">{{ keyword ? '搜索全部会话，包含历史会话' : '全部会话，按需分页加载' }} · {{ total }} 个</p>
    <p v-if="error" role="alert">{{ error }} <el-button link type="primary" @click="load">重试</el-button></p>
    <div v-loading="loading" class="chat-history__items">
      <el-empty v-if="!loading && !error && !items.length" description="没有匹配的历史会话" :image-size="48" />
      <button v-for="item in items" :key="item.key" type="button" class="chat-history__item" @click="emit('open', { ...item, projectType: item.kind })">
        <strong>{{ item.title }}</strong><span>{{ item.subtitle || '-' }}</span>
        <small>{{ labels[item.kind] || '会话' }}<template v-if="Number.isFinite(item.memberCount)"> · {{ item.memberCount }} 人</template> · 点击查看聊天记录</small>
      </button>
    </div>
    <el-pagination v-if="total > pageSize" size="small" layout="prev, pager, next" :page-size="pageSize" :total="total" :current-page="page" :pager-count="5" :disabled="loading" @current-change="changePage" />
  </section>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { chatRequest } from '@/api/projectChat'

const props = defineProps({ keyword: { type: String, default: '' }, active: Boolean, revision: Number })
const emit = defineEmits(['open'])
const labels = { annotation: '标注项目群', translation: '笔译项目群', direct: '私聊', discussion: '讨论群' }
const pageSize = 30
const items = ref([]), total = ref(0), page = ref(1), loading = ref(false), error = ref('')
let controller, sequence = 0

function cancel() { controller?.abort(); ++sequence; loading.value = false }
async function load() {
  cancel()
  if (!props.active) return
  const current = sequence, actor = localStorage.getItem('user_id')
  controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const data = await chatRequest('sessions/history', { params: {
      keyword: props.keyword, offset: (page.value - 1) * pageSize, limit: pageSize,
    }, signal: controller.signal })
    if (current !== sequence || actor !== localStorage.getItem('user_id')) return
    items.value = data.items || []; total.value = data.total || 0
    const last = Math.max(1, Math.ceil(total.value / pageSize))
    if (page.value > last) { page.value = last; void load() }
  } catch (cause) {
    if (current === sequence && cause.code !== 'ERR_CANCELED') error.value = '历史会话暂时无法加载'
  } finally { if (current === sequence) loading.value = false }
}
function changePage(value) { page.value = value; void load() }
watch(() => [props.keyword, props.active, props.revision], () => {
  page.value = 1; items.value = []; total.value = 0; void load()
}, { immediate: true })
onBeforeUnmount(cancel)
</script>

<style scoped>
.chat-history{min-width:0}.chat-history__hint{font-size:12px;color:#64748b;padding:0 10px}.chat-history__items{min-height:80px}.chat-history__item{display:flex;flex-direction:column;gap:5px;width:100%;padding:12px;text-align:left;border:0;border-bottom:1px solid #e2e8f0;background:#fff;color:#334155;cursor:pointer}.chat-history__item:hover,.chat-history__item:focus-visible{background:#eff6ff}.chat-history__item strong,.chat-history__item span{overflow-wrap:anywhere}.chat-history__item small{font-size:12px;color:#64748b}.chat-history :deep(.el-pagination){justify-content:center;padding:12px 0;max-width:100%}
</style>
