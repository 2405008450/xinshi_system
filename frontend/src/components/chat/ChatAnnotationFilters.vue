<template>
  <span class="chat-annotation-filters" data-auto-draft="off" @mousedown.stop @dblclick.stop>
    <el-button size="small" :type="mine ? 'primary' : 'default'" :aria-pressed="mine" @click="emit('change', { mine: !mine })">我是项目经理</el-button>
  </span>
</template>
<script setup>
defineProps({mine:Boolean,statuses:{type:Array,default:()=>[]}})
const emit=defineEmits(['change'])
</script>
<style scoped>
.chat-annotation-filters{display:inline-flex;align-items:center;gap:6px;flex:none}
.chat-annotation-filters .el-button{margin:0;height:21px;padding:0 6px;font-size:11px}
</style>
