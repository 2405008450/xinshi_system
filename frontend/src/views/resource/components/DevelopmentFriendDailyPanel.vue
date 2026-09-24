<template>
  <DevelopmentFriendDailyEditor ref="editorRef" :options="options" @options-changed="refreshOptions" />
</template>

<script setup>
import { nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { friendDailyApi as api } from '@/api/resourceFriendDaily'
import DevelopmentFriendDailyEditor from './DevelopmentFriendDailyEditor.vue'

// 仅在点击日期时加载统计，列表页不再常驻统计表。
const options = reactive({ accounts: [], languages: [], overview_rows: [], can_write: false })
const editorRef = ref()
let opening = false, sequence = 0
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
async function loadOptions() {
  const current = ++sequence
  const data = await api.options()
  if (current !== sequence) return false
  Object.assign(options, data)
  await nextTick()
  return true
}
async function refreshOptions() {
  try { await loadOptions() } catch (e) { ElMessage.error(e.message) }
}
async function open(day = today()) {
  if (opening) return
  opening = true
  try { if (await loadOptions()) await editorRef.value?.open(day) }
  catch (e) { ElMessage.error(e.message) }
  finally { opening = false }
}
onBeforeUnmount(() => { sequence++ })
defineExpose({ open })
</script>
