<template>
  <div class="requirement-receipts"><strong>收到 / 已完成回执</strong><div v-for="person in recipients" :key="person.user_id" class="person-receipts"><strong>{{person.user_name}}</strong><span>收到：<template v-if="person.received_at">{{person.reply}} · {{time(person.received_at)}}</template><template v-else>待回复</template></span><span>已完成：<template v-if="person.completed_at">{{person.completed_reply}} · {{time(person.completed_at)}}</template><template v-else>待回执</template></span></div></div>
</template>
<script setup>
import {formatBusinessDateTime as time} from '@/utils/dateTime'
defineProps({recipients:{type:Array,default:()=>[]}})
</script>
<style scoped>.requirement-receipts{margin-top:10px;font-size:12px;line-height:1.8}.person-receipts{display:flex;flex-direction:column;margin:6px 0;overflow-wrap:anywhere}</style>
