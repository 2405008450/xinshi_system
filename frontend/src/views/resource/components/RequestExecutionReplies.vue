<template>
  <div class="execution-replies">
    <div v-for="item in rows" :key="item.id" class="execution-reply">
      <strong>{{ item.name }} · {{ formatTime(item.createdAt) }}</strong>
      <p>执行平台：{{ item.platforms.map(p=>(p.parentName ? p.parentName+' / ' : '')+p.name).join('、') }}</p>
      <ScreenshotText :text="item.content || '未填写补充说明'" />
    </div>
  </div>
</template>
<script setup>
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
defineProps({rows:{type:Array,default:()=>[]}})
</script>
<style scoped>.execution-reply{margin:8px 0;padding:10px;border:1px solid #e2e8f0;border-radius:6px;font-size:12px;line-height:1.7}.execution-reply p{margin:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}</style>
