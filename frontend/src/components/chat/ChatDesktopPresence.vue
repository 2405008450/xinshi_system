<template><span class="chat-desktop-presence" :class="{ 'is-online': online === true }" title="表示电脑浏览器当前连接状态，不代表已阅读消息">{{ online === true ? '电脑端在线' : online === false ? '电脑端离线' : loading ? '检测中' : '状态未知' }}</span></template>
<script setup>
defineProps({ online: { type: Boolean, default: undefined }, loading: Boolean })
</script>
<style scoped>.chat-desktop-presence{flex:none;font-size:11px;color:#64748b;white-space:nowrap}.chat-desktop-presence.is-online{color:#15803d}.chat-desktop-presence::before{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;background:currentColor;margin-right:4px;vertical-align:middle}</style>
