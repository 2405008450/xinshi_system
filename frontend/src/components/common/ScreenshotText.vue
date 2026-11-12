<template>
  <span class="screenshot-text">
    <span v-if="showText" class="screenshot-plain">{{ plain }}</span>
    <span class="screenshot-previews">
      <span v-for="(id,index) in ids" :key="id" class="screenshot-preview">
        <a v-if="files[id]?.extension" class="screenshot-document" :href="files[id].url"
          :download="`发票-${index+1}.${files[id].extension}`" @click.stop>下载 {{ files[id].extension.toUpperCase() }} 发票</a>
        <el-image v-else-if="files[id]" :src="files[id].url" :preview-src-list="imageUrls" preview-teleported fit="contain" @click.stop />
        <span v-else>{{ errors[id] || '正在加载附件…' }}</span>
        <button v-if="removable" type="button" :aria-label="files[id]?.extension ? '移除发票附件' : '移除截图'" @click.stop="$emit('remove',id)">×</button>
      </span>
    </span>
  </span>
</template>
<script setup>
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import api from '@/api'
import { screenshotIds,screenshotText } from '@/utils/screenshotReferences'
const props=defineProps({text:{type:String,default:''},showText:{type:Boolean,default:true},removable:Boolean,chatMessageId:[String,Number],chatKind:String})
defineEmits(['remove'])
const ids=computed(()=>screenshotIds(props.text)),plain=computed(()=>screenshotText(props.text)),files=ref({}),errors=ref({})
const imageUrls = computed(() => ids.value.filter(id => files.value[id] && !files.value[id].extension).map(id => files.value[id].url))
const documentExtensions = {'application/pdf':'pdf','application/ofd':'ofd'}
let version=0
watch(() => [props.text, props.chatMessageId], async () => {
  const current = ++version
  for (const [id, file] of Object.entries(files.value)) {
    if (ids.value.includes(id)) continue
    URL.revokeObjectURL(file.url)
    delete files.value[id]
  }
  await Promise.all(ids.value.map(async id => {
    if (files.value[id]) return
    try {
      const blob = await api.get(`/editor-screenshots/${id}`, {
        responseType:'blob', timeout:60000, screenshotIds:[id],
        params:props.chatMessageId ? {chat_message_id:props.chatMessageId,chat_kind:props.chatKind || 'project'} : {},
      })
      if (current === version) files.value[id] = {url: URL.createObjectURL(blob), extension: documentExtensions[blob.type]}
    } catch (e) {
      if (current === version) errors.value[id] = [404,410].includes(e.response?.status || e.status) ? '附件已过期或不存在' : e.detail || '请重新打开记录以查看附件'
    }
  }))
}, {immediate:true})
onBeforeUnmount(() => {
  ++version
  for (const file of Object.values(files.value)) URL.revokeObjectURL(file.url)
})
</script>
<style scoped>
.screenshot-document { padding: 6px 30px 6px 8px; color: var(--el-color-primary); font-size: 13px; }
</style>
<style scoped>.screenshot-text{display:inline-flex;flex-direction:column;max-width:100%;white-space:normal;vertical-align:top}.screenshot-plain{white-space:pre-wrap;overflow-wrap:anywhere}.screenshot-previews{display:flex;flex-wrap:wrap;gap:8px;margin-top:5px}.screenshot-preview{position:relative;display:inline-flex;flex-direction:column;max-width:280px;min-width:80px;font-size:11px;color:#94a3b8}.screenshot-preview .el-image{max-width:280px;height:130px;border:1px solid #e2e8f0;border-radius:6px}.screenshot-preview button{position:absolute;right:0;top:0;width:22px;height:22px;border:1px solid #cbd5e1;background:white;border-radius:4px;cursor:pointer}</style>
