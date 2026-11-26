<template>
  <section v-for="item in visibleNotes" :key="item.kind" class="request-dispatch-note">
    <h4>{{ item.label }}说明</h4>
    <ScreenshotText :text="item.content" />
  </section>
</template>
<script setup>
import { computed } from 'vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
const props=defineProps({notes:{type:Object,default:()=>({})},kind:{type:String,default:''}})
const labels={circle:'发圈需求',post:'发帖需求',wechatPublic:'发圈（+公众号）需求',xiaohongshu:'小红书需求',development:'资源开拓 · 需求管理'}
const visibleNotes=computed(()=>Object.entries(labels).filter(([kind])=>!props.kind||kind===(['wechat_public','wechat_broadcast'].includes(props.kind)?'wechatPublic':props.kind)).map(([kind,label])=>({kind,label,content:props.notes[kind]||''})).filter(item=>item.content.trim()))
</script>
<style scoped>
.request-dispatch-note{margin:12px 0;overflow-wrap:anywhere}.request-dispatch-note h4{margin:0 0 6px}
</style>
